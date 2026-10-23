import { api } from "@/lib/careerproof/api";
export type ClaimData = {
  text: string;
  association: string;
  role: string;
  kind:
    | "experience"
    | "project"
    | "skill"
    | "dates"
    | "education"
    | "achievement"
    | "certification";
  technologies: string[];
  metrics: string[];
  dates: string;
  contribution: string;
  temporal_status: "unknown" | "planned" | "in_progress" | "completed";
  tags: string[];
};
export type CatalogSource = {
  id: number;
  filename: string;
  kind: string;
  resume_id: number | null;
  sha256: string;
  quote: string;
  start: number | null;
  end: number | null;
  revision: number;
};
export type Claim = {
  id: number;
  revision: number;
  data: ClaimData;
  approval: string;
  verification: string;
  confidence_indicator: string;
  conflict_ids: number[];
  sources: CatalogSource[];
  history: Record<string, unknown>[];
};
export type Conflict = {
  id: number;
  kind: string;
  claim_ids: number[];
  question: string;
  benefit: string;
  state: string;
  resolution: Record<string, unknown> | null;
};
export type CatalogSummary = { id: number; name: string; revision: number };
export type Catalog = CatalogSummary & {
  claims: Claim[];
  conflicts: Conflict[];
  events: {
    id: number;
    claim_id: number | null;
    action: string;
    actor: string;
    created_at: string | null;
    details: Record<string, unknown>;
  }[];
};
export const catalogApi = {
  list: () => api<CatalogSummary[]>("/catalogs"),
  get: (id: number) => api<Catalog>(`/catalogs/${id}`),
  create: (name: string) => api<Catalog>("/catalogs", "POST", { name }),
  import: (catalog: Catalog, resume_ids: number[]) =>
    api<Catalog>(`/catalogs/${catalog.id}/imports`, "POST", {
      resume_ids,
      revision: catalog.revision,
      same_candidate_confirmed: true,
    }),
  action: (
    catalog: Catalog,
    claim: Claim,
    action: string,
    extra: Record<string, unknown>,
  ) =>
    api<Catalog>(`/catalogs/${catalog.id}/claims/${claim.id}/actions`, "POST", {
      catalog_revision: catalog.revision,
      claim_revision: claim.revision,
      action,
      ...extra,
    }),
  resolve: (
    catalog: Catalog,
    conflict: Conflict,
    choice: string,
    selected_claim_id: number | null,
    reason: string,
  ) =>
    api<Catalog>(
      `/catalogs/${catalog.id}/conflicts/${conflict.id}/resolve`,
      "POST",
      { catalog_revision: catalog.revision, choice, selected_claim_id, reason },
    ),
  artifact: (
    catalog: Catalog,
    claim: Claim,
    payload: Record<string, unknown>,
  ) =>
    api<Catalog>(
      `/catalogs/${catalog.id}/claims/${claim.id}/artifacts`,
      "POST",
      {
        catalog_revision: catalog.revision,
        claim_revision: claim.revision,
        ...payload,
      },
    ),
};
