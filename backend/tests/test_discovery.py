import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.config import settings
from app.models.schemas import User, Resume, ResumeBullet, JobDescription, CandidateEvidence, EvidenceDraft, OptimizedResume
from app.api.routes import router as base_router
from app.api.discovery import router
from app.services.discovery import next_question, apply_answer, evidence_bullet


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr("app.api.discovery.next_question", next_question)
    monkeypatch.setattr("app.api.discovery.llm_next_question", next_question)
    monkeypatch.setattr("app.api.discovery.heuristic_next_question", next_question)
    def mock_optimize(self, bullets, jd):
        return [{"original_id": b["id"], "source": b["source"],
                 "optimized_bullet": b["content"]} for b in bullets], []
    monkeypatch.setattr("app.services.resume_optimizer.ResumeOptimizer.optimize_bullets", mock_optimize)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([User(id="alice"), User(id="bob")]); db.flush()
        db.add_all([
            Resume(id=1, user_id="alice", name="one.pdf", parsed_raw={"name": "Alice Example", "email": "alice@example.com", "skills": ["Python"], "education": []}),
            Resume(id=2, user_id="alice", name="two.pdf", parsed_raw={"skills": ["SQL"], "education": []}),
            Resume(id=3, user_id="bob", name="private.pdf", parsed_raw={"skills": []}),
            JobDescription(id=1, user_id="alice", company="Target", role="Backend", raw_text="Python APIs and Redis caching", required_skills=["Python", "Redis"], ats_keywords=["Python", "Redis"]),
            JobDescription(id=2, user_id="bob", company="Private", role="Backend", raw_text="Private", required_skills=[]),
        ]); db.flush()
        for rid in (1, 2):
            db.add(ResumeBullet(resume_id=rid, company="Chatbot", role="Developer", section="Projects", bullet="Improved API performance by 40%."))
        db.commit()
    app = FastAPI(); app.include_router(base_router); app.include_router(router)
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    from app.worker.tasks import optimize_resume_task
    monkeypatch.setattr(optimize_resume_task, "delay", lambda _: None)
    with TestClient(app, headers={"x-user-id": "alice"}) as client:
        yield client, factory
    engine.dispose()


def start(client):
    response = client.post("/api/discovery", json={"resume_ids": [1, 2], "job_id": 1})
    assert response.status_code == 200, response.text
    return response.json()


def test_previous_candidate_answers_do_not_leak_into_new_resume(api):
    client, factory = api
    with factory() as db:
        prior = __import__("app.models.schemas", fromlist=["DiscoverySession"]).DiscoverySession(
            user_id="alice", job_id=1, resume_ids=[1], evidence_ids=[], questions=[], status="ready")
        db.add(prior); db.flush()
        db.add(CandidateEvidence(user_id="alice", revision=1, history=[],
            source_refs=[f"discovery:{prior.id}:question:1"],
            data={"content": "Worked at Darwix AI", "company": "Darwix AI", "section": "Experience", "role": "Engineer"}))
        db.commit()
    response = client.post("/api/discovery", json={"resume_ids": [2], "job_id": 1})
    assert response.status_code == 200
    assert all(e["data"]["company"] != "Darwix AI" for e in response.json()["evidence"])


def test_zero_questions_goes_straight_to_ready(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr("app.api.discovery.next_question", lambda *args: None)
    session = start(client)
    assert session["status"] == "ready"
    assert session["questions"] == []
    assert session["limit"] == 5


def test_profile_conflicts_are_confirmed_and_remembered(api, monkeypatch):
    client, factory = api
    monkeypatch.setattr("app.api.discovery.next_question", lambda *args: None)
    with factory() as db:
        for rid, dates in [(1, "2020–2023"), (2, "2020–2024")]:
            resume = db.query(Resume).filter_by(id=rid).one()
            resume.parsed_raw = {**resume.parsed_raw, "experience": [{"company": "Acme", "role": "Engineer", "dates": dates}]}
        db.commit()
    session = start(client)
    assert session["status"] == "reviewing" and session["questions"] == []
    assert client.post(f"/api/discovery/{session['id']}/optimize").status_code == 409
    conflict = session["conflicts"][0]
    resolved = client.post(f"/api/discovery/{session['id']}/resolve", json={"conflict_id": conflict["id"], "choice": "2020–2024"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "ready"
    again = start(client)
    assert not again["conflicts"]
    assert again["profile"]["experience"][0]["dates"] == "2020–2024"


def test_review_revert_accept_and_submitted_immutability(api, monkeypatch):
    client, factory = api
    from app.worker import tasks
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    session = finish(client, start(client))
    draft_id = client.post(f"/api/discovery/{session['id']}/optimize").json()["id"]
    tasks.optimize_resume_task.run(draft_id)
    bullet = client.get(f"/api/optimizations/{draft_id}").json()["optimized_content"][0]
    payload = {"evidence_id": bullet["original_id"], "action": "revert", "expected_text": bullet["optimized_bullet"]}
    path = f"/api/evidence-drafts/{draft_id}/review"
    assert client.post(path, json=payload, headers={"x-user-id": "bob"}).status_code == 404
    assert client.post(path, json={**payload, "expected_text": "stale"}).status_code == 409
    assert client.post(path, json={**payload, "action": "edit", "text": "Built Kubernetes saving 99%."}).status_code == 422
    result = client.post(path, json=payload)
    assert result.status_code == 200, result.text
    updated = result.json()["optimized_content"][0]
    assert updated["review_state"] == "reverted" and updated["source_refs"]
    assert updated["review_history"][-1]["action"] == "revert"
    assert client.post(f"/api/evidence-drafts/{draft_id}/submit").status_code == 200
    assert client.post(path, json=payload).status_code == 409


def test_pdf_overflow_requires_choice_and_keep_downloads(api, monkeypatch):
    client, factory = api
    session = finish(client, start(client))
    draft_id = client.post(f"/api/discovery/{session['id']}/optimize").json()["id"]
    with factory() as db:
        db.query(EvidenceDraft).filter_by(optimization_id=draft_id).one().status = "complete"
        db.commit()
    monkeypatch.setattr("app.services.pdf_export.compile_export", lambda *args: (b"%PDF-two-pages", 2))
    path = f"/api/optimizations/{draft_id}/export/pdf"
    response = client.post(path, json={"template_choice": "default"})
    assert response.status_code == 409
    assert response.json()["detail"]["pages"] == 2
    kept = client.post(path, json={"page_policy": "keep"})
    assert kept.status_code == 200 and kept.content == b"%PDF-two-pages"
    assert kept.headers["X-Resume-Pages"] == "2"
    monkeypatch.setattr("app.services.pdf_export.concise_export", lambda *args: (b"%PDF-one-page", 1, [3]))
    concise = client.post(path, json={"page_policy": "one_page"})
    assert concise.status_code == 200
    assert concise.headers["X-Resume-Pages"] == "1"
    assert concise.headers["X-Resume-Omitted"] == "1"


def finish(client, session):
    while session["status"] != "ready":
        response = client.post(f"/api/discovery/{session['id']}/answers", json={"question_id": session["questions"][-1]["id"], "skip": True})
        assert response.status_code == 200, response.text
        session = response.json()
    return session


def test_four_questions_with_confirmation_gap_and_ownership(api):
    client, factory = api
    session = start(client)
    assert len(session["evidence"]) == 1  # same achievement across two resumes
    assert len(session["evidence"][0]["source_refs"]) == 2
    path = f"/api/discovery/{session['id']}/answers"
    assert session["questions"][0]["benefit"]
    session = client.post(path, json={"question_id": 1, "answer": "I stored responses and reused them for repeated requests."}).json()
    assert session["questions"][-1]["kind"] == "interpretation"
    assert not session["evidence"][0]["data"].get("confirmed_terms")
    session = client.post(path, json={"question_id": 2, "confirm": True}).json()
    assert session["evidence"][0]["data"]["confirmed_terms"] == ["response caching"]
    assert session["questions"][-1]["kind"] == "ownership"
    session = client.post(path, json={"question_id": 3, "answer": "I implemented response reuse in my personal application.", "depth": "personal_project"}).json()
    assert session["questions"][-1]["kind"] == "gap"
    assert "Redis" in session["questions"][-1]["prompt"]
    session = client.post(path, json={"question_id": 4, "answer": "I followed a Redis tutorial.", "company": "Practice", "depth": "tutorial"}).json()
    assert session["status"] == "ready" and len(session["questions"]) == 4
    assert evidence_bullet(session["evidence"][-1]) is None
    assert client.post(path, json={"question_id": 4, "skip": True}).status_code == 409
    assert client.get(f"/api/discovery/{session['id']}").json()["questions"] == session["questions"]
    # Confirmed additional learning persists into the next application.
    assert len(start(client)["evidence"]) == 2


def test_skip_reject_and_tenant_boundaries(api):
    client, _ = api
    assert client.post("/api/discovery", json={"resume_ids": [1, 1], "job_id": 1}).status_code == 422
    assert client.post("/api/discovery", json={"resume_ids": [1, 2, 3, 4], "job_id": 1}).status_code == 422
    assert client.post("/api/discovery", json={"resume_ids": [3], "job_id": 1}).status_code == 404
    assert client.post("/api/discovery", json={"resume_ids": [1], "job_id": 2}).status_code == 404
    session = start(client); path = f"/api/discovery/{session['id']}"
    assert client.get(path, headers={"x-user-id": "bob"}).status_code == 404
    assert client.post(path + "/answers", json={"question_id": 2, "skip": True}).status_code == 409
    assert client.post(path + "/answers", json={"question_id": 1, "answer": " "}).status_code == 422
    assert client.post(path + "/optimize").status_code == 409
    ready = finish(client, session)
    assert ready["evidence"] == session["evidence"]
    assert len(ready["questions"]) <= 4


def test_correction_preserves_submitted_snapshot_and_survives_reimport(api):
    client, factory = api
    session = finish(client, start(client))
    eid = session["evidence"][0]["id"]
    original_data = session["evidence"][0]["data"]
    draft_id = client.post(f"/api/discovery/{session['id']}/optimize").json()["id"]
    with factory() as db:
        draft = db.query(EvidenceDraft).filter_by(optimization_id=draft_id).one()
        assert draft.profile_snapshot["skills"] == ["Python", "SQL"]
        draft.status = "complete"
        db.query(OptimizedResume).filter_by(id=draft_id).one().optimized_content = [{"original_id": eid, "optimized_bullet": "Old chatbot claim"}]
        db.commit()
    assert client.post(f"/api/evidence-drafts/{draft_id}/submit").status_code == 200
    payload = {"revision": 1, "content": "Improved ingestion throughput by 40%.", "company": "Ingestion", "role": "Developer", "section": "Projects", "depth": "personal_project", "ownership": "Improved ingestion throughput by 40%.", "reason": "The metric belongs to ingestion, not chatbot."}
    assert client.put(f"/api/evidence/{eid}", json=payload, headers={"x-user-id": "bob"}).status_code == 404
    corrected = client.put(f"/api/evidence/{eid}", json=payload)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["affected_drafts"][0]["submitted"] is True
    assert client.put(f"/api/evidence/{eid}", json=payload).status_code == 409
    new_id = client.post(f"/api/evidence-drafts/{draft_id}/revise").json()["id"]
    with factory() as db:
        old = db.query(EvidenceDraft).filter_by(optimization_id=draft_id).one()
        new = db.query(EvidenceDraft).filter_by(optimization_id=new_id).one()
        assert old.evidence_snapshot[0]["data"] == original_data
        assert old.submitted and old.stale_evidence_ids == [eid]
        assert new.evidence_snapshot[0]["data"]["company"] == "Ingestion"
        assert new.evidence_snapshot[0]["revision"] == 2
        assert db.query(OptimizedResume).filter_by(id=draft_id).one().optimized_content[0]["optimized_bullet"] == "Old chatbot claim"
        # Re-uploading an older resume must not resurrect a corrected claim.
        db.add(Resume(id=4, user_id="alice", name="old.pdf", parsed_raw={"email": "alice@example.com", "skills": []})); db.flush()
        db.add(ResumeBullet(resume_id=4, company="Chatbot", role="Developer", section="Projects", bullet="Improved API performance by 40%.")); db.commit()
    reimported = client.post("/api/discovery", json={"resume_ids": [4], "job_id": 1}).json()
    assert reimported["evidence"][0]["id"] == eid
    assert reimported["evidence"][0]["data"]["company"] == "Ingestion"


def test_worker_uses_snapshot_and_does_not_overwrite_completed_draft(api, monkeypatch):
    client, factory = api
    from app.worker import tasks
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    session = finish(client, start(client))
    draft_id = client.post(f"/api/discovery/{session['id']}/optimize").json()["id"]
    tasks.optimize_resume_task.run(draft_id)
    report = client.get(f"/api/optimizations/{draft_id}").json()
    assert report["optimized_content"][0]["source"] == "candidate_evidence"
    assert report["optimized_content"][0]["evidence_revision"] == 1
    assert client.get("/api/evidence-drafts").json()[0]["status"] == "complete"
    with factory() as db:
        snapshot = db.query(EvidenceDraft).filter_by(optimization_id=draft_id).one().profile_snapshot
        assert snapshot["name"] == "Alice Example"
        assert snapshot["email"] == "alice@example.com"
    tasks.optimize_resume_task.run(draft_id)
    assert client.get(f"/api/optimizations/{draft_id}").json() == report


def test_interpretation_rejection_and_depth_never_promote_claims():
    data = {"content": "Team deployed services.", "section": "Experience", "company": "Team", "role": "Engineer", "depth": "unspecified"}
    q = {"kind": "interpretation", "term": "monitoring"}
    assert apply_answer(data, q, "", confirm=False)["rejected_terms"] == ["monitoring"]
    for depth in ["team_only", "tutorial", "familiarity"]:
        item = {"id": 1, "revision": 1, "data": {**data, "depth": depth}}
        assert evidence_bullet(item) is None
    assert next_question([], [{"kind": "work", "evidence_id": 1}] * 5, "Redis") is None


def test_batch_upload_validation_and_legacy_optimization_gate(api, monkeypatch):
    client, _ = api
    from app.worker.tasks import parse_resume_task
    monkeypatch.setattr(parse_resume_task, "delay", lambda *args: None)
    files = [("files", (f"resume-{i}.txt", b"- Built APIs.", "text/plain")) for i in range(3)]
    uploaded = client.post("/api/resumes/upload-batch", files=files)
    assert uploaded.status_code == 200, uploaded.text
    assert len(uploaded.json()) == 3
    assert all(r["parsed_raw"]["parsing_status"] == "queued" for r in uploaded.json())
    assert client.post("/api/resumes/upload-batch", files=files + [files[0]]).status_code == 422
    assert client.post("/api/optimize", json={"resume_id": 1, "job_id": 1}).status_code == 409
    session = finish(client, start(client))
    assert client.post("/api/optimize", json={"resume_id": 1, "job_id": 1, "discovery_session_id": session["id"]}).status_code == 200


def test_exports_use_completed_snapshots(api, monkeypatch):
    client, factory = api
    from app.worker import tasks
    monkeypatch.setattr(tasks, "SessionLocal", factory)
    session = finish(client, start(client))
    draft_id = client.post(f"/api/discovery/{session['id']}/optimize").json()["id"]
    assert client.get(f"/api/optimizations/{draft_id}/export/docx").status_code == 409
    tasks.optimize_resume_task.run(draft_id)
    pending = client.get(f"/api/optimizations/{draft_id}").json()["optimized_content"]
    assert client.get(f"/api/optimizations/{draft_id}/export/pdf").status_code == 409
    for bullet in pending:
        accepted = client.post(f"/api/evidence-drafts/{draft_id}/review", json={"evidence_id": bullet["original_id"], "action": "accept", "expected_text": bullet["optimized_bullet"]})
        assert accepted.status_code == 200, accepted.text
    for format, prefix in [("docx", b"PK"), ("pdf", b"%PDF")]:
        exported = client.get(f"/api/optimizations/{draft_id}/export/{format}")
        assert exported.status_code == 200, exported.text
        assert exported.content.startswith(prefix)


def test_queue_failures_are_visible_and_pending_questions_detect_corrections(api, monkeypatch):
    client, factory = api
    session = start(client)
    eid = session["evidence"][0]["id"]
    corrected = client.put(f"/api/evidence/{eid}", json={"revision": 1, "content": "Built ingestion APIs.", "company": "Ingestion", "role": "Developer", "section": "Projects", "depth": "personal_project", "reason": "Fixed attribution"})
    assert corrected.status_code == 200
    path = f"/api/discovery/{session['id']}/answers"
    assert client.post(path, json={"question_id": 1, "answer": "Details about the old chatbot"}).status_code == 409
    session = finish(client, session)
    from app.worker.tasks import optimize_resume_task
    def fail(_):
        raise RuntimeError("Queue unavailable")
    monkeypatch.setattr(optimize_resume_task, "delay", fail)
    assert client.post(f"/api/discovery/{session['id']}/optimize").status_code == 503
    draft = client.get("/api/evidence-drafts").json()[0]
    assert draft["status"] == "failed" and draft["error"]
    assert client.post(f"/api/evidence-drafts/{draft['id']}/submit").status_code == 409
