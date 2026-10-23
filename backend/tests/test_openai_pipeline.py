import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import Settings, settings
from app.services.resume_parser import validate_resume_parse
from app.services.resume_optimizer import ResumeOptimizer
from app.services.discovery import llm_next_question


def test_environment_precedence(tmp_path, monkeypatch):
    root = tmp_path / "root.env"
    backend = tmp_path / "backend.env"
    root.write_text("OPENAI_API_KEY=root-test\n")
    backend.write_text("OPENAI_API_KEY=backend-test\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert Settings(_env_file=(root, backend)).OPENAI_API_KEY == "backend-test"
    monkeypatch.setenv("OPENAI_API_KEY", "process-test")
    assert Settings(_env_file=(root, backend)).OPENAI_API_KEY == "process-test"


def test_identity_and_dates_survive_validation():
    parsed = {"name": "Alex Example", "email": "alex@example.com", "phone": "+1 555 0100",
              "education": [{"school": "Example College", "degree": "BSc", "dates": "2020–2024"}]}
    raw = "Alex Example alex@example.com +1 555 0100 Example College BSc 2020–2024"
    result = validate_resume_parse(parsed, raw)
    assert result["name"] == parsed["name"]
    assert result["email"] == parsed["email"]
    assert result["education"] == parsed["education"]
    parsed["name"] = "Invented Person"
    with pytest.raises(ValueError, match="unsupported"):
        validate_resume_parse(parsed, raw)


def test_tailoring_requires_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ValueError, match="unavailable"):
        ResumeOptimizer().optimize_bullets([], {})


def test_discovery_uses_llm_preserving_five_question_limit(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-only")
    create = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({"question": {"kind": "work", "evidence_id": 7, "prompt": "What did you personally change in the API?", "benefit": "Clarifies ownership.", "requirement_quote": "Python", "necessity": "material"}})
    ))]))
    monkeypatch.setattr("app.services.discovery.OpenAI", lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    evidence = [{"id": 7, "data": {"content": "Built APIs", "company": "Acme"}}]
    question = llm_next_question(evidence, [], "Python API role")
    assert question["evidence_id"] == 7
    assert question["benefit"] == "Clarifies ownership."
    assert create.call_args.kwargs["model"] == settings.OPENAI_MODEL
    assert llm_next_question(evidence, [{}] * 5, "Python") is None
    assert create.call_count == 1


def test_discovery_missing_key_fails_explicitly(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ValueError, match="OpenAI is required"):
        llm_next_question([{"id": 1, "data": {"content": "Built APIs"}}], [], "Python")


@pytest.mark.parametrize("payload,prior", [
    ({"question": None}, []),
    ({"question": {"kind": "gap", "evidence_id": None, "skill": "Python", "prompt": "Any Python work?", "benefit": "Supports Python requirement", "requirement_quote": "Python", "necessity": "material"}}, [{}] * 4),
])
def test_unnecessary_questions_stop_immediately(monkeypatch, payload, prior):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test")
    create = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]))
    monkeypatch.setattr("app.services.discovery.OpenAI", lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    assert llm_next_question([], prior, "Python") is None


def test_employer_and_bullets_require_matching_source_passage():
    raw = "Acme Developer Built APIs. Beta Analyst Analyzed sales."
    parsed = {"experience": [{"company": "Acme", "role": "Developer", "bullets": ["Analyzed sales."], "source_quote": "Acme Developer Built APIs."}]}
    with pytest.raises(ValueError, match="source passage"):
        validate_resume_parse(parsed, raw, require_source_quotes=True)
    parsed["experience"][0]["company"] = "Darwix AI"
    with pytest.raises(ValueError, match="unsupported"):
        validate_resume_parse(parsed, raw, require_source_quotes=True)
