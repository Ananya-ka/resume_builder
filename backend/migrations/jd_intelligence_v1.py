"""Versioned additive migration for JD Intelligence & Evidence Mapping.

Run: PYTHONPATH=. python -m migrations.jd_intelligence_v1
"""
from sqlalchemy import Table, Column, String, MetaData, select, inspect
from app.core.database import Base, engine
from app.models import schemas  # register users, jobs, resumes
from app.catalog import models as catalog_models  # register catalogs
from app.jd_intelligence import models as jd_models  # register new tables

VERSION = "20261023_jd_intelligence_v1"
TABLES = [
    jd_models.JobVersion,
    jd_models.JobRequirement,
    jd_models.AnalysisRun,
    jd_models.RequirementMatch
]


def upgrade(connection):
    if not inspect(connection).has_table("users"):
        raise RuntimeError("Initialize the existing application schema before running migrations.")
    versions = Table("careerproof_schema_versions", MetaData(), Column("version", String, primary_key=True))
    versions.create(connection, checkfirst=True)
    if connection.execute(select(versions.c.version).where(versions.c.version == VERSION)).first():
        return
    for model in TABLES:
        model.__table__.create(connection, checkfirst=True)
    connection.execute(versions.insert().values(version=VERSION))


if __name__ == "__main__":
    with engine.begin() as connection:
        upgrade(connection)
    print("Applied " + VERSION)
