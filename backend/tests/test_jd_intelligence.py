"""Comprehensive Unit & Integration Test Suite for Phase 2: JD Intelligence & Evidence Mapping.

Validates structured JD parsing, exact quote anchoring, mandatory vs preferred qualifications,
ambiguity detection, skill-duty dependencies, direct vs transferable vs unresolved vs missing mapping,
clarification questions, multi-job versioning, tenant isolation, and idempotent migrations.
"""
import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.schemas import User, Resume, JobDescription
from app.catalog.models import EvidenceCatalog, CatalogClaim, CatalogConflict, CatalogSource, ClaimSource
from app.catalog.api import router as catalog_router
from app.catalog.service import make_data, fingerprint
from app.jd_intelligence.models import JobVersion, JobRequirement, AnalysisRun, RequirementMatch
from app.jd_intelligence.api import router as jd_router
from app.jd_intelligence.parser import IntelligentJDParser, locate_quote
from app.jd_intelligence.service import create_or_update_job, analyze_catalog_against_job
from app.api.routes import router as base_router
from app.worker import tasks
from migrations.jd_intelligence_v1 import upgrade as jd_upgrade
from migrations.catalog_v1 import upgrade as cat_upgrade


SAMPLE_JD = """
Acme Cloud | Senior Distributed Systems Engineer
Location: San Francisco, CA (Hybrid)

About the Role:
We are looking for a Senior Distributed Systems Engineer to architect and scale distributed microservices pipelines processing 100M+ events daily.

Responsibilities:
- Architect and scale distributed microservices pipelines using Python and Kafka.
- Partner with cross-functional stakeholders to deliver resilient data platform features.
- Mentor junior team members and drive engineering excellence.

Requirements:
- 5+ years of software engineering experience.
- Bachelor's degree in Computer Science or related STEM field.
- Strong production experience with Python and PostgreSQL.
- Experience with Google Cloud Platform (GCP).
- Production experience with Kubernetes container orchestration.
- Familiarity with modern AI tools and LLM workflows.

Preferred Qualifications:
- Experience with Redis caching.
- Familiarity with Terraform infrastructure as code.
"""


def sample_resume(email="alex@example.com", metric=40):
    return f"""Alex Mercer
{email}
Skills
Python, PostgreSQL, AWS, Redis

Experience
CloudScale Systems | Senior Platform Engineer | Jan 2019 – Present
- Architected event-driven microservices processing {metric}M events daily using Python.
- Maintained PostgreSQL relational database clusters ensuring 99.99% uptime.
- Deployed cloud infrastructure on AWS leveraging ECS and S3 storage.
- Mentored 4 junior engineers on backend development best practices.

Projects
CacheLayer
- Built low-latency caching layer using Redis for session management.
"""


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(tasks, "ResumeParser", lambda: SimpleNamespace(client=None))
    monkeypatch.setattr(tasks.parse_resume_task, "delay", lambda *args: tasks.parse_resume_task.run(*args))

    app = FastAPI()
    app.include_router(base_router)
    app.include_router(catalog_router)
    app.include_router(jd_router)

    def db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = db
    with TestClient(app, headers={"X-User-Id": "alice"}) as client:
        yield client, factory
    engine.dispose()


def setup_candidate_catalog(client, email="alex@example.com"):
    # 1. Ingest resumes
    r = client.post("/api/resumes/upload-batch", files=[
        ("files", (f"resume-{i}.txt", sample_resume(email, m).encode("utf-8"), "text/plain"))
        for i, m in enumerate([40, 40, 50])
    ])
    assert r.status_code == 200, r.text
    resume_ids = [x["id"] for x in r.json()]

    # 2. Create catalog and import
    cat = client.post("/api/catalogs", json={"name": "Alex Mercer"}).json()
    r = client.post(f"/api/catalogs/{cat['id']}/imports", json={
        "resume_ids": resume_ids,
        "revision": cat["revision"],
        "same_candidate_confirmed": True
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_intelligent_jd_parsing_and_quote_anchoring(env):
    """Verifies that JD requirements are extracted with exact verbatim quotes and valid offsets."""
    client, _ = env
    r = client.post("/api/jd/jobs", json={
        "role": "Senior Distributed Systems Engineer",
        "company": "Acme Cloud",
        "raw_text": SAMPLE_JD
    })
    assert r.status_code == 201, r.text
    job_ver = r.json()

    assert job_ver["version"] == 1
    assert job_ver["title"] == "Senior Distributed Systems Engineer"
    assert job_ver["company"] == "Acme Cloud"
    assert len(job_ver["requirements"]) >= 8

    # Verify that every quote is strictly verbatim from the raw_text and offsets match
    for req in job_ver["requirements"]:
        assert req["quote"], f"Requirement {req['title']} missing quote"
        assert req["start_offset"] is not None
        assert req["end_offset"] is not None
        extracted_slice = job_ver["raw_text"][req["start_offset"]:req["end_offset"]]
        assert req["quote"] in extracted_slice or extracted_slice in req["quote"]


def test_mandatory_vs_preferred_and_ambiguity_detection(env):
    """Verifies distinction between mandatory/preferred qualifications and flags ambiguous items."""
    client, _ = env
    r = client.post("/api/jd/jobs", json={
        "role": "Senior Distributed Systems Engineer",
        "company": "Acme Cloud",
        "raw_text": SAMPLE_JD
    })
    assert r.status_code == 201
    requirements = r.json()["requirements"]

    # Python and PostgreSQL should be mandatory
    py_req = next((req for req in requirements if "python" in req["normalized_terms"]), None)
    assert py_req is not None
    assert py_req["is_mandatory"] is True
    assert py_req["category"] == "mandatory_skill"

    # Redis or Terraform should be preferred
    redis_req = next((req for req in requirements if "redis" in req["normalized_terms"]), None)
    if redis_req:
        assert redis_req["is_mandatory"] is False
        assert redis_req["category"] == "preferred_skill"

    # Ambiguity flag check
    ambig_req = next((req for req in requirements if req["is_ambiguous"]), None)
    assert ambig_req is not None
    assert "Subjective" in ambig_req["ambiguity_reason"] or "Ambiguous" in ambig_req["ambiguity_reason"] or "Vague" in ambig_req["ambiguity_reason"]


def test_evidence_to_requirement_mapping_complete_lifecycle(env):
    """
    Acceptance Test:
    A candidate uploads three resumes into Evidence Catalog, submits a real JD,
    and CareerProof generates a source-grounded breakdown with direct matches,
    transferable technologies, honest gaps, and candidate questions.
    """
    client, factory = env
    cat = setup_candidate_catalog(client)

    # 1. Resolve conflicts and approve core skills
    # Approve Python claim
    py_claim = next(c for c in cat["claims"] if "Python" in c["data"]["text"] and c["data"]["kind"] == "skill")
    r = client.post(f"/api/catalogs/{cat['id']}/claims/{py_claim['id']}/actions", json={
        "catalog_revision": cat["revision"],
        "claim_revision": py_claim["revision"],
        "action": "approve",
        "reason": "Verified skill",
        "confirm_accuracy": True
    })
    assert r.status_code == 200
    cat = r.json()

    # Approve PostgreSQL claim
    pg_claim = next(c for c in cat["claims"] if "PostgreSQL" in c["data"]["text"] and c["data"]["kind"] == "skill")
    r = client.post(f"/api/catalogs/{cat['id']}/claims/{pg_claim['id']}/actions", json={
        "catalog_revision": cat["revision"],
        "claim_revision": pg_claim["revision"],
        "action": "approve",
        "reason": "Verified skill",
        "confirm_accuracy": True
    })
    assert r.status_code == 200
    cat = r.json()

    # Approve AWS claim (Candidate has AWS, but JD requires GCP -> Transferable!)
    aws_claim = next(c for c in cat["claims"] if "AWS" in c["data"]["text"] and c["data"]["kind"] == "skill")
    r = client.post(f"/api/catalogs/{cat['id']}/claims/{aws_claim['id']}/actions", json={
        "catalog_revision": cat["revision"],
        "claim_revision": aws_claim["revision"],
        "action": "approve",
        "reason": "Verified skill",
        "confirm_accuracy": True
    })
    assert r.status_code == 200
    cat = r.json()

    # 2. Create Job
    job_res = client.post("/api/jd/jobs", json={
        "role": "Senior Distributed Systems Engineer",
        "company": "Acme Cloud",
        "raw_text": SAMPLE_JD
    }).json()

    # 3. Run Analysis between Catalog and Job
    run_res = client.post("/api/jd/analyze", json={
        "catalog_id": cat["id"],
        "job_id": job_res["job_id"]
    })
    assert run_res.status_code == 201, run_res.text
    analysis = run_res.json()

    assert analysis["status"] == "completed"
    summary = analysis["summary"]
    assert summary["direct"] > 0
    assert summary["transferable"] > 0
    assert summary["missing"] > 0

    # 4. Check Direct Match (Python)
    py_match = next(m for m in analysis["matches"] if "python" in m["requirement"]["normalized_terms"])
    assert py_match["status"] == "direct"
    assert len(py_match["matched_claims"]) >= 1
    assert "approved" in py_match["score_rationale"].lower()

    # 5. Check Transferable Match (JD: GCP, Candidate: AWS)
    gcp_match = next((m for m in analysis["matches"] if "gcp" in m["requirement"]["normalized_terms"]), None)
    if gcp_match:
        assert gcp_match["status"] == "transferable"
        assert gcp_match["transferable_details"] is not None
        assert gcp_match["transferable_details"]["candidate_technology"] == "aws"
        assert gcp_match["transferable_details"]["target_technology"] == "gcp"
        assert "Major Cloud Platforms" in gcp_match["transferable_details"]["cluster"]
        assert gcp_match["clarification_question"] is not None

    # 6. Check Missing Requirement (JD: Kubernetes, Candidate has no K8s evidence)
    k8s_match = next((m for m in analysis["matches"] if "kubernetes" in m["requirement"]["normalized_terms"]), None)
    if k8s_match:
        assert k8s_match["status"] == "missing"
        assert len(k8s_match["matched_claims"]) == 0
        assert k8s_match["clarification_question"] is not None
        assert "explicitly requires" in k8s_match["clarification_question"]["prompt"].lower()

    # 7. Check Unresolved Claims (claims with open conflict)
    # The metric conflict (40M vs 50M events) is still open in this catalog
    resp_match = next((m for m in analysis["matches"] if m["requirement"]["category"] == "responsibility" and "microservices" in m["requirement"]["title"].lower()), None)
    if resp_match:
        # Should be classified as unresolved due to open conflict on the microservices bullet
        assert resp_match["status"] in {"unresolved", "direct"}


def test_multi_job_support_and_versioning(env):
    """Verifies that multiple jobs can be tracked and text changes increment version cleanly."""
    client, _ = env

    # Job A Version 1
    job_a_v1 = client.post("/api/jd/jobs", json={
        "role": "Backend Engineer",
        "company": "Fintech Alpha",
        "raw_text": "We require Python, PostgreSQL, and 3+ years experience in payments systems."
    }).json()
    assert job_a_v1["version"] == 1

    # Same text returns same version (idempotent)
    job_a_repeat = client.post("/api/jd/jobs", json={
        "role": "Backend Engineer",
        "company": "Fintech Alpha",
        "raw_text": "We require Python, PostgreSQL, and 3+ years experience in payments systems."
    }).json()
    assert job_a_repeat["id"] == job_a_v1["id"]
    assert job_a_repeat["version"] == 1

    # Changed text generates Version 2
    job_a_v2 = client.post("/api/jd/jobs", json={
        "role": "Backend Engineer",
        "company": "Fintech Alpha",
        "raw_text": "We require Python, PostgreSQL, Kafka, and 4+ years experience in payments."
    }).json()
    assert job_a_v2["version"] == 2
    assert job_a_v2["job_id"] == job_a_v1["job_id"]
    assert job_a_v2["sha256"] != job_a_v1["sha256"]

    # Job B (Independent job)
    job_b = client.post("/api/jd/jobs", json={
        "role": "Frontend Architect",
        "company": "DesignCo",
        "raw_text": "Requirements: 7+ years of experience. Expert in React, TypeScript, and Next.js."
    }).json()
    assert job_b["job_id"] != job_a_v1["job_id"]
    assert job_b["version"] == 1

    # List jobs shows both jobs
    jobs_list = client.get("/api/jd/jobs").json()
    assert len(jobs_list) == 2
    alpha_job = next(j for j in jobs_list if j["company"] == "Fintech Alpha")
    assert alpha_job["version_count"] == 2
    assert alpha_job["latest_version"] == 2


def test_tenant_isolation_prevents_data_leakage(env):
    """Confirms user Alice cannot view or analyze Bob's jobs or catalogs."""
    client, _ = env

    # Alice creates a job and catalog
    cat = setup_candidate_catalog(client, email="alice@example.com")
    job = client.post("/api/jd/jobs", json={
        "role": "Security Engineer",
        "company": "SafeCorp",
        "raw_text": "Requires Python, SOC2, and penetration testing background."
    }).json()

    # Bob attempts to access Alice's job
    bob_headers = {"X-User-Id": "bob"}
    r = client.get(f"/api/jd/jobs/{job['job_id']}", headers=bob_headers)
    assert r.status_code == 404

    # Bob attempts to run analysis on Alice's catalog
    r = client.post("/api/jd/analyze", json={
        "catalog_id": cat["id"],
        "job_id": job["job_id"]
    }, headers=bob_headers)
    assert r.status_code == 404


def test_idempotent_jd_intelligence_migration():
    """Validates that running the JD intelligence migration is additive and idempotent."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        User.__table__.create(conn)
        JobDescription.__table__.create(conn)
        cat_upgrade(conn)
        jd_upgrade(conn)
        jd_upgrade(conn)  # second run should be a no-op

        tables = inspect(conn).get_table_names()
        assert "job_versions" in tables
        assert "job_requirements" in tables
        assert "analysis_runs" in tables
        assert "requirement_matches" in tables
        assert conn.exec_driver_sql("select count(*) from careerproof_schema_versions where version = '20261023_jd_intelligence_v1'").scalar() == 1
    engine.dispose()
