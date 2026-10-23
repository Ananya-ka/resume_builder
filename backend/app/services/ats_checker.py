import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.schemas import Resume, ResumeBullet, JobDescription, OptimizedResume, EvidenceDraft
from app.services.rule_engine import RuleEngine

logger = logging.getLogger(__name__)

COMMON_TECH_SKILLS = [
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang", "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "bash", "shell",
    # Frontend
    "react", "react.js", "next.js", "vue", "vue.js", "angular", "svelte", "html", "html5", "css", "css3", "tailwind", "tailwind css", "redux", "webpack", "vite",
    # Backend & Frameworks
    "fastapi", "flask", "django", "node.js", "nodejs", "express", "express.js", "spring", "spring boot", "ruby on rails", "asp.net", "graphql", "rest", "restful apis", "grpc", "microservices",
    # Cloud & DevOps
    "aws", "amazon web services", "gcp", "google cloud", "azure", "docker", "kubernetes", "k8s", "terraform", "ci/cd", "github actions", "gitlab", "jenkins", "linux", "helm", "ansible",
    # Databases & Storage
    "postgresql", "postgres", "mysql", "mongodb", "redis", "dynamodb", "elasticsearch", "cassandra", "sqlite", "snowflake", "bigquery", "kafka", "rabbitmq", "pgvector", "faiss",
    # AI / Machine Learning
    "machine learning", "deep learning", "nlp", "llms", "large language models", "rag", "pytorch", "tensorflow", "scikit-learn", "hugging face", "langchain", "langgraph", "embeddings", "vector databases", "computer vision", "pandas", "numpy",
    # Testing & Architecture
    "unit testing", "pytest", "jest", "cypress", "system design", "distributed systems", "agile", "scrum", "jira"
]

class ATSCheckerEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()

    def check_match(
        self,
        db: Session,
        user_id: str,
        resume_id: Optional[int] = None,
        resume_text: Optional[str] = None,
        job_id: Optional[int] = None,
        jd_text: Optional[str] = None,
        company: Optional[str] = None,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates pure-engine ATS match between candidate resume and target JD.
        Supports both saved records and raw text inputs.
        Also calculates baseline-vs-optimized score lift if an optimized draft exists.
        """
        # 1. Resolve Resume Data
        resume_data, resume_meta = self._resolve_resume_data(db, user_id, resume_id, resume_text)

        # 2. Resolve Job Data
        jd_data, job_meta = self._resolve_jd_data(db, user_id, job_id, jd_text, company, role)

        # 3. Execute RuleEngine Analysis
        analysis = self.rule_engine.analyze(resume_data, jd_data)

        # 4. Score categorization & labels
        score = analysis.get("ats_score", 0.0)
        label = self._get_match_label(score)

        # 5. Check if an optimized version exists to show score boost comparison
        comparison = self._find_optimization_comparison(db, user_id, resume_id, job_id, score, job_meta.get("company"), job_meta.get("role"))

        # 6. Actionable recommendations
        recommendations = self._generate_recommendations(analysis, jd_data, comparison)

        return {
            "ats_score": score,
            "overall_fit_score": analysis.get("overall_fit_score", score),
            "match_tier": label["tier"],
            "score_label": label["label"],
            "summary_tagline": label["tagline"],
            "hard_eligibility": analysis.get("hard_eligibility", {}),
            "dimension_scores": analysis.get("dimension_scores", {}),
            "skills_breakdown": analysis.get("skills_breakdown", {}),
            "responsibilities_breakdown": analysis.get("responsibilities_breakdown", {}),
            "education_breakdown": analysis.get("education_breakdown", {}),
            "domain_breakdown": analysis.get("domain_breakdown", {}),
            "evidence_ledger": analysis.get("evidence_ledger", []),
            "missing_information_report": analysis.get("missing_information_report", {}),
            "breakdown": {
                "keyword_match": analysis.get("keyword_match", 0.0),
                "skill_match": analysis.get("skill_match", 0.0),
                "experience_match": analysis.get("experience_match", 0.0),
                "resume_years": analysis.get("resume_years", 0.0),
                "resume_months": analysis.get("resume_months", 0),
                "required_years": analysis.get("required_years", 0.0),
                "experience_duration_known": analysis.get("experience_duration_known", False),
                "section_score": round((sum(1 for v in analysis.get("section_validation", {}).values() if v) / 4.0) * 100.0, 1),
                "action_verb_rate": analysis.get("formatting_report", {}).get("action_verb_rate", 0.0),
                "tenure_report": analysis.get("tenure_report", {}),
                "hard_eligibility": analysis.get("hard_eligibility", {}),
                "dimension_scores": analysis.get("dimension_scores", {}),
                "responsibilities_breakdown": analysis.get("responsibilities_breakdown", {}),
                "education_breakdown": analysis.get("education_breakdown", {}),
                "domain_breakdown": analysis.get("domain_breakdown", {})
            },
            "tenure_report": analysis.get("tenure_report", {}),
            "matched_keywords": analysis.get("matched_keywords", []),
            "missing_keywords": analysis.get("missing_keywords", []),
            "section_validation": analysis.get("section_validation", {}),
            "formatting_report": analysis.get("formatting_report", {}),
            "resume_meta": resume_meta,
            "job_meta": job_meta,
            "comparison": comparison,
            "recommendations": recommendations
        }

    def _resolve_resume_data(
        self,
        db: Session,
        user_id: str,
        resume_id: Optional[int],
        resume_text: Optional[str]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        resume_data = {
            "profile_summary": "",
            "experience": [],
            "projects": [],
            "skills": [],
            "education": []
        }
        meta = {
            "source": "raw_text",
            "resume_id": resume_id,
            "name": "Pasted Resume Text",
            "bullet_count": 0
        }

        if resume_id:
            db_resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user_id).first()
            if not db_resume:
                raise ValueError(f"Resume with ID {resume_id} not found")

            meta["name"] = db_resume.name
            meta["source"] = "saved_resume"

            parsed = db_resume.parsed_raw or {}
            if isinstance(parsed, dict) and parsed.get("experience"):
                resume_data["experience"] = parsed.get("experience", [])
                resume_data["skills"] = parsed.get("skills", [])
                resume_data["projects"] = parsed.get("projects", [])
                resume_data["education"] = parsed.get("education", [])
                resume_data["profile_summary"] = parsed.get("profile_summary", "")

            # If experience is empty, try reconstructing from ResumeBullet table
            bullets = db.query(ResumeBullet).filter(ResumeBullet.resume_id == resume_id).all()
            if bullets:
                meta["bullet_count"] = len(bullets)
                if not resume_data["experience"] and not resume_data["projects"]:
                    exp_map = {}
                    proj_map = {}
                    for b in bullets:
                        if b.section == "Experience":
                            key = (b.company or "Experience", b.role or "Role")
                            exp_map.setdefault(key, []).append(b.bullet)
                        elif b.section == "Projects":
                            proj_map.setdefault(b.company or "Project", []).append(b.bullet)
                        if b.keywords:
                            resume_data["skills"].extend([k for k in b.keywords if k not in resume_data["skills"]])
                        if b.technologies:
                            resume_data["skills"].extend([t for t in b.technologies if t not in resume_data["skills"]])

                    for (comp, rle), b_list in exp_map.items():
                        resume_data["experience"].append({"company": comp, "role": rle, "bullets": b_list})
                    for name, b_list in proj_map.items():
                        resume_data["projects"].append({"name": name, "bullets": b_list})

            # If experience has no dates or is generic ('Experience') or empty, and raw_source_text exists, refresh from raw text
            needs_refresh = (
                not resume_data["experience"]
                or all(not exp.get("dates") for exp in resume_data["experience"])
                or any(exp.get("company") == "Experience" for exp in resume_data["experience"])
            )
            if needs_refresh and parsed.get("raw_source_text"):
                parsed_text_data = self._parse_raw_resume_text(parsed["raw_source_text"])
                if parsed_text_data.get("experience"):
                    resume_data["experience"] = parsed_text_data["experience"]
                    parsed["experience"] = parsed_text_data["experience"]
                    if not resume_data["skills"] and parsed_text_data.get("skills"):
                        resume_data["skills"] = parsed_text_data["skills"]
                        parsed["skills"] = parsed_text_data["skills"]
                    for k in ["projects", "education"]:
                        if not resume_data[k] and parsed_text_data.get(k):
                            resume_data[k] = parsed_text_data[k]
                            parsed[k] = parsed_text_data[k]
                    db_resume.parsed_raw = dict(parsed)
                    db.commit()

        elif resume_text and resume_text.strip():
            resume_data = self._parse_raw_resume_text(resume_text.strip())
            total_bullets = sum(len(e.get("bullets", [])) for e in resume_data["experience"]) + sum(len(p.get("bullets", [])) for p in resume_data["projects"])
            meta["bullet_count"] = total_bullets
        else:
            raise ValueError("Provide either a valid resume_id or resume_text")

        return resume_data, meta

    def _resolve_jd_data(
        self,
        db: Session,
        user_id: str,
        job_id: Optional[int],
        jd_text: Optional[str],
        company: Optional[str],
        role: Optional[str]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        jd_data = {
            "ats_keywords": [],
            "required_skills": [],
            "preferred_skills": [],
            "experience_years": 0.0,
            "company": company or "Target Company",
            "role": role or "Target Role"
        }
        meta = {
            "source": "raw_text",
            "job_id": job_id,
            "company": jd_data["company"],
            "role": jd_data["role"],
            "keywords_count": 0
        }

        if job_id:
            db_job = db.query(JobDescription).filter(JobDescription.id == job_id, JobDescription.user_id == user_id).first()
            if not db_job:
                raise ValueError(f"Job description with ID {job_id} not found")

            meta["company"] = db_job.company
            meta["role"] = db_job.role
            meta["source"] = "saved_job"

            # Populate keywords from all available structured columns
            kw_set = set([k.lower() for k in (db_job.ats_keywords or [])])
            if db_job.languages:
                kw_set.update([l.lower() for l in db_job.languages])
            if db_job.frameworks:
                kw_set.update([f.lower() for f in db_job.frameworks])
            if db_job.databases:
                kw_set.update([d.lower() for d in db_job.databases])
            if db_job.cloud:
                kw_set.update([c.lower() for c in db_job.cloud])

            jd_data["ats_keywords"] = list(kw_set)
            jd_data["required_skills"] = [s.lower() for s in (db_job.required_skills or [])]
            jd_data["preferred_skills"] = [s.lower() for s in (db_job.preferred_skills or [])]
            jd_data["experience_years"] = float(db_job.experience_years or 0.0)
            jd_data["company"] = db_job.company
            jd_data["role"] = db_job.role
            jd_data["raw_text"] = db_job.raw_text or ""
            meta["keywords_count"] = len(jd_data["ats_keywords"]) + len(jd_data["required_skills"])

        elif jd_text and jd_text.strip():
            extracted = self._parse_raw_jd_text(jd_text.strip())
            jd_data.update(extracted)
            jd_data["raw_text"] = jd_text.strip()
            if company:
                jd_data["company"] = company
                meta["company"] = company
            if role:
                jd_data["role"] = role
                meta["role"] = role
            meta["keywords_count"] = len(jd_data["ats_keywords"]) + len(jd_data["required_skills"])
        else:
            raise ValueError("Provide either a valid job_id or jd_text")

        return jd_data, meta

    def _parse_raw_resume_text(self, text: str) -> Dict[str, Any]:
        """
        Parses raw text into resume_data dict containing experience, projects, skills, and education.
        Uses StructuredResumeParser if structured sections are found, with fallback to line-level extraction.
        """
        text_lower = text.lower()
        extracted_tech = []
        for tech in COMMON_TECH_SKILLS:
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, text_lower):
                extracted_tech.append(tech)

        # 1. Attempt structured parsing with StructuredResumeParser
        try:
            from app.services.structured_parser import StructuredResumeParser
            structured = StructuredResumeParser().parse(text)
            if structured.get("experience"):
                all_skills = list(set([s.lower() for s in (structured.get("skills") or [])] + extracted_tech))
                return {
                    "profile_summary": structured.get("profile_summary", ""),
                    "experience": structured.get("experience", []),
                    "projects": structured.get("projects", []),
                    "skills": all_skills,
                    "education": structured.get("education", []) or [{"school": "University", "degree": "Degree"}]
                }
        except Exception as e:
            logger.debug(f"Structured parser fallback: {e}")

        # 2. Fallback line-level extraction
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        skills = extracted_tech
        bullets = []

        # Detect bullet points
        bullet_prefixes = ("-", "*", "•", "–", "—", ">")
        for line in lines:
            if line.startswith(bullet_prefixes):
                clean_b = line.lstrip("-*•–—> \t")
                if len(clean_b) > 10:
                    bullets.append(clean_b)
            elif re.match(r'^\d+[\.\)]\s+', line):
                clean_b = re.sub(r'^\d+[\.\)]\s+', '', line)
                if len(clean_b) > 10:
                    bullets.append(clean_b)

        # Extract basic education if present
        edu_entries = []
        edu_keywords = ["university", "college", "institute", "bachelor", "master", "phd", "b.tech", "m.tech", "b.s.", "m.s."]
        for line in lines:
            if any(k in line.lower() for k in edu_keywords):
                edu_entries.append({"school": line, "degree": "Degree"})

        # Extract summary preamble
        summary_lines = []
        for line in lines:
            if line.startswith(bullet_prefixes) or re.match(r'^\d+[\.\)]\s+', line) or any(k in line.lower() for k in ["experience:", "skills:", "education:", "projects:"]):
                break
            summary_lines.append(line)
        profile_summary = " ".join(summary_lines) if summary_lines else (lines[0] if lines else "")

        # Look for date intervals in lines
        detected_dates = ""
        for line in lines:
            intervals = self.rule_engine._extract_date_intervals(line)
            if intervals:
                detected_dates = line
                break

        return {
            "profile_summary": profile_summary,
            "experience": [{"company": "Experience", "role": "Candidate Role", "dates": detected_dates, "bullets": bullets}],
            "projects": [],
            "skills": skills,
            "education": edu_entries or [{"school": "University", "degree": "Degree"}]
        }

    def _parse_raw_jd_text(self, text: str) -> Dict[str, Any]:
        """
        Extracts skills, keywords, and experience tenure from raw job description text.
        """
        text_lower = text.lower()
        extracted_skills = []

        # 1. Match known tech terms
        for tech in COMMON_TECH_SKILLS:
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, text_lower):
                extracted_skills.append(tech)

        # 2. Extract tenure requirements with precision TenureMatcher
        from dataclasses import asdict
        tenure_reqs = self.rule_engine.tenure_matcher.extract_jd_requirements(text)
        years = tenure_reqs.min_years

        # 3. Extract capitalized phrases from requirement lines
        custom_keywords = set(extracted_skills)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        in_requirements = False
        for line in lines:
            lower = line.lower()
            if any(h in lower for h in ["requirement", "qualification", "what you need", "skills required", "must have"]):
                in_requirements = True
                continue
            if in_requirements and any(h in lower for h in ["benefits", "about us", "perks", "equal opportunity"]):
                in_requirements = False

            if in_requirements:
                # Extract words or phrases
                matches = re.findall(r'\b[A-Z][a-zA-Z0-9\+\#\.\-]+\b', line)
                for m in matches:
                    if len(m) > 2 and m.lower() not in {"and", "the", "for", "with", "must", "have", "you", "will", "our"}:
                        custom_keywords.add(m.lower())

        ats_keywords = list(custom_keywords)
        # Split into required (first half or high priority) and preferred
        half = len(ats_keywords) // 2 or len(ats_keywords)
        return {
            "ats_keywords": ats_keywords,
            "required_skills": ats_keywords[:half],
            "preferred_skills": ats_keywords[half:],
            "experience_years": years,
            "min_years": tenure_reqs.min_years,
            "max_years": tenure_reqs.max_years,
            "has_explicit_maximum": tenure_reqs.has_explicit_maximum,
            "preferred_years": tenure_reqs.preferred_years,
            "role_specific_requirements": [asdict(r) for r in tenure_reqs.role_specific],
            "raw_text": text
        }

    def _get_match_label(self, score: float) -> Dict[str, str]:
        if score >= 80.0:
            return {
                "tier": "strong_match",
                "label": "Strong ATS Match",
                "tagline": "High interview probability. Resume strongly aligns with JD keywords and requirements."
            }
        elif score >= 65.0:
            return {
                "tier": "competitive_match",
                "label": "Competitive Match",
                "tagline": "Good foundational match with minor keyword gaps. Readily addressable with targeted tailoring."
            }
        elif score >= 50.0:
            return {
                "tier": "needs_alignment",
                "label": "Needs Alignment",
                "tagline": "Notable keyword or technical gaps detected. Likely to be filtered by strict ATS parsers."
            }
        else:
            return {
                "tier": "high_risk",
                "label": "High Risk / Screening Gap",
                "tagline": "Major keyword and qualification deficits. High risk of ATS rejection without substantial evidence additions."
            }

    def _find_optimization_comparison(
        self,
        db: Session,
        user_id: str,
        resume_id: Optional[int],
        job_id: Optional[int],
        baseline_score: float,
        company: Optional[str],
        role: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Looks up any existing OptimizedResume or EvidenceDraft matching this resume and job.
        Computes score delta demonstrating CareerProof lift.
        """
        opt = None
        if resume_id and job_id:
            opt = db.query(OptimizedResume).filter(
                OptimizedResume.resume_id == resume_id,
                OptimizedResume.job_id == job_id
            ).order_by(OptimizedResume.created_at.desc()).first()

        # If not found by IDs, check by company & role match
        if not opt and company and role:
            opt = db.query(OptimizedResume).join(JobDescription).filter(
                JobDescription.company.ilike(f"%{company.strip()}%"),
                JobDescription.role.ilike(f"%{role.strip()}%")
            ).order_by(OptimizedResume.created_at.desc()).first()

        if opt:
            optimized_score = opt.ats_score
            delta = round(optimized_score - baseline_score, 1)
            return {
                "has_optimized_version": True,
                "optimization_id": opt.id,
                "optimized_score": optimized_score,
                "baseline_score": baseline_score,
                "score_delta": delta,
                "status": "ready"
            }

        return {
            "has_optimized_version": False,
            "baseline_score": baseline_score,
            "optimized_score": None,
            "score_delta": None,
            "status": "not_optimized"
        }

    def _generate_recommendations(
        self,
        analysis: Dict[str, Any],
        jd_data: Dict[str, Any],
        comparison: Optional[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        recs = []
        missing = analysis.get("missing_keywords", [])
        if missing:
            top_3 = ", ".join(missing[:3])
            recs.append({
                "type": "keywords",
                "title": f"Incorporate {len(missing)} Missing Keywords",
                "description": f"Missing critical terms like '{top_3}'. Add evidence-backed projects or bullets covering these skills.",
                "action": "Add to Evidence Catalog"
            })

        fmt = analysis.get("formatting_report", {})
        if fmt.get("action_verb_rate", 100.0) < 70.0:
            recs.append({
                "type": "action_verbs",
                "title": "Strengthen Action Verbs",
                "description": f"Only {fmt.get('action_verb_rate')}% of bullets start with strong action verbs. Use verbs like 'Architected', 'Deployed', 'Engineered'.",
                "action": "Revise Bullet Openers"
            })

        if fmt.get("bullet_warnings"):
            recs.append({
                "type": "formatting",
                "title": "Fix Bullet Punctuation & Grammar",
                "description": f"{len(fmt.get('bullet_warnings'))} bullets do not end with periods or have consistency issues.",
                "action": "Standardize Formatting"
            })

        sections = analysis.get("section_validation", {})
        missing_sections = [sec for sec, present in sections.items() if not present]
        if missing_sections:
            recs.append({
                "type": "sections",
                "title": f"Add Missing Sections ({', '.join(missing_sections)})",
                "description": f"Standard ATS parsers search specifically for {', '.join(missing_sections)} headings.",
                "action": "Insert Section Headers"
            })

        if comparison and comparison.get("has_optimized_version"):
            delta = comparison.get("score_delta", 0)
            recs.append({
                "type": "optimization",
                "title": f"CareerProof Optimization Available (+{delta}% Boost)",
                "description": f"You already have a tailored draft that increases your ATS score to {comparison.get('optimized_score')}%.",
                "action": "View Tailored Draft"
            })

        exp_known = analysis.get("experience_duration_known", False)
        res_years = analysis.get("resume_years", 0.0)
        req_years = analysis.get("required_years", 0.0)
        tenure_rep = analysis.get("tenure_report", {})

        if not exp_known:
            recs.append({
                "type": "tenure",
                "title": "Add Clear Job Dates in Experience Section",
                "description": "ATS parsers look for explicit employment date ranges (e.g., 'Jan 2021 – Present' or '2019 – 2023') to calculate your professional tenure.",
                "action": "Add Employment Dates"
            })
        else:
            # Check for explicit overqualification cap
            if tenure_rep.get("has_explicit_maximum") and tenure_rep.get("max_years") and res_years > tenure_rep.get("max_years"):
                max_y = tenure_rep.get("max_years")
                recs.append({
                    "type": "tenure_overqualified",
                    "title": f"Exceeds Stated Maximum Experience ({res_years} yrs vs {max_y} yrs max)",
                    "description": f"The position explicitly specifies up to {max_y} years of experience. Emphasize hands-on technical execution and direct contribution over senior leadership.",
                    "action": "Highlight Hands-on Work"
                })
            elif req_years > 0 and res_years < req_years:
                recs.append({
                    "type": "tenure",
                    "title": f"Tenure Deficit ({res_years} yrs vs {req_years} yrs required)",
                    "description": f"The job description seeks {req_years}+ years of experience, while {res_years} years were detected from your timeline. Ensure earlier roles or contract projects are represented.",
                    "action": "Highlight Relevant Experience"
                })

            # Check role-specific or domain penalties
            for pen in tenure_rep.get("penalties", []):
                if pen.get("code") in {"ROLE_SPECIFIC_DEFICIT", "ROLE_SPECIFIC_MISSING"}:
                    recs.append({
                        "type": "tenure_domain",
                        "title": f"Target Domain Tenure: {pen.get('reason')}",
                        "description": "Recruiters and automated screeners filter candidate tenure in specific required technologies or role titles. Add targeted project bullets.",
                        "action": "Add Domain Bullets"
                    })

        # Append multi-dimensional recommendations
        for m_rec in analysis.get("match_recommendations", []):
            if not any(r.get("title") == m_rec.get("title") for r in recs):
                recs.append(m_rec)

        return recs
