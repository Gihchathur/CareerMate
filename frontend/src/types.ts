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
export type JobSourceId = "jobtech_links" | "remoteok" | "arbeitnow" | "greenhouse" | "lever" | "teamtailor";

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
  board_token?: string;
  site?: string;
  api_key_env?: string;
  region?: string;
};

export type JobSourceConfiguration = {
  greenhouse: JobBoardConfig[];
  lever: JobBoardConfig[];
  teamtailor: JobBoardConfig[];
};

export type JobSourceConfigurationResponse = {
  success: boolean;
  config: JobSourceConfiguration;
  sources: Record<JobSourceId, JobSourceStatus>;
  message?: string;
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
  description_source?: "search_result" | "original_listing";
  description_fetch_status?: "not_attempted" | "success" | "failed";
  description_fetched_at?: string;
  description_fetch_message?: string;
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

export type BrowserFieldDraft = BrowserFormField & { include: boolean; value: string; suggestion_source?: string };
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
