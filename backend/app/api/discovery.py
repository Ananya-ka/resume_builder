"""Persistent discovery, revisions, and immutable draft snapshots."""
from typing import Literal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schemas import CandidateEvidence, DiscoverySession, EvidenceDraft, Resume, JobDescription, OptimizedResume, User, ProfileDecision
from app.services.candidate_profile import candidate_key, merge_profile
from app.services.discovery import (
    llm_next_question,
    next_question as heuristic_next_question,
    evidence_key,
    apply_answer,
    evidence_bullet,
    MAX_QUESTIONS,
)
from app.services.jd_parser import JDParser

next_question = heuristic_next_question

router = APIRouter(prefix="/api")

# Imported lazily by the main router to share the existing user dependency.
from app.api.routes import get_current_user_id


class StartDiscovery(BaseModel):
    resume_ids: list[int] = Field(min_length=1, max_length=3)
    job_id: int
    project_notes: str = Field(default="", max_length=6000)

    @field_validator("resume_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct resumes")
        return value


class Answer(BaseModel):
    question_id: int
    answer: str = Field(default="", max_length=6000)
    depth: Literal["unspecified", "professional", "personal_project", "tutorial", "familiarity", "team_only"] = "unspecified"
    confirm: bool = False
    skip: bool = False
    company: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=300)
    section: Literal["Experience", "Projects"] = "Projects"


class Correction(BaseModel):
    revision: int
    content: str = Field(min_length=1, max_length=6000)
    company: str = Field(min_length=1, max_length=300)
    role: str = Field(default="", max_length=300)
    section: Literal["Experience", "Projects"]
    depth: Literal["unspecified", "professional", "personal_project", "tutorial", "familiarity", "team_only"]
    ownership: str = Field(default="", max_length=3000)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("content", "company", "reason")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()


def owned(db, model, record_id, user_id, lock=False):
    query = db.query(model).filter(model.id == record_id, model.user_id == user_id)
    if lock:
        query = query.with_for_update()
    record = query.first()
    if not record:
        raise HTTPException(404, "Record not found")
    return record


def serialize(item):
    return {"id": item.id, "revision": item.revision, "data": item.data, "source_refs": item.source_refs, "history": item.history}


def session_view(db, session):
    evidence = db.query(CandidateEvidence).filter(CandidateEvidence.id.in_(session.evidence_ids), CandidateEvidence.user_id == session.user_id).all()
    resumes = [owned(db, Resume, rid, session.user_id) for rid in session.resume_ids]
    decisions = {d.conflict_key: d.choice for d in db.query(ProfileDecision).filter_by(user_id=session.user_id, candidate_key=candidate_key(resumes)).all()}
    profile, conflicts = merge_profile(resumes, [serialize(e) for e in evidence], decisions)
    return {"id": session.id, "job_id": session.job_id, "resume_ids": session.resume_ids,
            "status": session.status, "questions": session.questions, "limit": MAX_QUESTIONS,
            "evidence": profile.pop("evidence"), "profile": profile, "conflicts": conflicts}


def advance(db, session):
    view = session_view(db, session)
    if view["conflicts"]:
        session.status = "reviewing"
        return
    session.status = "discovering"
    if session.questions and "answer" not in session.questions[-1]:
        return
    evidence = view["evidence"]
    job = owned(db, JobDescription, session.job_id, session.user_id)
    skills = view["profile"]["skills"]
    try:
        if next_question != heuristic_next_question:
            q = next_question(evidence, session.questions, job.raw_text, job.required_skills or [], skills, view["profile"])
        else:
            q = llm_next_question(evidence, session.questions, job.raw_text, job.required_skills or [], skills, view["profile"])
    except ValueError:
        try:
            q = heuristic_next_question(evidence, session.questions, job.raw_text, job.required_skills or [], skills, view["profile"])
        except Exception as exc:
            raise HTTPException(503, str(exc)) from exc
    if q:
        q["id"] = len(session.questions) + 1
        q["evidence_revision"] = next((e["revision"] for e in evidence if e["id"] == q["evidence_id"]), None)
        session.questions = [*session.questions, q]
    else:
        session.status = "ready"


def revise(db, item, data, reason):
    if data == item.data:
        return
    item.history = [*item.history, {"revision": item.revision, "data": item.data, "reason": reason, "recorded_at": datetime.now(timezone.utc).isoformat()}]
    item.data = data
    item.revision += 1
    # Serialize correction and submit/regenerate actions for this user's drafts.
    for draft in db.query(EvidenceDraft).filter(EvidenceDraft.user_id == item.user_id).with_for_update().all():
        if any(e["id"] == item.id and e["revision"] != item.revision for e in draft.evidence_snapshot):
            draft.stale_evidence_ids = sorted(set([*draft.stale_evidence_ids, item.id]))


@router.post("/discovery")
def start(req: StartDiscovery, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.query(User).filter(User.id == user_id).with_for_update().first()
    job = owned(db, JobDescription, req.job_id, user_id)
    resumes = [owned(db, Resume, i, user_id, lock=True) for i in sorted(req.resume_ids)]
    # Same-account uploads are not automatically the same person. Expand only
    # when the exact parsed email identifies the candidate across ready uploads.
    selected_emails = {((r.parsed_raw or {}).get("email") or "").strip().casefold() for r in resumes} - {""}
    if len(selected_emails) == 1:
        selected_ids = {r.id for r in resumes}
        for other in db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.id).all():
            raw = other.parsed_raw or {}
            if other.id not in selected_ids and (raw.get("email") or "").strip().casefold() in selected_emails and raw.get("parsing_status") == "ready":
                resumes.append(other)
                selected_ids.add(other.id)
        req.resume_ids = [r.id for r in resumes]
    if any(not r.parsed_raw or r.parsed_raw.get("parsing_status") in {"queued", "parsing", "failed"} or not r.bullets for r in resumes):
        raise HTTPException(409, "Resumes are still parsing or contain no experience bullets. Retry when parsing finishes.")
    from app.services.resume_parser import normalize_claim_text, validate_resume_parse
    for field in ("name", "email"):
        identities = {normalize_claim_text(r.parsed_raw[field]) for r in resumes if r.parsed_raw.get(field)}
        if len(identities) > 1 and not (field == "name" and len(selected_emails) == 1):
            raise HTTPException(422, "Selected resumes have different candidate identities. Select only versions of the same person's resume.")
    for resume in resumes:
        raw = resume.parsed_raw.get("raw_source_text")
        if raw:
            try:
                validate_resume_parse(resume.parsed_raw, raw)
            except ValueError as exc:
                raise HTTPException(409, "Parsed profile details could not be traced to the upload. Re-parse or correct this source before tailoring.") from exc
            source = normalize_claim_text(raw)
            for bullet in resume.bullets:
                for value in (bullet.company, bullet.role if bullet.section == "Experience" else "", bullet.bullet):
                    if value and normalize_claim_text(value) not in source:
                        raise HTTPException(409, "Stored resume evidence does not match the uploaded text. Re-upload this resume to parse it again before tailoring.")
    if job.required_skills is None:
        try:
            parsed = JDParser().parse_job_description(job.raw_text)
        except ValueError as exc:
            raise HTTPException(503, str(exc))
        for key in ("required_skills", "preferred_skills", "ats_keywords", "responsibilities", "experience_years"):
            if key in parsed:
                setattr(job, key, parsed[key])
    # Account ownership is not candidate identity: never import another selected
    # resume's answers or corrections merely because the uploader is the same.
    emails = {normalize_claim_text(r.parsed_raw.get("email", "")) for r in resumes} - {""}
    matching_ids = {r.id for r in resumes}
    if emails:
        matching_ids.update(r.id for r in db.query(Resume).filter(Resume.user_id == user_id).all()
                            if normalize_claim_text((r.parsed_raw or {}).get("email", "")) in emails)
    selected_prefixes = tuple(f"resume:{rid}:" for rid in matching_ids)
    prior_sessions = db.query(DiscoverySession).filter(DiscoverySession.user_id == user_id).all()
    related = {s.id for s in prior_sessions if set(s.resume_ids).issubset(matching_ids)}
    discovery_prefixes = tuple(f"discovery:{sid}:" for sid in related)
    catalog = [e for e in db.query(CandidateEvidence).filter(CandidateEvidence.user_id == user_id).all()
               if any(ref.startswith(selected_prefixes + discovery_prefixes) for ref in e.source_refs)]
    by_ref = {ref: e for e in catalog for ref in e.source_refs}
    by_key = {}
    for e in catalog:
        for version in e.history:
            by_key[evidence_key(version["data"])] = e
        by_key[evidence_key(e.data)] = e
    selected = [e.id for e in catalog if any(ref.startswith("discovery:") for ref in e.source_refs)]
    for resume in resumes:
        for bullet in resume.bullets:
            ref = f"resume:{resume.id}:bullet:{bullet.id}"
            data = {"content": bullet.bullet, "section": bullet.section, "company": bullet.company or "",
                    "role": bullet.role or "", "depth": "unspecified", "ownership_confirmed": False}
            item = by_ref.get(ref)
            if not item:
                item = by_key.get(evidence_key(data))
                if item:
                    item.source_refs = [*item.source_refs, ref]
                else:
                    item = CandidateEvidence(user_id=user_id, data=data, source_refs=[ref], revision=1, history=[])
                    db.add(item)
                    db.flush()
                    by_key[evidence_key(data)] = item
                by_ref[ref] = item
            selected.append(item.id)
    session = DiscoverySession(user_id=user_id, job_id=req.job_id, resume_ids=req.resume_ids,
                               evidence_ids=list(dict.fromkeys(selected)), questions=[], status="discovering")
    db.add(session)
    db.flush()
    advance(db, session)
    db.commit()
    return session_view(db, session)


@router.get("/discovery/{session_id}")
def get_session(session_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return session_view(db, owned(db, DiscoverySession, session_id, user_id))


class ResolveConflict(BaseModel):
    conflict_id: str
    choice: str | int | list[str]


class ReviewClaim(BaseModel):
    evidence_id: int
    action: Literal["accept", "revert", "edit", "include", "exclude"]
    text: str = Field(default="", max_length=3000)
    expected_text: str


@router.post("/evidence-drafts/{opt_id}/review")
def review_claim(opt_id: int, req: ReviewClaim, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    from app.services.fact_verifier import FactVerifier
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).with_for_update().first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "complete" or draft.submitted or draft.stale_evidence_ids:
        raise HTTPException(409, "Create a current editable draft before reviewing claims")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    bullets = [dict(b) for b in opt.optimized_content]
    bullet = next((b for b in bullets if b.get("original_id") == req.evidence_id), None)
    source = next((evidence_bullet(e) for e in draft.evidence_snapshot if e["id"] == req.evidence_id), None)
    if not bullet or not source:
        raise HTTPException(404, "Source achievement not found")
    if bullet["optimized_bullet"] != req.expected_text:
        raise HTTPException(409, "This wording changed. Reload before editing.")
    before = {k: bullet.get(k) for k in ("optimized_bullet", "review_state", "included")}
    if req.action == "edit":
        text = req.text.strip()
        if not text:
            raise HTTPException(422, "Enter wording to review")
        if text != source["content"]:
            checked = FactVerifier().verify_optimized_bullets([source], [{**bullet, "optimized_bullet": text}])[0]
            if not checked.get("verified"):
                raise HTTPException(422, "This edit could not be verified against its source. Add or correct the underlying evidence first, then create a revised draft.")
        bullet.update(optimized_bullet=text, review_state="accepted")
    elif req.action == "revert":
        bullet.update(optimized_bullet=source["content"], review_state="reverted")
    elif req.action == "accept":
        if not bullet.get("verified") and bullet["optimized_bullet"] != source["content"]:
            raise HTTPException(422, "Revert or verify this claim before accepting it")
        bullet["review_state"] = "accepted"
    else:
        bullet["included"] = req.action == "include"
    bullet["review_history"] = [*bullet.get("review_history", []), {"action": req.action, "before": before, "at": datetime.now(timezone.utc).isoformat()}]
    opt.optimized_content = bullets
    refresh_opt_scores(opt, draft, db)
    db.commit()
    return {
        "id": opt.id,
        "optimized_content": bullets,
        "ats_score": opt.ats_score,
        "keyword_match": opt.keyword_match,
        "skill_match": opt.skill_match,
        "experience_match": opt.experience_match,
        "job_company": opt.job.company if opt.job else None,
        "job_role": opt.job.role if opt.job else None,
        "gap_report": opt.gap_report,
    }


@router.post("/discovery/{session_id}/resolve")
def resolve_conflict(session_id: int, req: ResolveConflict, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.query(User).filter(User.id == user_id).with_for_update().first()
    session = owned(db, DiscoverySession, session_id, user_id, lock=True)
    view = session_view(db, session)
    conflict = next((c for c in view["conflicts"] if c["id"] == req.conflict_id), None)
    if not conflict or not any(o["value"] == req.choice for o in conflict["options"]):
        raise HTTPException(409, "Conflict changed or choice is not supported. Reload the profile.")
    resumes = [owned(db, Resume, rid, user_id) for rid in session.resume_ids]
    key = candidate_key(resumes)
    decision = db.query(ProfileDecision).filter_by(user_id=user_id, candidate_key=key, conflict_key=req.conflict_id).first()
    if decision:
        decision.choice = req.choice
    else:
        db.add(ProfileDecision(user_id=user_id, candidate_key=key, conflict_key=req.conflict_id, choice=req.choice))
    db.flush()
    # Profile changes invalidate current editable drafts, never submitted snapshots.
    for draft in db.query(EvidenceDraft).filter_by(user_id=user_id).all():
        if draft.session_id == session.id or draft.profile_snapshot.get("candidate_key") == key:
            draft.stale_evidence_ids = sorted(set(draft.stale_evidence_ids + session.evidence_ids))
    advance(db, session)
    db.commit()
    return session_view(db, session)


@router.post("/discovery/{session_id}/answers")
def answer(session_id: int, req: Answer, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    session = owned(db, DiscoverySession, session_id, user_id, lock=True)
    if session.status != "discovering" or not session.questions:
        raise HTTPException(409, "This discovery session is complete")
    q = session.questions[-1]
    if q["id"] != req.question_id or "answer" in q:
        raise HTTPException(409, "Question already answered or out of order; reload this session")
    if not req.skip and q["kind"] != "interpretation" and not req.answer.strip():
        raise HTTPException(422, "Enter your answer or skip this question")
    if not req.skip and q["kind"] == "ownership" and req.depth == "unspecified":
        raise HTTPException(422, "Choose the experience level, or skip")
    if q["kind"] == "gap":
        if not req.skip:
            if not req.company.strip() or req.depth == "unspecified":
                raise HTTPException(422, "Provide the project/employer and experience level, or skip")
            item = CandidateEvidence(user_id=user_id, revision=1, history=[],
                source_refs=[f"discovery:{session.id}:question:{q['id']}"],
                data={"content": req.answer.strip(), "company": req.company.strip(), "role": req.role.strip(),
                      "section": "Projects" if req.depth == "personal_project" else req.section,
                      "depth": req.depth, "ownership": req.answer.strip(), "ownership_confirmed": True,
                      "discovery_notes": req.answer.strip()})
            db.add(item)
            db.flush()
            session.evidence_ids = [*session.evidence_ids, item.id]
    else:
        item = owned(db, CandidateEvidence, q["evidence_id"], user_id, lock=True)
        if not req.skip and item.revision != q.get("evidence_revision"):
            raise HTTPException(409, "Evidence changed after this question. Skip it and review the corrected evidence.")
        data = apply_answer(item.data, q, req.answer.strip(), req.depth, req.confirm, req.skip)
        revise(db, item, data, "Candidate discovery answer")
        if not req.skip:
            item.source_refs = list(dict.fromkeys([*item.source_refs, f"discovery:{session.id}:question:{q['id']}"]))
    session.questions = [*session.questions[:-1], {**q, "answer": req.answer.strip(), "skipped": req.skip, "confirmed": req.confirm}]
    advance(db, session)
    db.commit()
    return session_view(db, session)


@router.get("/evidence")
def list_evidence(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return [serialize(e) for e in db.query(CandidateEvidence).filter(CandidateEvidence.user_id == user_id).all()]


@router.put("/evidence/{evidence_id}")
def correct(evidence_id: int, req: Correction, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    item = owned(db, CandidateEvidence, evidence_id, user_id, lock=True)
    if item.revision != req.revision:
        raise HTTPException(409, "This evidence changed. Reload before correcting it.")
    # A correction replaces the claim and clears earlier interpretations/context.
    # Otherwise old metrics or attribution could leak back into later drafts.
    data = req.model_dump(exclude={"revision", "reason"})
    data["ownership_confirmed"] = bool(req.ownership.strip())
    revise(db, item, data, req.reason)
    db.commit()
    affected = db.query(EvidenceDraft).filter(EvidenceDraft.user_id == user_id).all()
    return {"evidence": serialize(item), "affected_drafts": [draft_view(d) for d in affected if evidence_id in d.stale_evidence_ids]}


def refresh_opt_scores(opt, draft, db):
    from app.services.rule_engine import RuleEngine
    job = db.query(JobDescription).filter(JobDescription.id == opt.job_id).first()
    if not job:
        return
    profile = draft.profile_snapshot if draft else {}
    reconstructed_resume = {
        "profile_summary": "",
        "skills": profile.get("skills", []),
        "experience": [],
        "projects": [],
        "education": profile.get("education", [])
    }
    exp_dict = {}
    proj_dict = {}
    for b in (opt.optimized_content or []):
        if not b.get("included", True):
            continue
        if b.get("section") == "Experience":
            key = (b.get("company"), b.get("role"))
            if key not in exp_dict:
                exp_dict[key] = []
            exp_dict[key].append(b.get("optimized_bullet", b.get("original_bullet", "")))
        elif b.get("section") == "Projects":
            key = b.get("company")
            if key not in proj_dict:
                proj_dict[key] = []
            proj_dict[key].append(b.get("optimized_bullet", b.get("original_bullet", "")))

    for (company, role), bullets in exp_dict.items():
        reconstructed_resume["experience"].append({
            "company": company,
            "role": role,
            "bullets": bullets
        })
    for name, bullets in proj_dict.items():
        reconstructed_resume["projects"].append({
            "name": name,
            "bullets": bullets
        })

    rule_results = RuleEngine().analyze(reconstructed_resume, job.__dict__)
    opt.ats_score = rule_results.get("ats_score", 0.0)
    opt.keyword_match = rule_results.get("keyword_match", 0.0)
    opt.skill_match = rule_results.get("skill_match", 0.0)
    opt.experience_match = rule_results.get("experience_match", 0.0)
    from app.services.objection_engine import ObjectionEngine
    evidence_snapshot = draft.evidence_snapshot if draft else []
    active_mode = (opt.gap_report or {}).get("mode", "advance")
    objection_results = ObjectionEngine().analyze(profile, reconstructed_resume, job.__dict__, evidence_snapshot, mode=active_mode)
    opt.gap_report = {
        **(opt.gap_report or {}),
        "mode": active_mode,
        "missing_keywords": rule_results.get("missing_keywords", []),
        "matched_keywords": rule_results.get("matched_keywords", []),
        "score_label": rule_results.get("score_label"),
        "experience_duration_known": rule_results.get("experience_duration_known"),
        "formatting_report": rule_results.get("formatting_report", {}),
        "section_validation": rule_results.get("section_validation", {}),
        "objection_analysis": objection_results,
        "scores_require_refresh": False,
    }


def draft_view(d, opt=None):
    score_info = {}
    if opt:
        score_info = {
            "ats_score": opt.ats_score,
            "keyword_match": opt.keyword_match,
            "skill_match": opt.skill_match,
            "experience_match": opt.experience_match,
            "job_company": opt.job.company if opt.job else None,
            "job_role": opt.job.role if opt.job else None,
        }
    return {
        "id": d.optimization_id,
        "session_id": d.session_id,
        "status": d.status,
        "submitted": bool(d.submitted),
        "stale_evidence_ids": d.stale_evidence_ids,
        "error": d.error,
        **score_info
    }


@router.get("/evidence-drafts")
def list_drafts(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    drafts = db.query(EvidenceDraft).filter(EvidenceDraft.user_id == user_id).order_by(EvidenceDraft.id.desc()).all()
    opt_ids = [d.optimization_id for d in drafts]
    opts = {o.id: o for o in db.query(OptimizedResume).filter(OptimizedResume.id.in_(opt_ids)).all()} if opt_ids else {}
    return [draft_view(d, opts.get(d.optimization_id)) for d in drafts]


def create_draft(db, session, user_id):
    if session.status != "ready":
        raise HTTPException(409, "Finish or skip discovery questions before tailoring")
    evidence = db.query(CandidateEvidence).filter(CandidateEvidence.id.in_(session.evidence_ids), CandidateEvidence.user_id == user_id).order_by(CandidateEvidence.id).with_for_update().all()
    snapshot = [serialize(e) for e in evidence]
    if not any(evidence_bullet(e) for e in snapshot):
        raise HTTPException(422, "No supported achievement bullets available; review your evidence")
    opt = OptimizedResume(resume_id=session.resume_ids[0], job_id=session.job_id, optimized_content=[],
                          ats_score=0, keyword_match=0, skill_match=0, experience_match=0)
    db.add(opt)
    db.flush()
    resumes = [owned(db, Resume, i, user_id) for i in session.resume_ids]
    view = session_view(db, session)
    if view["conflicts"]:
        raise HTTPException(409, "Resolve conflicting claims before tailoring")
    profile = view["profile"]
    snapshot = view["evidence"]
    db.add(EvidenceDraft(optimization_id=opt.id, session_id=session.id, user_id=user_id,
                         profile_snapshot=profile,
                         evidence_snapshot=snapshot, stale_evidence_ids=[], status="queued", submitted=0))
    db.commit()
    from app.worker.tasks import optimize_resume_task
    try:
        optimize_resume_task.delay(opt.id)
    except Exception:
        draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt.id).first()
        draft.status = "failed"
        draft.error = "Could not queue optimization. Check the worker and retry."
        db.commit()
        raise HTTPException(503, draft.error)
    return {"id": opt.id}


@router.post("/discovery/{session_id}/optimize")
def optimize(session_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return create_draft(db, owned(db, DiscoverySession, session_id, user_id, lock=True), user_id)


@router.post("/evidence-drafts/{opt_id}/submit")
def submit(opt_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt_id, EvidenceDraft.user_id == user_id).with_for_update().first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "complete" or draft.stale_evidence_ids:
        raise HTTPException(409, "Only completed drafts with current evidence can be marked submitted")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    if any(b.get("included", True) and b.get("review_state") == "pending" for b in opt.optimized_content):
        raise HTTPException(409, "Accept or revert all included claims before marking submitted")
    draft.submitted = 1
    db.commit()
    return draft_view(draft, opt)


@router.post("/evidence-drafts/{opt_id}/revise")
def regenerate(opt_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt_id, EvidenceDraft.user_id == user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return create_draft(db, owned(db, DiscoverySession, draft.session_id, user_id, lock=True), user_id)


class SetModeRequest(BaseModel):
    mode: Literal["launch", "advance"]


@router.get("/evidence-drafts/{opt_id}/objections")
def get_draft_objections(opt_id: int, mode: str | None = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    active_mode = mode or (opt.gap_report or {}).get("mode", "advance")
    cached = (opt.gap_report or {}).get("objection_analysis")
    if cached and cached.get("mode") == active_mode and not (opt.gap_report or {}).get("scores_require_refresh"):
        return cached
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    from app.services.objection_engine import ObjectionEngine
    profile = draft.profile_snapshot or {}
    reconstructed_resume = {
        "profile_summary": "",
        "skills": profile.get("skills", []),
        "experience": [],
        "projects": [],
        "education": profile.get("education", [])
    }
    exp_dict = {}
    proj_dict = {}
    for b in (opt.optimized_content or []):
        if not b.get("included", True):
            continue
        if b.get("section") == "Experience":
            key = (b.get("company"), b.get("role"))
            if key not in exp_dict:
                exp_dict[key] = []
            exp_dict[key].append(b.get("optimized_bullet", b.get("original_bullet", "")))
        elif b.get("section") == "Projects":
            key = b.get("company")
            if key not in proj_dict:
                proj_dict[key] = []
            proj_dict[key].append(b.get("optimized_bullet", b.get("original_bullet", "")))
    for (company, role), bullets in exp_dict.items():
        reconstructed_resume["experience"].append({"company": company, "role": role, "bullets": bullets})
    for name, bullets in proj_dict.items():
        reconstructed_resume["projects"].append({"name": name, "bullets": bullets})
    analysis = ObjectionEngine().analyze(profile, reconstructed_resume, job.__dict__, draft.evidence_snapshot or [], mode=active_mode)
    opt.gap_report = {**(opt.gap_report or {}), "mode": active_mode, "objection_analysis": analysis}
    db.commit()
    return analysis


@router.post("/evidence-drafts/{opt_id}/mode")
def set_draft_mode(opt_id: int, req: SetModeRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    # Force recomputation under new mode
    analysis = get_draft_objections(opt_id, mode=req.mode, user_id=user_id, db=db)
    return {"mode": req.mode, "objection_analysis": analysis}


@router.get("/discovery/{session_id}/objections")
def get_session_objections(session_id: int, mode: str | None = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    session = owned(db, DiscoverySession, session_id, user_id)
    view = session_view(db, session)
    job = owned(db, JobDescription, session.job_id, user_id)
    profile = view["profile"]
    reconstructed = {
        "profile_summary": "",
        "skills": profile.get("skills", []),
        "experience": profile.get("experience", []),
        "projects": profile.get("projects", []),
        "education": profile.get("education", [])
    }
    active_mode = mode or "advance"
    from app.services.objection_engine import ObjectionEngine
    return ObjectionEngine().analyze(profile, reconstructed, job.__dict__, view["evidence"], mode=active_mode)


class EvaluateDefenseRequest(BaseModel):
    card_id: str
    explanation: str = Field(min_length=5, max_length=5000)


@router.get("/evidence-drafts/{opt_id}/defense-cards")
def get_draft_defense_cards(opt_id: int, mode: str | None = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    active_mode = mode or (opt.gap_report or {}).get("mode", "advance")
    from app.services.interview_defense import InterviewDefenseEngine
    engine = InterviewDefenseEngine()
    bullets = opt.optimized_content or []
    return engine.generate_defense_cards(bullets, draft.profile_snapshot or {}, job.__dict__, mode=active_mode)


@router.post("/evidence-drafts/{opt_id}/evaluate-defense")
def evaluate_draft_defense(opt_id: int, req: EvaluateDefenseRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    from app.services.interview_defense import InterviewDefenseEngine
    engine = InterviewDefenseEngine()
    bullets = opt.optimized_content or []
    cards = engine.generate_defense_cards(bullets, draft.profile_snapshot or {}, job.__dict__)
    card = next((c for c in cards if c["id"] == req.card_id), None)
    if not card:
        raise HTTPException(404, "Defense card not found")
    return engine.evaluate_defense_explanation(card, req.explanation)


@router.get("/evidence-drafts/{opt_id}/proof-specs")
def get_draft_proof_specs(opt_id: int, mode: str | None = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    active_mode = mode or (opt.gap_report or {}).get("mode", "advance")
    objections = get_draft_objections(opt_id, mode=active_mode, user_id=user_id, db=db)
    gap_classifications = objections.get("gap_classifications", [])
    from app.services.interview_defense import InterviewDefenseEngine
    engine = InterviewDefenseEngine()
    return engine.generate_proof_specs(gap_classifications, job.__dict__, mode=active_mode)


@router.get("/evidence-drafts/{opt_id}/outreach")
def get_draft_outreach(opt_id: int, mode: str | None = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    draft = db.query(EvidenceDraft).filter_by(optimization_id=opt_id, user_id=user_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    opt = db.query(OptimizedResume).filter_by(id=opt_id).one()
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    active_mode = mode or (opt.gap_report or {}).get("mode", "advance")
    objection_analysis = get_draft_objections(opt_id, mode=active_mode, user_id=user_id, db=db)
    from app.services.outreach_engine import OutreachEngine
    engine = OutreachEngine()
    bullets = opt.optimized_content or []
    return engine.generate_application_pack(
        bullets,
        draft.profile_snapshot or {},
        job.__dict__,
        objection_analysis,
        mode=active_mode
    )


class TrackDraftRequest(BaseModel):
    optimization_id: int
    status: Literal["Applied", "Referral", "OA", "Interview", "Rejected", "Offer"] = "Applied"
    salary: float | None = None
    notes: str | None = None


@router.post("/tracker/track-draft")
def track_draft_application(
    req: TrackDraftRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    opt = db.query(OptimizedResume).filter_by(id=req.optimization_id).first()
    if not opt:
        raise HTTPException(404, "Optimized resume not found")
    job = db.query(JobDescription).filter_by(id=opt.job_id).first()
    if not job:
        raise HTTPException(404, "Job description not found")
    
    from app.models.schemas import ApplicationTracker
    existing = db.query(ApplicationTracker).filter_by(user_id=user_id, optimization_id=req.optimization_id).first()
    if existing:
        existing.status = req.status
        if req.salary is not None:
            existing.salary = req.salary
        if req.notes:
            existing.notes = req.notes
        db.commit()
        db.refresh(existing)
        return {
            "id": existing.id,
            "company": existing.company,
            "role": existing.role,
            "status": existing.status,
            "optimization_id": existing.optimization_id,
            "message": "Updated existing application tracking"
        }
    
    item = ApplicationTracker(
        user_id=user_id,
        company=job.company,
        role=job.role,
        status=req.status,
        salary=req.salary,
        notes=req.notes or f"Applied via CareerProof using optimized draft #{opt.id}",
        optimization_id=req.optimization_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "company": item.company,
        "role": item.role,
        "status": item.status,
        "optimization_id": item.optimization_id,
        "message": "Application tracked successfully"
    }


@router.get("/analytics/claim-heatmap")
def get_claim_heatmap(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    from app.models.schemas import ApplicationTracker, CandidateEvidence
    from app.services.claim_analytics import ClaimAnalyticsEngine

    evidence_items = [
        {"id": e.id, "data": e.data, "revision": e.revision}
        for e in db.query(CandidateEvidence).filter_by(user_id=user_id).all()
    ]
    tracked_apps = [
        {
            "id": a.id,
            "company": a.company,
            "role": a.role,
            "status": a.status,
            "optimization_id": a.optimization_id
        }
        for a in db.query(ApplicationTracker).filter_by(user_id=user_id).all()
    ]
    drafts = db.query(EvidenceDraft).filter_by(user_id=user_id).all()
    opt_ids = [d.optimization_id for d in drafts if d.optimization_id]
    optimizations = []
    if opt_ids:
        opts = db.query(OptimizedResume).filter(OptimizedResume.id.in_(opt_ids)).all()
        for o in opts:
            optimizations.append({
                "id": o.id,
                "optimized_content": o.optimized_content or []
            })

    engine = ClaimAnalyticsEngine()
    return engine.analyze_claims(evidence_items, tracked_apps, optimizations)



