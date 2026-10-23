export type RequirementCategory =
  | "mandatory_skill"
  | "preferred_skill"
  | "responsibility"
  | "education"
  | "experience"
  | "seniority"
  | "domain"
  | "eligibility_constraint";

export type MatchStatus = "direct" | "transferable" | "missing" | "unresolved";

export type JobRequirement = {
  id: number;
  category: RequirementCategory;
  title: string;
  verbatim_quote: string;
  start_offset: number;
  end_offset: number;
  is_mandatory: boolean;
  importance: string;
  normalized_terms: string[];
  dependencies: string[];
  is_ambiguous: boolean;
  ambiguity_explanation?: string | null;
};

export type JobVersion = {
  id: number;
  job_id: number;
  role_title: string;
  company_name: string;
  raw_text: string;
  text_hash: string;
  version_number: number;
  target_domain?: string | null;
  location?: string | null;
  requirements: JobRequirement[];
  created_at?: string | null;
};

export type TransferableDetail = {
  candidate_technology: string;
  target_technology: string;
  cluster_name: string;
  rationale: string;
};

export type MatchedClaimSnapshot = {
  id: number;
  text: string;
  association?: string;
  role?: string;
  kind?: string;
  technologies?: string[];
  metrics?: string[];
  contribution?: string;
  dates?: string;
  sources?: {
    filename: string;
    quote: string;
    start?: number | null;
    end?: number | null;
  }[];
};

export type RequirementMatch = {
  id: number;
  requirement_id: number;
  requirement: JobRequirement;
  match_status: MatchStatus;
  matched_claim_ids: number[];
  matched_claims: MatchedClaimSnapshot[];
  candidate_depth?: string | null;
  score_rationale: string;
  transferable_details?: TransferableDetail | null;
  clarification_question?: string | null;
};

export type AnalysisSummary = {
  total_requirements: number;
  mandatory_total: number;
  preferred_total: number;
  direct_matches: number;
  transferable_matches: number;
  missing_requirements: number;
  unresolved_requirements: number;
  direct_match_pct: number;
  coverage_pct: number;
};

export type AnalysisRun = {
  id: number;
  job_version_id: number;
  catalog_id: number;
  catalog_revision: number;
  status: string;
  summary: AnalysisSummary;
  matches: RequirementMatch[];
  created_at?: string | null;
};

export type CreateJobPayload = {
  role_title: string;
  company_name: string;
  raw_text: string;
  target_domain?: string;
  location?: string;
};

export type AnalyzeJobPayload = {
  job_id: number;
  catalog_id: number;
  job_version_id?: number;
};
