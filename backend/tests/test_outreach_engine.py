import pytest
from app.services.outreach_engine import OutreachEngine, CandidateMode
from app.services.objection_engine import ObjectionEngine
from app.services.interview_defense import InterviewDefenseEngine


def test_outreach_engine_advance_generation():
    engine = OutreachEngine()
    bullets = [
        {
            "original_id": 1,
            "optimized_bullet": "Architected distributed Redis cluster reducing p99 latency by 40% across 10k rps.",
            "company": "Stripe Clone",
            "role": "Senior Engineer",
            "section": "Experience",
            "included": True,
            "verified": True
        },
        {
            "original_id": 2,
            "optimized_bullet": "Engineered FastAPI microservices with PostgreSQL connection pooling handling 5M daily queries.",
            "company": "Payment Gateway",
            "role": "Backend Engineer",
            "section": "Experience",
            "included": True,
            "verified": True
        }
    ]
    candidate_profile = {"name": "Alex Chen", "skills": ["python", "redis", "fastapi"]}
    jd = {"company": "Acme Corp", "role": "Senior Backend Architect", "required_skills": ["redis", "fastapi"]}
    
    pack = engine.generate_application_pack(
        bullets, candidate_profile, jd, mode="advance"
    )

    assert pack["mode"] == "advance"
    assert pack["claims_referenced_count"] == 2

    # Cold InMail
    inmail = pack["cold_inmail"]
    assert "Acme Corp" in inmail["subject"]
    assert "proven systems ownership" in inmail["subject"]
    assert "[Claim #1]" in inmail["body"]
    assert inmail["character_count"] > 100
    assert inmail["word_count"] < 150

    # Cover Letter
    cover = pack["cover_letter"]
    assert "Dear Acme Corp Hiring Team" in cover["body"]
    assert "[Claim #1]" in cover["body"]
    assert "[Claim #2]" in cover["body"]
    assert cover["word_count"] > 100

    # Screening Answers
    answers = pack["screening_answers"]
    assert len(answers) == 3
    assert "[Claim #1]" in answers[0]["answer"]
    assert "truth_boundary_note" in answers[0]


def test_outreach_engine_launch_mode():
    engine = OutreachEngine()
    bullets = [
        {
            "original_id": 10,
            "optimized_bullet": "Developed full-stack AI document search with LangChain, ChromaDB, and FastAPI, achieving 92% retrieval precision.",
            "company": "Portfolio Project",
            "role": "Creator",
            "section": "Projects",
            "included": True,
            "verified": True
        }
    ]
    candidate_profile = {"name": "Jordan Lee", "skills": ["python", "langchain"]}
    jd = {"company": "AI Labs", "role": "Junior AI Engineer", "required_skills": ["langchain"]}
    
    pack = engine.generate_application_pack(
        bullets, candidate_profile, jd, mode="launch"
    )

    assert pack["mode"] == "launch"
    inmail = pack["cold_inmail"]
    assert "verified technical proof" in inmail["subject"]
    assert "tutorial clones" in inmail["body"]
    assert "[Claim #1]" in inmail["body"]


def test_objection_engine_mode_differentiation():
    obj_engine = ObjectionEngine()
    profile = {"skills": ["python"], "education": []}
    reconstructed = {
        "profile_summary": "",
        "skills": ["python"],
        "experience": [],
        "projects": [
            {"name": "Chatbot", "bullets": ["Built simple chatbot using Flask"]}
        ],
        "education": []
    }
    jd = {
        "raw_text": "Looking for Software Engineer with 2 years experience in Python and FastAPI",
        "company": "Tech Startup",
        "role": "Software Engineer",
        "experience_years": 2.0,
        "required_skills": ["python", "fastapi"]
    }

    # Analyze under launch mode
    launch_res = obj_engine.analyze(profile, reconstructed, jd, mode="launch")
    assert launch_res["mode"] == "launch"
    launch_hypotheses = [o["hypothesis"] for o in launch_res["objections"]]
    assert any("boilerplate clones" in h or "tutorial" in h for h in launch_hypotheses)
    assert any("agile" in h or "mentoring overhead" in h or "SDLC" in h for h in launch_hypotheses)

    # Analyze under advance mode
    advance_res = obj_engine.analyze(profile, reconstructed, jd, mode="advance")
    assert advance_res["mode"] == "advance"


def test_interview_defense_mode_deliverables():
    defense_engine = InterviewDefenseEngine()
    gap_classifications = [
        {
            "term": "kubernetes",
            "bucket": "true_deficit",
            "is_required": True,
            "suggested_proof_tier": "implementation"
        }
    ]
    jd = {"company": "Scale Co", "role": "Cloud Engineer"}

    # Launch mode proof specs should include live deployment requirement
    launch_specs = defense_engine.generate_proof_specs(gap_classifications, jd, mode="launch")
    assert len(launch_specs) == 1
    assert any("Live deployed URL" in d for d in launch_specs[0]["deliverables"])

    # Advance mode proof specs focus on core production benchmark
    advance_specs = defense_engine.generate_proof_specs(gap_classifications, jd, mode="advance")
    assert len(advance_specs) == 1
    assert not any("Live deployed URL" in d for d in advance_specs[0]["deliverables"])
