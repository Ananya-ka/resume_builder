import logging
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schemas import User, Resume, ResumeBullet, JobDescription, OptimizedResume, ApplicationTracker, KnowledgeBase, EvidenceDraft
from app.schemas.schemas import (
    UserCreate, UserOut, ResumeOut, JobDescriptionIn, JobDescriptionOut,
    OptimizeRequest, OptimizedResumeOut, ApplicationTrackerIn, ApplicationTrackerOut,
    KnowledgeBaseIn, KnowledgeBaseOut, ExportPdfRequest, DefaultTemplateOut
)
from app.worker.tasks import parse_resume_task, optimize_resume_task
from app.services.document_generator import (
    generate_docx_bytes, generate_pdf_bytes, generate_optimized_latex,
    compile_latex_to_pdf, render_latex_resume, DEFAULT_ATS_LATEX_TEMPLATE
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    # Fallback to user_test for easy API testing when header is omitted
    return x_user_id or "user_test"

# --- Users ---

@router.post("/users", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_in.id).first()
    if not db_user:
        db_user = User(id=user_in.id, email=user_in.email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user

# --- Resumes ---

@router.post("/resumes/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return (await persist_uploads([file], user_id, db))[0]


@router.post("/resumes/upload-batch", response_model=List[ResumeOut])
async def upload_resume_batch(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return await persist_uploads(files, user_id, db)


async def persist_uploads(files, user_id, db):
    if not 1 <= len(files) <= 3:
        raise HTTPException(422, "Upload one to three resumes at a time")
    uploads = []
    for file in files:
        name = file.filename or ""
        if not name.lower().endswith((".pdf", ".docx", ".txt")):
            raise HTTPException(422, "Supported resume formats: PDF, DOCX, TXT")
        content = await file.read(10 * 1024 * 1024 + 1)
        if not content or len(content) > 10 * 1024 * 1024:
            raise HTTPException(422, "Each resume must be nonempty and no larger than 10 MB")
        uploads.append((name, content))
    if not db.query(User).filter(User.id == user_id).first():
        db.add(User(id=user_id, email=f"{user_id}@clerk.user"))
        db.flush()
    resumes = [Resume(user_id=user_id, name=name, parsed_raw={"parsing_status": "queued"}) for name, _ in uploads]
    db.add_all(resumes)
    db.commit()
    for resume, (name, content) in zip(resumes, uploads):
        try:
            parse_resume_task.delay(resume.id, content.hex(), name)
        except Exception:
            logger.exception("Could not queue resume parsing")
            resume.parsed_raw = {"parsing_status": "failed", "error": "Could not queue parsing. Check the worker and upload again."}
    db.commit()
    return resumes


@router.get("/resumes", response_model=List[ResumeOut])
def list_resumes(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc()).all()

@router.get("/resumes/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume

@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    db.delete(resume)
    db.commit()
    return None


from pydantic import BaseModel, Field

class PasteResumeIn(BaseModel):
    name: str = Field(default="Pasted Resume.txt", max_length=200)
    text: str = Field(min_length=1, max_length=100000)


@router.post("/resumes/paste-text", response_model=ResumeOut)
def paste_resume(
    payload: PasteResumeIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    if not payload.text.strip():
        raise HTTPException(422, "Pasted resume text cannot be empty")
    if not db.query(User).filter(User.id == user_id).first():
        db.add(User(id=user_id, email=f"{user_id}@clerk.user"))
        db.flush()
    resume = Resume(
        user_id=user_id,
        name=payload.name.strip() or "Pasted Resume.txt",
        parsed_raw={"parsing_status": "queued"}
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    try:
        parse_resume_task.delay(resume.id, payload.text.encode("utf-8").hex(), payload.name.strip() or "Pasted Resume.txt")
    except Exception:
        logger.exception("Could not queue resume parsing for pasted text")
        resume.parsed_raw = {"parsing_status": "failed", "error": "Could not queue parsing. Check the worker and retry."}
        db.commit()
    return resume


@router.get("/system/status")
def system_status():
    from app.core.config import settings
    from app.services.document_extractor import DocumentExtractor
    extractor = DocumentExtractor()
    has_key = bool(settings.OPENAI_API_KEY)
    return {
        "openai_configured": has_key,
        "ai_model": settings.OPENAI_MODEL,
        "ocr_available": extractor.ocr_available,
        "capabilities": {
            "local_extraction": True,
            "structured_parsing": has_key,
            "evidence_catalog": True,
            "manual_editing": True,
            "ai_tailoring": has_key,
            "ai_questions": has_key
        },
        "message": (
            "OpenAI configured for parsing and tailoring. Model access is checked when processing."
            if has_key
            else "Configure OPENAI_API_KEY to enable resume parsing, discovery questions, and tailoring."
        )
    }

@router.post("/jobs/parse-file")
async def parse_job_file(file: UploadFile = File(...)):
    file_bytes = await file.read()
    filename = file.filename.lower()
    try:
        if filename.endswith(".pdf"):
            from app.services.resume_parser import extract_text_from_pdf
            text = extract_text_from_pdf(file_bytes)
        elif filename.endswith(".docx"):
            from app.services.resume_parser import extract_text_from_docx
            text = extract_text_from_docx(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
        return {"text": text}
    except Exception as e:
        logger.error(f"Failed to parse job file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse job file: {str(e)}")

# --- Job Descriptions ---

@router.post("/jobs", response_model=JobDescriptionOut)
def create_job(
    job_in: JobDescriptionIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Ensure user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        db_user = User(id=user_id, email=f"{user_id}@clerk.user")
        db.add(db_user)
        db.commit()

    job = JobDescription(
        user_id=user_id,
        company=job_in.company,
        role=job_in.role,
        department=job_in.department,
        raw_text=job_in.raw_text
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.get("/jobs", response_model=List[JobDescriptionOut])
def list_jobs(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(JobDescription).filter(JobDescription.user_id == user_id).order_by(JobDescription.created_at.desc()).all()

# --- Optimizations ---

@router.post("/optimize", response_model=OptimizedResumeOut)
def optimize_resume(
    req: OptimizeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Verify owner of resume
    resume = db.query(Resume).filter(Resume.id == req.resume_id, Resume.user_id == user_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Verify job description
    job = db.query(JobDescription).filter(JobDescription.id == req.job_id, JobDescription.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job description not found")

    if req.discovery_session_id is None:
        raise HTTPException(409, "Start /api/discovery and finish or skip its questions before optimizing")
    from app.api.discovery import owned, create_draft
    from app.models.schemas import DiscoverySession
    session = owned(db, DiscoverySession, req.discovery_session_id, user_id, lock=True)
    if session.job_id != req.job_id or session.resume_ids[0] != req.resume_id:
        raise HTTPException(422, "Resume and job must match the discovery session")
    result = create_draft(db, session, user_id)
    return db.query(OptimizedResume).filter(OptimizedResume.id == result["id"]).one()


@router.get("/optimizations/{opt_id}", response_model=OptimizedResumeOut)
def get_optimization(opt_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    opt = db.query(OptimizedResume).join(Resume).filter(OptimizedResume.id == opt_id, Resume.user_id == user_id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimization record not found")
    return opt

# --- Knowledge Base ---

@router.post("/knowledge", response_model=KnowledgeBaseOut)
def add_knowledge(
    kb_in: KnowledgeBaseIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Process embedding
    from app.services.resume_parser import ResumeParser
    parser = ResumeParser()
    emb = parser.get_embedding(kb_in.content)

    kb = KnowledgeBase(
        user_id=user_id,
        category=kb_in.category,
        content=kb_in.content,
        technologies=kb_in.technologies,
        keywords=kb_in.keywords,
        metrics=kb_in.metrics,
        embedding=emb
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb

@router.get("/knowledge", response_model=List[KnowledgeBaseOut])
def list_knowledge(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id).order_by(KnowledgeBase.created_at.desc()).all()

@router.delete("/knowledge/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge(kb_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    db.delete(kb)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Application Tracker ---

@router.post("/tracker", response_model=ApplicationTrackerOut)
def add_tracker_item(
    tracker_in: ApplicationTrackerIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        db_user = User(id=user_id, email=f"{user_id}@clerk.user")
        db.add(db_user)
        db.commit()

    item = ApplicationTracker(
        user_id=user_id,
        company=tracker_in.company,
        role=tracker_in.role,
        status=tracker_in.status,
        salary=tracker_in.salary,
        recruiter_name=tracker_in.recruiter_name,
        recruiter_contact=tracker_in.recruiter_contact,
        notes=tracker_in.notes,
        optimization_id=tracker_in.optimization_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/tracker", response_model=List[ApplicationTrackerOut])
def list_tracker_items(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(ApplicationTracker).filter(ApplicationTracker.user_id == user_id).order_by(ApplicationTracker.updated_at.desc()).all()

@router.put("/tracker/{tracker_id}", response_model=ApplicationTrackerOut)
def update_tracker_item(
    tracker_id: int,
    tracker_in: ApplicationTrackerIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    item = db.query(ApplicationTracker).filter(ApplicationTracker.id == tracker_id, ApplicationTracker.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracker item not found")
    
    for k, v in tracker_in.dict().items():
        setattr(item, k, v)
        
    db.commit()
    db.refresh(item)
    return item

@router.delete("/tracker/{tracker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracker_item(tracker_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    item = db.query(ApplicationTracker).filter(ApplicationTracker.id == tracker_id, ApplicationTracker.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracker item not found")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Exporters ---

def export_profile(db, opt):
    draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt.id).first()
    if draft:
        if draft.status != "complete":
            raise HTTPException(409, "Wait for the draft to finish before exporting")
        if not draft.submitted and draft.stale_evidence_ids:
            raise HTTPException(409, "Evidence changed. Create a corrected version before exporting.")
        if any(b.get("included", True) and b.get("review_state") == "pending" for b in opt.optimized_content):
            raise HTTPException(409, "Accept or revert the included claims in Review before exporting.")
        # Never rewrite an old LaTeX source containing superseded claims.
        return draft.profile_snapshot
    return opt.resume.parsed_raw or {}


@router.get("/optimizations/{opt_id}/export/docx")
def export_docx(opt_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    opt = db.query(OptimizedResume).join(Resume).filter(OptimizedResume.id == opt_id, Resume.user_id == user_id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimization record not found")
    
    parsed_raw = export_profile(db, opt)
    user_email = parsed_raw.get("email") or ""
    user_name = parsed_raw.get("name") or ""

    docx_bytes = generate_docx_bytes(
        name=user_name,
        email=user_email,
        parsed_resume=parsed_raw,
        optimized_bullets=[b for b in (opt.optimized_content or []) if b.get("included", True)]
    )

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=Optimized_Resume_{opt.job.company}.docx"}
    )

def _handle_pdf_export(
    opt_id: int, user_id: str, db: Session,
    template_choice: str = "default", custom_template: Optional[str] = None,
    page_policy: str = "ask",
):
    from app.services.pdf_export import compile_export, concise_export
    opt = db.query(OptimizedResume).join(Resume).filter(OptimizedResume.id == opt_id, Resume.user_id == user_id).first()
    if not opt:
        raise HTTPException(404, "Optimization record not found")
    profile = export_profile(db, opt)
    try:
        pdf_bytes, pages = compile_export(profile, opt.optimized_content or [], template_choice, custom_template)
        omitted = []
        if pages > 1 and page_policy == "ask":
            raise HTTPException(409, detail={"code": "page_limit", "pages": pages,
                "message": f"Your resume is {pages} pages. Keep all pages or create a concise one-page version?"})
        if pages > 1 and page_policy == "one_page":
            pdf_bytes, pages, omitted = concise_export(profile, opt.optimized_content or [],
                {"role": opt.job.role, "company": opt.job.company,
                 "required_skills": opt.job.required_skills or [], "ats_keywords": opt.job.ats_keywords or [],
                 "responsibilities": opt.job.responsibilities or []}, template_choice, custom_template)
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=Optimized_Resume_{opt.id}.pdf",
            "X-Resume-Pages": str(pages), "X-Resume-Omitted": str(len(omitted)),
        })
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF export failed")
        raise HTTPException(503, "PDF generation failed. Check the backend compiler logs and retry.") from exc


def _handle_latex_export(
    opt_id: int,
    user_id: str,
    db: Session,
    template_choice: str = "default",
    custom_template: Optional[str] = None
):
    opt = db.query(OptimizedResume).join(Resume).filter(OptimizedResume.id == opt_id, Resume.user_id == user_id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimization record not found")

    parsed_raw = export_profile(db, opt)
    raw_source = parsed_raw.get("raw_source_text", "")

    user_email = parsed_raw.get("email") or ""
    user_name = parsed_raw.get("name") or ""

    if template_choice == "original" and raw_source and ("\\documentclass" in raw_source or "\\begin{document}" in raw_source):
        opt_latex = generate_optimized_latex(raw_source, opt.optimized_content or [])
    else:
        opt_latex = render_latex_resume(
            name=user_name,
            email=user_email,
            parsed_resume=parsed_raw,
            optimized_bullets=[b for b in (opt.optimized_content or []) if b.get("included", True)],
            template_choice=template_choice,
            custom_template=custom_template
        )

    return StreamingResponse(
        io.BytesIO(opt_latex.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=Optimized_Resume_{opt.job.company}.tex"}
    )


@router.get("/templates/default-latex")
def get_default_latex_template():
    return {"template": DEFAULT_ATS_LATEX_TEMPLATE}


@router.get("/optimizations/{opt_id}/export/pdf")
def export_pdf(
    opt_id: int,
    template_choice: str = "default",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return _handle_pdf_export(
        opt_id=opt_id,
        user_id=user_id,
        db=db,
        template_choice=template_choice,
        custom_template=None
    )


@router.post("/optimizations/{opt_id}/export/pdf")
def export_pdf_post(
    opt_id: int,
    req: ExportPdfRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return _handle_pdf_export(
        opt_id=opt_id,
        user_id=user_id,
        db=db,
        template_choice=req.template_choice,
        custom_template=req.custom_template,
        page_policy=req.page_policy
    )


@router.get("/optimizations/{opt_id}/export/latex")
def export_latex(
    opt_id: int,
    template_choice: str = "default",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return _handle_latex_export(
        opt_id=opt_id,
        user_id=user_id,
        db=db,
        template_choice=template_choice,
        custom_template=None
    )


@router.post("/optimizations/{opt_id}/export/latex")
def export_latex_post(
    opt_id: int,
    req: ExportPdfRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return _handle_latex_export(
        opt_id=opt_id,
        user_id=user_id,
        db=db,
        template_choice=req.template_choice,
        custom_template=req.custom_template
    )
