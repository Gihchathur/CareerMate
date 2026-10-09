export type CandidatePersonal = {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
  portfolio: string;
};

export type Experience = {
  job_title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  description: string[];
};

export type Education = {
  degree: string;
  institution: string;
  location: string;
  start_date: string;
  end_date: string;
};

export type CandidateProfile = {
  personal: CandidatePersonal;
  summary: string;
  skills: string[];
  experience: Experience[];
  education: Education[];
  certifications: string[];
  languages: string[];
};

export type CvStatus = {
  uploaded: boolean;
  extracted_text_characters: number;
  profile_saved: boolean;
};

export type WorkMode = "any" | "remote" | "hybrid" | "on_site";
export type DetectedWorkMode = Exclude<WorkMode, "any"> | "unknown";
export type JobSourceId = "jobtech_links" | "greenhouse" | "lever" | "teamtailor";

export type JobSourceStatus = {
  configured: boolean;
  employers: number | null;
  requires_api_key: boolean;
  credentials_ready?: boolean;
  missing_credentials?: number;
};

export type JobSourcesResponse = {
  success: boolean;
  sources: Record<JobSourceId, JobSourceStatus>;
};

export type JobResult = {
  id: string;
  source: string;
  source_id: string;
  title: string;
  company: string;
  location: string;
  description: string;
  published_at: string;
  source_url: string;
  apply_url: string;
  city?: string;
  country?: string;
  work_mode?: DetectedWorkMode;
  search_roles?: string[];
};

export type JobSearchCriteria = {
  roles: string[];
  country: string;
  city: string;
  work_mode: WorkMode;
  sources: JobSourceId[];
  limit: number;
};

export type JobSearchOptions = JobSearchCriteria & {
  offset: number;
};

export type JobSearchResponse = {
  success: boolean;
  roles: string[];
  country: string;
  city: string;
  work_mode: WorkMode;
  sources: JobSourceId[];
  configured_employer_boards: number;
  total_reported: number;
  total_is_approximate: boolean;
  offset: number;
  limit: number;
  returned: number;
  has_more: boolean;
  filtered_out: number;
  role_searches: number;
  warnings: string[];
  filter_note: string;
  saved_total: number;
  jobs: JobResult[];
};

export type RequirementCategory =
  | "skill"
  | "experience"
  | "education"
  | "certification"
  | "language"
  | "responsibility"
  | "work_mode"
  | "location"
  | "other";

export type RequirementAssessment = {
  requirement: string;
  category: RequirementCategory;
  importance: "required" | "preferred" | "unclear";
  status: "supported" | "partially_supported" | "not_evidenced";
  evidence: string;
  explanation: string;
};

export type JobMatchResult = JobResult & {
  match_score: number | null;
  match_confidence: string;
  match_method: string;
  matched_skills: string[];
  matched_requirements: string[];
  partially_matched_requirements: string[];
  missing_requirements: string[];
  requirements: RequirementAssessment[];
  match_explanation: string;
  score_note: string;
};


export type ApplicationStatus =
  | "saved"
  | "preparing"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export type ApplicationAnswer = {
  question: string;
  answer: string;
  updated_at: string;
};

export type ApplicationRecord = {
  id: string;
  job_id: string;
  company: string;
  title: string;
  location: string;
  source: string;
  job_url: string;
  job_description: string;
  status: ApplicationStatus;
  notes: string;
  follow_up_date: string;
  cover_letter: string;
  answers: ApplicationAnswer[];
  created_at: string;
  updated_at: string;
  applied_at: string;
};

export type ApplicationsResponse = {
  success: boolean;
  total: number;
  status_counts: Record<string, number>;
  applications: ApplicationRecord[];
};
