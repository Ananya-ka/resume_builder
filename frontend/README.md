# CareerProof frontend

Run `npm install` and `npm run dev` in this directory. Configure
`NEXT_PUBLIC_API_URL` to point to the backend (default: `http://localhost:8000/api`).
The API, database, Redis, and worker must be running for parsing and tailoring.

The application opens directly to resume upload. Add up to three versions of the
same candidate's resume, optionally add project notes, enter the target role and
job description, and continue. Discovery asks only necessary questions before
creating a tailored draft. Saved drafts, evidence corrections, and exports use
the backend.

Run `npx tsc --noEmit` for type checks. `npm run test:journey` runs the entry-flow
browser smoke test against `BASE_URL` (default `http://127.0.0.1:3000`). It uses
mocked API responses so it does not upload personal data or call OpenAI.
