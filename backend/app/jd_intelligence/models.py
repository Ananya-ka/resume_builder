"""JD Intelligence & Evidence Mapping Models.

Provides immutable versioned job descriptions, quoted requirements with exact offsets,
reproducible analysis runs against Evidence Catalogs, and bidirectional evidence matches.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, JSON, ForeignKey,
    UniqueConstraint, DateTime
)
from sqlalchemy.sql import func
from app.core.database import Base


class JobVersion(Base):
    """Immutable parsed version of a job description with source text and hash."""
    __tablename__ = "job_versions"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    sha256 = Column(String, nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("job_id", "version", name="uq_job_version"),
        UniqueConstraint("job_id", "sha256", name="uq_job_sha256"),
    )


class JobRequirement(Base):
    """Atomic requirement extracted from a job description with exact source quotation."""
    __tablename__ = "job_requirements"

    id = Column(Integer, primary_key=True)
    job_version_id = Column(Integer, ForeignKey("job_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_key = Column(String, nullable=False)
    category = Column(String, nullable=False)  # mandatory_skill, preferred_skill, responsibility, education, experience, seniority, domain, constraint
    title = Column(String, nullable=False)
    quote = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    is_mandatory = Column(Boolean, nullable=False, default=True)
    importance = Column(String, nullable=False, default="high")  # critical, high, medium, preferred
    normalized_terms = Column(JSON, nullable=False, default=list)  # canonical tech/skill terms
    dependencies = Column(JSON, nullable=False, default=list)  # linked responsibilities or skills
    is_ambiguous = Column(Boolean, nullable=False, default=False)
    ambiguity_reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("job_version_id", "requirement_key", name="uq_job_req_key"),
    )


class AnalysisRun(Base):
    """Snapshot analysis linking an EvidenceCatalog revision to a JobVersion."""
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("evidence_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_revision = Column(Integer, nullable=False)
    job_version_id = Column(Integer, ForeignKey("job_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="completed")  # completed, failed
    summary = Column(JSON, nullable=False, default=dict)  # counts & breakdown: direct, transferable, missing, unresolved
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RequirementMatch(Base):
    """Bidirectional match result between a JobRequirement and CatalogClaim evidence."""
    __tablename__ = "requirement_matches"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("job_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)  # direct, transferable, missing, unresolved
    matched_claim_ids = Column(JSON, nullable=False, default=list)
    transferable_details = Column(JSON, nullable=True)
    candidate_depth = Column(String, nullable=True)
    score_rationale = Column(Text, nullable=False)
    clarification_question = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("analysis_run_id", "requirement_id", name="uq_run_requirement"),
    )
