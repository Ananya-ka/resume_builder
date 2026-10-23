import pytest
from app.services.ats_matcher import (
    ATSMatchingEngine,
    ATSMatcherConfig,
    EvidenceMatch,
    HardEligibilityGate
)
from app.services.rule_engine import RuleEngine

def test_semantic_synonym_matching():
    """Validates that technical synonyms, canonical forms, and aliases match seamlessly."""
    engine = ATSMatchingEngine()

    resume_data = {
        "skills": ["k8s", "Postgres", "AWS", "Golang"],
        "experience": [
            {
                "company": "CloudCorp",
                "role": "Cloud Engineer",
                "bullets": ["Deployed microservices onto k8s clusters using Postgres for persistence."]
            }
        ]
    }

    jd_data = {
        "required_skills": ["Kubernetes", "PostgreSQL", "Amazon Web Services", "Go"]
    }

    eval_res = engine.evaluate(resume_data, jd_data)
    skills_rep = eval_res["skills_breakdown"]

    matched_canonicals = [e["canonical"] for e in skills_rep["mandatory_matched"]]
    assert "kubernetes" in matched_canonicals
    assert "postgresql" in matched_canonicals
    assert "aws" in matched_canonicals
    assert "golang" in matched_canonicals
    assert len(skills_rep["mandatory_missing"]) == 0
    assert skills_rep["match_pct"] >= 80.0


def test_mandatory_vs_preferred_skills_separation():
    """Ensures mandatory and preferred qualifications are separated without double-counting."""
    engine = ATSMatchingEngine()

    resume_data = {
        "skills": ["Python", "FastAPI"],
        "experience": [
            {"company": "A", "role": "Dev", "bullets": ["Built Python microservices using FastAPI."]}
        ]
    }

    jd_data = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker", "Kubernetes", "Python"],  # Python shouldn't be double-counted
        "ats_keywords": ["Python", "FastAPI", "Docker"]
    }

    eval_res = engine.evaluate(resume_data, jd_data)
    skills_rep = eval_res["skills_breakdown"]

    # Python is mandatory, so preferred should only contain Docker and Kubernetes
    assert "python" in [e["canonical"] for e in skills_rep["mandatory_matched"]]
    assert "fastapi" in [e["canonical"] for e in skills_rep["mandatory_matched"]]
    assert "docker" in skills_rep["preferred_missing"]
    assert "kubernetes" in skills_rep["preferred_missing"]

    # Mandatory match should be 100% while preferred is 0%
    assert eval_res["dimension_scores"]["mandatory_skills"] == 100.0
    assert eval_res["dimension_scores"]["preferred_skills"] == 0.0


def test_evidence_based_scoring_levels():
    """
    Verifies that skills demonstrated in production experience receive strong credit,
    while skills merely keyword-stuffed in a skills list receive reduced credit.
    """
    engine = ATSMatchingEngine()

    # Candidate A: Demonstrates Python in active work experience
    res_proven = {
        "skills": [],
        "experience": [
            {"company": "Stripe", "role": "Backend Engineer", "bullets": ["Engineered high-throughput payments engine in Python."]}
        ]
    }

    # Candidate B: Merely lists Python in raw skills section without bullet evidence
    res_listed_only = {
        "skills": ["Python"],
        "experience": [
            {"company": "Generic Corp", "role": "Engineer", "bullets": ["Built internal operational dashboards."]}
        ]
    }

    jd = {"required_skills": ["Python"]}

    eval_proven = engine.evaluate(res_proven, jd)
    eval_listed = engine.evaluate(res_listed_only, jd)

    ev_proven = eval_proven["skills_breakdown"]["mandatory_matched"][0]
    ev_listed = eval_listed["skills_breakdown"]["mandatory_matched"][0]

    assert ev_proven["evidence_level"] == "strong"
    assert ev_listed["evidence_level"] == "listed_only"
    # Strong evidence yields 100%, listed only yields 60%
    assert eval_proven["dimension_scores"]["mandatory_skills"] == 100.0
    assert eval_listed["dimension_scores"]["mandatory_skills"] == 60.0


def test_responsibilities_coverage():
    """Evaluates matching of JD core duties to candidate work accomplishments."""
    engine = ATSMatchingEngine()

    resume_data = {
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Senior Engineer",
                "bullets": [
                    "Architected event-driven microservices processing 100M events per day.",
                    "Collaborated with product and frontend teams in 2-week agile sprints.",
                    "Mentored 4 junior engineers and standardized pull request review guidelines."
                ]
            }
        ]
    }

    jd_data = {
        "responsibilities": [
            "Architect and scale distributed microservices pipelines",
            "Partner with cross-functional product stakeholders to deliver roadmaps",
            "Mentor team members and drive engineering excellence",
            "Manage on-premise hardware data center cooling infrastructure"  # Uncovered
        ]
    }

    eval_res = engine.evaluate(resume_data, jd_data)
    resp_rep = eval_res["responsibilities_breakdown"]

    assert len(resp_rep["covered"]) == 3
    assert len(resp_rep["uncovered"]) == 1
    assert "data center" in resp_rep["uncovered"][0].lower()
    assert resp_rep["coverage_pct"] == 75.0


def test_education_level_and_field_alignment():
    """Evaluates degree level checks and transparent missing education handling."""
    engine = ATSMatchingEngine()

    jd_degree_req = {
        "raw_text": "Requirements: Bachelor's degree in Computer Science or related STEM field required."
    }

    # 1. Candidate with Master's in CS (Exceeds requirement -> Passed)
    res_masters = {
        "education": [{"degree": "Master of Science in Computer Science", "school": "MIT"}]
    }
    eval_masters = engine.evaluate(res_masters, jd_degree_req)
    assert eval_masters["dimension_scores"]["education"] == 100.0
    assert eval_masters["education_breakdown"]["status"] == "meets_requirement"

    # 2. Candidate with Associate degree (Below requirement -> Failed Gate)
    res_associate = {
        "education": [{"degree": "Associate Degree in Web Tech", "school": "City College"}]
    }
    eval_associate = engine.evaluate(res_associate, jd_degree_req)
    assert eval_associate["dimension_scores"]["education"] < 100.0
    edu_gate = next(g for g in eval_associate["hard_eligibility"]["gates"] if g["gate_name"] == "education_level")
    assert edu_gate["is_passed"] is False

    # 3. Candidate with no education section (Transparently flagged as unverifiable)
    res_no_edu = {"experience": [{"company": "X", "role": "Dev", "bullets": ["Code."]}]}
    eval_no_edu = engine.evaluate(res_no_edu, jd_degree_req)
    assert eval_no_edu["education_breakdown"]["status"] == "unverifiable"
    assert eval_no_edu["missing_information_report"]["missing_education"] is True


def test_domain_knowledge_evaluation():
    """Tests industry domain context detection and candidate alignment."""
    engine = ATSMatchingEngine()

    # Fintech JD
    jd_fintech = {
        "domain": "Fintech",
        "raw_text": "Fintech platform scaling real-time payments, banking ledgers, and fraud prevention."
    }

    # Candidate with payments and ledger background
    res_fintech = {
        "experience": [
            {
                "company": "PaymentGate",
                "role": "Engineer",
                "bullets": ["Processed card payments and built double-entry accounting ledger."]
            }
        ]
    }
    eval_fintech = engine.evaluate(res_fintech, jd_fintech)
    assert eval_fintech["dimension_scores"]["domain"] == 100.0
    assert "fintech" in eval_fintech["domain_breakdown"]["matched_domains"]

    # Candidate with gaming background (no fintech)
    res_gaming = {
        "experience": [
            {
                "company": "GameStudio",
                "role": "Gameplay Programmer",
                "bullets": ["Developed 3D physics engine and character animation scripts."]
            }
        ]
    }
    eval_gaming = engine.evaluate(res_gaming, jd_fintech)
    assert eval_gaming["dimension_scores"]["domain"] == 0.0
    assert "fintech" in eval_gaming["domain_breakdown"]["missing_domains"]


def test_hard_eligibility_gating_separation():
    """Validates that hard eligibility gating is cleanly separated from overall match fit."""
    engine = ATSMatchingEngine()

    # JD requires 5+ years experience and Bachelor's degree
    jd = {
        "raw_text": "Senior Platform Lead. Requirements: 5+ years of software experience. Bachelor's degree required.",
        "experience_years": 5.0,
        "required_skills": ["Python", "FastAPI", "Docker"]
    }

    # Candidate has excellent skill match (100%) but only 2 years experience (fails tenure gate)
    resume = {
        "skills": ["Python", "FastAPI", "Docker"],
        "education": [{"degree": "BS in Computer Science", "school": "Stanford"}],
        "experience": [
            {
                "company": "Startup",
                "role": "Developer",
                "dates": "2021 – 2022", # 2.0 yrs
                "bullets": ["Engineered microservices using Python, FastAPI, and Docker."]
            }
        ]
    }

    eval_res = engine.evaluate(resume, jd)
    hard_elig = eval_res["hard_eligibility"]

    # Hard eligibility check MUST be failed
    assert hard_elig["is_eligible"] is False
    assert "minimum_tenure" in hard_elig["failed_gates"]

    # Tenure score is strictly 0.0% as per binary gating requirement
    assert eval_res["dimension_scores"]["tenure"] == 0.0

    # Skills score remains un-corrupted and accurate (100.0%)
    assert eval_res["dimension_scores"]["mandatory_skills"] == 100.0

    # Overall fit score reflects skill relevance while tenure gating penalty keeps it bounded
    assert 0.0 < eval_res["overall_fit_score"] < 100.0


def test_dynamic_weight_renormalization_prevents_inflation():
    """
    Confirms that omitting optional JD fields (e.g. no education required, no preferred skills)
    dynamically rebalances weights to 1.0 without score inflation or deflation.
    """
    engine = ATSMatchingEngine()

    # Candidate with perfect match on skills and experience
    resume = {
        "skills": ["Python", "PostgreSQL"],
        "experience": [
            {
                "company": "SaaS Corp",
                "role": "Engineer",
                "dates": "2018 – 2022", # 5 yrs
                "bullets": ["Built Python APIs with PostgreSQL databases."]
            }
        ]
    }

    # JD without education requirement or preferred skills
    jd_lean = {
        "required_skills": ["Python", "PostgreSQL"],
        "experience_years": 3.0
    }

    eval_res = engine.evaluate(resume, jd_lean)
    # Score should be 100.0 without any missing field penalties
    assert eval_res["overall_fit_score"] == 100.0
    assert eval_res["hard_eligibility"]["is_eligible"] is True


def test_rule_engine_integration_and_backwards_compatibility():
    """Verifies end-to-end integration in RuleEngine, returning legacy and rich metrics."""
    engine = RuleEngine()

    resume = {
        "profile_summary": "Staff Backend Engineer specialized in distributed systems and cloud platforms.",
        "skills": ["Go", "Kubernetes", "PostgreSQL", "AWS"],
        "education": [{"degree": "BS Computer Science", "school": "Berkeley"}],
        "experience": [
            {
                "company": "Cloud Corp",
                "role": "Lead Architect",
                "dates": "2016 – 2022", # 7 yrs
                "bullets": [
                    "Designed distributed data streaming pipeline using Go and Kubernetes.",
                    "Scaled AWS cloud infrastructure reducing hosting costs by 25%."
                ]
            }
        ],
        "projects": [
            {
                "name": "DB Tool",
                "bullets": ["Optimized PostgreSQL indexing strategies for analytical queries."]
            }
        ]
    }

    jd = {
        "role": "Staff Cloud Architect",
        "company": "ScaleWorks",
        "raw_text": "Requirements: 5+ years experience. Bachelor's in CS. Mandatory skills: Go, Kubernetes, AWS, PostgreSQL.",
        "ats_keywords": ["Go", "Kubernetes", "AWS", "PostgreSQL"],
        "required_skills": ["Go", "Kubernetes", "AWS", "PostgreSQL"],
        "experience_years": 5.0
    }

    result = engine.analyze(resume, jd)

    # Legacy contract preserved
    assert "ats_score" in result
    assert result["ats_score"] >= 85.0
    assert result["skill_match"] == 100.0
    assert result["keyword_match"] == 100.0
    assert result["experience_match"] == 100.0
    assert result["experience_duration_known"] is True
    assert result["required_years"] == 5.0
    assert result["resume_years"] >= 7.0
    assert "formatting_report" in result

    # Rich dimensional contract available
    assert "hard_eligibility" in result
    assert result["hard_eligibility"]["is_eligible"] is True
    assert "dimension_scores" in result
    assert "evidence_ledger" in result
    assert len(result["evidence_ledger"]) >= 4
    assert "skills_breakdown" in result
    assert "education_breakdown" in result
