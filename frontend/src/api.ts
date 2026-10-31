import type {
  ApplicationRecord,
  AIProviderSettingsInput,
  AISettingsResponse,
  AIProviderId,
  ApplicationsResponse,
  ApplicationStatus,
  ApplicationAnswer,
  BrowserDiagnostics,
  BrowserNavigationIntent,
  BrowserAnswerSuggestion,
  LocalDataSummary,
  BrowserFieldDraft,
  BrowserFormSession,
  CandidateProfile,
  CvStatus,
  JobMatchResult,
  JobResult,
  JobSearchOptions,
  JobSearchResponse,
  JobSourcesResponse,
  JobSourceConfiguration,
  JobSourceConfigurationResponse,
  JobPlatform,
  TailoredCvResponse,
  WorkMode,
  JobSourceId,
} from "./types";

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();
export const API_BASE = configuredApiUrl === "/same-origin" ? "" : (configuredApiUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");

type ApiEnvelope<T> = T & { detail?: string | Array<{ msg?: string }> };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(
      "Cannot reach CareerMate's backend. Start FastAPI at http://127.0.0.1:8000 and try again.",
    );
  }

  let payload: ApiEnvelope<T>;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new Error(`CareerMate returned an unreadable response (HTTP ${response.status}).`);
  }

  if (!response.ok) {
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join("; ")
      : detail;
    throw new Error(message || `Request failed with HTTP ${response.status}.`);
  }

  return payload;
}

export async function getLocalDataSummary(): Promise<LocalDataSummary> {
  return request<LocalDataSummary>("/api/data/summary");
}

export async function clearLocalCaches(): Promise<LocalDataSummary> {
  return request<LocalDataSummary>("/api/data/clear-cache", { method: "POST" });
}

export async function resetLocalWorkspaceData(confirmation: string): Promise<LocalDataSummary> {
  return request<LocalDataSummary>("/api/data/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation }),
  });
}

export async function getBrowserDiagnostics(): Promise<BrowserDiagnostics> {
  return request<BrowserDiagnostics>("/api/browser/diagnostics");
}


export async function getHealth(): Promise<{ status: string; service: string }> {
  return request("/api/health");
}


export async function getAiSettings(): Promise<AISettingsResponse> {
  return request<AISettingsResponse>("/api/ai/settings");
}

export async function saveAiSettings(settings: AIProviderSettingsInput): Promise<AISettingsResponse> {
  return request<AISettingsResponse>("/api/ai/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export async function testAiProvider(settings: Pick<AIProviderSettingsInput, "provider" | "model" | "base_url">): Promise<{ success: boolean; provider: AIProviderId; model: string; message: string }> {
  return request("/api/ai/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export async function getCvStatus(): Promise<CvStatus> {
  return request("/api/cv/status");
}

export async function getProfile(): Promise<CandidateProfile> {
  const result = await request<{ success: boolean; profile: CandidateProfile }>(
    "/api/cv/profile",
  );
  return result.profile;
}

export async function uploadCv(file: File): Promise<{ filename: string; characters: number; format: string }> {
  const body = new FormData();
  body.append("file", file);
  return request("/api/cv/upload", { method: "POST", body });
}

export async function analyzeCv(): Promise<CandidateProfile> {
  const result = await request<{ success: boolean; profile: CandidateProfile }>(
    "/api/cv/analyze",
    { method: "POST" },
  );
  return result.profile;
}

export async function saveProfile(profile: CandidateProfile): Promise<void> {
  await request("/api/cv/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
}

export async function getSavedJobs(): Promise<JobResult[]> {
  const result = await request<{ success: boolean; jobs: JobResult[] }>("/api/jobs");
  return result.jobs ?? [];
}

export async function getJobSources(): Promise<JobSourcesResponse> {
  return request<JobSourcesResponse>("/api/jobs/sources");
}

export async function getJobSourceConfig(): Promise<JobSourceConfigurationResponse> {
  return request<JobSourceConfigurationResponse>("/api/jobs/source-config");
}

export async function saveJobSourceConfig(config: JobSourceConfiguration): Promise<JobSourceConfigurationResponse> {
  return request<JobSourceConfigurationResponse>("/api/jobs/source-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

export async function searchJobs(options: JobSearchOptions): Promise<JobSearchResponse> {
  const params = new URLSearchParams();
  options.roles.forEach((role) => params.append("roles", role));
  options.sources.forEach((source) => params.append("sources", source));
  params.set("country", options.country);
  params.set("city", options.city);
  params.set("work_mode", options.work_mode);
  params.set("limit", String(options.limit));
  params.set("offset", String(options.offset));
  if (options.min_salary !== undefined) params.set("min_salary", String(options.min_salary));
  if (options.max_salary !== undefined) params.set("max_salary", String(options.max_salary));
  if (options.posted_within_days !== undefined) params.set("posted_within_days", String(options.posted_within_days));
  options.excluded_companies?.forEach((company) => params.append("excluded_companies", company));
  return request(`/api/jobs/search?${params.toString()}`);
}

export async function enrichJobDetails(
  jobId: string,
  forceRefresh = false,
  manualDescription?: string,
): Promise<{ success: boolean; message: string; job: JobResult }> {
  return request("/api/jobs/enrich", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_id: jobId,
      force_refresh: forceRefresh,
      ...(manualDescription === undefined ? {} : { manual_description: manualDescription }),
    }),
  });
}

export async function enrichApplicationDescription(
  applicationId: string,
): Promise<{ success: boolean; message: string; application: ApplicationRecord }> {
  return request(`/api/applications/${encodeURIComponent(applicationId)}/enrich-description`, {
    method: "POST",
  });
}

export async function matchJobs(
  limit: number,
  jobIds: string[],
): Promise<{ jobs: JobMatchResult[]; total_saved: number; analyzed: number }> {
  const params = new URLSearchParams({ limit: String(limit) });
  jobIds.forEach((id) => params.append("job_ids", id));
  return request(`/api/jobs/matches?${params.toString()}`);
}


export async function getApplications(): Promise<ApplicationsResponse> {
  return request<ApplicationsResponse>("/api/applications");
}

export async function createApplication(
  jobId: string,
  notes = "",
): Promise<{ created: boolean; message: string; application: ApplicationRecord }> {
  return request("/api/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, notes }),
  });
}

export async function updateApplication(
  applicationId: string,
  changes: {
    status?: ApplicationStatus;
    notes?: string;
    follow_up_date?: string;
    cover_letter?: string;
    answers?: ApplicationAnswer[];
  },
): Promise<ApplicationRecord> {
  const result = await request<{ success: boolean; application: ApplicationRecord }>(
    `/api/applications/${encodeURIComponent(applicationId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    },
  );
  return result.application;
}

export async function generateCoverLetter(applicationId: string): Promise<ApplicationRecord> {
  const result = await request<{ success: boolean; application: ApplicationRecord }>(
    `/api/applications/${encodeURIComponent(applicationId)}/draft-cover-letter`,
    { method: "POST" },
  );
  return result.application;
}

export async function generateApplicationAnswer(
  applicationId: string,
  question: string,
): Promise<ApplicationRecord> {
  const result = await request<{ success: boolean; application: ApplicationRecord }>(
    `/api/applications/${encodeURIComponent(applicationId)}/draft-answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    },
  );
  return result.application;
}


export async function openApplicationBrowser(applicationId: string): Promise<BrowserFormSession> {
  return request<BrowserFormSession>(`/api/applications/${encodeURIComponent(applicationId)}/browser/open`, { method: "POST" });
}

export async function scanBrowserForm(): Promise<BrowserFormSession> {
  return request<BrowserFormSession>("/api/browser/scan", { method: "POST" });
}

export async function advanceBrowserStep(
  applicationId: string,
  intent: BrowserNavigationIntent,
): Promise<BrowserFormSession> {
  return request<BrowserFormSession>(`/api/applications/${encodeURIComponent(applicationId)}/browser/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent }),
  });
}

export async function selectBrowserPage(
  applicationId: string,
  pageIndex: number,
): Promise<BrowserFormSession> {
  return request<BrowserFormSession>(`/api/applications/${encodeURIComponent(applicationId)}/browser/select-page`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page_index: pageIndex }),
  });
}

export async function suggestBrowserAnswers(
  applicationId: string,
  fieldIds: string[],
  expectedUrl?: string,
): Promise<{ success: boolean; suggestions: BrowserAnswerSuggestion[]; message: string }> {
  return request(`/api/applications/${encodeURIComponent(applicationId)}/browser/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field_ids: fieldIds, expected_url: expectedUrl }),
  });
}

export async function submitBrowserApplication(
  applicationId: string,
  confirmSubmission: boolean,
  expectedUrl?: string,
  submittedDetails: ApplicationAnswer[] = [],
): Promise<{ success: boolean; clicked: boolean; confirmation_detected: boolean; message: string; url: string; title: string }> {
  return request(`/api/applications/${encodeURIComponent(applicationId)}/browser/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_submission: confirmSubmission, expected_url: expectedUrl, submitted_details: submittedDetails }),
  });
}

export async function fillBrowserForm(
  applicationId: string,
  fields: BrowserFieldDraft[],
  expectedUrl?: string,
): Promise<{ filled_count: number; filled_field_ids?: string[]; skipped: { field_id: string; reason: string }[]; message: string }> {
  return request<{ filled_count: number; filled_field_ids?: string[]; skipped: { field_id: string; reason: string }[]; message: string }>(`/api/applications/${encodeURIComponent(applicationId)}/browser/fill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: fields.filter((field) => field.include && field.value.trim()).map(({ field_id, value }) => ({ field_id, value })), expected_url: expectedUrl }),
  });
}

export async function closeBrowserSession(): Promise<void> {
  await request("/api/browser/session", { method: "DELETE" });
}


export async function getPlatformDirectory(): Promise<{ success: boolean; total: number; platforms: JobPlatform[]; integration_note: string }> {
  return request("/api/platforms");
}

export async function tailorCvForJob(job_description: string, template: "classic" | "modern" | "compact"): Promise<TailoredCvResponse> {
  return request("/api/cv/tailor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_description, template }),
  });
}

export const TAILORED_CV_DOWNLOAD_BASE = API_BASE;

export type SavedSearch = { id: string; name: string; roles: string[]; country: string; city: string; work_mode: WorkMode; sources: JobSourceId[]; frequency: "manual" | "daily" | "weekly"; created_at: string };
export async function getSavedSearches(): Promise<{ success: boolean; searches: SavedSearch[] }> { return request("/api/searches"); }
export async function createSavedSearch(search: Omit<SavedSearch, "id" | "created_at">): Promise<{ success: boolean; search: SavedSearch }> {
  return request("/api/searches", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(search) });
}
export async function deleteSavedSearch(id: string): Promise<void> { await request(`/api/searches/${encodeURIComponent(id)}`, {method:"DELETE"}); }
export async function checkSavedSearchAlerts(id: string): Promise<{ success:boolean; new_count:number; new_jobs:JobResult[] }> {
  return request(`/api/searches/${encodeURIComponent(id)}/check-alerts`, {method:"POST"});
}

export type JobAlert = { id:string; search_id:string; search_name:string; job_id:string; title:string; company:string; location:string; url:string; found_at:string; read:boolean };
export async function getJobAlerts(): Promise<{success:boolean;alerts:JobAlert[];unread:number}> { return request("/api/alerts"); }
export async function markJobAlertRead(id:string): Promise<void> { await request(`/api/alerts/${encodeURIComponent(id)}/read`,{method:"POST"}); }

export type TailoredCvVersion = { filename:string; template:string; created_at:string; ats_score:number | null };
export async function getTailoredCvVersions(): Promise<{success:boolean;versions:TailoredCvVersion[]}> { return request("/api/cv/tailored"); }
