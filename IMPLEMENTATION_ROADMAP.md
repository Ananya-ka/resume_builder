# CareerProof: implementation roadmap

Planning only, 2026-10-23. No migrations, dependency changes or application refactor have been executed. See [current-state audit](CURRENT_STATE_AUDIT.md), [finding register](GAP_ANALYSIS.md), and [proposed architecture/contracts](TARGET_ARCHITECTURE.md).

## Delivery strategy

Restore one coherent evidence-first vertical slice, then strengthen its data model. Preserve the current light design and reuse working backend/legacy UI behavior. Do not start by adding new scores, three autonomous agents, a separate vector platform, or another frontend. Evidence Catalog, Objection Engine, Gap Resolver, and explicit claim approval are release-critical; outreach/analytics/ATS enhancements are secondary.

Recommended sequence: **P0 containment → P1 catalog → P2 requirements/objections → P3 gap resolution and approval → P4 exact-version resume/export/defense → P5 consolidation**. Frontend extraction accompanies each phase, rather than preceding it as an untestable rewrite. Phases are dependency gates, not promises of calendar duration; estimate after fixture and migration discovery.

## Phase 0 — restore truthful behavior and containment

**Findings:** F01–F06, F13–F16, F25–F26. **Prerequisite:** none beyond an isolated development/test environment.

Reuse and change:

- Extract a `useApplicationWorkflow` adapter from `LiveWorkspace.submitAnswer`, `reviewClaim`, conflict resolution and draft handlers. Main `Workspace.handleTailorJob` must retain returned session state, handle parsing/reviewing/discovering/ready, and call optimize only on ready.
- Wire main Gap Resolver to `/discovery/{id}/answers`; main Studio to `/evidence-drafts/{id}/review` with expected_text. Keep existing backend functions and validation. Show the server's question benefit; no default two-question placeholders.
- Separate sample jobs/fit percentages/applications into explicit demo mode. Remove invented evidence skills and unsupported Verified badges in `loadBackendData`. Empty/error/loading are distinct.
- Preserve dirty edits and selected candidate/draft during refresh. Replace success-after-15-seconds behavior with actual server terminal status. A failed queue/provider call cannot produce a success toast.
- Repair `track_draft_application` ownership checks; implement authentication before any shared deployment. Explicit local-development mode may retain a test identity, but not production default header trust.
- Fail closed on unknown/missing approval states in `export_profile`/`submit`. Temporarily disable one-page semantic shortening until it returns a reviewable version; allow layout-only rendering and existing keep/ask policy.
- Update the runnable browser journey to the actual root route and legacy route independently; do not mask missing APIs with fixtures in the integration suite.

**Acceptance gate:**

1. Same user uploads two resume versions; parse completion is awaited; merged profile is shown; a conflict is resolved; one necessary question is answered and remains after refresh; draft is generated, edited, accepted and exported with matching wording.
2. A fully supported JD produces zero questions and reaches ready without a forced questionnaire. A provider outage is clearly labeled and cannot silently solicit unrelated questions.
3. Browser refresh does not erase a persisted answer; selecting another draft does not get overwritten by polling; dirty text prompts before replacement.
4. Editing a draft changes server state; PDF contains that accepted edit; pending/unknown review states return 409.
5. Cross-user optimization ID in tracking returns 404. Invalid authentication outside development returns 401.
6. Sample jobs never appear as live job analyses; every displayed skill/verification label is source-derived and semantically accurate.

**Risks:** pending existing drafts may no longer export until reviewed; communicate a review-required state. Main UI and legacy UI have different DTO assumptions; adapter tests must precede removing either path. No schema rewrite needed for most bridge work.

## Phase 1 — candidate-scoped Evidence Catalog

**Findings:** F07–F09, F15, F17–F19, F24. **Dependencies:** Phase 0 identity/owner boundaries; migrations M000–M002.

Reuse `DocumentExtractor`, `StructuredResumeParser`, `validate_resume_parse`, existing extraction/identity tests and `merge_profile`. Implement source objects, immutable parse runs/spans, explicit candidates/engagements, atomic claim versions and support relations. `CandidateEvidence` becomes a compatibility projection during rollout, not a deleted starting point.

Tasks:

- Route all persistent uploads, including `ats.upload_resume_for_ats`, through one pipeline. Scanner-only ephemeral text must not create “ready verified” library records.
- Persist the original file hash/object reference and extraction quote locators. Reparse writes a new parse run; preserve old bullet/claim references through mapping.
- Extract claim atoms from each achievement conservatively, preserving original text, owner, temporal status and metrics. If extraction cannot confidently split, retain an unapproved compound proposal for review; do not invent atomic facts.
- Exact dedup may suggest a merge; semantic similarity only proposes candidates. Do not merge different projects with the same numbers or identical text absent attribution confirmation.
- Convert source/body citations to navigable claim support. Store unsupported fields as unknown. A confirmed fact without an uploaded source uses a timestamped explicit user confirmation as its source.
- Backfill legacy revisions/decisions with immutable mapping; do not infer real-world verification or approval from depth flags. Quarantine ambiguous candidate identity. Keep historical snapshots unchanged.
- Introduce `CatalogPage`, `ClaimDrawer`, `ConflictReview`, `ClaimApprovalPanel`, with candidate-scoped query keys.

**Acceptance gate:**

- Catalog is available without creating a JD or discovery session.
- Every export-eligible claim has supported fields, stable engagement, approved current version and no unresolved conflict.
- Two resumes describing the same achievement produce one canonical claim family with both source links; different employers/projects remain distinct.
- A “40% ingestion” correction never attaches to a chatbot; old version stays accessible; only dependent editable drafts are marked stale.
- Uploaded resumes of two different people under one account remain separate in UI and APIs, even with missing email. Email similarity only prompts identity review.
- Reparse and migration reruns do not duplicate canonical claims or break existing references. Missing original bytes are explicitly reported, not recreated.

**Risks/dependencies:** object retention/privacy policy; historical source bytes may not exist; all-field grounding is stricter than current literal-presence validation. Add Alembic and storage adapter; do not add a new retrieval service yet.

## Phase 2 — grounded requirements and three-persona objections

**Findings:** F10–F12, F20, F23. **Dependencies:** Phase 1 versioned catalog; M003 requirement/analysis tables.

Reuse `JDParser`, `ATSMatchingEngine` canonicalization and `TenureMatcher`. Keep `ObjectionEngine` rule detectors as explainable signals; replace guessed years and confidence promotion. Introduce durable job versions, quoted requirements, mappings and analysis snapshots before resume generation.

Tasks:

- Typed JD parser output with quote validation and required/preferred/unknown distinctions, including alternatives and negation. Changed JD text creates a new version even when company and title match.
- Match complete catalog against requirements; separately record which claims appear in the selected resume. Preserve skill breadth without treating keyword presence as professional proof.
- Produce Recruiter, Hiring Manager and Technical Interviewer objections only when there is a grounded issue. Three panels may be empty; no quota of objections per persona.
- Each objection links requirement IDs, claim versions, uncertainty, action and detector/model basis. No unrelated URL upgrades another claim; numeric results do not imply measured methodology.
- Use chronology-derived tenure with unknown intervals retained. Hard constraints require mandatory source wording and relevant qualification type; no inference of citizenship or eligibility from absence.
- Add evaluation traces and bounded model-call budgets. Rules and LLM outputs are distinguishable in the API and UI; model failure returns partial/failed analysis, not invented results.

**Acceptance gate:**

- A preferred master's degree is not flagged as mandatory; an unrelated degree cannot satisfy an explicitly required license/credential.
- Multiple overlapping jobs produce the same tenure result in ATS diagnostics and objection analysis.
- Adding a repository URL unrelated to Redis leaves Redis's support classification unchanged.
- A source containing “planned Kubernetes deployment” never becomes operational Kubernetes experience.
- All surfaced objections have valid, inspectable requirement/support references; none use fabricated JD triggers or inferred facts as source quotations.
- Analysis of complete catalog does not mistake an omitted resume bullet for missing candidate experience.

**Risks:** deterministic rules currently encode behavior tests endorse; revise policy tests before replacing results. Exact matching may miss synonyms; evaluate recall without relaxing attribution or allowing implied technologies.

## Phase 3 — stateful four-bucket Gap Resolver and approval

**Findings:** F02, F12–F13, F15. **Dependencies:** Phases 1–2 and M003 discovery records.

Reuse `llm_next_question` input checks, `apply_answer`, `source_text`, `evidence_bullet`, revision conflicts and existing answer API semantics. Extract user-confirmed facts from answers into pending claim versions, with an explicit approval surface before drafting.

Tasks:

- Give each gap a stable ID, A/B/C/D bucket, provisional state, requirement linkage and resolution history.
- A: select/clarify existing evidence. B: confirm transferable work with honest wording. C: distinguish unknown from denied experience, offer deferred proof tasks. D: record met/not-met/unknown eligibility without rewriting it away.
- Questions are selected across the current analysis, not separately per persona; use all sources/prior confirmed answers first. Persist skipped/denied topics and exact interpretation confirmations.
- Ask 0–5, fifth critical-only, with precise benefit and decision impact. Do not force metrics or generic ownership questions when evidence is sufficient.
- Explicitly ingest project_notes as candidate-authored pending evidence with engagement and provenance, or remove unsupported input until available.
- Introduce claim factual approval before resume generation, separate from draft wording approval. Approving revision 1 cannot approve revision 2 implicitly.
- Proof tasks remain plans until a new source/confirmation establishes completion and scope. No tutorial-to-production promotion.

**Acceptance gate:**

- Fixtures demonstrate each bucket's distinct resolution behavior; reload restores answers, unresolved gaps and approval status.
- A candidate can decline a skill question and continue without invented skill, repeated prompt or fake completion.
- A complete profile asks zero questions; a sparse profile asks at most five, every one grounded in a material JD requirement, with a benefit displayed.
- “That sounds like caching” remains a proposal until separately confirmed; rejecting it prevents that term from entering generated wording.
- A newly discovered outcome carries its actual employer/project, metric and personal contribution; user can correct/reject before generation.
- New application for the same candidate reuses applicable confirmed answers; another candidate cannot inherit them.

**Risks:** confirmation UI can become burdensome. Group related atoms in achievement-level review, while recording version-specific decisions and supporting bulk approval only for visible, supported facts. Do not auto-check boxes to reduce friction.

## Phase 4 — exact-version tailoring, export and interview defense

**Findings:** F03, F16–F18, F21, F27. **Dependencies:** approved catalog and gap dispositions; M004/M005.

Reuse `ResumeOptimizer`, `FactVerifier`, `pdf_export.selected_profile/compile_export/check_readability`, `document_generator.render_latex_resume`, existing default template, and source-linked defense card patterns.

Tasks:

- Build deterministic generation input from approved current claim versions and immutable JD/analysis snapshots. Preserve source-to-output atom mappings.
- Retain conservative rollback, strengthen metric bindings and ownership/temporal validations. Rename machine verification results to reflect entailment, not externally proven truth.
- Store selection reasons, omitted evidence, pinned items and output versions. Review accepts edits and inclusion changes; export content is a fixed approved hash.
- One-page shortening creates a proposed derived version with all wording/removal changes visible. User can accept a longer document rather than reducing font below readability limits.
- Run isolated render jobs and display actual generated PDF. Check content preservation, clipping, font sizes and page count. Store exact export bytes/hash; a download never invokes tailoring.
- Defense cards cite exact selected resume wording, claim versions, known scope and unknowns. Save practice answers; propose factual corrections rather than silently modifying the catalog. Avoid unconditional “truthful” feedback based on keywords.

**Acceptance gate:**

- Every substantive exported clause maps to approved supported claim versions; no unrelated metric/tool/ownership is introduced across roles.
- One-page edit cannot bypass review; two downloads of the same export artifact produce identical hashes.
- Changing a source claim invalidates current drafts, preserves submitted PDF bytes and exposes affected versions.
- Actual preview and downloaded PDF match; long names/education/Unicode and one-/two-page fixtures preserve factual content and attribution.
- Render tests reject forbidden file/network access and excessive resources; compiler cannot read model keys or DB credentials.
- Defense answers persist and feedback distinguishes unsupported assertions from unknown details. “No warning found” is not a truth certification.

**Risks:** LaTeX template flexibility vs isolation; font/Unicode support; legacy submitted artifact bytes may be absent. Retain historical metadata and clearly mark unavailable originals.

## Phase 5 — consolidate frontend, contracts and operations

**Findings:** F22–F26. **Dependencies:** earlier vertical slices accepted; M005–M006.

- Complete feature-based routing and modules described in TARGET_ARCHITECTURE. `Workspace` becomes shell/layout composition, not API/data/rendering for every feature. Remove duplicate workflow logic only after feature parity tests.
- Generate TS DTOs from typed API contracts; consolidate errors/query keys and stale-edit handling. Keep reusable legacy views behind adapters until migrated.
- Connect Kanban to real applications and exact resume/export versions; add outcome-event history. Label heatmap as descriptive association with sample size, not evidence quality or causal hiring success.
- Introduce outbox, job leases/heartbeats/recovery, idempotent ingestion/generation and bounded retries. No synchronous model call under long-lived DB locks; no raw upload bytes in Redis payload.
- Retire `KnowledgeBase` duplication and ATS-specific persistent ingestion only after migration reconciliation. Keep ATS diagnostics available without centering product navigation on score maximization.
- Update README, endpoint examples, run commands and workspace documentation to actual behavior. Add isolated PostgreSQL/Redis/worker/browser CI; lock reproducible dependencies and review updates separately from feature work.

**Acceptance gate:**

- Route refresh/back navigation preserves candidate/job/draft context; every feature can be mounted with a test repository independently of the giant workspace.
- Source imports from feature folders do not create circular dependencies; views cannot import sample fixtures in API mode.
- Worker termination during processing is recovered by lease expiry without duplicate versions or permanent processing state.
- Concurrent correction/approval/export requests yield one valid revision or 409, never stale approval.
- Migration dry run and rerun reconcile counts/hashes and history; rollback of UI/read path preserves new events.
- Browser workflow uses actual test backend/worker/storage, no mocked `/api/**`, and includes zero-question path, conflicts, answers, review, correction and exact export download.

## Work package / dependency matrix

| Package | Reuse | Proposed dependency | Release risk |
|---|---|---|---|
| Identity and API trust | Existing owner filters / owned helper | Verified auth principal; candidate scoping | P0 before shared deployment; header impersonation otherwise persists. |
| Catalog | CandidateEvidence history, merge_profile, extractor | M000–M002, object storage | Ambiguous legacy identity/source data must not be auto-approved. |
| Requirements and objections | JDParser, ObjectionEngine, TenureMatcher | M003, typed provider interface | Must replace tests that reward false confidence rather than preserving them. |
| Gap workflow | Session answer validation, apply_answer, revision handling | Claim approval events, gap states | Repeated questions and unsupported inferred terminology. |
| Studio/export | review_claim, FactVerifier, renderer/readability | M004, immutable artifacts, renderer isolation | Post-review changes and unsaved local edits. |
| Defense | Pattern probes, source anchors | Persisted attempts/current claim versions | Template assumptions presented as candidate facts. |
| Frontend | Light CSS/primitives and reusable careerproof components | Typed adapter/query layer; optional cache library | Large replacement diff; use small vertical migrations. |
| Async reliability | Existing Celery/Redis | M005 outbox/leases; storage refs | Duplicates, stranded jobs, expensive serial model calls. |

## Evaluation and release evidence

Use a versioned, consented/synthetic source corpus with ground truth and explicit candidate confirmations. Preserve test manifests, source hashes, model/prompt versions, expected requirement mappings and final approved exports. Compare against a well-written single-model baseline using the same allowed inputs; do not optimize only for ATS score.

| Measure | Method and acceptance expectation |
|---|---|
| Unsupported substantive claims | Human-reviewed exported claim/source pairs plus automated provenance checks; **zero in release regression fixtures**. This is a test gate, not a promise of perfect future model behavior. |
| Wrong attribution | Swapped metrics/projects, same employer/different role, team-only work, multiple candidates; zero incorrect bindings in adversarial fixtures. |
| Relevant evidence recall | Annotated relevant achievements across all uploaded versions; report misses, denominator, baseline and uncertainty. Set launch threshold after corpus measurement, not invented today. |
| Question necessity | Review each question's explicit requirement and possible effect; all questions grounded; zero unnecessary questions on complete-evidence fixtures; maximum five enforced server-side. |
| Correction persistence | Change achievement metric/owner, regenerate, switch JD and reload; old fact never reappears in current output, submitted historical artifact unchanged. |
| Approval integrity | Pending/rejected/stale/unknown facts and wording cannot export; approve exact hashes; concurrency tests return 409 when expected version changed. |
| Model robustness | Invalid JSON/IDs, hallucinated employer, unavailable service, prompt injection in resume/JD, partial timeout; explicit failure/degraded state, never synthetic success. |
| Rendering | Page count/readability/content comparison with representative names/education/skills; approve every semantic compaction change. |
| Latency/cost | Capture per-stage p50/p95, token usage, call count, queue delay on fixed corpus; establish budgets from measurements before committing numerical SLAs. |
| Migration integrity | Idempotent backfill, foreign-key scope, quote hashes, approval provenance and historical snapshot hashes; unresolved records explicitly reported. |

## Audit verification results and limits

Executed without modifying source or installing dependencies:

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests -q -p no:cacheprovider`: Python 3.13 collection blocked by missing SQLAlchemy, python-docx and pypdf; eight collection errors.
2. Same interpreter, eight compatible test files (objections, defense, analytics, outreach, ATS matcher, rule engine, candidate profile, fact verifier): **43 passed in 0.70s**.
3. `/opt/anaconda3/bin/python3` with the same full-suite flags: **107 passed, 10 failed, 9 warnings in 14.73s**. Failures are in `tests/test_ats_checker.py`; local PostgreSQL access at port 5433 was blocked (`Operation not permitted`). This does not establish those tests fail in a properly configured environment, nor establish that they pass.

Tests were not rerun with unrestricted access to the developer database because `test_ats_checker.py::db_session` uses the configured application database, several tests assume existing records (including fallback IDs 17 and 1), and its upload endpoint tests can persist library records; a dedicated disposable, seeded test database is required first. No live model quality, deployed auth, browser flow or renderer isolation is certified here. Current frontend browser tests have obsolete selectors/routes noted in F26. The existing README's all-passing test claim must not be used as this audit's verification result.

## Definition of product completion

A candidate can ingest multiple resume versions, inspect a sourced unified catalog, resolve conflicting facts, analyze a real JD through three evidence-grounded perspectives, answer only necessary questions, approve exact claim versions, review truthful tailored wording, download the exact approved readable artifact and practice its actual claims. Corrections persist into future applications while submitted history remains intact. Every displayed save, verification status and readiness message represents persisted, inspectable state.

This roadmap intentionally does not authorize or implement application changes; it makes those changes concrete and reviewable for the next engineering phase.
