# OpenAI processing

Set `OPENAI_API_KEY` in `backend/.env`. The default text model is the pinned
`gpt-4.1-2025-04-14` snapshot; `OPENAI_MODEL` can override it with a model that
supports Chat Completions, JSON mode, and temperature. Embeddings use
`text-embedding-3-large` (3072 dimensions, matching the database schema).

Configuration priority is process environment, then `backend/.env`, then the
project root `.env`. Docker Compose loads `backend/.env` into both API and worker
containers while keeping its container database and Redis addresses.

Restart both the API and Celery worker after changing configuration. Re-upload
previously parsed documents to run them through the new LLM parsing flow.

PDF/DOCX extraction, PDF rendering, factual validation, and score calculations
remain deterministic. OpenAI handles semantic parsing, bullet metadata,
tailoring, question wording, semantic verification, and application writing.
Discovery selection/confirmation rules enforce zero to five JD-relevant questions; the fifth requires a critical unresolved need.
API failures fail processing rather than returning mock or local AI results.
The system status endpoint reports configuration, not a successful provider
health check. Scores are internal alignment measures, not guaranteed ATS scores.
