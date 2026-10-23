import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.routes import get_current_user_id
from app.models.schemas import Resume, JobDescription
from app.services.ats_checker import ATSCheckerEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ats", tags=["ATS Checker"])

class ATSCheckIn(BaseModel):
    resume_id: Optional[int] = None
    resume_text: Optional[str] = Field(default=None, max_length=150000)
    job_id: Optional[int] = None
    jd_text: Optional[str] = Field(default=None, max_length=150000)
    company: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=200)

@router.post("/check")
def check_ats_score(
    payload: ATSCheckIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Evaluates ATS match score between an existing candidate resume (or raw text)
    and a target job description (or raw text).
    Returns match percentage, breakdown, keywords, formatting report, comparison, and recommendations.
    """
    if not payload.resume_id and not (payload.resume_text and payload.resume_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select an existing resume or paste resume text."
        )

    if not payload.job_id and not (payload.jd_text and payload.jd_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a target job or paste job description text."
        )

    engine = ATSCheckerEngine()
    try:
        result = engine.check_match(
            db=db,
            user_id=user_id,
            resume_id=payload.resume_id,
            resume_text=payload.resume_text,
            job_id=payload.job_id,
            jd_text=payload.jd_text,
            company=payload.company,
            role=payload.role
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("ATS Check failed unexpectedly")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"ATS Check error: {str(e)}")

@router.get("/check-existing/{resume_id}/{job_id}")
def check_existing_pair(
    resume_id: int,
    job_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Quick GET endpoint to run ATS score calculation between any saved resume and job.
    """
    engine = ATSCheckerEngine()
    try:
        return engine.check_match(
            db=db,
            user_id=user_id,
            resume_id=resume_id,
            job_id=job_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("ATS check existing pair failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/catalog")
def get_ats_selection_catalog(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns available user resumes and target jobs formatted for easy UI dropdown selection.
    """
    resumes = db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc()).all()
    jobs = db.query(JobDescription).filter(JobDescription.user_id == user_id).order_by(JobDescription.created_at.desc()).all()

    formatted_resumes = []
    for r in resumes:
        bullet_count = len(r.bullets) if r.bullets else 0
        parsed = r.parsed_raw or {}
        skills_count = len(parsed.get("skills", []))
        formatted_resumes.append({
            "id": r.id,
            "name": r.name,
            "bullet_count": bullet_count,
            "skills_count": skills_count,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })

    formatted_jobs = []
    for j in jobs:
        kw_count = len(j.ats_keywords or []) + len(j.required_skills or [])
        formatted_jobs.append({
            "id": j.id,
            "company": j.company,
            "role": j.role,
            "department": j.department,
            "experience_years": j.experience_years,
            "keywords_count": kw_count,
            "created_at": j.created_at.isoformat() if j.created_at else None
        })

    return {
        "resumes": formatted_resumes,
        "jobs": formatted_jobs
    }

def extract_file_content(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        from app.services.resume_parser import extract_text_from_pdf
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        from app.services.resume_parser import extract_text_from_docx
        return extract_text_from_docx(file_bytes)
    else:
        return file_bytes.decode("utf-8", errors="ignore")

from fastapi import UploadFile, File, Form
from app.models.schemas import User, ResumeBullet
import re

@router.post("/upload-resume")
async def upload_resume_for_ats(
    file: UploadFile = File(...),
    save_to_library: bool = Form(True),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Uploads a resume file (.pdf, .docx, .txt), extracts text synchronously,
    optionally registers it into the user's permanent resume library,
    and returns resume_id and extracted text for immediate ATS evaluation.
    """
    filename = file.filename or "uploaded_resume.pdf"
    if not filename.lower().endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supported resume formats: PDF, DOCX, TXT"
        )

    content = await file.read(10 * 1024 * 1024 + 1)
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume file must be non-empty and under 10 MB."
        )

    try:
        text = extract_file_content(content, filename)
    except Exception as e:
        logger.error(f"Failed to extract resume text: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read resume file: {str(e)}"
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract readable text from resume. Try another file or paste text."
        )

    engine = ATSCheckerEngine()
    parsed_sections = engine._parse_raw_resume_text(text)

    db_resume_id = None
    if save_to_library:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            db.add(User(id=user_id, email=f"{user_id}@clerk.user"))
            db.flush()

        resume = Resume(
            user_id=user_id,
            name=filename,
            parsed_raw={
                "parsing_status": "ready",
                "raw_source_text": text,
                "skills": parsed_sections.get("skills", []),
                "experience": parsed_sections.get("experience", []),
                "projects": parsed_sections.get("projects", []),
                "education": parsed_sections.get("education", []),
                "profile_summary": parsed_sections.get("profile_summary", "")
            }
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        db_resume_id = resume.id

        # Insert ResumeBullets
        for exp in parsed_sections.get("experience", []):
            for bullet_str in exp.get("bullets", []):
                db.add(ResumeBullet(
                    resume_id=resume.id,
                    company=exp.get("company", "Experience"),
                    role=exp.get("role", "Role"),
                    section="Experience",
                    bullet=bullet_str,
                    technologies=parsed_sections.get("skills", [])
                ))
        db.commit()

    words = text.split()
    return {
        "filename": filename,
        "text": text,
        "word_count": len(words),
        "resume_id": db_resume_id,
        "saved_to_library": bool(db_resume_id),
        "preview": " ".join(words[:40]) + ("..." if len(words) > 40 else ""),
        "detected_skills_count": len(parsed_sections.get("skills", []))
    }

@router.post("/upload-jd")
async def upload_jd_for_ats(
    file: UploadFile = File(...),
    company: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    save_to_library: bool = Form(True),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Uploads a JD file (.pdf, .docx, .txt), extracts text synchronously,
    extracts requirements/skills, optionally saves it as a JobDescription,
    and returns job_id and extracted text for immediate ATS evaluation.
    """
    filename = file.filename or "job_description.pdf"
    if not filename.lower().endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supported job description formats: PDF, DOCX, TXT"
        )

    content = await file.read(10 * 1024 * 1024 + 1)
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job description file must be non-empty and under 10 MB."
        )

    try:
        text = extract_file_content(content, filename)
    except Exception as e:
        logger.error(f"Failed to extract JD text: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read job description file: {str(e)}"
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract readable text from job description. Try another file or paste text."
        )

    engine = ATSCheckerEngine()
    extracted = engine._parse_raw_jd_text(text)

    # Heuristic company and role inference if blank
    clean_company = company.strip() if company and company.strip() else ""
    clean_role = role.strip() if role and role.strip() else ""

    if not clean_company or not clean_role:
        base_name = re.sub(r'\.(pdf|docx|txt)$', '', filename, flags=re.I)
        parts = [p.strip() for p in re.split(r'[-_—]', base_name) if p.strip()]
        if len(parts) >= 2:
            if not clean_company:
                clean_company = parts[0].replace('_', ' ').title()
            if not clean_role:
                clean_role = " ".join(parts[1:]).replace('_', ' ').title()
        elif parts and not clean_role:
            clean_role = parts[0].replace('_', ' ').title()

    if not clean_company:
        clean_company = "Target Company"
    if not clean_role:
        clean_role = "Target Role"

    db_job_id = None
    if save_to_library:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            db.add(User(id=user_id, email=f"{user_id}@clerk.user"))
            db.flush()

        job = JobDescription(
            user_id=user_id,
            company=clean_company,
            role=clean_role,
            raw_text=text,
            ats_keywords=extracted.get("ats_keywords", []),
            required_skills=extracted.get("required_skills", []),
            preferred_skills=extracted.get("preferred_skills", []),
            experience_years=extracted.get("experience_years", 0.0)
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        db_job_id = job.id

    words = text.split()
    return {
        "filename": filename,
        "text": text,
        "word_count": len(words),
        "company": clean_company,
        "role": clean_role,
        "job_id": db_job_id,
        "saved_to_library": bool(db_job_id),
        "preview": " ".join(words[:40]) + ("..." if len(words) > 40 else ""),
        "detected_keywords_count": len(extracted.get("ats_keywords", []))
    }
