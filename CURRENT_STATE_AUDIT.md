# CareerProof: current-state audit

Audit date: 2026-10-23. Scope: repository code and tests, not a deployed-service certification. No application source, configuration, schema, or dependency changes were made for this audit. The companion documents are [gap analysis](GAP_ANALYSIS.md), [target architecture](TARGET_ARCHITECTURE.md), and [implementation roadmap](IMPLEMENTATION_ROADMAP.md).

## Executive assessment

CareerProof has a reusable evidence-aware backend, but the default workspace does not implement the intended evidence-first sequence end to end. It combines live API data with sample jobs, synthetic fit scores, local-only edits, and unsupported verification labels. The backend already has source-scoped discovery, revision history, conflicts, immutable input snapshots, and draft wording review. Those capabilities should become the shared product foundation, not be replaced.

The highest-priority repair is the path **catalog → requirements → objections → gap disposition → discovery → approved claim versions → reviewed draft**. Today discovery builds the catalog on demand, objections are largely downstream reports, and the main UI attempts optimization before discovery is ready. ATS matching is a real deterministic subsystem, but it is neither evidence verification nor a hiring prediction.

Status vocabulary used throughout:

- **Implemented:** executable behavior exists in the cited path; this does not imply production readiness or empirical AI accuracy.
- **Partial:** meaningful implementation exists, but its integration, scope, or guarantees are incomplete.
- **Mocked:** fixtures, constants, or local simulation stand in for product behavior.
- **Missing:** no implementation was found in the inspected models, routes, services, and frontend consumers.

## Repository and runtime map

| Area | Actual code and entry points | Observed responsibility |
|---|---|---|
| API bootstrap | `backend/app/main.py`: `on_startup`, `read_root` | FastAPI; registers general, discovery, ATS routers; startup initializes DB; wildcard CORS with credentials. API title still says “AI Job Application Copilot”. |
| Configuration | `backend/app/core/config.py`: `Settings` | PostgreSQL, Redis, optional OpenAI key; configured default model string is `gpt-4.1-2025-04-14`. This is a source default, not a verified deployment value. Environment files were not inspected. |
| Storage bootstrap | `backend/app/core/database.py`: `init_db`, `get_db` | SQLAlchemy sessions, `CREATE EXTENSION vector`, `Base.metadata.create_all`; no versioned migration framework found. |
| Async processing | `backend/app/worker/tasks.py`: `parse_resume_task`, `optimize_resume_task` | Celery with Redis broker/result backend; document parsing, per-bullet metadata/embeddings, draft generation, verification and scoring. |
| Infrastructure | `docker-compose.yml`; `backend/Dockerfile`; `run.sh`; `Makefile` | Compose uses pgvector **pg16**, Redis 7, API and worker; Docker runs uvicorn with `--reload`. Local launcher searches Anaconda/venv. These are development arrangements, not proof of production operations. |
| Main frontend | `frontend/src/app/page.tsx`: `Home` → `components/workspace/workspace.tsx`: `Workspace` | Current **3,743-line** client component, partly API-connected. Ten navigation entries including ATS Scanner; all feature navigation is component state. |
| Legacy frontend | `frontend/src/app/legacy/page.tsx`: `Home` → `components/careerproof/workspace.tsx`: `CareerWorkspace` | Demo shell with server-workspace option; `live-workspace.tsx`: `LiveWorkspace` is **2,020 lines**, with more complete discovery/conflict/review integration. |
| Shared UI | `components/workspace/primitives.tsx`: `Button`, `Modal`, `Badge`; `workspace.css`; `components/careerproof/ui.tsx` | Reusable Radix dialogs and light workspace styling; separate older UI system. Preserve visual design during extraction. |
| Client contracts | `frontend/src/lib/careerproof/api.ts`: `api`, `downloadExport`, `validateFiles`, DTO types | Fetch wrapper hardcodes `X-User-Id: user_test`, 120-second timeout; PDF overflow error class. Hand-maintained types, several loose `any` usages in consumers. |
| Fixtures / alternate export | `frontend/src/lib/workspace/data.ts`; `pdf.ts`: `createResume`; `lib/careerproof/fixtures.ts`, `demo-service.ts` | Sample data and browser demo logic remain. Main Workspace now uses backend exports rather than importing `createResume`; do not describe the old browser PDF path as current production behavior. |

## Database map

All current ORM entities are in `backend/app/models/schemas.py`; API DTOs are in `backend/app/schemas/schemas.py`.

| Entity | Important persisted fields | Boundary / limitation |
|---|---|---|
| `User` | string ID, email | Comment calls ID a Clerk ID; request dependency does not validate Clerk/JWT credentials. |
| `Resume` | user, name, `parsed_raw` JSON | Extraction metadata/raw text live in JSON; no immutable uploaded-object/hash model. |
| `ResumeBullet` | resume FK, company, role, section, text, technologies/keywords/metrics JSON, `Vector(3072)` | One bullet is not an atomic claim. No engagement FK, claim approval, or first-class source-span FK. |
| `KnowledgeBase` | user, category, text, metadata, embedding | Parallel evidence silo; legacy retrieval includes it, discovery does not merge it into `CandidateEvidence`. |
| `JobDescription` | user, company/role, raw JD, skill/responsibility arrays and other fields | No requirement IDs, source spans, requirement revisions or approved extraction records. |
| `CandidateEvidence` | user, revision, data/source_refs/history JSON | Useful versioned achievement precursor; no candidate FK, structured metric/ownership verification, independent approval table, or source integrity constraint. |
| `ProfileDecision` | user, candidate_key, conflict_key, choice JSON | Reused conflict choices; no declared uniqueness constraint on that logical tuple. |
| `DiscoverySession` | user/job, resume_ids/evidence_ids/questions JSON, status | Question/answer state embedded; no requirement/objection FKs or catalog snapshot version. |
| `OptimizedResume` | job/resume FKs, optimized_content JSON, scores/reports/assets | Bullet review state embedded; first resume is still the relational anchor for multi-resume drafts. |
| `EvidenceDraft` | optimization/session/user FKs, evidence/profile snapshots, stale IDs, status, submitted integer | Preserves input snapshots and historical submission state; output/history/export lineage not normalized. |
| `ApplicationTracker` | user, company/role, status, optimization FK, notes/contact fields | DB link to optimization exists; main Kanban does not consume it. No outcome-event history or immutable submitted export FK. |

## API inventory: current contracts, not proposed endpoints

All paths below begin with `/api`. Dependency `api/routes.py::get_current_user_id` trusts a caller-controlled header or defaults to `user_test`. Existing ownership filters are useful but are not authentication.

| Routes | Handler / request / result |
|---|---|
| `POST /users` | `routes.create_user(UserCreate)` → `UserOut`; caller chooses ID. |
| `POST /resumes/upload`, `/resumes/upload-batch` | `upload_resume`, `upload_resume_batch` → `persist_uploads`; multipart file/files, 1–3 files per batch, up to 10 MB each; commits queued Resume rows then queues Celery. |
| `POST /resumes/paste-text`; `GET /resumes`, `/resumes/{id}`; `DELETE /resumes/{id}` | `paste_resume`, `list_resumes`, `get_resume`, `delete_resume`; existing upload/paste lifecycle. |
| `GET /system/status` | `system_status`; configuration/service capability hints, not authenticated operational monitoring. |
| `POST /jobs/parse-file`; `POST /jobs`; `GET /jobs` | `parse_job_file`, `create_job(JobDescriptionIn)`, `list_jobs`; creating a job saves raw text; discovery/worker later parse fields. |
| `POST /discovery` | `discovery.start(StartDiscovery)` with `resume_ids[1..3]`, `job_id`, `project_notes`; returns merged profile, evidence, conflicts, questions, status, limit. `project_notes` is declared but never consumed by `start`. |
| `GET /discovery/{id}`; `POST /discovery/{id}/resolve` | `get_session`, `resolve_conflict`; choice must match a current conflict option. |
| `POST /discovery/{id}/answers` | `answer(Answer)` with question_id, answer, depth, confirm/skip, company/role/section; only active question accepted, revision checked, then advances. |
| `GET /evidence`; `PUT /evidence/{id}` | `list_evidence`, `correct(Correction)`; expected revision + content/company/role/section/depth/ownership/reason; returns evidence and affected drafts. GET is account-wide. |
| `POST /discovery/{id}/optimize`; `POST /optimize` | `optimize`, `routes.optimize_resume`; legacy request now requires matching discovery_session_id; `create_draft` requires ready/no conflicts and queues snapshot-based work. |
| `GET /evidence-drafts`; `GET /optimizations/{id}` | `list_drafts`, `routes.get_optimization`; list status vs detailed content. |
| `POST /evidence-drafts/{id}/review` | `review_claim(ReviewClaim)` with evidence_id, action (`accept/revert/edit/include/exclude`), text, expected_text; supports stale-write protection and semantic edit verification. |
| `POST /evidence-drafts/{id}/submit`, `/revise` | `submit`, `regenerate`; submit requires current completed draft and no pending included bullets; revise creates a new optimization from session. |
| `GET /discovery/{id}/objections`; `GET /evidence-drafts/{id}/objections`; `POST /evidence-drafts/{id}/mode` | `get_session_objections`, `get_draft_objections`, `set_draft_mode`; modes launch/advance; reports cached inside gap_report, not versioned analysis entities. |
| `GET /evidence-drafts/{id}/defense-cards`, `/proof-specs`, `/outreach`; `POST /evidence-drafts/{id}/evaluate-defense` | `get_draft_defense_cards`, `get_draft_proof_specs`, `get_draft_outreach`, `evaluate_draft_defense`; explanation evaluation is returned, not persisted. |
| `POST/GET /knowledge`; `DELETE /knowledge/{id}` | `add_knowledge`, `list_knowledge`, `delete_knowledge`; legacy evidence silo. |
| `POST/GET /tracker`; `PUT/DELETE /tracker/{id}`; `POST /tracker/track-draft` | CRUD in routes; `discovery.track_draft_application` accepts optimization_id/status and creates/updates linked application. Ownership omission noted in F14. |
| `GET /analytics/claim-heatmap` | `get_claim_heatmap` → `ClaimAnalyticsEngine.analyze_claims`; aggregates included claim IDs and current application statuses. |
| `GET /templates/default-latex`; `GET /optimizations/{id}/export/docx`; `GET/POST .../export/pdf`, `.../export/latex` | `get_default_latex_template`, `export_docx`, `_handle_pdf_export`, `_handle_latex_export`; PDF request supports template/custom text and ask/keep/one_page policies, emits page/omission count headers. |
| `POST /ats/check`; `GET /ats/check-existing/{resume_id}/{job_id}`, `/ats/catalog`; `POST /ats/upload-resume`, `/ats/upload-jd` | `ats.check_ats_score`, `check_existing_pair`, `get_ats_selection_catalog`, upload handlers. Raw text or stored records. README's `/api/ats/evaluate` route is **not registered**. |

## Implemented workflows and boundaries

### Ingestion and catalog: partial

`DocumentExtractor.extract` supports PDF/DOCX/TXT; layout blocks have page/bbox/source references (`TextBlock.to_dict`). `StructuredResumeParser.parse` extracts locally and retains per-entry `bullet_provenance` strings; these are not normalized source spans or carried into ResumeBullet/source-support relations. `parse_resume_task` attempts optional `ResumeParser.parse_resume_to_json` enhancement and falls back to the structured parse on failure. `validate_resume_parse` checks literal facts and, for the LLM parse, employer/project source passages. Worker metadata and embeddings are optional; “requires OpenAI” in its docstring is stale.

`discovery.start` creates/reuses CandidateEvidence **when starting a JD session**, deduplicating `evidence_key(section,company,role,content)`. It guards identities and expands same-email ready uploads, potentially beyond the request's three selected resumes. Previously answered evidence is reused through source-prefix/session identity rules. `candidate_profile.merge_profile` merges sourced profile fields, exact identity groups, and flags similar descriptions with conflicting numbers/attribution/polarity. This is not a complete universal catalog: no explicit candidate entity, no standalone claim ingestion, no atomization of bullets or durable document locator joins.

### Requirements and discovery: partial

`JDParser.parse_job_description` uses JSON-object LLM output without typed requirement validation or per-requirement quotations. `discovery.advance` calls `llm_next_question`; that function checks an exact JD quote, supported evidence ID, duplicate question topics, and a maximum of five. It can return zero questions; fifth must be critical. However `advance` falls back on `ValueError` to `next_question`, whose generic work/ownership prompts have no positive relevance threshold. Question policy therefore changes silently under provider failure.

`answer`, `apply_answer`, `source_text`, and `evidence_bullet` retain personal context; tutorial/familiarity/team-only entries are not auto-generated as achievement bullets. Corrections clear prior context and invalidate affected snapshots. Strong foundations, but not an independent approval model.

### Objections and four buckets: implemented rules, partial product workflow

`ObjectionEngine.analyze` implements three personas and unexpressed/transferable/true_deficit/hard_constraint classification, adjacent-technology maps and launch/advance behavior. It uses regex/templates/constants, **not three LLM agents**. Rules emit prose hypotheses and fixed confidence/relevance values without claim-version or requirement IDs. `get_session_objections` is available before tailoring, but `advance` does not consume its output. Session reconstructed profile entries from `merge_profile` lack bullets; this can make pre-draft analysis interpret present catalog evidence as absent from the resume.

### Drafting and approval: implemented backend, broken main UI integration

`create_draft` snapshots merged profile/evidence. `optimize_resume_task` ranks evidence, requests one proposal per source, verifies with `FactVerifier`, then selects up to 330 words and four bullets per role. `ResumeOptimizer` prompts explicitly forbid invented metrics, ownership transfer, and planned-to-completed changes. Failure falls back to unchanged source text plus heuristic relevance. `FactVerifier` checks IDs, metric/technology additions, temporal wording and semantic entailment, reverting failed proposals.

`review_claim` handles review and optimistic text checking. `submit` and `export_profile` reject pending included claims. Existing safeguards must be reused. Main `Workspace.handleTailorJob` does not retain/resolve discovery state, and editor setters do not call `review_claim`; legacy `LiveWorkspace.submitAnswer`, `reviewClaim`, conflict/optimize handlers do.

### Corrections, output and interview preparation: partial

`revise`, `correct`, `resolve_conflict`, `regenerate` preserve old snapshots, mark stale evidence, and create corrected drafts. Submitted content is not rewritten; submitted historical exports are allowed. Invalidation scans all user's drafts and generic JSON snapshots; source deletion/reparse lineage is unresolved.

`pdf_export.compile_export` renders LaTeX, counts actual PDF pages, and checks edge clipping/tiny text. `concise_export` may perform another model rewrite and remove bullets during export **after review**, without creating a newly approved artifact. This is an approval boundary gap, not evidence that PDF rendering is missing. Main HTML preview is local text and is not the exported PDF.

`InterviewDefenseEngine.generate_defense_cards` links included bullets to source IDs and supplies pattern-based probes. `evaluate_defense_explanation` scores keywords and warns on a few patterns; it does not verify complete answers or save them. Proof specs are suggested plans, not completed evidence. Outreach and claim analytics exist but should remain secondary until evidence controls are reliable.

## Tests and verification limits

Inspected tests cover ingestion/layout, literal parsing, candidate merge, source-specific verification, discovery/corrections, objections, defense, outreach, ATS/tenure, PDF policy/templates, and analytics. `tests/test_discovery.py::api` uses in-memory SQLite and mocked provider/queue behavior; `test_openai_pipeline.py` mocks responses. Passing these does not establish PostgreSQL locking, Redis delivery, real model quality or compiler safety.

Audit execution: default Python 3.13 full-suite collection failed with eight errors due to missing SQLAlchemy/python-docx/pypdf dependencies. A dependency-compatible subset of eight files ran **43 passed in 0.70s**. A separate full-suite attempt with the interpreter referenced by run.sh is recorded in the verification addendum below. No dependency installations or live LLM calls were requested for the audit.

Frontend test sources are stale against today's root route: `tests/premium-workspace.mjs` and `premium-accessibility.mjs` expect “Good morning, Alex.”; `tests/journey.mjs` defaults to `/` and expects the legacy “Try sample resumes” button while mocking `/api/**`. These are not current evidence of a real full-stack journey. Browser tests, production builds, live DB state, and production authentication were not certified in this audit.

## Documentation drift

`README.md` calls the product an enterprise/production-grade ATS engine, documents an unregistered `/api/ats/evaluate` endpoint, and shows pgvector PostgreSQL 18 while Compose uses pg16. Its “117 passed” claim is historical, not an audit result. `components/workspace/README.md` describes `/` as a local demo although current `Workspace` imports APIs. These contradictions should be corrected only in the subsequent implementation/documentation phase; this audit leaves those files untouched.

### Verification addendum

Using `/opt/anaconda3/bin/python3` (an interpreter referenced by `run.sh`) the full suite completed: **107 passed, 10 failed, 9 warnings in 14.73s**. All ten failures are ATS checker tests encountering blocked PostgreSQL access (`Operation not permitted` on localhost:5433), directly or through API startup/requests. No unrestricted developer-database rerun was performed. Read the test harness before such a rerun: `test_ats_checker.py::db_session` uses the configured database, tests assume existing records, and upload tests can persist records; use a disposable, seeded test DB. This result is not an application-wide pass or a claim that those ten tests fail when dependencies/services are available.
