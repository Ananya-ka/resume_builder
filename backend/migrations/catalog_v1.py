"""Versioned additive migration. Run: PYTHONPATH=. python -m migrations.catalog_v1.

Existing databases: users table must already exist. Fresh development databases
also receive these tables via init_db metadata. No legacy data is rewritten.
Rollback is code/read-path rollback; do not drop retained evidence/approval data.
"""
from sqlalchemy import Table, Column, String, MetaData, select, inspect
from app.core.database import Base, engine
from app.models import schemas  # register legacy FK targets
from app.catalog import models  # register new tables

VERSION = "20261023_catalog_v1"
TABLES = [models.EvidenceCatalog, models.CatalogSource, models.CatalogClaim,
          models.ClaimSource, models.CatalogConflict, models.CatalogEvent]


def upgrade(connection):
    if not inspect(connection).has_table("users"):
        raise RuntimeError("Initialize the existing application schema before catalog migration")
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
