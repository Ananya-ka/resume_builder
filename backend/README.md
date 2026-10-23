# Evidence-first resume tailoring backend

This version adds multi-resume discovery, ownership-aware evidence, persistent
corrections, and immutable draft inputs. No frontend changes are required to test
it: use FastAPI's `/docs` or the API sequence below.

## Run

From `backend/`, install `requirements.txt`, configure `DATABASE_URL`, `REDIS_URL`,
and `OPENAI_API_KEY`, then start the API and worker in separate terminals:

```sh
uvicorn app.main:app --reload
celery -A app.worker.tasks.celery_app worker --loglevel=info
```

PostgreSQL with pgvector and Redis must be running (the root `docker-compose.yml`
contains the existing development services). API startup creates the new
`candidate_evidence`, `discovery_sessions`, and `evidence_drafts` tables; it does
not rewrite existing resume or optimization tables. Restart both API and worker
after updating the code.

The existing `X-User-Id` header selects a development user, defaulting to
`user_test`. It is **not authentication**. The new endpoints consistently check
ownership against that identity; replace this shared dependency with verified
authentication before exposing the application to other users.

## API sequence

All paths below have the `/api` prefix. Keep the same `X-User-Id` throughout.

1. `POST /resumes/upload-batch` with multipart `files` (1–3 files). PDF, DOCX,
   and TXT are supported, up to 10 MB each. The existing single-file
   `POST /resumes/upload` also works. Poll `GET /resumes/{id}` until
   `parsed_raw.parsing_status` is `ready`; `failed` includes an error.
2. `POST /jobs` with `company`, `role`, and `raw_text`.
3. `POST /discovery` with `{"resume_ids": [1, 2], "job_id": 1}`.
   The first selected resume supplies education; explicit skills are merged
   across selected resumes. Duplicate achievements with the same section,
   employer/project, role, and normalized text share one evidence record.
4. Read the last entry in `questions`. Each contains `id`, `kind`, `prompt`,
   `benefit` (the explanation to show the candidate), and evidence provenance.
   Submit to `POST /discovery/{session_id}/answers`:

   ```json
   {"question_id": 1, "answer": "I stored responses and reused them for repeated requests."}
   ```

   Answer an `interpretation` question with `{"question_id": 2, "confirm": true}`
   or `false`. The proposed term is not evidence until explicitly confirmed.
   For `ownership`, include `answer` and `depth`. Allowed depth values:
   `professional`, `personal_project`, `tutorial`, `familiarity`, `team_only`.
   For `gap`, also include `company` (employer or project name), `role`, and
   `section` (`Experience` or `Projects`). A gap answer becomes separate evidence,
   rather than being attached to an unrelated existing bullet. `personal_project`
   always belongs in `Projects`.

   Any question can be skipped with `{"question_id": 1, "skip": true}`.
   Empty answers must be explicitly skipped. Replayed or out-of-order answers
   return 409. An evidence correction made after a question was issued requires
   skipping that stale question and reviewing the new evidence.
5. Repeat until `status` is `ready`. The server enforces **at most four questions
   for the entire session**, including follow-ups and skips. It can finish sooner
   when there is nothing useful left to ask. `GET /discovery/{id}` resumes the
   persisted session without issuing another question.
6. Review `evidence`, then `POST /discovery/{id}/optimize`. This returns a draft
   optimization `id`. Poll `GET /evidence-drafts` for `queued`, `processing`,
   `complete`, or `failed`. Errors are visible and evidence remains saved.
7. Fetch `GET /optimizations/{id}` and export via
   `GET /optimizations/{id}/export/docx` or `/export/pdf` after completion.

The existing `POST /optimize` now requires `discovery_session_id` alongside its
`resume_id` and `job_id`, matching a completed discovery session. Calls without it
return 409 so clients cannot bypass discovery or persisted corrections.

## Corrections and historical copies

`GET /evidence` lists the reusable catalog. To correct a claim or its attribution,
use `PUT /evidence/{id}` with the current revision:

```json
{
  "revision": 1,
  "content": "Improved ingestion throughput by 40%.",
  "company": "Ingestion project",
  "role": "Developer",
  "section": "Projects",
  "depth": "personal_project",
  "ownership": "Improved ingestion throughput by 40%.",
  "reason": "The improvement belongs to ingestion, not the chatbot."
}
```

The update preserves revision history, clears superseded discovery context and
interpretations, and returns affected drafts. A stale `revision` returns 409.
Reimporting identical old resume wording resolves to the corrected evidence,
including when it arrives in a newly uploaded file. Confirmed answers about
additional experience are reused across future discovery sessions.

Drafts retain evidence and profile snapshots. `stale_evidence_ids` identifies
changed dependencies; the previous content is not silently regenerated.
`POST /evidence-drafts/{id}/revise` queues a **new** draft from current evidence.
`POST /evidence-drafts/{id}/submit` marks a completed, current copy as a historical
submitted version; this records status only and does not send an application.
Submitted copies remain readable/exportable after later corrections.

Discovery drafts export structured DOCX/PDF from snapshots. Rewriting an old
LaTeX source is not supported for these drafts, because it could preserve
superseded claims.

## Factual safeguards and current scope

- Questions start with relevant work, then clarify ownership and propose terms
  such as caching, retries, monitoring, or evaluation for confirmation. A missing
  required skill can occupy the final question. Selection and interpretation
  suggestions currently use deterministic rules, not an open-ended interviewer.
- Every question explains how answering it improves the resume. Skipping never
  creates evidence or extra questions beyond the session cap.
- Tutorial, familiarity, and team-only evidence remains in the catalog and is
  excluded from personal achievement bullets. Unclarified original bullets can
  retain their original wording; they are not proof of technical depth.
- Each rewrite sees only its own source and confirmed context. Knowing a skill
  elsewhere in the profile does not establish its use in this job/project.
- Added numbers/units and technologies are checked, followed by semantic model
  verification. Unavailable, invalid, or failed verification rolls back the rewrite
  and clears its change log. Model verification is a safeguard, not proof that a
  candidate's original statements are true.
- Parsing failures never produce fabricated example skills, employers, education,
  or metrics. Extracted resume claims must also occur in the uploaded text.
- Match scores are internal estimates, not employer ATS scores or a guaranteed
  90+. Missing dates never become assumed years of experience.
- This milestone does not implement company web research, page-length-aware
  selection/pinning, or claim-specific interview cards. New discovery drafts also
  leave generic recruiter predictions and application assets empty rather than
  publishing unverified auxiliary claims.

## Tests

```sh
pip install -r requirements-dev.txt
OPENAI_API_KEY='' PYTHONPATH=. python -m pytest tests -q
```

The suite uses an isolated SQLite database and mocked queue/model calls for API
lifecycle tests, including a direct worker execution and real DOCX/PDF generation.
It does not exercise a live model, Redis delivery, PostgreSQL locking, or pgvector
retrieval. No external calls or production data are needed for these tests.
