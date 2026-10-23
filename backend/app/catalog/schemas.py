from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateCatalog(StrictInput):
    name: str = Field(min_length=1, max_length=150)


class ImportResumes(StrictInput):
    resume_ids: list[int] = Field(min_length=1, max_length=3)
    revision: int = Field(ge=1)
    same_candidate_confirmed: bool

    @field_validator("resume_ids")
    @classmethod
    def unique(cls, value):
        if len(value) != len(set(value)) or any(v < 1 for v in value):
            raise ValueError("Select distinct positive resume IDs")
        return value


class ClaimData(StrictInput):
    text: str = Field(min_length=1, max_length=6000)
    association: str = Field(min_length=1, max_length=300)
    role: str = Field(default="", max_length=300)
    kind: Literal["experience", "project", "skill", "dates", "education", "achievement", "certification"]
    technologies: list[str] = Field(default_factory=list, max_length=100)
    metrics: list[str] = Field(default_factory=list, max_length=50)
    dates: str = Field(default="", max_length=200)
    contribution: str = Field(default="", max_length=3000)
    temporal_status: Literal["unknown", "planned", "in_progress", "completed"] = "unknown"
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("technologies", "metrics", "tags")
    @classmethod
    def bounded_strings(cls, values):
        if any(not v.strip() or len(v) > 200 for v in values):
            raise ValueError("List values must be nonempty and at most 200 characters")
        return list(dict.fromkeys(v.strip() for v in values))


class ClaimAction(StrictInput):
    catalog_revision: int = Field(ge=1)
    claim_revision: int = Field(ge=1)
    action: Literal["approve", "reject", "edit", "organize"]
    data: ClaimData | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(min_length=1, max_length=1000)
    confirm_accuracy: bool = False

    @field_validator("tags")
    @classmethod
    def tags_valid(cls, value):
        return ClaimData.bounded_strings(value)


class ResolveConflict(StrictInput):
    catalog_revision: int = Field(ge=1)
    choice: Literal["keep_both", "select"]
    selected_claim_id: int | None = None
    reason: str = Field(min_length=1, max_length=1000)


class ArtifactInput(StrictInput):
    catalog_revision: int = Field(ge=1)
    claim_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=50000)
    quote: str = Field(min_length=1, max_length=6000)
    attest_support: bool


class SourceOut(BaseModel):
    id: int
    filename: str
    kind: str
    resume_id: int | None
    sha256: str
    quote: str
    start: int | None
    end: int | None
    revision: int


class ClaimOut(BaseModel):
    id: int
    revision: int
    data: ClaimData
    approval: str
    verification: str
    confidence_indicator: str
    conflict_ids: list[int]
    sources: list[SourceOut]
    history: list[dict]


class ConflictOut(BaseModel):
    id: int
    kind: str
    claim_ids: list[int]
    question: str
    benefit: str
    state: str
    resolution: dict | None


class CatalogSummary(BaseModel):
    id: int
    name: str
    revision: int


class CatalogOut(CatalogSummary):
    claims: list[ClaimOut]
    conflicts: list[ConflictOut]
    events: list[dict]
