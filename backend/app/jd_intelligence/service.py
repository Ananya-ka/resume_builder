"""Service orchestration for Job Intelligence & Evidence Mapping."""
import hashlib
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.schemas import JobDescription, User
from app.catalog.models import EvidenceCatalog, CatalogClaim, CatalogConflict, CatalogSource, ClaimSource
from app.jd_intelligence.models import JobVersion, JobRequirement, AnalysisRun, RequirementMatch
from app.jd_intelligence.schemas import JobCreate, JobVersionOut, JobRequirementOut, AnalysisRunOut, RequirementMatchOut
from app.jd_intelligence.parser import IntelligentJDParser
from app.jd_intelligence.matcher import EvidenceRequirementMatcher


def owned_job(db: Session, job_id: int, user_id: str) -> JobDescription:
    job = db.query(JobDescription).filter_by(id=job_id, user_id=user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job description not found")
    return job


def owned_catalog(db: Session, catalog_id: int, user_id: str) -> EvidenceCatalog:
    catalog = db.query(EvidenceCatalog).filter_by(id=catalog_id, user_id=user_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Evidence catalog not found")
    return catalog


def owned_job_version(db: Session, version_id: int, user_id: str) -> JobVersion:
    jv = db.query(JobVersion).filter_by(id=version_id, user_id=user_id).first()
    if not jv:
        raise HTTPException(status_code=404, detail="Job version not found")
    return jv


def create_or_update_job(db: Session, user_id: str, req: JobCreate) -> JobVersion:
    """Creates a job description and parses it into an immutable, hashed JobVersion."""
    # Find existing job with same title & company for this user or create a new one
    job = db.query(JobDescription).filter_by(
        user_id=user_id,
        role=req.role,
        company=req.company
    ).first()

    if not job:
        job = JobDescription(
            user_id=user_id,
            role=req.role,
            company=req.company,
            raw_text=req.raw_text
        )
        db.add(job)
        db.flush()

    raw_text = req.raw_text.strip()
    sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    # Check if this exact text version is already parsed
    existing_version = db.query(JobVersion).filter_by(job_id=job.id, sha256=sha).first()
    if existing_version:
        return existing_version

    # Get next version number
    latest_version = db.query(JobVersion).filter_by(job_id=job.id).order_by(JobVersion.version.desc()).first()
    next_ver_num = (latest_version.version + 1) if latest_version else 1

    # Parse with IntelligentJDParser
    parser = IntelligentJDParser()
    parsed = parser.parse(raw_text, role_hint=req.role, company_hint=req.company)

    # Sync top-level JobDescription metadata for backwards compatibility
    job.raw_text = raw_text
    job.experience_years = parsed.get("experience_years")
    job.domain = parsed.get("domain")
    job.seniority = parsed.get("seniority")

    parsed_summary = {
        "experience_years": parsed.get("experience_years"),
        "seniority": parsed.get("seniority"),
        "domain": parsed.get("domain"),
        "requirement_count": len(parsed.get("requirements", []))
    }

    job_version = JobVersion(
        job_id=job.id,
        user_id=user_id,
        version=next_ver_num,
        sha256=sha,
        title=req.role,
        company=req.company,
        raw_text=raw_text,
        parsed_data=parsed_summary
    )
    db.add(job_version)
    db.flush()

    # Persist JobRequirements
    for req_item in parsed.get("requirements", []):
        db_req = JobRequirement(
            job_version_id=job_version.id,
            requirement_key=req_item["requirement_key"],
            category=req_item["category"],
            title=req_item["title"],
            quote=req_item["quote"],
            start_offset=req_item.get("start_offset"),
            end_offset=req_item.get("end_offset"),
            is_mandatory=req_item.get("is_mandatory", True),
            importance=req_item.get("importance", "high"),
            normalized_terms=req_item.get("normalized_terms", []),
            dependencies=req_item.get("dependencies", []),
            is_ambiguous=req_item.get("is_ambiguous", False),
            ambiguity_reason=req_item.get("ambiguity_reason")
        )
        db.add(db_req)

    db.commit()
    db.refresh(job_version)
    return job_version


def serialize_job_version(db: Session, jv: JobVersion) -> Dict[str, Any]:
    requirements = db.query(JobRequirement).filter_by(job_version_id=jv.id).order_by(JobRequirement.id).all()
    return {
        "id": jv.id,
        "job_id": jv.job_id,
        "version": jv.version,
        "sha256": jv.sha256,
        "title": jv.title,
        "company": jv.company,
        "raw_text": jv.raw_text,
        "parsed_data": jv.parsed_data or {},
        "created_at": jv.created_at.isoformat() if jv.created_at else None,
        "requirements": [
            {
                "id": r.id,
                "requirement_key": r.requirement_key,
                "category": r.category,
                "title": r.title,
                "quote": r.quote,
                "start_offset": r.start_offset,
                "end_offset": r.end_offset,
                "is_mandatory": r.is_mandatory,
                "importance": r.importance,
                "normalized_terms": r.normalized_terms or [],
                "dependencies": r.dependencies or [],
                "is_ambiguous": r.is_ambiguous,
                "ambiguity_reason": r.ambiguity_reason
            }
            for r in requirements
        ]
    }


def analyze_catalog_against_job(
    db: Session,
    user_id: str,
    catalog_id: int,
    job_id: int,
    job_version_id: Optional[int] = None
) -> AnalysisRun:
    """Executes evidence-to-requirement mapping and persists an AnalysisRun snapshot."""
    catalog = owned_catalog(db, catalog_id, user_id)
    job = owned_job(db, job_id, user_id)

    if job_version_id:
        jv = owned_job_version(db, job_version_id, user_id)
        if jv.job_id != job.id:
            raise HTTPException(status_code=422, detail="Job version does not belong to specified job")
    else:
        jv = db.query(JobVersion).filter_by(job_id=job.id).order_by(JobVersion.version.desc()).first()
        if not jv:
            raise HTTPException(status_code=404, detail="No parsed versions found for this job")

    # Fetch catalog claims and open conflicts
    claims = db.query(CatalogClaim).filter_by(catalog_id=catalog.id).all()
    open_conflicts = db.query(CatalogConflict).filter_by(catalog_id=catalog.id, state="open").all()
    open_conflict_claim_ids = {cid for c in open_conflicts for cid in c.claim_ids}

    # Fetch job requirements
    requirements = db.query(JobRequirement).filter_by(job_version_id=jv.id).order_by(JobRequirement.id).all()

    matcher = EvidenceRequirementMatcher()
    match_results = []
    summary_counts = {"direct": 0, "transferable": 0, "missing": 0, "unresolved": 0, "total": len(requirements)}

    for req in requirements:
        req_dict = {
            "category": req.category,
            "title": req.title,
            "quote": req.quote,
            "is_mandatory": req.is_mandatory,
            "importance": req.importance,
            "normalized_terms": req.normalized_terms or [],
            "dependencies": req.dependencies or [],
            "is_ambiguous": req.is_ambiguous
        }
        res = matcher.evaluate_requirement(req_dict, claims, open_conflict_claim_ids)
        res["requirement_id"] = req.id
        match_results.append(res)
        status = res["status"]
        if status in summary_counts:
            summary_counts[status] += 1

    # Create AnalysisRun
    run = AnalysisRun(
        user_id=user_id,
        catalog_id=catalog.id,
        catalog_revision=catalog.revision,
        job_version_id=jv.id,
        status="completed",
        summary=summary_counts
    )
    db.add(run)
    db.flush()

    for m in match_results:
        req_match = RequirementMatch(
            analysis_run_id=run.id,
            requirement_id=m["requirement_id"],
            status=m["status"],
            matched_claim_ids=m["matched_claim_ids"],
            transferable_details=m["transferable_details"],
            candidate_depth=m["candidate_depth"],
            score_rationale=m["score_rationale"],
            clarification_question=m["clarification_question"]
        )
        db.add(req_match)

    db.commit()
    db.refresh(run)
    return run


def serialize_analysis_run(db: Session, run: AnalysisRun) -> Dict[str, Any]:
    matches = db.query(RequirementMatch).filter_by(analysis_run_id=run.id).order_by(RequirementMatch.id).all()
    req_ids = [m.requirement_id for m in matches]
    requirements = {r.id: r for r in db.query(JobRequirement).filter(JobRequirement.id.in_(req_ids)).all()} if req_ids else {}

    # Fetch claims and sources
    claim_ids = {cid for m in matches for cid in (m.matched_claim_ids or [])}
    claims_map = {c.id: c for c in db.query(CatalogClaim).filter(CatalogClaim.id.in_(claim_ids)).all()} if claim_ids else {}
    claim_sources = db.query(ClaimSource).filter(ClaimSource.claim_id.in_(claim_ids)).all() if claim_ids else []
    sources = {s.id: s for s in db.query(CatalogSource).filter(CatalogSource.id.in_([cs.source_id for cs in claim_sources])).all()} if claim_sources else {}

    serialized_matches = []
    for m in matches:
        req = requirements.get(m.requirement_id)
        if not req:
            continue

        matched_claims_list = []
        for cid in (m.matched_claim_ids or []):
            cl = claims_map.get(cid)
            if cl:
                citations = []
                for cs in claim_sources:
                    if cs.claim_id == cl.id:
                        src = sources.get(cs.source_id)
                        if src:
                            citations.append({
                                "filename": src.filename,
                                "quote": cs.quote,
                                "start": cs.start,
                                "end": cs.end
                            })
                matched_claims_list.append({
                    "id": cl.id,
                    "revision": cl.revision,
                    "text": cl.data.get("text"),
                    "association": cl.data.get("association"),
                    "role": cl.data.get("role"),
                    "technologies": cl.data.get("technologies", []),
                    "depth": cl.data.get("depth", "unspecified"),
                    "approval": cl.approval,
                    "verification": cl.verification,
                    "citations": citations
                })

        serialized_matches.append({
            "id": m.id,
            "requirement": {
                "id": req.id,
                "requirement_key": req.requirement_key,
                "category": req.category,
                "title": req.title,
                "quote": req.quote,
                "start_offset": req.start_offset,
                "end_offset": req.end_offset,
                "is_mandatory": req.is_mandatory,
                "importance": req.importance,
                "normalized_terms": req.normalized_terms or [],
                "dependencies": req.dependencies or [],
                "is_ambiguous": req.is_ambiguous,
                "ambiguity_reason": req.ambiguity_reason
            },
            "status": m.status,
            "matched_claims": matched_claims_list,
            "transferable_details": m.transferable_details,
            "candidate_depth": m.candidate_depth,
            "score_rationale": m.score_rationale,
            "clarification_question": m.clarification_question
        })

    return {
        "id": run.id,
        "catalog_id": run.catalog_id,
        "catalog_revision": run.catalog_revision,
        "job_version_id": run.job_version_id,
        "status": run.status,
        "summary": run.summary or {},
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "matches": serialized_matches
    }
