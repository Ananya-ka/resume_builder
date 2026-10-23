import logging
import json
from celery import Celery
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.schemas import Resume, ResumeBullet, JobDescription, OptimizedResume, KnowledgeBase, EvidenceDraft, DiscoverySession
from app.services.resume_parser import ResumeParser, extract_text_from_pdf, extract_text_from_docx
from app.services.structured_parser import StructuredResumeParser
from app.services.jd_parser import JDParser
from app.services.rule_engine import RuleEngine
from app.services.semantic_match import SemanticMatchEngine
from app.services.resume_optimizer import ResumeOptimizer
from app.services.fact_verifier import FactVerifier
from app.services.discovery import evidence_bullet, relevance
from app.services.agents import RecruiterAgent, ApplicationAgent, InterviewAgent

logger = logging.getLogger(__name__)

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

from app.services.document_extractor import (
    DocumentExtractor, DocumentEncryptedError, DocumentCorruptedError, DocumentEmptyError
)

@celery_app.task
def parse_resume_task(resume_id: int, file_bytes_hex: str, filename: str):
    """
    Background task to parse raw resume document bytes, generate embeddings
    for each bullet point, and save them in the database.
    Requires OpenAI for structured parsing and bullet metadata.
    """
    db = SessionLocal()
    try:
        filename_lower = filename.lower()
        file_bytes = bytes.fromhex(file_bytes_hex)

        # 1. Document Extraction (Local, layout-aware, no OpenAI calls)
        extractor = DocumentExtractor()
        try:
            extraction = extractor.extract(file_bytes, filename_lower)
        except DocumentEncryptedError as enc_err:
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.parsed_raw = {"parsing_status": "failed", "error": "This PDF is encrypted or password-protected. Please upload an unprotected file."}
                db.commit()
            return
        except DocumentCorruptedError as cor_err:
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.parsed_raw = {"parsing_status": "failed", "error": f"The document is corrupted: {cor_err}"}
                db.commit()
            return
        except DocumentEmptyError:
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.parsed_raw = {"parsing_status": "failed", "error": "The uploaded document is empty (0 bytes)."}
                db.commit()
            return

        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            logger.error(f"Resume with id {resume_id} not found.")
            return

        # Handle OCR required (scanned / image-only document)
        if extraction.needs_ocr:
            resume.parsed_raw = {
                "parsing_status": "needs_ocr",
                "error": "This document appears to be scanned or image-only and requires OCR. You can paste the text directly.",
                "raw_source_text": extraction.raw_text,
                "pages": extraction.pages_summary(),
                "needs_review": True
            }
            db.commit()
            return

        raw_text = extraction.raw_text
        if not raw_text.strip():
            resume.parsed_raw = {
                "parsing_status": "failed",
                "error": "Could not extract text from document. Ensure file is not scanned/empty.",
                "raw_source_text": "",
                "needs_review": True
            }
            db.commit()
            return

        # Step 2: Structured Parsing (completely independent of external AI or API keys)
        structured_parser = StructuredResumeParser()
        parsed_json = structured_parser.parse(raw_text, blocks=extraction.blocks)
        parsed_json.update({
            "raw_source_text": raw_text,
            "pages": extraction.pages_summary(),
            "ai_enhanced": False,
            "needs_review": True,
            "document_provenance": {
                "document_id": resume.id,
                "filename": filename,
                "page_count": len(extraction.pages),
                "block_count": len(extraction.blocks),
            },
        })

        # Step 3: Optional AI Enhancement if OpenAI is available and valid
        ai_parser = ResumeParser()
        if ai_parser.client:
            try:
                ai_parsed = ai_parser.parse_resume_to_json(raw_text)
                if ai_parsed and isinstance(ai_parsed, dict):
                    # Empty model fields must clear local guesses as well.
                    parsed_json.update(ai_parsed)
                    parsed_json["ai_enhanced"] = True
                    parsed_json["ai_model"] = settings.OPENAI_MODEL
            except Exception as ai_err:
                logger.warning(f"AI parsing enhancement skipped/failed: {ai_err}. Using deterministic structured parse.")
                parsed_json["ai_enhanced"] = False
                parsed_json["ai_warning"] = str(ai_err)

        # 3. Save individual bullets and generate metadata
        # Clear existing bullets if re-parsing
        db.query(ResumeBullet).filter(ResumeBullet.resume_id == resume.id).delete()

        bullet_count = 0

        # Process experience bullets
        for exp in parsed_json.get("experience", []):
            company = exp.get("company", "")
            role = exp.get("role", "")
            for bullet in exp.get("bullets", []):
                meta = structured_parser.extract_bullet_metadata(bullet, company, role)
                if parsed_json.get("ai_enhanced") and ai_parser.client:
                    try:
                        ai_meta = ai_parser.extract_bullet_metadata(bullet, company, role)
                        if ai_meta and isinstance(ai_meta, dict):
                            meta.update({k: v for k, v in ai_meta.items() if v})
                    except Exception as meta_err:
                        logger.debug(f"AI bullet metadata enhancement skipped: {meta_err}")

                emb = None
                if parsed_json.get("ai_enhanced") and ai_parser.client:
                    try:
                        emb = ai_parser.get_embedding(bullet)
                    except Exception as emb_err:
                        logger.debug(f"AI embedding generation skipped: {emb_err}")

                db_bullet = ResumeBullet(
                    resume_id=resume.id,
                    company=company,
                    role=role,
                    section="Experience",
                    bullet=bullet,
                    technologies=meta.get("technologies", []),
                    keywords=meta.get("keywords", []),
                    metrics=meta.get("metrics", []),
                    domain=meta.get("domain", "General"),
                    embedding=emb
                )
                db.add(db_bullet)
                bullet_count += 1

        # Process projects
        for proj in parsed_json.get("projects", []):
            name = proj.get("name", "")
            for bullet in proj.get("bullets", []):
                meta = structured_parser.extract_bullet_metadata(bullet, name, "Project")
                if parsed_json.get("ai_enhanced") and ai_parser.client:
                    try:
                        ai_meta = ai_parser.extract_bullet_metadata(bullet, name, "Project")
                        if ai_meta and isinstance(ai_meta, dict):
                            meta.update({k: v for k, v in ai_meta.items() if v})
                    except Exception as meta_err:
                        logger.debug(f"AI bullet metadata enhancement skipped: {meta_err}")

                emb = None
                if parsed_json.get("ai_enhanced") and ai_parser.client:
                    try:
                        emb = ai_parser.get_embedding(bullet)
                    except Exception as emb_err:
                        logger.debug(f"AI embedding generation skipped: {emb_err}")

                db_bullet = ResumeBullet(
                    resume_id=resume.id,
                    company=name,
                    role="Project Member",
                    section="Projects",
                    bullet=bullet,
                    technologies=meta.get("technologies", []),
                    keywords=meta.get("keywords", []),
                    metrics=meta.get("metrics", []),
                    domain=meta.get("domain", "General"),
                    embedding=emb
                )
                db.add(db_bullet)
                bullet_count += 1

        # 4. Mark status as ready
        resume.parsed_raw = {**parsed_json, "parsing_status": "ready"}
        db.commit()
        logger.info(f"Successfully extracted and parsed resume {resume_id} with {bullet_count} bullets (ai_enhanced={parsed_json.get('ai_enhanced')})")

    except Exception as e:
        logger.exception(f"Error in parse_resume_task: {e}")
        db.rollback()
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            resume.parsed_raw = {"parsing_status": "failed", "error": f"Document extraction/parsing failed: {e}"}
            db.commit()
    finally:
        db.close()

@celery_app.task
def optimize_resume_task(opt_id: int):
    """
    RAG-based resume optimizer task.
    Retrieves bullets, optimizes them, verifies, runs agents, and updates DB.
    """
    db = SessionLocal()
    try:
        opt_resume = db.query(OptimizedResume).filter(OptimizedResume.id == opt_id).first()
        if not opt_resume:
            logger.error(f"OptimizedResume {opt_id} not found.")
            return

        resume = opt_resume.resume
        jd = opt_resume.job

        draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt_id).with_for_update().first()
        if draft and draft.status != "queued":
            return  # A redelivered task must never overwrite a saved version.
        if draft:
            draft.status = "processing"
            db.commit()

        # 1. Parse JD if not already structured
        if jd.required_skills is None or jd.ats_keywords is None:
            jd_parser = JDParser()
            parsed_jd = jd_parser.parse_job_description(jd.raw_text)
            for k, v in parsed_jd.items():
                if k not in {"id", "user_id", "company", "role", "raw_text"} and hasattr(JobDescription, k):
                    setattr(jd, k, v)
            db.commit()

        # Discovery drafts use an immutable, attributable evidence snapshot.
        if draft:
            ranked = sorted(draft.evidence_snapshot, key=lambda e: (-relevance(e["data"], jd.raw_text), e["id"]))
            retrieved_bullets = [b for e in ranked if (b := evidence_bullet(e)) is not None]
        else:
            semantic_engine = SemanticMatchEngine(db)
            retrieved_bullets = semantic_engine.retrieve_relevant_bullets(
                user_id=resume.user_id, resume_id=resume.id, jd_text=jd.raw_text, limit=20
            )

        # 3. Optimize Bullets via ResumeOptimizer
        optimizer = ResumeOptimizer()
        jd_dict = {
            "company": jd.company,
            "role": jd.role,
            "required_skills": jd.required_skills or [],
            "ats_keywords": jd.ats_keywords or [],
            "responsibilities": jd.responsibilities or []
        }
        try:
            optimized_raw, learnable_skills = optimizer.optimize_bullets(retrieved_bullets, jd_dict)
        except Exception as opt_err:
            logger.warning("AI tailoring call failed (%s); using deterministic keyword alignment fallback", opt_err)
            optimized_raw, learnable_skills = optimizer._deterministic_optimize(retrieved_bullets, jd_dict)

        # Retrieve base profile skills for Condition A/B check
        allowed_base_skills = resume.parsed_raw.get("skills", []) if resume.parsed_raw else []

        # 4. Verify Bullets via FactVerifier
        verifier = FactVerifier()
        verified_bullets = verifier.verify_optimized_bullets(
            retrieved_bullets, 
            optimized_raw, 
            allowed_base_skills=allowed_base_skills
        )

        for source, verified in zip(retrieved_bullets, verified_bullets):
            verified["evidence_revision"] = source.get("revision")
            verified["depth"] = source.get("depth")
            verified["source_refs"] = source.get("source_refs", [])
            verified["evidence_context"] = source.get("evidence_context", source.get("content", ""))
            verified["review_state"] = "pending"
            verified["proposed_bullet"] = verified["optimized_bullet"]
            verified["review_history"] = []

        verified_bullets.sort(key=lambda b: -b.get("relevance_score", 50))
        words, per_role = 0, {}
        for bullet in verified_bullets:
            key = (bullet.get("section"), bullet.get("company"), bullet.get("role"))
            length = len(bullet["optimized_bullet"].split())
            include = bullet.get("relevance_score", 50) > 0 and words + length <= 330 and per_role.get(key, 0) < 4
            bullet["included"] = include
            if include:
                words += length
                per_role[key] = per_role.get(key, 0) + 1
            else:
                bullet["selection_reason"] = bullet.get("selection_reason", "") + " Omitted from the initial one-page selection to avoid repetition or overflow; available for review."

        # 5. Run Rule Engine calculations
        rule_engine = RuleEngine()
        
        # Summary claims are not copied from another version of the resume.
        profile = draft.profile_snapshot if draft else (resume.parsed_raw or {})
        reconstructed_resume = {
            "profile_summary": "",
            "skills": profile.get("skills", []),
            "experience": [],
            "projects": [],
            "education": profile.get("education", [])
        }
        
        # Group verified bullets by company/role for experience, and by project name for projects
        exp_dict = {}
        proj_dict = {}
        for b in verified_bullets:
            if not b.get("included", True):
                continue
            if b.get("section") == "Experience":
                key = (b.get("company"), b.get("role"))
                if key not in exp_dict:
                    exp_dict[key] = []
                exp_dict[key].append(b.get("optimized_bullet"))
            elif b.get("section") == "Projects":
                key = b.get("company") # project name
                if key not in proj_dict:
                    proj_dict[key] = []
                proj_dict[key].append(b.get("optimized_bullet"))

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

        rule_results = rule_engine.analyze(reconstructed_resume, jd.__dict__)

        # Discovery v1 publishes verified resume claims only. Extra application
        # assets and claim-specific interview cards are separate future steps.
        rec_report, app_assets, interview_questions = {}, {}, []
        if not draft:
            # 6. Run Recruiter Agent
            recruiter_agent = RecruiterAgent()
            rec_report = recruiter_agent.evaluate(
                resume_content=json.dumps(reconstructed_resume),
                jd_content=jd.raw_text
            )

            # 7. Run Application Agent
            app_agent = ApplicationAgent()
            app_assets = app_agent.generate_assets(
                resume_content=json.dumps(reconstructed_resume),
                jd_data=jd.__dict__
            )

            # 8. Run Interview Agent
            interview_agent = InterviewAgent()
            interview_questions = interview_agent.generate_interview_prep(
                resume_content=json.dumps(reconstructed_resume),
                jd_content=jd.raw_text
            )

        # 9. Update Database record
        opt_resume.optimized_content = verified_bullets
        opt_resume.ats_score = rule_results.get("ats_score", 0.0)
        opt_resume.keyword_match = rule_results.get("keyword_match", 0.0)
        opt_resume.skill_match = rule_results.get("skill_match", 0.0)
        opt_resume.experience_match = rule_results.get("experience_match", 0.0)
        from app.services.objection_engine import ObjectionEngine
        evidence_snapshot = draft.evidence_snapshot if draft else []
        objection_results = ObjectionEngine().analyze(profile, reconstructed_resume, jd.__dict__, evidence_snapshot)
        opt_resume.gap_report = {
            "missing_keywords": rule_results.get("missing_keywords", []),
            "matched_keywords": rule_results.get("matched_keywords", []),
            "score_label": rule_results.get("score_label"),
            "experience_duration_known": rule_results.get("experience_duration_known"),
            "formatting_report": rule_results.get("formatting_report", {}),
            "section_validation": rule_results.get("section_validation", {}),
            "suggested_learnable_skills": learnable_skills,
            "objection_analysis": objection_results,
        }
        opt_resume.recruiter_report = rec_report
        opt_resume.cover_letter = app_assets.get("cover_letter", "")
        opt_resume.referral_messages = {
            "referral_message": app_assets.get("referral_message", ""),
            "linkedin_dm": app_assets.get("linkedin_dm", ""),
            "cold_email": app_assets.get("cold_email", "")
        }
        opt_resume.interview_questions = interview_questions
        
        if draft:
            draft.status = "complete"
            draft.error = None
        db.commit()
        logger.info(f"Successfully processed optimization task for OptimizedResume {opt_id}")

    except Exception as e:
        logger.exception(f"Error in optimize_resume_task: {e}")
        db.rollback()
        draft = db.query(EvidenceDraft).filter(EvidenceDraft.optimization_id == opt_id).first()
        if draft:
            draft.status = "failed"
            draft.error = "Optimization failed. Your evidence is saved; retry to create a new draft."
            db.commit()
    finally:
        db.close()
