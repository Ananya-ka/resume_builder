import pytest
from app.services.objection_engine import ObjectionEngine, GapBucket, EvidenceConfidence, ProofTier


def test_objection_engine_hard_constraints():
    engine = ObjectionEngine()
    candidate_profile = {"skills": ["Python", "Docker"], "education": []}
    reconstructed_resume = {
        "experience": [{"company": "Acme", "role": "Dev", "bullets": ["Built Python APIs."]}],
        "projects": [],
        "skills": ["Python", "Docker"]
    }
    jd = {
        "raw_text": "Must possess active Top Secret clearance and US citizenship. Master's degree preferred.",
        "required_skills": ["python"],
        "preferred_skills": [],
        "experience_years": 2.0
    }

    result = engine.analyze(candidate_profile, reconstructed_resume, jd)
    hc_types = [h["type"] for h in result["hard_constraints"]]
    assert any("Clearance" in t for t in hc_types)
    assert any(o["persona"] == "Recruiter Screen" for o in result["objections"])


def test_objection_engine_4_bucket_gaps():
    engine = ObjectionEngine()
    candidate_profile = {
        "skills": ["Python", "RabbitMQ", "PostgreSQL"],
        "education": [{"school": "State Univ", "degree": "BS CS"}]
    }
    reconstructed_resume = {
        "experience": [
            {
                "company": "TechCorp",
                "role": "Backend Engineer",
                "bullets": ["Designed message queues using RabbitMQ handling 5,000 rps, reducing latency by 40%."]
            }
        ],
        "projects": [],
        "skills": ["Python", "RabbitMQ"]
    }
    catalog_evidence = [
        {"data": {"content": "Managed PostgreSQL query optimizations and indexing strategies.", "company": "TechCorp", "role": "Engineer"}}
    ]
    jd = {
        "raw_text": "Looking for an engineer with Kafka, PostgreSQL, and Rust.",
        "required_skills": ["kafka", "postgresql", "rust"],
        "preferred_skills": [],
        "experience_years": 1.0
    }

    result = engine.analyze(candidate_profile, reconstructed_resume, jd, catalog_evidence)
    gap_map = {g["term"]: g for g in result["gap_classifications"]}

    # Kafka should be Transferable (Bucket B) because RabbitMQ is in resume
    assert gap_map["kafka"]["bucket"] == GapBucket.TRANSFERABLE.value
    assert gap_map["kafka"]["transferable_from"] == "rabbitmq"

    # PostgreSQL should be Unexpressed (Bucket A) because it's in catalog/profile but not on resume
    assert gap_map["postgresql"]["bucket"] == GapBucket.UNEXPRESSED.value

    # Rust should be True Deficit (Bucket C) because it's nowhere
    assert gap_map["rust"]["bucket"] == GapBucket.TRUE_DEFICIT.value
    assert gap_map["rust"]["suggested_proof_tier"] == ProofTier.IMPLEMENTATION.value


def test_objection_engine_evidence_confidence_tiers():
    engine = ObjectionEngine()
    bullets = [
        "Reduced p99 query latency from 800ms to 240ms by 45% using Redis caching.",
        "Open source contributions at github.com/myrepo with full test suite."
    ]
    
    tier, score = engine._determine_confidence("redis", True, True, bullets, [])
    assert tier == EvidenceConfidence.MEASUREMENT_BACKED
    assert score >= 90.0

    tier2, score2 = engine._determine_confidence("open source", True, True, bullets, [])
    assert tier2 == EvidenceConfidence.ARTIFACT_BACKED
    assert score2 >= 75.0


def test_objection_engine_three_personas():
    engine = ObjectionEngine()
    candidate_profile = {"skills": ["Java"], "education": []}
    reconstructed_resume = {
        "experience": [
            {
                "company": "Startup",
                "role": "Junior Dev",
                "bullets": [
                    "Assisted with backend codebase maintenance.",
                    "Participated in sprint planning meetings."
                ]
            }
        ],
        "projects": [],
        "skills": ["Java"]
    }
    jd = {
        "raw_text": "Senior Distributed Engineer required. Must have 5+ years experience.",
        "required_skills": ["java", "kubernetes"],
        "preferred_skills": [],
        "experience_years": 5.0
    }

    result = engine.analyze(candidate_profile, reconstructed_resume, jd)
    personas = {o["persona"] for o in result["objections"]}
    assert "Recruiter Screen" in personas
    assert "Hiring Manager" in personas
    assert "Technical Bar-Raiser" in personas
