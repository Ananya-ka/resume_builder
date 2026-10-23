import { api } from "@/lib/careerproof/api";
import type {
  JobVersion,
  AnalysisRun,
  CreateJobPayload,
  AnalyzeJobPayload,
} from "./types";

export const jdApi = {
  createOrUpdateJob: (payload: CreateJobPayload) =>
    api<JobVersion>("/jd/jobs", "POST", payload),

  listJobs: () =>
    api<JobVersion[]>("/jd/jobs"),

  getJob: (jobId: number) =>
    api<JobVersion>(`/jd/jobs/${jobId}`),

  getJobVersions: (jobId: number) =>
    api<JobVersion[]>(`/jd/jobs/${jobId}/versions`),

  analyze: (payload: AnalyzeJobPayload) =>
    api<AnalysisRun>("/jd/analyze", "POST", payload),

  getAnalysis: (analysisId: number) =>
    api<AnalysisRun>(`/jd/analyses/${analysisId}`),

  listCatalogAnalyses: (catalogId: number) =>
    api<AnalysisRun[]>(`/jd/catalogs/${catalogId}/analyses`),
};
