import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import SessionLocal
from app.models.schemas import User, Resume, JobDescription, OptimizedResume, ResumeBullet
from app.services.ats_checker import ATSCheckerEngine

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_ats_checker_engine_raw_text(db_session: Session):
    engine = ATSCheckerEngine()
    resume_text = """
    Jane Doe
    Senior AI Engineer with 4 years of experience building production systems.
    Skills: Python, FastAPI, Docker, PyTorch, LangChain, PostgreSQL, Kubernetes
    Experience:
    - Designed and deployed RAG pipelines using Python and LangChain.
    - Optimized Postgres vector queries reducing latency by 40%.
    - Containerized microservices using Docker and orchestrated via Kubernetes.
    Education:
    BS Computer Science, Stanford University
    """

    jd_text = """
    AI Engineer
    Acme AI
    Requirements:
    - 3+ years experience with Python and FastAPI
    - Deep knowledge of Docker, Kubernetes, and PostgreSQL
    - Hands-on experience with PyTorch and LangChain
    """

    result = engine.check_match(
        db=db_session,
        user_id="user_test",
        resume_text=resume_text,
        jd_text=jd_text,
        company="Acme AI",
        role="AI Engineer"
    )

    assert result["ats_score"] > 50.0
    assert result["match_tier"] in ["strong_match", "competitive_match", "needs_alignment"]
    assert "python" in result["matched_keywords"]
    assert "docker" in result["matched_keywords"]
    assert result["breakdown"]["keyword_match"] > 0
    assert result["breakdown"]["experience_match"] == 100.0
    assert len(result["recommendations"]) >= 1

def test_ats_checker_engine_saved_records(db_session: Session):
    engine = ATSCheckerEngine()
    opt = db_session.query(OptimizedResume).first()
    res_id = opt.resume_id if opt else 17
    j_id = opt.job_id if opt else 1
    result = engine.check_match(
        db=db_session,
        user_id="user_test",
        resume_id=res_id,
        job_id=j_id
    )

    assert "ats_score" in result
    assert result["resume_meta"]["source"] == "saved_resume"
    assert result["job_meta"]["source"] == "saved_job"
    assert "comparison" in result
    assert result["comparison"]["has_optimized_version"] is True
    assert result["comparison"]["optimization_id"] is not None

def test_ats_api_check_endpoint(db_session: Session):
    res = db_session.query(Resume).filter(Resume.user_id == "user_test").first()
    job = db_session.query(JobDescription).filter(JobDescription.user_id == "user_test").first()
    response = client.post(
        "/api/ats/check",
        json={
            "resume_id": res.id,
            "job_id": job.id
        },
        headers={"X-User-Id": "user_test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "ats_score" in data
    assert "breakdown" in data
    assert "matched_keywords" in data
    assert "missing_keywords" in data
    assert "recommendations" in data

def test_ats_api_check_raw_text():
    response = client.post(
        "/api/ats/check",
        json={
            "resume_text": "Experienced React and TypeScript engineer with 3 years building modern web applications.",
            "jd_text": "Frontend Developer with React, TypeScript, and CSS skills. 2+ years experience.",
            "company": "Tech Corp",
            "role": "Frontend Developer"
        },
        headers={"X-User-Id": "user_test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ats_score"] > 50.0
    assert "react" in data["matched_keywords"]
    assert data["job_meta"]["company"] == "Tech Corp"

def test_ats_api_validation_errors(db_session: Session):
    res = db_session.query(Resume).filter(Resume.user_id == "user_test").first()
    job = db_session.query(JobDescription).filter(JobDescription.user_id == "user_test").first()
    # Missing resume
    r1 = client.post("/api/ats/check", json={"job_id": job.id}, headers={"X-User-Id": "user_test"})
    assert r1.status_code == 422

    # Missing job
    r2 = client.post("/api/ats/check", json={"resume_id": res.id}, headers={"X-User-Id": "user_test"})
    assert r2.status_code == 422

def test_ats_catalog_endpoint():
    response = client.get("/api/ats/catalog", headers={"X-User-Id": "user_test"})
    assert response.status_code == 200
    data = response.json()
    assert "resumes" in data
    assert "jobs" in data
    assert len(data["resumes"]) >= 1
    assert len(data["jobs"]) >= 1

def test_ats_check_existing_pair_endpoint(db_session: Session):
    res = db_session.query(Resume).filter(Resume.user_id == "user_test").first()
    job = db_session.query(JobDescription).filter(JobDescription.user_id == "user_test").first()
    response = client.get(f"/api/ats/check-existing/{res.id}/{job.id}", headers={"X-User-Id": "user_test"})
    assert response.status_code == 200
    data = response.json()
    assert data["resume_meta"]["resume_id"] == res.id
    assert data["job_meta"]["job_id"] == job.id

def test_ats_upload_resume_endpoint():
    import io
    content = b"Candidate Name\nSoftware Engineer with Python and Docker skills.\nExperience:\n- Built APIs with Python.\nEducation:\nBS CS"
    response = client.post(
        "/api/ats/upload-resume",
        files={"file": ("test_upload_resume.txt", io.BytesIO(content), "text/plain")},
        data={"save_to_library": "true"},
        headers={"X-User-Id": "user_test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test_upload_resume.txt"
    assert "Python" in data["text"]
    assert data["resume_id"] is not None

def test_ats_upload_jd_endpoint():
    import io
    content = b"Tech Lead\nAcme Systems\nRequirements:\n- 5+ years experience in Python and AWS\n- Docker experience"
    response = client.post(
        "/api/ats/upload-jd",
        files={"file": ("Acme_Tech_Lead.txt", io.BytesIO(content), "text/plain")},
        data={"company": "Acme Systems", "role": "Tech Lead", "save_to_library": "true"},
        headers={"X-User-Id": "user_test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "Acme_Tech_Lead.txt"
    assert data["company"] == "Acme Systems"
    assert data["job_id"] is not None


def test_ats_checker_extracts_tenure_from_experience_date_ranges(db_session: Session):
    engine = ATSCheckerEngine()
    resume_text = """
    Jane Doe
    jane@example.com

    EXPERIENCE
    Stripe | Software Engineer | Jan 2021 – Present
    - Built payments microservices using FastAPI and PostgreSQL.
    - Scaled backend architecture.

    Shopify | Junior Developer | 2018 – 2020
    - Built merchant web tools in React and TypeScript.

    EDUCATION
    BS Computer Science, Waterloo | 2014 – 2018
    """

    jd_text = """
    Senior Backend Engineer
    Requirements:
    - 4+ years of professional backend experience
    - Strong skills in FastAPI, PostgreSQL, and Python
    """

    result = engine.check_match(
        db=db_session,
        user_id="user_test",
        resume_text=resume_text,
        jd_text=jd_text
    )

    assert result["breakdown"]["experience_duration_known"] is True
    assert result["breakdown"]["resume_years"] >= 7.0
    assert result["breakdown"]["required_years"] == 4.0
    assert result["breakdown"]["experience_match"] == 100.0

