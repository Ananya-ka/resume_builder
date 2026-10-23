from types import SimpleNamespace
from app.services.candidate_profile import merge_profile
from app.services.fact_verifier import FactVerifier


def resume(id, **data):
    return SimpleNamespace(id=id, parsed_raw=data)


def test_all_sources_are_merged_with_provenance_and_conflicts():
    resumes = [resume(1, name="Sam", skills=["Python"], education=[{"school": "A", "degree": "BSc"}], experience=[{"company": "Acme", "role": "Engineer", "dates": "2020–2023"}]),
               resume(2, email="sam@example.com", skills=["python", "SQL"], education=[{"school": "B", "degree": "MSc"}], experience=[{"company": "Acme", "role": "Engineer", "dates": "2020–2024"}])]
    profile, conflicts = merge_profile(resumes, [])
    assert profile["name"] == "Sam" and profile["email"] == "sam@example.com"
    assert profile["skills"] == ["Python", "SQL"]
    assert len(profile["education"]) == 2
    assert profile["experience"][0]["dates"] == ""
    assert len(conflicts) == 1
    resolved, conflicts = merge_profile(resumes, [], {conflicts[0]["id"]: "2020–2024"})
    assert not conflicts and resolved["experience"][0]["dates"] == "2020–2024"
    assert profile["source_map"]["skills:Python"] == ["resume:1"]


def test_metric_conflicts_do_not_cross_projects_without_confirmation():
    def evidence(id, company, metric):
        return {"id": id, "revision": 1, "source_refs": [f"resume:{id}"], "data": {"company": company, "role": "Engineer", "section": "Projects", "content": f"Reduced latency by {metric}%."}}
    items = [evidence(1, "Ingestion", 40), evidence(2, "Chatbot", 60)]
    _, conflicts = merge_profile([], items)
    assert len(conflicts) == 1
    profile, unresolved = merge_profile([], items, {conflicts[0]["id"]: 1})
    assert not unresolved and [e["id"] for e in profile["evidence"]] == [1]
    items[1]["revision"] = 2
    assert merge_profile([], items, {conflicts[0]["id"]: 1})[1]


def test_planned_work_cannot_turn_into_completed_work():
    verifier = FactVerifier()
    passed, errors = verifier._deterministic_verify("Planned to build a Python API.", "Built a Python API.", [])
    assert not passed
    assert any("Planned" in e for e in errors)
