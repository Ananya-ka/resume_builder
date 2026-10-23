import pytest
from app.services.resume_parser import ResumeParser
from app.services.jd_parser import JDParser
from app.services.resume_optimizer import ResumeOptimizer
from types import SimpleNamespace
from unittest.mock import Mock


def test_unavailable_parsers_never_return_mock_candidates_or_requirements():
    for parser, method in [(ResumeParser(), "parse_resume_to_json"), (JDParser(), "parse_job_description")]:
        parser.client = None
        with pytest.raises(ValueError, match="unavailable"):
            getattr(parser, method)("Some real text")


def test_duplicate_source_indices_fail_instead_of_reporting_success():
    optimizer = ResumeOptimizer()
    response = '{"optimized_bullets": [{"index": 0, "optimized_bullet": "Changed one"}, {"index": 0, "optimized_bullet": "Changed two"}]}'
    create = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))]))
    optimizer.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    bullets = [{"id": 1, "content": "First fact"}, {"id": 2, "content": "Second fact"}]
    with pytest.raises(ValueError, match="tailoring failed"):
        optimizer.optimize_bullets(bullets, {})


def test_parser_rejects_claims_not_in_uploaded_text():
    from app.services.resume_parser import validate_resume_parse
    raw = "Acme\nDeveloper\nBuilt APIs.\nSkills: Python"
    parsed = {"skills": ["Python"], "experience": [{"company": "Acme", "role": "Developer", "bullets": ["Built APIs."]}]}
    assert validate_resume_parse(parsed, raw)["experience"][0]["bullets"] == ["Built APIs."]
    parsed["skills"].append("Redis")
    with pytest.raises(ValueError, match="unsupported"):
        validate_resume_parse(parsed, raw)
