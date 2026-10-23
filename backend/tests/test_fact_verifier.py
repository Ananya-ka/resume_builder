from app.services.fact_verifier import FactVerifier

def test_deterministic_verifier():
    verifier = FactVerifier()

    # Case 1: Valid rephrase (no new techs or metrics)
    original = "Designed a scalable API backend with FastAPI."
    optimized = "Designed and architected a high-throughput API backend leveraging FastAPI."
    passed, errors = verifier._deterministic_verify(original, optimized, ["FastAPI"])
    assert passed is True
    assert len(errors) == 0

    # Case 2: Hallucinated technology added (not in base skills and not implied)
    original = "Designed a scalable API backend with FastAPI."
    optimized = "Designed a scalable API backend with FastAPI, deploying to AWS Kubernetes."
    passed, errors = verifier._deterministic_verify(original, optimized, ["FastAPI"])
    assert passed is False
    assert any("Technology Rules violation" in err for err in errors)

    # Case 3: Hallucinated metric added
    original = "Designed a scalable API backend with FastAPI."
    optimized = "Designed a scalable API backend with FastAPI, reducing API latency by 45%."
    passed, errors = verifier._deterministic_verify(original, optimized, ["FastAPI"])
    assert passed is False
    assert any("Metric Rules violation" in err for err in errors)

    # Case 4: Framework use alone does not establish REST API work
    original = "Designed a scalable API backend with FastAPI."
    optimized = "Designed a scalable REST API backend with FastAPI."
    passed, errors = verifier._deterministic_verify(original, optimized, ["FastAPI"])
    assert passed is False
    assert any("Technology Rules violation" in err for err in errors)


def test_no_global_skill_or_metric_unit_inference():
    verifier = FactVerifier()
    assert not verifier._deterministic_verify("Built APIs.", "Built APIs using Redis.", ["Redis"])[0]
    assert not verifier._deterministic_verify("Handled 40 requests.", "Improved throughput by 40%.", [])[0]
    assert not verifier._deterministic_verify("Used Cloud SQL.", "Used PostgreSQL.", [])[0]


def test_verification_failures_roll_back_and_clear_logs():
    from types import SimpleNamespace
    from unittest.mock import Mock
    verifier = FactVerifier()
    original = [{"id": 1, "source": "candidate_evidence", "content": "Built APIs.", "section": "Projects", "company": "API project", "role": "Developer"}]
    proposed = [{"original_id": 1, "source": "candidate_evidence", "optimized_bullet": "Developed APIs.", "keywords_added": ["Developed"], "keywords_removed": ["Built"]}]
    for result in [None, '{"verified": "false", "reasons": []}', '{"verified": true, "reasons": "bad shape"}']:
        create = Mock(side_effect=RuntimeError("Unavailable")) if result is None else Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=result))]))
        verifier.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        bullet = verifier.verify_optimized_bullets(original, proposed)[0]
        assert bullet["optimized_bullet"] == "Built APIs."
        assert bullet["verified"] is False
        assert bullet["keywords_added"] == bullet["keywords_removed"] == []
    verifier.client = None
    assert verifier.verify_optimized_bullets(original, proposed)[0]["verified"] is False
    # Missing/misidentified model output cannot delete or relocate evidence.
    assert verifier.verify_optimized_bullets(original, [])[0]["optimized_bullet"] == "Built APIs."
    proposed[0]["original_id"] = 100
    assert verifier.verify_optimized_bullets(original, proposed)[0]["original_id"] == 1


def test_rejected_interpretation_is_blocked_even_if_model_approves():
    from unittest.mock import Mock
    verifier = FactVerifier()
    verifier._llm_verify = Mock(return_value=(True, []))
    original = [{"id": 1, "source": "candidate_evidence", "content": "Stored and reused responses.", "blocked_terms": ["response caching"]}]
    proposed = [{"original_id": 1, "source": "candidate_evidence", "optimized_bullet": "Built response caching."}]
    result = verifier.verify_optimized_bullets(original, proposed)[0]
    assert result["optimized_bullet"] == "Stored and reused responses."
    assert any("rejected interpretation" in error for error in result["verification_errors"])
