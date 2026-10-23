# Evidence-based tailoring

The server workspace keeps the existing upload, discovery, review and export UI.
The separate fictional demo remains available and does not call the model.

1. Select resumes for one candidate. Ready uploads with the same exact parsed
   email are included automatically; unrelated candidates are never merged just
   because the uploader's account is the same. The UI shows the included sources.
2. The combined profile merges skills, education, contacts and job/project
   metadata with source references. Equivalent evidence is deduplicated;
   possible metric/attribution conflicts and differing metadata require a choice.
   Choices persist in the new `profile_decisions` table. Startup creates this
   table using the existing database initialization path.
3. Discovery receives the complete profile plus confirmed evidence. It asks
   zero to five JD-specific questions with a stated benefit. The fifth requires
   a critical unresolved need. Profile conflicts are resolved before discovery.
4. All eligible achievements go through factual rewriting and relevance ranking.
   The first selection uses a word budget and limits repetition per role. Omitted
   proposals remain available. Skills are grouped without adding new skills.
5. Each draft claim stores its source references, evidence context, proposed
   wording, selection reason and review state. Review supports accept, edit,
   revert, include and omit. Edits must pass verification against the frozen
   source achievement; new facts require an explicit evidence correction.
6. Export and submission require review of included claims. Corrections flag
   affected drafts; submitted versions stay immutable. Export respects the
   selected claims. PDFs are compiled before counting pages and checking clipping
   and small text. Concise copies retain factual verification; saved drafts are
   unchanged. If one page cannot fit readably, export reports the limitation.

Restart the API and worker after updating. Existing legacy drafts keep their
stored content; generate a new draft to use the new selection/review fields.
Model-quality evaluation still requires valid OpenAI credentials and realistic
candidate/JD examples. Unit and mocked browser tests do not establish model quality.
