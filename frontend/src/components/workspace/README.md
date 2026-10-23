# CareerProof workspace

The `/` route is a local, interactive product demo. `/legacy` retains the previous workspace, including its connected API mode.

- `workspace.tsx`: navigation and workspace interactions, role-specific drafts, local answer and application persistence.
- `primitives.tsx`: shadcn-style composable Button and accessible Radix dialog/drawer primitives.
- `workspace.css`: scoped responsive graphite/violet design system.
- `../../lib/workspace/data.ts`: typed sample candidate, role, evidence, objection, and application records. Replace these with API DTO adapters when connecting the new UI.
- `../../lib/workspace/pdf.ts`: real client-side PDF generation with pagination and Modern/Classic templates.

Data lives under the browser storage key `careerproof-premium-v1`. Fit and confidence values are illustrative, not computed hiring predictions. Saving an answer does not automatically substantiate or rewrite a resume claim. Current sample references represent mock source documents, not uploaded files. Display name is a workspace preference; the sample resume is Alex Morgan's.

Checks: `npx tsc --noEmit`, targeted ESLint, `node tests/premium-workspace.mjs`, and `node tests/premium-accessibility.mjs`. Browser checks use the local server at port 3001 and installed Chrome. `npm run build -- --webpack` provides a fallback when a sandbox blocks Turbopack's internal process/port binding.
