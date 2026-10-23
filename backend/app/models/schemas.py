from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True) # Clerk user ID
    email = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("JobDescription", back_populates="user", cascade="all, delete-orphan")
    tracker_items = relationship("ApplicationTracker", back_populates="user", cascade="all, delete-orphan")

class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    parsed_raw = Column(JSON, nullable=True) # Full structured parse of the resume
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="resumes")
    bullets = relationship("ResumeBullet", back_populates="resume", cascade="all, delete-orphan")
    optimizations = relationship("OptimizedResume", back_populates="resume", cascade="all, delete-orphan")

class ResumeBullet(Base):
    __tablename__ = "resume_bullets"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    section = Column(String, nullable=False) # e.g. "Experience", "Projects", "Achievements"
    bullet = Column(Text, nullable=False)
    technologies = Column(JSON, nullable=True) # list of strings
    keywords = Column(JSON, nullable=True) # list of strings
    metrics = Column(JSON, nullable=True) # list of strings
    domain = Column(String, nullable=True)
    embedding = Column(Vector(3072), nullable=True) # OpenAI text-embedding-3-large

    resume = relationship("Resume", back_populates="bullets")

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=False) # 'Project', 'Bullet', 'Achievement', 'Certification', 'Company', 'Education'
    content = Column(Text, nullable=False)
    technologies = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    embedding = Column(Vector(3072), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    department = Column(String, nullable=True)
    experience_years = Column(Float, nullable=True)
    responsibilities = Column(JSON, nullable=True)
    required_skills = Column(JSON, nullable=True)
    preferred_skills = Column(JSON, nullable=True)
    cloud = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    frameworks = Column(JSON, nullable=True)
    databases = Column(JSON, nullable=True)
    soft_skills = Column(JSON, nullable=True)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    seniority = Column(String, nullable=True)
    ats_keywords = Column(JSON, nullable=True)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="jobs")
    optimizations = relationship("OptimizedResume", back_populates="job", cascade="all, delete-orphan")

class OptimizedResume(Base):
    __tablename__ = "optimized_resumes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    optimized_content = Column(JSON, nullable=False) # JSON array of edited bullets
    ats_score = Column(Float, nullable=False)
    keyword_match = Column(Float, nullable=False)
    skill_match = Column(Float, nullable=False)
    experience_match = Column(Float, nullable=False)
    gap_report = Column(JSON, nullable=True)
    recruiter_report = Column(JSON, nullable=True)
    cover_letter = Column(Text, nullable=True)
    referral_messages = Column(JSON, nullable=True)
    interview_questions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("JobDescription", back_populates="optimizations")
    resume = relationship("Resume", back_populates="optimizations")

class ApplicationTracker(Base):
    __tablename__ = "application_tracker"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, default="Applied") # 'Applied', 'Referral', 'OA', 'Interview', 'Rejected', 'Offer'
    salary = Column(Float, nullable=True)
    recruiter_name = Column(String, nullable=True)
    recruiter_contact = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    optimization_id = Column(Integer, ForeignKey("optimized_resumes.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="tracker_items")


class CandidateEvidence(Base):
    __tablename__ = "candidate_evidence"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    data = Column(JSON, nullable=False)
    source_refs = Column(JSON, nullable=False, default=list)
    history = Column(JSON, nullable=False, default=list)


class ProfileDecision(Base):
    __tablename__ = "profile_decisions"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    candidate_key = Column(String, nullable=False, index=True)
    conflict_key = Column(String, nullable=False)
    choice = Column(JSON, nullable=False)


class DiscoverySession(Base):
    __tablename__ = "discovery_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    resume_ids = Column(JSON, nullable=False)
    evidence_ids = Column(JSON, nullable=False)
    questions = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="discovering")


class EvidenceDraft(Base):
    """Immutable input snapshots; corrections create new optimizations, not edits."""
    __tablename__ = "evidence_drafts"
    id = Column(Integer, primary_key=True)
    optimization_id = Column(Integer, ForeignKey("optimized_resumes.id"), nullable=False, unique=True)
    session_id = Column(Integer, ForeignKey("discovery_sessions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="queued")
    evidence_snapshot = Column(JSON, nullable=False)
    profile_snapshot = Column(JSON, nullable=False, default=dict)
    stale_evidence_ids = Column(JSON, nullable=False, default=list)
    submitted = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
