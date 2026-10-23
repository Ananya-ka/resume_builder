from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

class UserBase(BaseModel):
    id: str
    email: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserOut(UserBase):
    created_at: datetime
    class Config:
        from_attributes = True

class ResumeBulletBase(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    section: str
    bullet: str
    technologies: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    metrics: Optional[List[str]] = []
    domain: Optional[str] = None

class ResumeBulletOut(ResumeBulletBase):
    id: int
    resume_id: int
    class Config:
        from_attributes = True

class ResumeOut(BaseModel):
    id: int
    user_id: str
    name: str
    parsed_raw: Optional[Dict[str, Any]] = None
    created_at: datetime
    bullets: List[ResumeBulletOut] = []

    class Config:
        from_attributes = True

class KnowledgeBaseIn(BaseModel):
    category: str # 'Project', 'Bullet', 'Achievement', 'Certification', 'Company', 'Education'
    content: str
    technologies: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    metrics: Optional[List[str]] = []

class KnowledgeBaseOut(KnowledgeBaseIn):
    id: int
    user_id: str
    created_at: datetime
    class Config:
        from_attributes = True

class JobDescriptionIn(BaseModel):
    company: str
    role: str
    raw_text: str
    department: Optional[str] = None

class JobDescriptionOut(BaseModel):
    id: int
    user_id: str
    company: str
    role: str
    department: Optional[str] = None
    experience_years: Optional[float] = None
    responsibilities: Optional[List[str]] = []
    required_skills: Optional[List[str]] = []
    preferred_skills: Optional[List[str]] = []
    cloud: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    frameworks: Optional[List[str]] = []
    databases: Optional[List[str]] = []
    soft_skills: Optional[List[str]] = []
    domain: Optional[str] = None
    industry: Optional[str] = None
    seniority: Optional[str] = None
    ats_keywords: Optional[List[str]] = []
    created_at: datetime
    class Config:
        from_attributes = True

class OptimizeRequest(BaseModel):
    resume_id: int
    job_id: int
    discovery_session_id: Optional[int] = None

class OptimizedResumeOut(BaseModel):
    id: int
    job_id: int
    resume_id: int
    optimized_content: List[Dict[str, Any]]
    ats_score: float
    keyword_match: float
    skill_match: float
    experience_match: float
    gap_report: Optional[Dict[str, Any]] = None
    job: Optional[JobDescriptionOut] = None
    recruiter_report: Optional[Dict[str, Any]] = None
    cover_letter: Optional[str] = None
    referral_messages: Optional[Dict[str, Any]] = None
    interview_questions: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ApplicationTrackerIn(BaseModel):
    company: str
    role: str
    status: str # 'Applied', 'Referral', 'OA', 'Interview', 'Rejected', 'Offer'
    salary: Optional[float] = None
    recruiter_name: Optional[str] = None
    recruiter_contact: Optional[str] = None
    notes: Optional[str] = None
    optimization_id: Optional[int] = None

class ApplicationTrackerOut(ApplicationTrackerIn):
    id: int
    user_id: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ExportPdfRequest(BaseModel):
    template_choice: str = "default" # "default" or "custom"
    custom_template: Optional[str] = None
    page_policy: Literal["ask", "keep", "one_page"] = "ask"

class DefaultTemplateOut(BaseModel):
    template: str
