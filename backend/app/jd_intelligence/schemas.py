"""Pydantic schemas for JD Intelligence and Evidence Mapping."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class JobCreate(BaseModel):
    role: str = Field(min_length=1, max_length=200)
    company: str = Field(default="Target Company", max_length=200)
    raw_text: str = Field(min_length=20, max_length=50000)

    @field_validator("role", "company", "raw_text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field must not be blank")
        return s


class JobRequirementOut(BaseModel):
    id: int
    requirement_key: str
    category: str
    title: str
    quote: str
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    is_mandatory: bool
    importance: str
    normalized_terms: List[str] = []
    dependencies: List[str] = []
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None


class JobVersionOut(BaseModel):
    id: int
    job_id: int
    version: int
    sha256: str
    title: str
    company: str
    raw_text: str
    parsed_data: Dict[str, Any] = {}
    requirements: List[JobRequirementOut] = []
    created_at: Optional[str] = None


class JobSummaryOut(BaseModel):
    id: int
    role: str
    company: str
    version_count: int
    latest_version: int
    requirement_count: int
    created_at: Optional[str] = None


class AnalyzeRequest(BaseModel):
    catalog_id: int
    job_id: int
    job_version_id: Optional[int] = None


class RequirementMatchOut(BaseModel):
    id: int
    requirement: JobRequirementOut
    status: str  # direct, transferable, missing, unresolved
    matched_claims: List[Dict[str, Any]] = []
    transferable_details: Optional[Dict[str, Any]] = None
    candidate_depth: Optional[str] = None
    score_rationale: str
    clarification_question: Optional[Dict[str, Any]] = None


class AnalysisRunOut(BaseModel):
    id: int
    catalog_id: int
    catalog_revision: int
    job_version_id: int
    status: str
    summary: Dict[str, Any]
    matches: List[RequirementMatchOut] = []
    created_at: Optional[str] = None
