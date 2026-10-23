"""Additive catalog storage. Source snapshots survive edits/deletion of legacy resumes."""
from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class EvidenceCatalog(Base):
    __tablename__ = "evidence_catalogs"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    identity = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("evidence_catalogs.id"), nullable=False, index=True)
    # Deliberately not a FK: retained historical source after legacy deletion.
    resume_id = Column(Integer, nullable=True)
    filename = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="resume")
    sha256 = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("catalog_id", "resume_id", "sha256"),)


class CatalogClaim(Base):
    __tablename__ = "catalog_claims"
    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("evidence_catalogs.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    fingerprint = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    approval = Column(String, nullable=False, default="pending")
    verification = Column(String, nullable=False, default="extracted")
    history = Column(JSON, nullable=False, default=list)
    __table_args__ = (UniqueConstraint("catalog_id", "fingerprint"),)


class ClaimSource(Base):
    __tablename__ = "catalog_claim_sources"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("catalog_claims.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("catalog_sources.id"), nullable=False)
    quote = Column(Text, nullable=False)
    start = Column(Integer, nullable=True)
    end = Column(Integer, nullable=True)
    revision = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("claim_id", "source_id", "revision"),)


class CatalogConflict(Base):
    __tablename__ = "catalog_conflicts"
    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("evidence_catalogs.id"), nullable=False, index=True)
    fingerprint = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    claim_ids = Column(JSON, nullable=False)
    revisions = Column(JSON, nullable=False)
    question = Column(Text, nullable=False)
    benefit = Column(Text, nullable=False)
    state = Column(String, nullable=False, default="open")
    resolution = Column(JSON, nullable=True)
    __table_args__ = (UniqueConstraint("catalog_id", "fingerprint"),)


class CatalogEvent(Base):
    __tablename__ = "catalog_events"
    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("evidence_catalogs.id"), nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("catalog_claims.id"), nullable=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
