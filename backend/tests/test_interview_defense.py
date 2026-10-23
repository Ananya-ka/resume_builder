import pytest
from app.services.interview_defense import InterviewDefenseEngine, ProofTier


def test_interview_defense_card_generation():
    engine = InterviewDefenseEngine()
    bullets = [
        {
            "original_id": 1,
            "optimized_bullet": "Architected hybrid RAG vector search pipeline using Redis caching, handling 5,000 qps and cutting latency by 35%.",
            "company": "AI Startup",
            "role": "Backend Engineer",
            "section": "Experience",
            "included": True
        }
    ]
    cards = engine.generate_defense_cards(bullets, {}, {"company": "Acme", "role": "Staff Engineer"})
    assert len(cards) == 1
    card = cards[0]
    assert "Retrieval" in card["topic"]
    assert "probe" in card["technical_probe"].lower() or "chunking" in card["technical_probe"].lower()
    assert "fine-tuned" in card["truth_boundary"]["do_not_cross_rule"].lower()
    assert "5,000 qps" in card["truth_boundary"]["verified_scale_limit"].lower()


def test_interview_defense_overreach_evaluation():
    engine = InterviewDefenseEngine()
    card = {
        "truth_boundary": {
            "do_not_cross_rule": "Do not claim you fine-tuned foundational models if you only implemented vector retrieval with prompt augmentation."
        }
    }
    # Candidate exaggerates in interview defense
    candidate_answer = "I fine-tuned foundation model weights on our internal corpus to boost retrieval accuracy."
    eval_result = engine.evaluate_defense_explanation(card, candidate_answer)

    assert eval_result["status"] == "overreach_detected"
    assert any("fine-tuning" in w for w in eval_result["warnings"])
    assert eval_result["score"] < 70


def test_interview_defense_solid_evaluation():
    engine = InterviewDefenseEngine()
    card = {
        "truth_boundary": {
            "do_not_cross_rule": "Do not claim distributed multi-region replication if Redis was deployed as a single VPC instance."
        }
    }
    # Candidate speaks truth with trade-offs
    candidate_answer = "We chose an in-memory Redis cache because serialization latency was our bottleneck, and measured p99 query times dropping under 15ms using Prometheus."
    eval_result = engine.evaluate_defense_explanation(card, candidate_answer)

    assert eval_result["status"] == "solid_defense"
    assert len(eval_result["warnings"]) == 0
    assert len(eval_result["strengths"]) >= 1
    assert eval_result["score"] >= 85


def test_minimum_proof_specs_generation():
    engine = InterviewDefenseEngine()
    gap_classifications = [
        {
            "term": "kafka",
            "bucket": "true_deficit",
            "is_required": True,
            "suggested_proof_tier": ProofTier.IMPLEMENTATION.value
        },
        {
            "term": "react",
            "bucket": "verified_present",
            "is_required": True
        }
    ]
    jd = {"company": "Fintech Co", "role": "Senior Engineer"}
    specs = engine.generate_proof_specs(gap_classifications, jd)

    assert len(specs) == 1
    spec = specs[0]
    assert spec["term"] == "kafka"
    assert spec["proof_tier"] == ProofTier.IMPLEMENTATION.value
    assert "Fintech Co" in spec["target_role"]
    assert any("GitHub" in d for d in spec["deliverables"])
    assert "truth_framing_guidance" in spec
