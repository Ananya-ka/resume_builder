"""REST API endpoints for JD Intelligence and Evidence-to-Requirement Mapping."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.routes import get_current_user_id
from app.models.schemas import User, JobDescription
from app.jd_intelligence.models import JobVersion, AnalysisRun
from app.jd_intelligence.schemas import (
    JobCreate, JobVersionOut, JobSummaryOut,
    AnalyzeRequest, AnalysisRunOut
)
from app.jd_intelligence import service

router = APIRouter(prefix="/api/jd", tags=["JD Intelligence"])


@router.post("/jobs", response_model=JobVersionOut, status_code=status.HTTP_201_CREATED)
def create_or_parse_job(
    req: JobCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Creates a job description or creates a new immutable version if text changed."""
    if not db.query(User).filter_by(id=user_id).first():
        db.add(User(id=user_id))
        db.flush()

    jv = service.create_or_update_job(db, user_id, req)
    return service.serialize_job_version(db, jv)


@router.get("/jobs", response_model=List[JobSummaryOut])
def list_jobs(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Lists all target jobs for the authenticated candidate."""
    jobs = db.query(JobDescription).filter_by(user_id=user_id).order_by(JobDescription.id.desc()).all()
    results = []
    for j in jobs:
        versions = db.query(JobVersion).filter_by(job_id=j.id).all()
        latest = max(versions, key=lambda v: v.version) if versions else None
        req_count = 0
        if latest:
            from app.jd_intelligence.models import JobRequirement
            req_count = db.query(JobRequirement).filter_by(job_version_id=latest.id).count()

        results.append({
            "id": j.id,
            "role": j.role,
            "company": j.company,
            "version_count": len(versions),
            "latest_version": latest.version if latest else 1,
            "requirement_count": req_count,
            "created_at": j.created_at.isoformat() if j.created_at else None
        })
    return results


@router.get("/jobs/{job_id}", response_model=JobVersionOut)
def get_job_latest_version(
    job_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Fetches the latest parsed version of a job with all source-quoted requirements."""
    job = service.owned_job(db, job_id, user_id)
    jv = db.query(JobVersion).filter_by(job_id=job.id).order_by(JobVersion.version.desc()).first()
    if not jv:
        raise HTTPException(status_code=404, detail="No parsed versions found for this job")
    return service.serialize_job_version(db, jv)


@router.get("/jobs/{job_id}/versions", response_model=List[JobVersionOut])
def get_job_all_versions(
    job_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Retrieves all version revisions for a given job."""
    job = service.owned_job(db, job_id, user_id)
    versions = db.query(JobVersion).filter_by(job_id=job.id).order_by(JobVersion.version.desc()).all()
    return [service.serialize_job_version(db, v) for v in versions]


@router.post("/analyze", response_model=AnalysisRunOut, status_code=status.HTTP_201_CREATED)
def run_analysis(
    req: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Evaluates candidate Evidence Catalog claims against Job Requirements."""
    run = service.analyze_catalog_against_job(
        db=db,
        user_id=user_id,
        catalog_id=req.catalog_id,
        job_id=req.job_id,
        job_version_id=req.job_version_id
    )
    return service.serialize_analysis_run(db, run)


@router.get("/analyses/{analysis_id}", response_model=AnalysisRunOut)
def get_analysis_run(
    analysis_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Fetches full analysis run with requirement matches, evidence links, and clarification questions."""
    run = db.query(AnalysisRun).filter_by(id=analysis_id, user_id=user_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return service.serialize_analysis_run(db, run)


@router.get("/catalogs/{catalog_id}/analyses", response_model=List[AnalysisRunOut])
def list_catalog_analyses(
    catalog_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Retrieves all historical analyses executed for a given candidate catalog."""
    service.owned_catalog(db, catalog_id, user_id)
    runs = db.query(AnalysisRun).filter_by(catalog_id=catalog_id, user_id=user_id).order_by(AnalysisRun.id.desc()).all()
    return [service.serialize_analysis_run(db, r) for r in runs]
