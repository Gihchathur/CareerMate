import type {
  CandidateProfile,
  CvStatus,
  JobMatchResult,
  JobResult,
} from "./types";

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();
export const API_BASE = (configuredApiUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");

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

export async function getHealth(): Promise<{ status: string; service: string }> {
  return request("/api/health");
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

export async function searchJobs(
  query: string,
  location: string,
  limit = 20,
): Promise<{ jobs: JobResult[]; total: number; returned: number; saved_total: number }> {
  const params = new URLSearchParams({ query, location, limit: String(limit) });
  return request(`/api/jobs/search?${params.toString()}`);
}

export async function matchJobs(
  limit: number,
  jobIds: string[],
): Promise<{ jobs: JobMatchResult[]; total_saved: number; analyzed: number }> {
  const params = new URLSearchParams({ limit: String(limit) });
  jobIds.forEach((id) => params.append("job_ids", id));
  return request(`/api/jobs/matches?${params.toString()}`);
}
