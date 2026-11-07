export type CandidatePersonal = {
  name: string;
  headline?: string;
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

export type Project = { name: string; year: string; description: string[]; url: string };

export type CandidateProfile = {
  personal: CandidatePersonal;
  summary: string;
  skills: string[];
  experience: Experience[];
  education: Education[];
  projects: Project[];
  achievements: string[];
  certifications: string[];
  languages: string[];
};

export type CandidateEvidence = {
  id: string;
  claim: string;
  category: "skill" | "experience" | "project" | "achievement" | "education" | "certification" | "language" | "metric" | "other";
  source_type: "cv" | "experience" | "project" | "certification" | "reference" | "manual";
  source_reference: string;
  supporting_detail: string;
  verified: boolean;
  created_at: string;
  updated_at: string;
};

export type CandidateEvidenceInput = Pick<CandidateEvidence, "claim" | "category" | "source_type" | "source_reference" | "supporting_detail">;

export type CvStatus = {
  uploaded: boolean;
  extracted_text_characters: number;
  profile_saved: boolean;
};

export type WorkMode = "any" | "remote" | "hybrid" | "on_site";
export type DetectedWorkMode = Exclude<WorkMode, "any"> | "unknown";
export type JobSourceId = "jobtech_links" | "remoteok" | "arbeitnow" | "greenhouse" | "lever" | "teamtailor" | "ashby" | "smartrecruiters" | "workable" | "recruitee" | "breezy" | "personio" | "workday";

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

export type JobBoardConfig = {
  enabled: boolean;
  company?: string;
  country?: string;
  career_url?: string;
  jobs_url?: string;
  notes?: string;
  starter_sample?: boolean;
  board_token?: string;
  site?: string;
  api_key_env?: string;
  slug?: string;
  region?: string;
};

export type JobSourceConfiguration = {
  greenhouse: JobBoardConfig[];
  lever: JobBoardConfig[];
  teamtailor: JobBoardConfig[];
  ashby: JobBoardConfig[];
  smartrecruiters: JobBoardConfig[];
  workable: JobBoardConfig[];
  recruitee: JobBoardConfig[];
  breezy: JobBoardConfig[];
  personio: JobBoardConfig[];
  workday: JobBoardConfig[];
};

export type JobSourceConfigurationResponse = {
  success: boolean;
  config: JobSourceConfiguration;
  sources: Record<JobSourceId, JobSourceStatus>;
  message?: string;
};

export type PortalHealthStatus = "live" | "empty" | "paused" | "needs_setup" | "broken" | "not_checked";

export type PortalHealthItem = {
  id: string;
  provider: keyof JobSourceConfiguration;
  provider_label: string;
  company: string;
  identifier: string;
  domain: string;
  country: string;
  career_url?: string;
  jobs_url?: string;
  notes?: string;
  enabled: boolean;
  status: PortalHealthStatus;
  job_count: number | null;
  checked_at: string | null;
  duration_ms: number | null;
  message: string;
};

export type PortalHealthSummary = {
  total: number;
  enabled: number;
  paused: number;
  live: number;
  empty: number;
  broken: number;
  needs_setup: number;
  not_checked: number;
};

export type PortalHealthResponse = {
  success: boolean;
  checked_at: string | null;
  summary: PortalHealthSummary;
  items: PortalHealthItem[];
  check_limit?: number;
};

export type JobResult = {
  id: string;
  source: string;
  source_id: string;
  /** Exact provider:company board identity attached by the backend. */
  portal_id?: string;
  portal_name?: string;
  source_fetched_at?: string;
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
  department?: string;
  team?: string;
  employment_type?: string;
  role_metadata?: string[];
  search_roles?: string[];
  description_source?: "search_result" | "original_listing";
  description_fetch_status?: "not_attempted" | "success" | "failed";
  description_fetched_at?: string;
  description_fetch_message?: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string;
};

export type JobSearchCriteria = {
  roles: string[];
  country: string;
  city: string;
  work_mode: WorkMode;
  sources: JobSourceId[];
  /** Stable provider:company identifiers for the specific employer boards selected in Explore. */
  portal_ids: string[];
  limit: number;
  min_salary?: number;
  max_salary?: number;
  posted_within_days?: number;
  excluded_companies?: string[];
};

export type JobSearchOptions = JobSearchCriteria & {
  offset: number;
  refresh_portals?: boolean;
};

export type PortalSearchCoverage = {
  portal_id: string;
  provider: string;
  company: string;
  fetched_count: number;
  role_matches: number;
  eligible_matches: number;
  returned_count: number;
  last_fetched_at?: string;
  age_seconds?: number | null;
  status: "matched" | "partial" | "stale" | "error" | "empty" | "no_role_matches" | "filtered_by_location" | string;
  warning: string;
};

export type JobSearchResponse = {
  success: boolean;
  roles: string[];
  country: string;
  city: string;
  work_mode: WorkMode;
  sources: JobSourceId[];
  portal_ids?: string[];
  configured_employer_boards: number;
  total_reported: number;
  total_is_approximate: boolean;
  offset: number;
  limit: number;
  returned: number;
  has_more: boolean;
  filtered_out: number;
  filtered_out_by?: { country: number; city: number; work_mode: number };
  role_searches: number;
  warnings: string[];
  filter_note: string;
  saved_total: number;
  discovered_this_search?: number;
  /** Complete unique inventory after role, location and advanced filters. */
  matching_jobs?: JobResult[];
  matching_jobs_count?: number;
  /** Listings that passed role/location checks but were excluded by advanced filters. */
  advanced_filtered_out?: number;
  portal_results?: PortalSearchCoverage[];
  /** Backwards-compatible page slice for older clients. */
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
  criticality?: "critical" | "important" | "nice_to_have";
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
  critical_gaps?: RequirementAssessment[];
  required_gaps_count?: number;
  recommendation?: "insufficient_evidence" | "incomplete_description" | "review_critical_gaps" | "strong_potential_fit" | "consider_after_review" | "significant_gaps";
  recommendation_label?: string;
  recommendation_explanation?: string;
  job_description_source?: "search_result" | "original_listing";
  description_complete?: boolean;
};


export type ApplicationStatus =
  | "saved"
  | "preparing"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export type JobTriageStage = "new" | "reviewing" | "shortlisted" | "skipped";

export type JobTriageRecord = {
  job_id: string;
  stage: JobTriageStage;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type JobInboxItem = { job: JobResult; triage: JobTriageRecord };
export type WorkflowInboxResponse = {
  success: boolean;
  total: number;
  counts: Record<JobTriageStage, number>;
  items: JobInboxItem[];
};

export type WorkflowEvent = {
  id: string;
  event_type: string;
  title: string;
  detail: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

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
  source_url?: string;
  job_description: string;
  job_description_source?: "search_result" | "original_listing";
  job_description_fetched_at?: string;
  job_description_fetch_status?: "not_attempted" | "success" | "failed";
  job_description_fetch_message?: string;
  status: ApplicationStatus;
  notes: string;
  follow_up_date: string;
  cover_letter: string;
  answers: ApplicationAnswer[];
  submitted_details?: ApplicationAnswer[];
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


export type BrowserFieldOption = { label: string; value: string };
export type BrowserNavigationIntent = "apply" | "continue";
export type BrowserPageInfo = { page_index: number; title: string; url: string; active: boolean };

export type BrowserFormField = {
  field_id: string;
  label: string;
  kind: string;
  required: boolean;
  placeholder: string;
  autocomplete: string;
  suggested_key: string;
  options?: BrowserFieldOption[];
  current_value?: string;
  group_name?: string;
  frame_index?: number;
};

export type BrowserFormSession = {
  success: boolean;
  active?: boolean;
  application_id: string;
  url: string;
  title: string;
  field_count: number;
  fields: BrowserFormField[];
  has_apply_action?: boolean;
  has_continue_action?: boolean;
  submit_available?: boolean;
  open_pages?: BrowserPageInfo[];
  active_page_index?: number;
  cookie_action?: string;
  message: string;
};

export type BrowserFieldDraft = BrowserFormField & { include: boolean; value: string; suggestion_source?: string; reviewed?: boolean; value_source?: "profile" | "existing" | "ai" | "manual" | "empty"; filled?: boolean };
export type BrowserAnswerSuggestion = { field_id: string; value: string; source: string };


export type AIProviderId = "ollama" | "openai" | "openai_compatible";

export type AIProviderConfiguration = {
  id: AIProviderId;
  label: string;
  model: string;
  base_url: string;
  configured: boolean;
  api_key_configured: boolean | null;
  requires_api_key: boolean;
  data_location: "local" | "external provider";
};

export type AISettingsResponse = {
  success: boolean;
  provider: AIProviderId;
  cloud_data_sharing_acknowledged: boolean;
  providers: Record<AIProviderId, AIProviderConfiguration>;
};

export type AIProviderSettingsInput = {
  provider: AIProviderId;
  model: string;
  base_url?: string;
  confirm_cloud_data_sharing?: boolean;
};


export type LocalDataSummary = {
  success: boolean;
  removed_files?: number;
  message?: string;
  counts: {
    cv_files: number;
    profile_saved: boolean;
    cv_text_saved: boolean;
    saved_jobs: number;
    applications: number;
    cache_files: number;
    settings_files: number;
    total_data_files: number;
  };
  preserved: string[];
};

export type BrowserDiagnostics = {
  success: boolean;
  playwright_installed: boolean;
  chromium_installed: boolean;
  install_command: string;
  message: string;
};


export type JobPlatform = {
  id: string;
  name: string;
  category: string;
  integration: "live" | "configurable" | "external";
  url: string;
  default_selected: boolean;
};

export type TailoredCvResponse = {
  success: boolean;
  filename: string;
  pdf_filename?: string;
  job_title?: string;
  company?: string;
  template: "classic" | "modern" | "compact" | "sectioned";
  tailored_profile: {
    summary: string;
    skills: string[];
    experience: Experience[];
    keyword_gaps: string[];
    projects?: Project[];
    achievements?: string[];
  };
  ats: {
    score: number;
    keyword_match_score: number;
    section_completeness_score: number;
    matched_keywords: string[];
    missing_keywords: string[];
    detected_requirement_count: number;
    checks: { name: string; passed: boolean }[];
    threshold: 70;
    status: "ready_for_review" | "needs_improvement";
    disclaimer: string;
  };
  review_required: boolean;
  download_url: string;
  message: string;
};


export type TailoredCvVersion = {
  filename: string;
  pdf_filename: string;
  template: string;
  created_at: string;
  ats_score: number | null;
  job_title?: string;
  company?: string;
  job_id?: string;
};
