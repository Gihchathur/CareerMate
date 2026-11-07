import { useCallback, useEffect, useRef, useState, type FormEvent, type HTMLInputTypeAttribute } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./components/ui/Icon";
import { SourceMark } from "./components/ui/SourceMark";
import { FloatingSelect } from "./components/ui/FloatingSelect";
import { WorkspaceShell, type WorkspaceView } from "./components/layout/WorkspaceShell";
import { AnalyticsStudio } from "./components/analytics/AnalyticsStudio";
import { AutomationCenter } from "./components/automation/AutomationCenter";
import { EvidenceVault } from "./components/profile/EvidenceVault";
import { TodayDashboard } from "./components/workflow/TodayDashboard";
import { JobInbox } from "./components/workflow/JobInbox";
import { PipelineBoard } from "./components/workflow/PipelineBoard";
import { FollowUps } from "./components/workflow/FollowUps";
import { DocumentsLibrary } from "./components/workflow/DocumentsLibrary";
import "./styles/workflow.css";
import "./reference-dashboard.css";
import {
  analyzeCv,
  closeBrowserSession,
  clearLocalCaches,
  getLocalDataSummary,
  getBrowserDiagnostics,
  resetLocalWorkspaceData,
  createApplication,
  enrichApplicationDescription,
  enrichJobDetails,
  fillBrowserForm,
  advanceBrowserStep,
  selectBrowserPage,
  suggestBrowserAnswers,
  submitBrowserApplication,
  generateApplicationAnswer,
  generateCoverLetter,
  getApplications,
  getWorkflowInbox,
  getWorkflowActivity,
  updateJobTriage,
  getAiSettings,
  saveAiSettings,
  testAiProvider,
  getCvStatus,
  getProfile,
  getSavedJobs,
  getJobSources,
  getJobSourceConfig,
  saveJobSourceConfig,
  getPortalHealth,
  checkPortalHealth,
  openApplicationBrowser,
  scanBrowserForm,
  matchJobs,
  saveProfile,
  searchJobs,
  updateApplication,
  uploadCv,
  tailorCvForJob,
  createSavedSearch,
  getSavedSearches,
  deleteSavedSearch,
  checkSavedSearchAlerts,
  getJobAlerts,
  markJobAlertRead,
  getTailoredCvVersions,
  TAILORED_CV_DOWNLOAD_BASE,
} from "./api";
import type {
  ApplicationAnswer,
  BrowserDiagnostics,
  LocalDataSummary,
  AIProviderId,
  AISettingsResponse,
  ApplicationRecord,
  BrowserFieldDraft,
  BrowserFormSession,
  BrowserNavigationIntent,
  ApplicationStatus,
  CandidatePersonal,
  CandidateProfile,
  Education,
  Experience,
  CvStatus,
  JobMatchResult,
  JobResult,
  RequirementAssessment,
  JobSearchCriteria,
  JobSourceId,
  JobSourceStatus,
  JobBoardConfig,
  JobSourceConfiguration,
  WorkMode,
  TailoredCvResponse,
  TailoredCvVersion,
  JobTriageStage,
  WorkflowEvent,
  WorkflowInboxResponse,
  PortalHealthResponse,
  PortalSearchCoverage,
  PortalHealthItem,
  PortalHealthStatus,
} from "./types";

const EMPTY_STATUS: CvStatus = {
  uploaded: false,
  extracted_text_characters: 0,
  profile_saved: false,
};

// Explore is intentionally portal-only: only employer ATS boards configured in
// Portals can feed the Inbox. Public aggregators and external shortcuts are not
// mixed into this search experience.
const SOURCE_OPTIONS: { id: keyof JobSourceConfiguration; title: string }[] = [
  { id: "greenhouse", title: "Greenhouse" },
  { id: "lever", title: "Lever" },
  { id: "teamtailor", title: "Teamtailor" },
  { id: "ashby", title: "Ashby" },
  { id: "smartrecruiters", title: "SmartRecruiters" },
  { id: "workable", title: "Workable" },
  { id: "recruitee", title: "Recruitee" },
  { id: "breezy", title: "Breezy HR" },
  { id: "personio", title: "Personio" },
  { id: "workday", title: "Workday" },
];

type EmployerBoardProvider = keyof JobSourceConfiguration;
const BOARD_PROVIDERS: EmployerBoardProvider[] = ["greenhouse", "lever", "teamtailor", "ashby", "smartrecruiters", "workable", "recruitee", "breezy", "personio", "workday"];
const BOARD_PROVIDER_LABELS: Record<EmployerBoardProvider, string> = {
  greenhouse: "Greenhouse", lever: "Lever", teamtailor: "Teamtailor", ashby: "Ashby",
  smartrecruiters: "SmartRecruiters", workable: "Workable", recruitee: "Recruitee",
  breezy: "Breezy HR", personio: "Personio", workday: "Workday",
};

function employerBoardIdentifier(provider: EmployerBoardProvider, board: JobBoardConfig): string {
  if (provider === "greenhouse") return board.board_token?.trim() ?? "";
  if (provider === "lever") return board.site?.trim() ?? "";
  if (provider === "teamtailor") return board.company?.trim() ?? "";
  return board.slug?.trim() ?? "";
}

function employerPortalId(provider: EmployerBoardProvider, board: JobBoardConfig): string {
  return `${provider}:${employerBoardIdentifier(provider, board).toLocaleLowerCase()}`;
}

function enabledEmployerPortalIds(
  config: JobSourceConfiguration,
  statuses: Record<JobSourceId, JobSourceStatus>,
): string[] {
  return BOARD_PROVIDERS.flatMap((provider) =>
    config[provider]
      .filter((board) => board.enabled && employerBoardIdentifier(provider, board) && canSelectSource(provider, statuses[provider]))
      .map((board) => employerPortalId(provider, board)),
  );
}

function selectedPortalSourceIds(config: JobSourceConfiguration, portalIds: string[]): JobSourceId[] {
  return BOARD_PROVIDERS
    .filter((provider) => config[provider].some((board) => portalIds.includes(employerPortalId(provider, board))))
    .map((provider) => provider);
}

function employerPortalDomain(provider: EmployerBoardProvider, board: JobBoardConfig): string {
  const identifier = employerBoardIdentifier(provider, board);
  if (provider === "greenhouse") return `job-boards.greenhouse.io/${identifier}`;
  if (provider === "lever") return `jobs.lever.co/${identifier}`;
  if (provider === "teamtailor") return `Teamtailor · ${(board.region || "eu").toUpperCase()} region`;
  if (provider === "ashby") return `jobs.ashbyhq.com/${identifier}`;
  if (provider === "smartrecruiters") return `jobs.smartrecruiters.com/${identifier}`;
  if (provider === "workable") return `apply.workable.com/${identifier}`;
  if (provider === "recruitee") return `${identifier}.recruitee.com`;
  if (provider === "breezy") return `${identifier}.breezy.hr`;
  if (provider === "personio") return `${identifier}.jobs.personio.de`;
  try { return new URL(identifier).host + new URL(identifier).pathname; } catch { return identifier; }
}

function employerPortalJobsUrl(provider: EmployerBoardProvider, board: JobBoardConfig): string | null {
  const explicit = safeExternalUrl(board.jobs_url?.trim() ?? "");
  if (explicit) return explicit;
  const identifier = employerBoardIdentifier(provider, board);
  if (!identifier) return null;
  const encoded = encodeURIComponent(identifier);
  const candidate = provider === "greenhouse" ? `https://boards.greenhouse.io/${encoded}`
    : provider === "lever" ? `https://jobs.lever.co/${encoded}`
      : provider === "ashby" ? `https://jobs.ashbyhq.com/${encoded}`
        : provider === "smartrecruiters" ? `https://jobs.smartrecruiters.com/${encoded}`
          : provider === "workable" ? `https://apply.workable.com/${encoded}`
            : provider === "recruitee" ? `https://${identifier}.recruitee.com`
              : provider === "breezy" ? `https://${identifier}.breezy.hr`
                : provider === "personio" ? `https://${identifier}.jobs.personio.de`
                  : provider === "workday" ? identifier : "";
  return safeExternalUrl(candidate);
}

function portalStatusLabel(status: PortalHealthStatus): string {
  return status === "live" ? "Live" : status === "empty" ? "Live · no jobs" : status === "paused" ? "Paused" : status === "needs_setup" ? "Needs setup" : status === "broken" ? "Unreachable" : "Not checked";
}

const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved",
  preparing: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const EMPTY_JOB_SOURCE_CONFIG: JobSourceConfiguration = { greenhouse: [], lever: [], teamtailor: [], ashby: [], smartrecruiters: [], workable: [], recruitee: [], breezy: [], personio: [], workday: [] };

const EMPTY_SOURCE_STATUS: Record<JobSourceId, JobSourceStatus> = {
  jobtech_links: { configured: true, employers: null, requires_api_key: false },
  remoteok: { configured: true, employers: null, requires_api_key: false },
  arbeitnow: { configured: true, employers: null, requires_api_key: false },
  greenhouse: { configured: false, employers: 0, requires_api_key: false },
  lever: { configured: false, employers: 0, requires_api_key: false },
  teamtailor: { configured: false, employers: 0, requires_api_key: true, credentials_ready: false, missing_credentials: 0 },
  ashby: { configured: false, employers: 0, requires_api_key: false },
  smartrecruiters: { configured: false, employers: 0, requires_api_key: false },
  workable: { configured: false, employers: 0, requires_api_key: false },
  recruitee: { configured: false, employers: 0, requires_api_key: false },
  breezy: { configured: false, employers: 0, requires_api_key: false },
  personio: { configured: false, employers: 0, requires_api_key: false },
  workday: { configured: false, employers: 0, requires_api_key: false },
};

function canSelectSource(source: JobSourceId, status: JobSourceStatus): boolean {
  // Search controls accept employer ATS providers only. Public feeds are not
  // exposed in Explore, even if their connectors remain available to older APIs.
  if (["jobtech_links", "remoteok", "arbeitnow"].includes(source)) return false;
  if (!status.configured) return false;
  return source !== "teamtailor" || status.credentials_ready === true;
}

function isJobFromEnabledPortal(job: JobResult, config: JobSourceConfiguration, selectedPortalIds: string[]): boolean {
  const provider = job.source.trim().toLocaleLowerCase() as keyof JobSourceConfiguration;
  if (!SOURCE_OPTIONS.some((item) => item.id === provider)) return false;
  const selected = new Set(selectedPortalIds.map((id) => id.trim().toLocaleLowerCase()));
  // New records carry an authoritative provider:company ID from the backend.
  // Use it first; company-name/source-ID heuristics remain for older saved jobs.
  if (job.portal_id?.trim()) return selected.has(job.portal_id.trim().toLocaleLowerCase());
  const normalize = (value: string) => value.trim().toLocaleLowerCase().replace(/[^a-z0-9]+/g, " ");
  const company = normalize(job.company || "");
  const sourceId = (job.source_id || "").toLocaleLowerCase();
  return (config[provider] ?? []).some((board) => {
    if (!board.enabled || !selectedPortalIds.includes(employerPortalId(provider, board))) return false;
    const configuredCompany = normalize(board.company || board.slug || board.site || board.board_token || "");
    const identifiers = [board.board_token, board.site, board.company, board.slug]
      .filter((value): value is string => Boolean(value?.trim()))
      .map((value) => value.trim().toLocaleLowerCase());
    const identifierMatch = identifiers.some((identifier) => sourceId === identifier || sourceId.startsWith(`${identifier}:`));
    const companyMatch = Boolean(configuredCompany && company && configuredCompany === company);
    return identifierMatch || companyMatch;
  });
}

function safeExternalUrl(value: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function suggestedBrowserValue(
  key: string,
  profile: CandidateProfile | null,
  application: ApplicationRecord | null,
  tailoredVersions: TailoredCvVersion[] = [],
): string {
  if (key === "cv_file") {
    const normalize = (value: string) => value.trim().toLocaleLowerCase().replace(/[^a-z0-9]+/g, " ");
    const appCompany = normalize(application?.company ?? "");
    const appTitle = normalize(application?.title ?? "");
    const matched = tailoredVersions.find((version) => version.job_id && version.job_id === application?.job_id)
      ?? tailoredVersions.find((version) => appCompany && appTitle && normalize(version.company ?? "") === appCompany && normalize(version.job_title ?? "") === appTitle)
      ?? tailoredVersions.find((version) => appCompany && normalize(version.company ?? "") === appCompany)
      ?? tailoredVersions.find((version) => appTitle && normalize(version.job_title ?? "") === appTitle)
      ?? tailoredVersions[0];
    // Never silently attach a tailored CV created for a different employer.
    // If no exact role/company match exists, ask the user to choose a document.
    return matched ? `__CAREERMATE_TAILORED_CV__:${matched.filename}` : "";
  }
  if (!profile) return "";
  const fullName = profile.personal?.name?.trim() ?? "";
  switch (key) {
    case "personal.name": return fullName;
    case "personal.first_name": return fullName.split(/\s+/).filter(Boolean)[0] ?? "";
    case "personal.last_name": return fullName.split(/\s+/).filter(Boolean).slice(1).join(" ");
    case "personal.email": return profile.personal?.email ?? "";
    case "personal.phone": return profile.personal?.phone ?? "";
    case "personal.location": return profile.personal?.location ?? "";
    case "personal.linkedin": return profile.personal?.linkedin ?? "";
    case "personal.github": return profile.personal?.github ?? "";
    case "personal.portfolio": return profile.personal?.portfolio ?? "";
    case "summary": return profile.summary ?? "";
    case "skills": return profile.skills.join(", ");
    case "languages": return profile.languages.join(", ");
    case "certifications": return profile.certifications.join(", ");
    case "cover_letter": return application?.cover_letter ?? "";
    case "latest_answer": return application?.answers.at(-1)?.answer ?? "";
    default: return "";
  }
}

function makeBrowserFieldDrafts(
  session: BrowserFormSession,
  profile: CandidateProfile | null,
  application: ApplicationRecord | null,
  tailoredVersions: TailoredCvVersion[] = [],
): BrowserFieldDraft[] {
  return session.fields.map((field) => {
    let value = suggestedBrowserValue(field.suggested_key, profile, application, tailoredVersions);
    if (!value && !["file", "checkbox", "radio"].includes(field.kind)) value = field.current_value ?? "";
    if (field.kind === "select" && value && field.options?.length) {
      const option = field.options.find((item) => item.value.toLocaleLowerCase() === value.toLocaleLowerCase())
        ?? field.options.find((item) => item.label.toLocaleLowerCase() === value.toLocaleLowerCase())
        ?? field.options.find((item) => value.toLocaleLowerCase().includes(item.label.toLocaleLowerCase()) || item.label.toLocaleLowerCase().includes(value.toLocaleLowerCase()));
      value = option?.value ?? "";
    }
    if (field.kind === "radio" && !value) value = field.current_value ?? "";
    if (field.kind === "checkbox" && !value) value = field.current_value ?? "false";
    const include = field.kind === "file" ? false : Boolean(value.trim()) && !["radio", "checkbox"].includes(field.kind);
    const valueSource = suggestedBrowserValue(field.suggested_key, profile, application, tailoredVersions)
      ? "profile"
      : field.current_value?.trim() ? "existing" : "empty";
    return { ...field, value, include, reviewed: false, value_source: valueSource, filled: false };
  });
}

function browserFieldDisplayValue(field: BrowserFieldDraft, tailoredVersions: TailoredCvVersion[]): string {
  if (field.kind !== "file") return field.value;
  if (field.value.startsWith("__CAREERMATE_TAILORED_CV__:")) {
    const filename = field.value.split(":").slice(1).join(":");
    return tailoredVersions.find((version) => version.filename === filename)?.pdf_filename || filename.replace(/\.docx$/i, ".pdf");
  }
  if (field.value === "__CAREERMATE_CURRENT_CV__") return "current.pdf";
  return "No CV selected";
}

function browserFieldNeedsUserInput(field: BrowserFieldDraft): boolean {
  const label = field.label.toLocaleLowerCase();
  const looksLikeQuestion = /\b(why|what|how|describe|tell us|explain|motivation|achievement|impressive|compensation|salary|notice period|work authori[sz]ation|visa|sponsorship)\b|\?/.test(label);
  // False is a valid explicit checkbox answer; it is only missing until the
  // user has actively reviewed that Yes/No choice.
  const isEmpty = field.kind === "checkbox"
    ? !field.reviewed
    : field.kind === "file"
      ? !field.value.trim() || (!field.include && !field.filled)
      : !field.value.trim();
  return isEmpty && (field.required || field.kind === "textarea" || looksLikeQuestion);
}

type PreparedBrowserStep = {
  step: number;
  title: string;
  url: string;
  fields: { label: string; value: string; required: boolean; filled: boolean }[];
  filled_count: number;
  status: "completed" | "ready" | "needs_attention";
  note: string;
};

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: HTMLInputTypeAttribute;
  placeholder?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        value={value}
        placeholder={placeholder}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}


function App() {
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvStatus, setCvStatus] = useState<CvStatus>(EMPTY_STATUS);
  const [profileSaved, setProfileSaved] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [cvLoading, setCvLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [jobLoading, setJobLoading] = useState(false);
  const [matchLoading, setMatchLoading] = useState(false);
  const [analyzingJobIds, setAnalyzingJobIds] = useState<string[]>([]);
  const [jobSources, setJobSources] = useState<Record<JobSourceId, JobSourceStatus>>(EMPTY_SOURCE_STATUS);
  const [sourceConfig, setSourceConfig] = useState<JobSourceConfiguration>(EMPTY_JOB_SOURCE_CONFIG);
  const [sourceConfigLoading, setSourceConfigLoading] = useState(false);
  const [sourceConfigSaving, setSourceConfigSaving] = useState(false);
  const [portalHealth, setPortalHealth] = useState<PortalHealthResponse | null>(null);
  const [portalHealthChecking, setPortalHealthChecking] = useState(false);
  const [portalAddOpen, setPortalAddOpen] = useState(false);
  const [portalSearch, setPortalSearch] = useState("");
  const [portalFilter, setPortalFilter] = useState<"all" | "enabled" | "paused" | "attention">("all");
  const [newBoardProvider, setNewBoardProvider] = useState<"greenhouse" | "lever" | "teamtailor" | "ashby" | "smartrecruiters" | "workable" | "recruitee" | "breezy" | "personio" | "workday">("greenhouse");
  const [newBoardIdentifier, setNewBoardIdentifier] = useState("");
  const [newBoardCompany, setNewBoardCompany] = useState("");
  const [newBoardCountry, setNewBoardCountry] = useState("Sweden");
  const [newBoardCareerUrl, setNewBoardCareerUrl] = useState("");
  const [newBoardJobsUrl, setNewBoardJobsUrl] = useState("");
  const [newBoardNotes, setNewBoardNotes] = useState("");
  const [newBoardRegion, setNewBoardRegion] = useState("eu");
  const [newBoardApiKeyEnv, setNewBoardApiKeyEnv] = useState("CAREERMATE_TEAMTAILOR_API_KEY");
  const [selectedSources, setSelectedSources] = useState<JobSourceId[]>([]);
  const [selectedPortalIds, setSelectedPortalIds] = useState<string[]>([]);
  const [exploreResultTab, setExploreResultTab] = useState<"results" | "selected" | "applied">("results");
  const [exploreSort, setExploreSort] = useState<"relevance" | "newest" | "company">("relevance");
  const [exploreViewMode, setExploreViewMode] = useState<"list" | "grid">("list");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [aiSettings, setAiSettings] = useState<AISettingsResponse | null>(null);
  const [aiProviderDraft, setAiProviderDraft] = useState<AIProviderId>("ollama");
  const [aiModelDraft, setAiModelDraft] = useState("qwen3:4b");
  const [aiBaseUrlDraft, setAiBaseUrlDraft] = useState("http://127.0.0.1:11434");
  const [cloudAiConsent, setCloudAiConsent] = useState(false);
  const [aiSaving, setAiSaving] = useState(false);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiTestMessage, setAiTestMessage] = useState("");

  const [jobRoles, setJobRoles] = useState("Software Engineer");
  const [jobCountry, setJobCountry] = useState("Sweden");
  const [jobCity, setJobCity] = useState("Stockholm");
  const [workMode, setWorkMode] = useState<WorkMode>("any");
  const [pageSize, setPageSize] = useState(20);
  const [searchOffset, setSearchOffset] = useState(0);
  const [searchTotalReported, setSearchTotalReported] = useState(0);
  const [searchFilterNote, setSearchFilterNote] = useState("");
  const [portalCoverage, setPortalCoverage] = useState<PortalSearchCoverage[]>([]);
  const [activeSearch, setActiveSearch] = useState<JobSearchCriteria | null>(null);
  const [jobs, setJobs] = useState<JobResult[]>([]);
  const [availableMatchJobs, setAvailableMatchJobs] = useState<JobResult[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [selectedMatchJobIds, setSelectedMatchJobIds] = useState<string[]>([]);
  const [matchSelectionSearch, setMatchSelectionSearch] = useState("");
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [selectedJob, setSelectedJob] = useState<JobResult | null>(null);

  const [cvTemplate, setCvTemplate] = useState<"classic" | "modern" | "compact" | "sectioned">("sectioned");
  const [cvStudioTargetTitle, setCvStudioTargetTitle] = useState("");
  const [cvStudioTargetCompany, setCvStudioTargetCompany] = useState("");
  const [cvStudioJobDescription, setCvStudioJobDescription] = useState("");
  const [tailoredCv, setTailoredCv] = useState<TailoredCvResponse | null>(null);
  const [tailoredCvVersions, setTailoredCvVersions] = useState<TailoredCvVersion[]>([]);
  useEffect(() => { setTailoredCv(null); setCvTailorError(""); }, [selectedJob?.id]);
  useEffect(() => {
    if (activeView !== "documents") return;
    void getTailoredCvVersions().then((result) => setTailoredCvVersions(result.versions)).catch(() => undefined);
  }, [activeView]);
  const [tailoringCv, setTailoringCv] = useState(false);
  const [cvTailorError, setCvTailorError] = useState("");
  const [minimumSalary, setMinimumSalary] = useState("");
  const [maximumSalary, setMaximumSalary] = useState("");
  const [freshnessDays, setFreshnessDays] = useState("30");
  const [excludedCompaniesText, setExcludedCompaniesText] = useState("");
  const [savedSearches, setSavedSearches] = useState<{id:string;name:string;roles:string[];country:string;city:string;work_mode:WorkMode;sources:JobSourceId[];portal_ids?:string[];frequency:"manual"|"daily"|"weekly";created_at:string}[]>([]);
  const [savedSearchName, setSavedSearchName] = useState("My job search");
  const [checkingAlertId, setCheckingAlertId] = useState<string | null>(null);
  const [alertFrequency, setAlertFrequency] = useState<"manual"|"daily"|"weekly">("daily");
  const [jobAlerts, setJobAlerts] = useState<{id:string;search_id:string;search_name:string;job_id:string;title:string;company:string;location:string;url:string;found_at:string;read:boolean}[]>([]);
  const [activeInsightJobId, setActiveInsightJobId] = useState<string | null>(null);

  // Keep modal interactions predictable: Escape closes, focus stays inside, and
  // closing returns focus to the control that opened the dialog.
  useEffect(() => {
    if (!selectedJob && !activeInsightJobId) return;
    const dialog = document.querySelector<HTMLElement>(selectedJob ? ".job-detail-drawer" : ".match-insight-drawer");
    if (!dialog) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter((element) => element.offsetParent !== null);
    const close = () => { setSelectedJob(null); setActiveInsightJobId(null); };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close(); return; }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); dialog.focus(); return; }
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    const oldOverflow = document.body.style.overflow;
    const appRoot = document.getElementById("root");
    const previousInert = appRoot?.inert ?? false;
    if (appRoot) appRoot.inert = true;
    document.body.style.overflow = "hidden";
    dialog.querySelector<HTMLElement>(".drawer-close, .match-insight-close")?.focus();
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = oldOverflow;
      if (appRoot) appRoot.inert = previousInert;
      previousFocus?.focus();
    };
  }, [selectedJob?.id, activeInsightJobId]);
  const [enrichingJobId, setEnrichingJobId] = useState<string | null>(null);
  const [manualAdvertJobId, setManualAdvertJobId] = useState<string | null>(null);
  const [manualAdvertText, setManualAdvertText] = useState("");
  const [manualAdvertSavingId, setManualAdvertSavingId] = useState<string | null>(null);
  const [enrichingApplicationId, setEnrichingApplicationId] = useState<string | null>(null);
  const [jobFilter, setJobFilter] = useState("");
  const [applicationListTab, setApplicationListTab] = useState<"all" | "active" | "submitted" | "offers">("all");
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [workflowInboxData, setWorkflowInboxData] = useState<WorkflowInboxResponse | null>(null);
  const [workflowEvents, setWorkflowEvents] = useState<WorkflowEvent[]>([]);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const workflowHasLoaded = useRef(false);
  const workflowRequestGeneration = useRef(0);
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null);
  const [applicationStatus, setApplicationStatus] = useState<ApplicationStatus>("saved");
  const [applicationNotes, setApplicationNotes] = useState("");
  const [applicationFollowUpDate, setApplicationFollowUpDate] = useState("");
  const [applicationCoverLetter, setApplicationCoverLetter] = useState("");
  const [applicationAnswers, setApplicationAnswers] = useState<ApplicationAnswer[]>([]);
  const [applicationQuestion, setApplicationQuestion] = useState("");
  const [applicationSaving, setApplicationSaving] = useState(false);
  const [draftingCoverLetter, setDraftingCoverLetter] = useState(false);
  const [draftingAnswer, setDraftingAnswer] = useState(false);
  const [browserSession, setBrowserSession] = useState<BrowserFormSession | null>(null);
  const [browserFieldDrafts, setBrowserFieldDrafts] = useState<BrowserFieldDraft[]>([]);
  const [browserOpening, setBrowserOpening] = useState(false);
  const [browserScanning, setBrowserScanning] = useState(false);
  const [browserFilling, setBrowserFilling] = useState(false);
  const [browserNavigating, setBrowserNavigating] = useState(false);
  const [browserSuggesting, setBrowserSuggesting] = useState(false);
  const [browserAutoPreparing, setBrowserAutoPreparing] = useState(false);
  const [browserPreparedSteps, setBrowserPreparedSteps] = useState<PreparedBrowserStep[]>([]);
  const [browserSubmitting, setBrowserSubmitting] = useState(false);
  const [browserSubmitApproved, setBrowserSubmitApproved] = useState(false);
  const [dataSummary, setDataSummary] = useState<LocalDataSummary | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataResetBusy, setDataResetBusy] = useState(false);
  const [cacheClearBusy, setCacheClearBusy] = useState(false);
  const [showResetConfirmation, setShowResetConfirmation] = useState(false);
  const [resetConfirmationText, setResetConfirmationText] = useState("");
  useEffect(() => {
    if (!showResetConfirmation) return;
    const dialog = document.querySelector<HTMLElement>(".reset-confirm-dialog");
    if (!dialog) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter((element) => element.offsetParent !== null);
    const oldOverflow = document.body.style.overflow;
    const appRoot = document.getElementById("root");
    const previousInert = appRoot?.inert ?? false;
    if (appRoot) appRoot.inert = true;
    document.body.style.overflow = "hidden";
    dialog.querySelector<HTMLInputElement>("input")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !dataResetBusy) {
        event.preventDefault();
        setShowResetConfirmation(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); dialog.focus(); return; }
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = oldOverflow;
      if (appRoot) appRoot.inert = previousInert;
      previousFocus?.focus();
    };
  }, [showResetConfirmation, dataResetBusy]);
  const [browserDiagnostics, setBrowserDiagnostics] = useState<BrowserDiagnostics | null>(null);
  const [browserDiagnosticsLoading, setBrowserDiagnosticsLoading] = useState(false);

  const refreshWorkflowData = useCallback(async () => {
    const requestGeneration = ++workflowRequestGeneration.current;
    if (!workflowHasLoaded.current) setWorkflowLoading(true);
    try {
      const [inboxResponse, events] = await Promise.all([getWorkflowInbox(), getWorkflowActivity(40)]);
      // A slower earlier request must never overwrite newer state after a reset
      // or after the user revisits the Inbox.
      if (requestGeneration !== workflowRequestGeneration.current) return;
      setWorkflowInboxData(inboxResponse);
      setWorkflowEvents(events);
    } catch (workflowError) {
      if (requestGeneration !== workflowRequestGeneration.current) return;
      setError(workflowError instanceof Error ? workflowError.message : "Could not refresh the career workflow.");
    } finally {
      if (requestGeneration === workflowRequestGeneration.current) {
        workflowHasLoaded.current = true;
        setWorkflowLoading(false);
      }
    }
  }, []);


  const refreshStatus = useCallback(async () => {
    const status = await getCvStatus();
    setCvStatus(status);
    setProfileSaved(status.profile_saved);
    return status;
  }, []);

  useEffect(() => {
    void refreshSavedSearches();
    void refreshWorkflowData();
    const alertRefresh = window.setInterval(() => { void refreshSavedSearches(); }, 60_000);
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [status, savedJobs, sourceResponse, sourceConfigResponse, applicationResponse, aiResponse, portalHealthResponse] = await Promise.all([
          getCvStatus(),
          getSavedJobs(),
          getJobSources().catch(() => null),
          getJobSourceConfig().catch(() => null),
          getApplications().catch((applicationsError) => {
            if (!cancelled) setError(applicationsError instanceof Error ? applicationsError.message : "Could not load application records.");
            return null;
          }),
          getAiSettings().catch(() => null),
          getPortalHealth().catch(() => null),
        ]);
        if (cancelled) return;
        if (portalHealthResponse) setPortalHealth(portalHealthResponse);
        setCvStatus(status);
        setProfileSaved(status.profile_saved);
        setJobs(savedJobs);
        setAvailableMatchJobs(savedJobs);
        setSelectedMatchJobIds(savedJobs.slice(0, 3).map((job) => job.id));
        if (applicationResponse) {
          setApplications(applicationResponse.applications);
          if (applicationResponse.applications.length) selectApplication(applicationResponse.applications[0]);
        }
        if (aiResponse) {
          setAiSettings(aiResponse);
          setAiProviderDraft(aiResponse.provider);
          setAiModelDraft(aiResponse.providers[aiResponse.provider].model);
          setAiBaseUrlDraft(aiResponse.providers[aiResponse.provider].base_url);
          setCloudAiConsent(false);
        }
        if (sourceResponse || sourceConfigResponse) {
          const mergedStatus = { ...EMPTY_SOURCE_STATUS, ...(sourceConfigResponse?.sources ?? sourceResponse?.sources ?? {}) };
          const loadedConfig = { ...EMPTY_JOB_SOURCE_CONFIG, ...(sourceConfigResponse?.config ?? {}) };
          setJobSources(mergedStatus);
          setSourceConfig(loadedConfig);
          const enabledPortals = enabledEmployerPortalIds(loadedConfig, mergedStatus);
          setSelectedPortalIds(enabledPortals);
          setSelectedSources(selectedPortalSourceIds(loadedConfig, enabledPortals));
        }

        if (status.profile_saved) {
          try {
            const savedProfile = await getProfile();
            if (!cancelled) setProfile(savedProfile);
          } catch (loadError) {
            if (!cancelled) {
              setError(loadError instanceof Error ? loadError.message : "Could not load the candidate profile.");
            }
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Could not load CareerMate data.");
        }
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    }

    void loadInitialData();
    return () => {
      cancelled = true;
      window.clearInterval(alertRefresh);
    };
  }, [refreshWorkflowData]);

  useEffect(() => {
    if (!error && !notice) return;
    const timeout = window.setTimeout(() => {
      setError("");
      setNotice("");
    }, error ? 9000 : 6500);
    return () => window.clearTimeout(timeout);
  }, [error, notice]);

  async function handleUploadCv() {
    if (!file) {
      setError("Choose a CV file first.");
      setNotice("");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The CV must be 10 MB or smaller.");
      setNotice("");
      return;
    }

    setCvLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await uploadCv(file);
      setProfile(null);
      setProfileSaved(false);
      setMatches([]);
      await refreshStatus();
      setNotice(`CV uploaded and text extracted locally (${result.characters.toLocaleString()} characters). Analyze it to create your profile.`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "CV upload failed.");
    } finally {
      setCvLoading(false);
    }
  }

  async function handleAnalyzeCv() {
    if (!cvStatus.uploaded) {
      setError("Upload a CV and extract its text before running analysis.");
      setNotice("");
      return;
    }

    setCvLoading(true);
    setError("");
    setNotice(`CareerMate is asking ${aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider"} to structure the CV.`);
    try {
      const analyzedProfile = await analyzeCv();
      setProfile(analyzedProfile);
      setProfileSaved(false);
      setCvStatus((current) => ({ ...current, profile_saved: false }));
      setMatches([]);
      setNotice("CV analysis finished. Review every field and save the profile when it is correct.");
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "CV analysis failed.");
      setNotice("");
    } finally {
      setCvLoading(false);
    }
  }

  function selectAiProvider(provider: AIProviderId) {
    const config = aiSettings?.providers[provider];
    setAiProviderDraft(provider);
    setAiModelDraft(config?.model ?? (provider === "ollama" ? "qwen3:4b" : provider === "openai" ? "gpt-6-luna" : ""));
    setAiBaseUrlDraft(config?.base_url ?? (provider === "ollama" ? "http://127.0.0.1:11434" : ""));
    setAiTestMessage("");
    setCloudAiConsent(false);
  }

  async function handleSaveAiSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAiSaving(true);
    setAiTestMessage("");
    setError("");
    setNotice("");
    try {
      const result = await saveAiSettings({
        provider: aiProviderDraft,
        model: aiModelDraft.trim(),
        base_url: aiBaseUrlDraft.trim(),
        confirm_cloud_data_sharing: aiProviderDraft === "ollama" ? false : cloudAiConsent,
      });
      setAiSettings(result);
      setAiProviderDraft(result.provider);
      setAiModelDraft(result.providers[result.provider].model);
      setAiBaseUrlDraft(result.providers[result.provider].base_url);
      setCloudAiConsent(false);
      setNotice(`AI provider updated to ${result.providers[result.provider].label}. New CV analysis, job matches and application drafts will use this provider.`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save AI provider settings.");
    } finally {
      setAiSaving(false);
    }
  }

  async function handleTestAiProvider() {
    setAiTesting(true);
    setAiTestMessage("");
    setError("");
    try {
      const result = await testAiProvider({
        provider: aiProviderDraft,
        model: aiModelDraft.trim(),
        base_url: aiBaseUrlDraft.trim(),
      });
      setAiTestMessage(`Connection successful · ${result.model} replied: ${result.message}`);
    } catch (testError) {
      setAiTestMessage(testError instanceof Error ? testError.message : "Provider connection test failed.");
    } finally {
      setAiTesting(false);
    }
  }

  async function handleSaveProfile() {
    if (!profile) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await saveProfile(profile);
      setProfileSaved(true);
      setCvStatus((current) => ({ ...current, profile_saved: true }));
      setNotice("Candidate profile saved locally and ready for matching.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  async function executeJobSearch(criteria: JobSearchCriteria, refreshPortals = false) {
    setJobLoading(true);
    setPortalCoverage([]);
    setError("");
    setNotice("Searching your enabled employer portals.");

    try {
      const result = await searchJobs({ ...criteria, offset: 0, refresh_portals: refreshPortals });
      // The server has already restricted this inventory to the exact selected
      // company portals and applied role/location/advanced filters. Do not run a
      // second client-side portal check that can hide valid returned matches.
      // `matching_jobs` is the full unique inventory; `jobs` remains a fallback
      // for an older backend so the workspace never drops a valid page silently.
      const searchInventory = Array.isArray(result.matching_jobs)
        ? result.matching_jobs
        : result.jobs;
      const searchCriteria = { ...criteria, limit: pageSize };
      setActiveSearch(searchCriteria);
      setJobs(searchInventory);
      setPortalCoverage(result.portal_results ?? []);
      // The search endpoint persists normalized jobs; refresh the workflow inbox
      // so every successful discovery immediately enters the triage process.
      await refreshWorkflowData();
      setAvailableMatchJobs((current) => {
        const merged = new Map(current.map((job) => [job.id, job]));
        searchInventory.forEach((job) => merged.set(job.id, { ...merged.get(job.id), ...job }));
        return Array.from(merged.values());
      });
      setSelectedMatchJobIds((current) => [...new Set([...current, ...searchInventory.slice(0, 3).map((job) => job.id)])].slice(0, 20));
      setMatchSelectionSearch("");
      setSelectedJob(null);
      setMatches([]);
      setSearchOffset(0);
      setSearchTotalReported(searchInventory.length);
      setSearchFilterNote(result.filter_note);

      const warningText = result.warnings.length
        ? ` Some source searches had warnings: ${result.warnings.join("; ")}`
        : "";
      const totalLabel = `Found ${result.total_reported.toLocaleString()} role and location matches before cross-board de-duplication${result.total_is_approximate ? " (approximate across portals and filters)" : ""}.`;
      const initialPageCount = Math.min(searchInventory.length, pageSize);
      setNotice(
        `Showing ${initialPageCount.toLocaleString()} of ${searchInventory.length.toLocaleString()} unique matching jobs. ` +
        `${result.saved_total.toLocaleString()} unique job records are saved locally. ${totalLabel}${warningText}`
      );

      if (searchInventory.length === 0 && (result.advanced_filtered_out ?? 0) > 0) {
        setNotice(
          `${result.advanced_filtered_out.toLocaleString()} listing(s) matched your requested role and location, but were removed by the advanced salary, freshness or company-exclusion filters. Review Advanced filters and relax any exclusions.`,
        );
      } else if (searchInventory.length === 0 && result.filtered_out > 0) {
        const exclusions = result.filtered_out_by ?? { country: 0, city: 0, work_mode: 0 };
        const reasons = [
          exclusions.country ? `${exclusions.country} country mismatch(es)` : "",
          exclusions.city ? `${exclusions.city} city mismatch(es)` : "",
          exclusions.work_mode ? `${exclusions.work_mode} work-arrangement mismatch(es)` : "",
        ].filter(Boolean);
        setNotice(`No jobs on this page passed your location and work-arrangement filters. ${reasons.join(", ") || `${result.filtered_out} listing(s) filtered out`}. Review each portal's coverage report below.`);
      }
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Job search failed.");
      setNotice("");
    } finally {
      setJobLoading(false);
    }
  }

  function toggleEmployerPortal(portalId: string, checked: boolean) {
    const nextPortalIds = checked
      ? (selectedPortalIds.includes(portalId) ? selectedPortalIds : [...selectedPortalIds, portalId])
      : selectedPortalIds.filter((item) => item !== portalId);
    setSelectedPortalIds(nextPortalIds);
    setSelectedSources(selectedPortalSourceIds(sourceConfig, nextPortalIds));
    setPortalCoverage([]);
    // Changing company boards invalidates the previous search context; the user
    // must run the new selection before paging or live-refreshing it.
    setActiveSearch(null);
  }

  async function handleRefreshSourceConfig() {
    setSourceConfigLoading(true);
    setError("");
    try {
      const result = await getJobSourceConfig();
      const nextConfig = { ...EMPTY_JOB_SOURCE_CONFIG, ...result.config };
      setSourceConfig(nextConfig);
      setJobSources({ ...EMPTY_SOURCE_STATUS, ...result.sources });
      const enabledPortals = enabledEmployerPortalIds(nextConfig, result.sources);
      const retainedSelection = selectedPortalIds.filter((portalId) => enabledPortals.includes(portalId));
      setSelectedPortalIds(retainedSelection);
      setSelectedSources(selectedPortalSourceIds(nextConfig, retainedSelection));
      setNotice("Employer portal configuration refreshed. Your current company selection was preserved.");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Could not refresh job platform configuration.");
      setNotice("");
    } finally { setSourceConfigLoading(false); }
  }

  async function handleCheckPortals() {
    setPortalHealthChecking(true);
    setError("");
    try {
      const result = await checkPortalHealth();
      setPortalHealth(result);
      setNotice(`Portal health check complete: ${result.summary.live} live, ${result.summary.empty} empty, ${result.summary.broken} unreachable.`);
    } catch (checkError) {
      setError(checkError instanceof Error ? checkError.message : "Could not check employer portal health.");
      setNotice("");
    } finally {
      setPortalHealthChecking(false);
    }
  }

  async function handleSaveSourceConfig() {
    setSourceConfigSaving(true);
    setError("");
    try {
      const result = await saveJobSourceConfig(sourceConfig);
      setSourceConfig({ ...EMPTY_JOB_SOURCE_CONFIG, ...result.config });
      setJobSources({ ...EMPTY_SOURCE_STATUS, ...result.sources });
      const health = await getPortalHealth().catch(() => null);
      if (health) setPortalHealth(health);
      // Keep the user's company-level selection when saving portal settings.
      // Newly added boards are available in Explore but are not silently selected.
      const enabledPortals = enabledEmployerPortalIds(result.config, result.sources);
      const retainedSelection = selectedPortalIds.filter((portalId) => enabledPortals.includes(portalId));
      setSelectedPortalIds(retainedSelection);
      setSelectedSources(selectedPortalSourceIds(result.config, retainedSelection));
      setNotice(result.message || "Job platform settings saved locally.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save job platform settings.");
      setNotice("");
    } finally { setSourceConfigSaving(false); }
  }

  function addEmployerBoard() {
    const identifier = newBoardIdentifier.trim();
    const company = newBoardCompany.trim() || identifier;
    if (newBoardProvider !== "teamtailor" && !identifier) { setError(`Enter the ${newBoardProvider === "greenhouse" ? "Greenhouse board token" : "Lever site slug"}.`); return; }
    if (newBoardProvider === "teamtailor" && !company) { setError("Enter the Teamtailor company/account name."); return; }
    if (newBoardProvider === "teamtailor" && !/^[A-Z][A-Z0-9_]{0,99}$/.test(newBoardApiKeyEnv.trim())) { setError("Use an environment variable name such as CAREERMATE_TEAMTAILOR_ACME_API_KEY, not the API key value."); return; }
    const careerUrl = newBoardCareerUrl.trim();
    const jobsUrl = newBoardJobsUrl.trim();
    for (const [label, value] of [["Career page URL", careerUrl], ["Public jobs URL", jobsUrl]] as const) {
      if (!value) continue;
      const parsed = safeExternalUrl(value);
      if (!parsed || !parsed.startsWith("https://")) { setError(`${label} must be a valid public HTTPS URL.`); return; }
    }
    const entry: JobBoardConfig = {
      enabled: true,
      company,
      country: newBoardCountry.trim(),
      career_url: careerUrl,
      jobs_url: jobsUrl,
      notes: newBoardNotes.trim(),
      ...(newBoardProvider === "greenhouse" ? { board_token: identifier } : {}),
      ...(newBoardProvider === "lever" ? { site: identifier, region: newBoardRegion === "na" || newBoardRegion === "apac" ? "global" : newBoardRegion } : {}),
      ...(newBoardProvider === "teamtailor" ? { api_key_env: newBoardApiKeyEnv.trim(), region: newBoardRegion } : {}),
      ...(["ashby","smartrecruiters","workable","recruitee","breezy","personio","workday"].includes(newBoardProvider) ? { slug: identifier } : {}),
    };
    setSourceConfig((current) => ({ ...current, [newBoardProvider]: [...current[newBoardProvider], entry] }));
    setNewBoardIdentifier(""); setNewBoardCompany(""); setNewBoardCareerUrl(""); setNewBoardJobsUrl(""); setNewBoardNotes(""); setError("");
    setNotice("Board added to the pending configuration. Save platform settings to activate it.");
  }

  function updateEmployerBoard(provider: "greenhouse" | "lever" | "teamtailor" | "ashby" | "smartrecruiters" | "workable" | "recruitee" | "breezy" | "personio" | "workday", index: number, changes: Partial<JobBoardConfig>) {
    setSourceConfig((current) => ({ ...current, [provider]: current[provider].map((board, itemIndex) => itemIndex === index ? { ...board, ...changes } : board) }));
  }

  function removeEmployerBoard(provider: "greenhouse" | "lever" | "teamtailor" | "ashby" | "smartrecruiters" | "workable" | "recruitee" | "breezy" | "personio" | "workday", index: number) {
    setSourceConfig((current) => ({ ...current, [provider]: current[provider].filter((_, itemIndex) => itemIndex !== index) }));
  }

  async function refreshSavedSearches() {
    try {
      const result = await getSavedSearches(); setSavedSearches(result.searches);
      const alerts = await getJobAlerts(); setJobAlerts(alerts.alerts);
    } catch { /* Saved searches are optional until the local API is available. */ }
  }

  async function handleSaveCurrentSearch() {
    const roles = jobRoles.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    if (!roles.length) { setError("Enter a job title before saving this search."); return; }
    if (!selectedPortalIds.length) { setError("Select at least one connected employer portal before saving this search."); return; }
    try {
      await createSavedSearch({ name: savedSearchName.trim() || "My job search", roles, country: jobCountry, city: jobCity, work_mode: workMode, sources: selectedSources, portal_ids: selectedPortalIds, frequency: alertFrequency });
      await refreshSavedSearches();
      setNotice("Search saved locally. Use Check new jobs to compare it with the latest results.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save search."); }
  }

  async function handleCheckSavedSearch(id: string) {
    const savedSearch = savedSearches.find((item) => item.id === id);
    const savedPortalIds = savedSearch?.portal_ids ?? [];
    if (!savedSearch || savedPortalIds.length === 0) {
      setError("This saved search was created before company-level portal selection. Save it again from Explore and choose the employer portals to monitor.");
      setNotice("");
      return;
    }
    const activePortalIds = enabledEmployerPortalIds(sourceConfig, jobSources);
    const hasEnabledSavedPortal = savedPortalIds.some((portalId) => activePortalIds.includes(portalId));
    if (!hasEnabledSavedPortal) {
      setError("None of this saved search's company portals is currently enabled. Update Portals or recreate the search.");
      setNotice("");
      return;
    }
    setCheckingAlertId(id);
    try {
      const result = await checkSavedSearchAlerts(id);
      setNotice(`${result.new_count} new job${result.new_count === 1 ? "" : "s"} found.`);
      if (result.new_jobs.length) {
        setJobs((current) => [...result.new_jobs, ...current].filter((job, index, all) => all.findIndex((x) => x.id === job.id) === index));
        await refreshWorkflowData();
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Could not check saved search."); }
    finally { setCheckingAlertId(null); }
  }

  async function handleTailorCvForSelectedJob(jobOverride?: JobResult | null) {
    const targetJob = jobOverride ?? selectedJob;
    if (!targetJob) return;
    const description = targetJob.description?.trim() ?? "";
    if (description.length < 100) {
      setCvTailorError("Fetch the full job description first. CareerMate needs the actual requirements to tailor your CV.");
      return;
    }
    setTailoringCv(true); setCvTailorError(""); setTailoredCv(null);
    try {
      setTailoredCv(await tailorCvForJob(description, cvTemplate, {
        job_title: targetJob.title,
        company: targetJob.company,
        job_id: targetJob.id,
      }));
      const versions = await getTailoredCvVersions();
      setTailoredCvVersions(versions.versions);
    }
    catch (e) {
      const message = e instanceof Error ? e.message : "Could not tailor the CV.";
      setCvTailorError(message.includes("Input should be 'classic', 'modern' or 'compact'")
        ? "The running FastAPI backend is older than this CareerMate frontend. Stop uvicorn and restart it from the CareerMate 3.7 backend folder so the Sectioned Professional template is available."
        : message);
    }
    finally { setTailoringCv(false); }
  }

  async function handleSearchJobs(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const roles = jobRoles
      .split(/\r?\n/)
      .map((role) => role.trim().replace(/\s+/g, " "))
      .filter(Boolean)
      .filter((role, index, all) => all.findIndex((item) => item.toLocaleLowerCase() === role.toLocaleLowerCase()) === index);

    if (roles.length === 0) {
      setError("Enter at least one job title or keyword.");
      setNotice("");
      return;
    }

    if (roles.length > 5) {
      setError("Search up to five job titles at a time, one per line.");
      setNotice("");
      return;
    }

    if (selectedPortalIds.length === 0) {
      setError("No company portals are selected. Open Portals, connect a company career board, then select it here.");
      setNotice("");
      return;
    }

    const criteria: JobSearchCriteria = {
      roles,
      country: jobCountry,
      city: jobCity.trim(),
      work_mode: workMode,
      sources: selectedSources,
      portal_ids: selectedPortalIds,
      limit: pageSize,
      ...(minimumSalary.trim() ? { min_salary: Number(minimumSalary) } : {}),
      ...(maximumSalary.trim() ? { max_salary: Number(maximumSalary) } : {}),
      ...(freshnessDays !== "any" ? { posted_within_days: Number(freshnessDays) } : {}),
      ...(excludedCompaniesText.trim() ? { excluded_companies: excludedCompaniesText.split(",").map((x) => x.trim()).filter(Boolean) } : {}),
    };

    await executeJobSearch(criteria);
  }

  function changeSearchPage(direction: -1 | 1) {
    if (!activeSearch || jobLoading) return;
    const pageLength = activeSearch.limit;
    const nextOffset = searchOffset + direction * pageLength;
    if (nextOffset < 0 || nextOffset >= searchTotalReported) return;
    setSearchOffset(nextOffset);
  }


  async function handleMatchJobs() {
    if (!profile) {
      setError("Analyze your CV first so CareerMate has a candidate profile to compare.");
      setNotice("");
      return;
    }
    const selectedJobs = availableMatchJobs.filter((job) => selectedMatchJobIds.includes(job.id));
    if (selectedJobs.length === 0) {
      setError("Select at least one job from the Find jobs list before analyzing matches.");
      setNotice("");
      return;
    }

    setMatchLoading(true);
    setError("");
    const activeProviderLabel = aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider";
    setNotice(aiSettings?.provider === "ollama"
      ? `Analyzing ${selectedJobs.length} selected job(s) with local Ollama. The first run can take time on this computer.`
      : `Analyzing ${selectedJobs.length} selected job(s) with ${activeProviderLabel}. Selected jobs can run concurrently; API usage may be billed.`);
    try {
      // Always persist the current, user-reviewed version before matching.
      await saveProfile(profile);
      setProfileSaved(true);
      setCvStatus((current) => ({ ...current, profile_saved: true }));

      const boundedJobs = selectedJobs.slice(0, 20);
      const result = await matchJobs(boundedJobs.length, boundedJobs.map((job) => job.id));
      setMatches((current) => [
        ...result.jobs,
        ...current.filter((item) => !result.jobs.some((updated) => updated.id === item.id)),
      ]);
      setNotice(`Analyzed ${result.analyzed} job(s) with ${activeProviderLabel}. Results are evidence-coverage estimates, not hiring probabilities.`);
    } catch (matchError) {
      setError(matchError instanceof Error ? matchError.message : "Could not analyze job matches.");
      setNotice("");
    } finally {
      setMatchLoading(false);
    }
  }


  async function handleAnalyzeSingleJob(job: JobResult) {
    if (!profile) {
      setError("Analyze your CV first so CareerMate has a candidate profile to compare.");
      setNotice("");
      return;
    }
    if (matchLoading || analyzingJobIds.includes(job.id)) return;

    setAnalyzingJobIds((current) => current.includes(job.id) ? current : [...current, job.id]);
    setError("");
    setNotice(`Analyzing ${job.title} at ${job.company || "this employer"}…`);
    try {
      // Persist the user's reviewed profile before asking the matcher to analyse a single job.
      await saveProfile(profile);
      setProfileSaved(true);
      setCvStatus((current) => ({ ...current, profile_saved: true }));

      const result = await matchJobs(1, [job.id]);
      const updated = result.jobs.find((item) => item.id === job.id) ?? result.jobs[0];
      if (!updated) throw new Error("CareerMate did not return an insight for this job. Please retry.");

      setMatches((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
      setActiveInsightJobId(updated.id);
      setJobs((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      setAvailableMatchJobs((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      setNotice(updated.match_score === null
        ? `Analysis finished for ${updated.title}, but the score is unavailable. Open the insight to review the reason.`
        : `Insight ready for ${updated.title}: ${updated.match_score}/100 evidence coverage. This is not a hiring probability.`);
    } catch (matchError) {
      setError(matchError instanceof Error ? matchError.message : `Could not analyze ${job.title}.`);
      setNotice("");
    } finally {
      setAnalyzingJobIds((current) => current.filter((id) => id !== job.id));
    }
  }

  function openExistingInsight(jobId: string) {
    setActiveInsightJobId(jobId);
  }

  function selectApplication(application: ApplicationRecord) {
    setSelectedApplicationId(application.id);
    setApplicationStatus(application.status);
    setApplicationNotes(application.notes ?? "");
    setApplicationFollowUpDate(application.follow_up_date ?? "");
    setApplicationCoverLetter(application.cover_letter ?? "");
    setApplicationAnswers(application.answers ?? []);
    setApplicationQuestion("");
  }

  function acceptUpdatedApplication(application: ApplicationRecord) {
    setApplications((current) => [application, ...current.filter((item) => item.id !== application.id)]);
    selectApplication(application);
  }

  async function handleEnrichJobDetails(job: JobResult, forceRefresh = false) {
    setEnrichingJobId(job.id);
    setError("");
    setNotice("Fetching the public original listing and extracting its full description…");
    try {
      const result = await enrichJobDetails(job.id, forceRefresh);
      setJobs((current) => current.map((item) => item.id === job.id ? result.job : item));
      setSelectedJob(result.job);
      if (result.success) {
        setMatches((current) => current.filter((item) => item.id !== job.id));
        setNotice("Full job description saved. Re-run match analysis so the score includes the newly retrieved requirements.");
      } else {
        setNotice("");
        setError(result.message);
      }
    } catch (enrichError) {
      setNotice("");
      setError(enrichError instanceof Error ? enrichError.message : "Could not fetch the full public job description.");
    } finally {
      setEnrichingJobId(null);
    }
  }

  async function handleEnrichAndReanalyze(job: JobMatchResult) {
    setEnrichingJobId(job.id);
    setError("");
    setNotice("Retrieving the full employer advert. CareerMate will re-run the match analysis if it succeeds…");
    try {
      const enrichment = await enrichJobDetails(job.id, true);
      setJobs((current) => current.map((item) => item.id === job.id ? enrichment.job : item));
      if (!enrichment.success || enrichment.job.description_source !== "original_listing") {
        setManualAdvertJobId(job.id);
        setManualAdvertText("");
        throw new Error(`${enrichment.message || "CareerMate could not retrieve the full original advert."} You can paste the advert text below and reanalyse it.`);
      }
      setNotice("Full listing retrieved. Rechecking all requirements against your reviewed profile…");
      const refreshed = await matchJobs(1, [job.id]);
      const updatedMatch = refreshed.jobs[0];
      if (!updatedMatch) {
        throw new Error("The full listing was saved, but CareerMate did not return a refreshed match. Run Analyze matches again.");
      }
      setMatches((current) => [updatedMatch, ...current.filter((item) => item.id !== job.id)]);
      setNotice(`Full advert analysed: ${updatedMatch.requirements.length} requirements reviewed. Confirm each red flag against your CV before deciding.`);
    } catch (enrichError) {
      setError(enrichError instanceof Error ? enrichError.message : "Could not retrieve and analyse the full job advert.");
      setNotice("");
    } finally {
      setEnrichingJobId(null);
    }
  }

  async function handleSaveManualAdvert(job: JobMatchResult) {
    const advert = manualAdvertText.trim();
    if (advert.length < 300) {
      setError("Paste at least 300 characters from the original advert before saving and analysing it.");
      return;
    }
    setManualAdvertSavingId(job.id);
    setError("");
    setNotice("Saving the pasted advert locally and re-running the match analysis…");
    try {
      const saved = await enrichJobDetails(job.id, false, advert);
      if (!saved.success) throw new Error(saved.message || "CareerMate could not save the pasted advert text.");
      setJobs((current) => current.map((item) => item.id === job.id ? saved.job : item));
      setSelectedJob((current) => current?.id === job.id ? saved.job : current);
      const refreshed = await matchJobs(1, [job.id]);
      const updatedMatch = refreshed.jobs[0];
      if (!updatedMatch) throw new Error("The advert was saved locally, but no refreshed match was returned. Run Analyze matches again.");
      setMatches((current) => [updatedMatch, ...current.filter((item) => item.id !== job.id)]);
      setManualAdvertJobId(null);
      setManualAdvertText("");
      setNotice(`Pasted advert analysed: ${updatedMatch.requirements.length} requirements reviewed. The text was not independently verified against the employer page.`);
    } catch (manualError) {
      setError(manualError instanceof Error ? manualError.message : "Could not save and analyse the pasted advert.");
      setNotice("");
    } finally {
      setManualAdvertSavingId(null);
    }
  }

  async function handleRefreshApplicationDescription() {
    if (!selectedApplication) return;
    setEnrichingApplicationId(selectedApplication.id);
    setError("");
    setNotice("Refreshing the original job description before preparing application materials…");
    try {
      const result = await enrichApplicationDescription(selectedApplication.id);
      acceptUpdatedApplication(result.application);
      if (result.success) {
        setNotice("Full job description saved to this application. Regenerate the cover letter to use the richer requirements.");
      } else {
        setError(result.message);
        setNotice("");
      }
    } catch (enrichError) {
      setError(enrichError instanceof Error ? enrichError.message : "Could not refresh the application description.");
      setNotice("");
    } finally {
      setEnrichingApplicationId(null);
    }
  }

  async function handleUpdateJobTriage(jobId: string, stage: JobTriageStage) {
    try {
      await updateJobTriage(jobId, stage);
      await refreshWorkflowData();
      setNotice(stage === "shortlisted" ? "Opportunity shortlisted." : stage === "skipped" ? "Opportunity moved to skipped." : stage === "reviewing" ? "Opportunity marked as under review." : "Opportunity returned to new.");
    } catch (triageError) {
      setError(triageError instanceof Error ? triageError.message : "Could not update the opportunity.");
    }
  }

  async function handlePipelineStatusChange(applicationId: string, status: ApplicationStatus) {
    try {
      const updated = await updateApplication(applicationId, { status });
      setApplications((current) => current.map((item) => item.id === applicationId ? updated : item));
      await refreshWorkflowData();
      setNotice(`Application moved to ${status.replace("_", " ")}.`);
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : "Could not update the application stage.");
    }
  }

  async function handleTrackJob(jobId: string) {
    setError("");
    setNotice("");
    try {
      const result = await createApplication(jobId);
      acceptUpdatedApplication(result.application);
      setSelectedJob(null);
      setActiveView("applications");
      await refreshWorkflowData();
      setNotice(result.created ? "Added to your application tracker. Add notes or prepare a draft next." : "This role is already tracked. Your existing record is open.");
    } catch (trackError) {
      setError(trackError instanceof Error ? trackError.message : "Could not add the job to your application tracker.");
    }
  }

  async function handleSaveApplication() {
    if (!selectedApplicationId) return;
    setApplicationSaving(true);
    setError("");
    setNotice("");
    try {
      const updated = await updateApplication(selectedApplicationId, {
        status: applicationStatus,
        notes: applicationNotes,
        follow_up_date: applicationFollowUpDate,
        cover_letter: applicationCoverLetter,
        answers: applicationAnswers,
      });
      acceptUpdatedApplication(updated);
      await refreshWorkflowData();
      setNotice("Application details and reviewed drafts saved locally.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save application changes.");
    } finally {
      setApplicationSaving(false);
    }
  }

  async function handleDraftCoverLetter() {
    if (!selectedApplicationId) return;
    setDraftingCoverLetter(true);
    setError("");
    const activeProviderLabel = aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider";
    setNotice(`Generating a CV-grounded cover-letter draft with ${activeProviderLabel}. Please review every claim before using it.`);
    try {
      const updated = await generateCoverLetter(selectedApplicationId);
      acceptUpdatedApplication(updated);
      setNotice(`Cover-letter draft generated with ${activeProviderLabel}. Review and edit it, then save any changes before use.`);
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Could not generate the cover-letter draft.");
      setNotice("");
    } finally {
      setDraftingCoverLetter(false);
    }
  }

  async function handleDraftAnswer() {
    if (!selectedApplicationId) return;
    if (applicationQuestion.trim().length < 5) {
      setError("Enter the full application question before generating an answer.");
      setNotice("");
      return;
    }
    setDraftingAnswer(true);
    setError("");
    const activeProviderLabel = aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider";
    setNotice(`Generating a draft answer from the reviewed profile with ${activeProviderLabel}.`);
    try {
      const updated = await generateApplicationAnswer(selectedApplicationId, applicationQuestion.trim());
      acceptUpdatedApplication(updated);
      setNotice("Answer draft generated and saved locally. Review it for accuracy before submitting.");
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Could not generate the answer draft.");
      setNotice("");
    } finally {
      setDraftingAnswer(false);
    }
  }

  async function refreshDataSummary() {
    setDataLoading(true);
    try {
      setDataSummary(await getLocalDataSummary());
    } catch (summaryError) {
      setError(summaryError instanceof Error ? summaryError.message : "Could not load local data summary.");
    } finally {
      setDataLoading(false);
    }
  }

  async function handleClearCaches() {
    setCacheClearBusy(true);
    setError("");
    try {
      const result = await clearLocalCaches();
      setDataSummary(result);
      setMatches([]);
      setNotice(result.message || "Local caches cleared. Match insights are cleared from this session too.");
    } catch (cacheError) {
      setError(cacheError instanceof Error ? cacheError.message : "Could not clear local caches.");
    } finally {
      setCacheClearBusy(false);
    }
  }

  async function handleResetEverything() {
    if (resetConfirmationText.trim() !== "DELETE ALL LOCAL DATA") {
      setError("Type DELETE ALL LOCAL DATA exactly to confirm the reset.");
      return;
    }
    setDataResetBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await resetLocalWorkspaceData(resetConfirmationText.trim());
      // Invalidate any GET that started before the reset; otherwise a slow old
      // response could restore deleted jobs after the empty state is displayed.
      workflowRequestGeneration.current += 1;
      // Reset derived workflow state immediately. The Inbox is backed by jobs.json,
      // but its React state can outlive the deleted file until the next fetch.
      setWorkflowInboxData({
        success: true,
        total: 0,
        counts: { new: 0, reviewing: 0, shortlisted: 0, skipped: 0 },
        items: [],
      });
      setWorkflowEvents([]);
      workflowHasLoaded.current = false;
      setWorkflowLoading(false);
      if (result.counts.saved_jobs !== 0 || result.counts.applications !== 0) {
        throw new Error(
          `The reset endpoint still reports ${result.counts.saved_jobs} saved jobs and ${result.counts.applications} applications. Check that the frontend is connected to the intended CareerMate backend and data folder.`,
        );
      }
      setProfile(null);
      setCvStatus(EMPTY_STATUS);
      setProfileSaved(false);
      setJobs([]);
      setAvailableMatchJobs([]);
      setSelectedMatchJobIds([]);
      setMatches([]);
      setApplications([]);
      setSelectedApplicationId(null);
      setApplicationStatus("saved");
      setApplicationNotes("");
      setApplicationFollowUpDate("");
      setApplicationCoverLetter("");
      setApplicationAnswers([]);
      setApplicationQuestion("");
      setSelectedJob(null);
      setActiveSearch(null);
      setSearchOffset(0);
      setSearchHasMore(false);
      setSearchTotalReported(0);
      setSearchTotalApproximate(false);
      setSearchFilterNote("");
      setJobRoles("Software Engineer");
      setJobCountry("Sweden");
      setJobCity("Stockholm");
      setWorkMode("any");
      setPageSize(20);
      setSelectedSources([]);
      setSelectedPortalIds([]);
      setJobFilter("");
      setFile(null);
      setBrowserSession(null);
      setBrowserFieldDrafts([]);
      setBrowserDiagnostics(null);
      setAiTestMessage("");
      setCloudAiConsent(false);
      setShowResetConfirmation(false);
      setResetConfirmationText("");
      setDataSummary(result);
      const [settings, sources] = await Promise.all([
        getAiSettings().catch(() => null),
        getJobSources().catch(() => null),
      ]);
      if (settings) {
        setAiSettings(settings);
        setAiProviderDraft(settings.provider);
        setAiModelDraft(settings.providers[settings.provider].model);
        setAiBaseUrlDraft(settings.providers[settings.provider].base_url);
      }
      if (sources) setJobSources(sources.sources);
      // Re-fetch with cache disabled so an old HTTP response cannot repopulate the Inbox.
      await refreshWorkflowData();
      setActiveView("overview");
      setNotice(`${result.message || "Workspace reset complete."} Your backend/.env API keys and project files were kept.`);
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : "Could not clean the local workspace.");
    } finally {
      setDataResetBusy(false);
    }
  }

  async function handleCheckBrowserSetup() {
    setBrowserDiagnosticsLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await getBrowserDiagnostics();
      setBrowserDiagnostics(result);
      if (result.playwright_installed && result.chromium_installed) {
        setNotice("Browser setup looks ready. If a listing still fails to open, check the listing URL and network connection.");
      } else {
        setError(`${result.message} In the activated backend virtual environment, run: ${result.install_command}`);
      }
    } catch (diagnosticError) {
      setError(diagnosticError instanceof Error ? diagnosticError.message : "Could not inspect browser setup.");
    } finally {
      setBrowserDiagnosticsLoading(false);
    }
  }

  async function handleOpenBrowserAssistant() {
    if (!selectedApplication) return;
    setBrowserOpening(true);
    setBrowserSubmitApproved(false);
    setBrowserPreparedSteps([]);
    setError("");
    setNotice("Opening the employer page and detecting the current application step…");
    try {
      const versionResult = await getTailoredCvVersions().catch(() => ({ success: false, versions: [] as TailoredCvVersion[] }));
      const availableVersions = versionResult.versions;
      setTailoredCvVersions(availableVersions);
      const session = await openApplicationBrowser(selectedApplication.id);
      setBrowserSession(session);
      setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication, availableVersions));
      setNotice(session.field_count > 0
        ? `Browser opened. ${session.field_count} supported field(s) are ready for review. CareerMate can suggest answers and prepare this step.`
        : "Browser opened. Use Find application form to follow the safe Apply link, or sign in/complete verification manually if the employer requires it.");
    } catch (browserError) {
      let message = browserError instanceof Error ? browserError.message : "Could not open browser assistance.";
      try {
        const diagnostics = await getBrowserDiagnostics();
        setBrowserDiagnostics(diagnostics);
        if (!diagnostics.playwright_installed || !diagnostics.chromium_installed) message = `${diagnostics.message} In the activated backend virtual environment, run: ${diagnostics.install_command}`;
      } catch { /* Keep the original browser error. */ }
      setError(message);
      setNotice("");
    } finally { setBrowserOpening(false); }
  }

  async function refreshBrowserSession(session: BrowserFormSession, message?: string) {
    setBrowserSession(session);
    setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication));
    setBrowserSubmitApproved(false);
    setNotice(message ?? session.message);
  }

  async function handleScanBrowserForm() {
    setBrowserScanning(true);
    setError("");
    setNotice("Scanning the current application step, including supported dropdowns and choices…");
    try {
      const session = await scanBrowserForm();
      await refreshBrowserSession(session, `Scanned ${session.field_count} field(s). Review every proposed answer before filling.`);
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not scan the current form.");
      setNotice("");
    } finally { setBrowserScanning(false); }
  }

  async function handleAdvanceBrowserStep(intent: BrowserNavigationIntent) {
    if (!selectedApplication) return;
    setBrowserNavigating(true);
    setError("");
    setNotice(intent === "apply" ? "Opening the employer's application form…" : "Moving to the next application step…");
    try {
      const session = await advanceBrowserStep(selectedApplication.id, intent);
      await refreshBrowserSession(session, session.message);
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not navigate to the next application step.");
      setNotice("");
    } finally { setBrowserNavigating(false); }
  }

  async function handleAutoPrepareApplication() {
    if (!selectedApplication) return;
    if (!profile) {
      setError("Review and save your CV profile before using Auto prepare application.");
      setNotice("");
      return;
    }

    setBrowserAutoPreparing(true);
    setBrowserSubmitApproved(false);
    setBrowserPreparedSteps([]);
    setError("");
    setNotice("Starting automatic application preparation. CareerMate will use saved profile data and eligible AI drafts, follow supported application steps, and pause before final submission.");

    const prepared: PreparedBrowserStep[] = [];
    const seenSteps = new Set<string>();
    const maxSteps = 12;
    let session: BrowserFormSession;
    let stopMessage = "";
    let availableCvVersions = tailoredCvVersions;

    try {
      const versionResult = await getTailoredCvVersions().catch(() => null);
      if (versionResult) {
        availableCvVersions = versionResult.versions;
        setTailoredCvVersions(availableCvVersions);
      }
      session = browserSession?.application_id === selectedApplication.id
        ? browserSession
        : await openApplicationBrowser(selectedApplication.id);
      setBrowserSession(session);
      setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication, availableCvVersions));

      for (let stepNumber = 1; stepNumber <= maxSteps; stepNumber += 1) {
        // Some job pages expose only an Apply button; follow it before trying
        // to treat the listing as a form step.
        if (session.field_count === 0 && (session.has_apply_action || session.has_continue_action)) {
          const navIntent: BrowserNavigationIntent = session.has_apply_action ? "apply" : "continue";
          const navigationKey = `${session.url}|navigation:${navIntent}`;
          if (seenSteps.has(navigationKey)) {
            stopMessage = "The same navigation step appeared twice. CareerMate stopped to avoid a loop; inspect the current page in Chromium.";
            break;
          }
          seenSteps.add(navigationKey);
          session = await advanceBrowserStep(selectedApplication.id, navIntent);
          setBrowserSession(session);
          setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication, availableCvVersions));
          continue;
        }

        if (session.field_count === 0) {
          stopMessage = "No supported application fields or safe next-step control were found. This page may require sign-in, a security check, or a site-specific widget.";
          break;
        }

        const fingerprint = `${session.url}|${session.fields.map((field) => `${field.label}:${field.kind}`).join("|")}`;
        if (seenSteps.has(fingerprint)) {
          stopMessage = "CareerMate detected a repeated application step and stopped to avoid looping. Review the current page before continuing.";
          setBrowserSession(session);
          setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication, availableCvVersions));
          break;
        }
        seenSteps.add(fingerprint);

        let drafts = makeBrowserFieldDrafts(session, profile, selectedApplication, availableCvVersions);
        let aiNotice = "";
        const questionIds = drafts
          .filter((field) => ["text", "textarea"].includes(field.kind) && !field.value.trim())
          .map((field) => field.field_id)
          .slice(0, 20);
        if (questionIds.length > 0) {
          try {
            const result = await suggestBrowserAnswers(selectedApplication.id, questionIds, session.url);
            const suggestions = new Map(result.suggestions.map((item) => [item.field_id, item.value]));
            drafts = drafts.map((field) => {
              const suggestion = suggestions.get(field.field_id);
              return suggestion && !field.value.trim()
                ? { ...field, value: suggestion, include: true, reviewed: false, value_source: "ai", suggestion_source: "AI suggestion · review before use" }
                : field;
            });
            if (result.message) aiNotice = result.message;
          } catch (aiError) {
            aiNotice = aiError instanceof Error ? aiError.message : "AI suggestions were unavailable for this step.";
          }
        }

        setBrowserSession(session);
        setBrowserFieldDrafts(drafts);
        const fillable = drafts.filter((field) => field.include && field.value.trim());
        let filledCount = 0;
        let filledIds = new Set<string>();
        let attachmentNames: string[] = [];
        let attachmentNamesByFieldId = new Map<string, string>();
        let fillProblem = "";
        if (fillable.length > 0) {
          try {
            const fillResult = await fillBrowserForm(selectedApplication.id, fillable, session.url);
            filledCount = fillResult.filled_count;
            filledIds = new Set(fillResult.filled_field_ids ?? []);
            attachmentNames = (fillResult.attached_files ?? []).map((item) => item.filename);
            attachmentNamesByFieldId = new Map((fillResult.attached_files ?? []).map((item) => [item.field_id, item.filename] as const));
            if (fillResult.skipped.length) fillProblem = fillResult.skipped.map((item) => item.reason).join(" ");
          } catch (fillError) {
            fillProblem = fillError instanceof Error ? fillError.message : "CareerMate could not fill one or more reviewed fields.";
          }
        }

        drafts = drafts.map((field) => filledIds.has(field.field_id)
          ? { ...field, filled: true, include: false }
          : field);
        const missingRequired = drafts.filter((field) => {
          if (browserFieldNeedsUserInput(field)) return true;
          return field.include && fillable.some((item) => item.field_id === field.field_id)
            && !filledIds.has(field.field_id) && Boolean(fillProblem);
        });

        let status: PreparedBrowserStep["status"] = "completed";
        let note = `${filledCount} value(s) filled from your saved profile, existing application drafts, or eligible AI suggestions.`;
        if (attachmentNames.length) note += ` Attached document: ${attachmentNames.join(", ")}.`;
        if (aiNotice && !drafts.some((field) => questionIds.includes(field.field_id) && field.value.trim())) {
          note += ` AI answer generation did not produce an answer on this step: ${aiNotice}`;
        }
        if (fillProblem) note += ` Some fields may need attention: ${fillProblem}`;

        if (missingRequired.length > 0) {
          status = "needs_attention";
          note = `CareerMate stopped because ${missingRequired.length} required field(s) still need a trustworthy answer or explicit choice: ${missingRequired.map((field) => field.label).join(", ")}. Review them in the editable current-step panel.`;
        } else if (session.submit_available) {
          status = "ready";
          note += " Final submission control detected; CareerMate will pause here for your review and separate approval.";
        }

        const historyItem: PreparedBrowserStep = {
          step: stepNumber,
          title: session.title || `Application step ${stepNumber}`,
          url: session.url,
          fields: drafts.map((field) => ({
            label: field.label,
            value: field.kind === "file"
              ? attachmentNamesByFieldId.get(field.field_id) ?? browserFieldDisplayValue(field, availableCvVersions)
              : field.value,
            required: field.required,
            filled: filledIds.has(field.field_id),
          })),
          filled_count: filledCount,
          status,
          note,
        };
        prepared.push(historyItem);
        setBrowserPreparedSteps([...prepared]);
        setBrowserFieldDrafts(drafts);

        if (missingRequired.length > 0) {
          stopMessage = note;
          break;
        }
        if (session.submit_available) {
          stopMessage = "Automatic preparation reached a likely final submission step. Review the entire preparation summary and the live form before submitting.";
          break;
        }
        if (!session.has_continue_action && !session.has_apply_action) {
          status = "needs_attention";
          stopMessage = "CareerMate filled supported fields, but could not identify a safe Next/Continue control. Use the employer page to proceed, then refresh the current step.";
          prepared[prepared.length - 1] = { ...historyItem, status, note: stopMessage };
          setBrowserPreparedSteps([...prepared]);
          break;
        }

        const intent: BrowserNavigationIntent = session.has_continue_action ? "continue" : "apply";
        session = await advanceBrowserStep(selectedApplication.id, intent);
        setBrowserSession(session);
        setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication, availableCvVersions));
        setBrowserSubmitApproved(false);
      }

      if (!stopMessage && prepared.length >= maxSteps) {
        stopMessage = `Stopped after ${maxSteps} steps to avoid an endless navigation loop. Review the current form and continue manually if the application has more sections.`;
      }
      setBrowserPreparedSteps([...prepared]);
      if (prepared.length > 0 && prepared[prepared.length - 1].status === "ready") {
        setNotice(`${stopMessage || "Application preparation finished."} ${prepared.length} step(s) processed. Previous-step values are summarized below; the current step remains editable.`);
        setError("");
      } else if (prepared.length > 0) {
        setNotice(`${stopMessage || "Application preparation paused."} ${prepared.length} step(s) processed. Review the highlighted current step; nothing has been submitted.`);
        if (prepared[prepared.length - 1].status === "needs_attention") setError(stopMessage);
      } else {
        setError(stopMessage || "CareerMate could not prepare this application automatically.");
        setNotice("");
      }
    } catch (prepareError) {
      setError(prepareError instanceof Error ? prepareError.message : "CareerMate could not prepare the full application.");
      setNotice("");
    } finally {
      setBrowserAutoPreparing(false);
    }
  }

  async function handleSelectBrowserPage(pageIndex: number) {
    if (!selectedApplication) return;
    setBrowserScanning(true);
    setError("");
    setNotice("Switching CareerMate to the selected application tab and scanning its form…");
    try {
      const session = await selectBrowserPage(selectedApplication.id, pageIndex);
      await refreshBrowserSession(session, `Selected ${session.title || "application tab"}. Scanned ${session.field_count} supported field(s).`);
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not select that browser tab.");
      setNotice("");
    } finally { setBrowserScanning(false); }
  }

  async function handleSuggestBrowserAnswers() {
    if (!selectedApplication) return;
    const ids = browserFieldDrafts
      .filter((field) => ["text", "textarea"].includes(field.kind))
      .map((field) => field.field_id);
    if (!ids.length) { setError("There are no eligible text questions on this step for AI suggestions."); return; }
    setBrowserSuggesting(true);
    setError("");
    setNotice("Generating one batch of CV-grounded draft answers. Nothing will be filled until you approve it.");
    try {
      const result = await suggestBrowserAnswers(selectedApplication.id, ids, browserSession?.url);
      const suggestionsById = new Map(result.suggestions.map((item) => [item.field_id, item.value]));
      setBrowserFieldDrafts((current) => current.map((field) => {
        const suggestion = suggestionsById.get(field.field_id);
        if (!suggestion || (field.value.trim() && field.suggested_key !== "latest_answer")) return field;
        return { ...field, value: suggestion, include: true, reviewed: false, value_source: "ai", suggestion_source: result.suggestions.find((item) => item.field_id === field.field_id)?.source || "AI draft · review before use" };
      }));
      if (result.suggestions.length) {
        setNotice(result.message);
        setError("");
      } else {
        setError(result.message || "No usable drafts were returned. Required unanswered fields are highlighted for your input.");
        setNotice("");
      }
    } catch (suggestError) {
      setError(suggestError instanceof Error ? suggestError.message : "AI answer suggestions failed. You can still enter values manually.");
      setNotice("");
    } finally { setBrowserSuggesting(false); }
  }

  async function handleFillBrowserForm(continueAfterFill = false) {
    if (!selectedApplication) return;
    const selectedFields = browserFieldDrafts.filter((field) => field.include && field.value.trim());
    if (selectedFields.length === 0 && !continueAfterFill) {
      setError("Select at least one field with a reviewed value before filling."); setNotice(""); return;
    }
    setBrowserFilling(true);
    setError("");
    setNotice(continueAfterFill ? "Filling approved values before moving to the next step…" : `Filling ${selectedFields.length} reviewed field(s). The application will not be submitted by this action.`);
    try {
      let filledCount = 0;
      let skipped: { field_id: string; reason: string }[] = [];
      let attachedFiles: string[] = [];
      if (selectedFields.length) {
        const result = await fillBrowserForm(selectedApplication.id, selectedFields, browserSession?.url);
        filledCount = result.filled_count;
        skipped = result.skipped;
        attachedFiles = (result.attached_files ?? []).map((item) => item.filename);
      }
      if (continueAfterFill) {
        const next = await advanceBrowserStep(selectedApplication.id, "continue");
        await refreshBrowserSession(next, `Approved values filled (${filledCount}); moved to the next step. ${next.field_count} field(s) are ready for review.`);
      } else {
        const refreshed = await scanBrowserForm();
        setBrowserSession(refreshed);
        const filledIds = new Set(selectedFields.map((field) => field.field_id));
        const selectedById = new Map(selectedFields.map((field) => [field.field_id, field] as const));
        setBrowserFieldDrafts(makeBrowserFieldDrafts(refreshed, profile, selectedApplication, tailoredCvVersions).map((field) => {
          const selected = selectedById.get(field.field_id);
          const preserved = selected ? { ...field, value: selected.value, value_source: selected.value_source, reviewed: selected.reviewed } : field;
          return filledIds.has(field.field_id)
            ? { ...preserved, include: false, reviewed: true, filled: true, value_source: "manual" }
            : { ...preserved, include: false };
        }));
        setBrowserSubmitApproved(false);
        setNotice(`Filled ${filledCount} field(s)${attachedFiles.length ? ` · attached ${attachedFiles.join(", ")}` : ""}. CareerMate has not submitted the application. Review the visible employer form${skipped.length ? `; ${skipped.length} field(s) were skipped` : ""}.`);
      }
      if (skipped.length) setError(skipped.map((item) => `${item.field_id}: ${item.reason}`).join(" "));
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not fill the reviewed fields or continue to the next step.");
      setNotice("");
    } finally { setBrowserFilling(false); }
  }

  async function handleSubmitBrowserApplication() {
    if (!selectedApplication || !browserSubmitApproved) return;
    setBrowserSubmitting(true);
    setError("");
    setNotice("Submitting the final application step after your explicit approval…");
    try {
      const submittedDetails = [
        ...browserPreparedSteps.flatMap((step) => step.fields.filter((field) => field.filled).map((field) => ({ question: `Step ${step.step}: ${field.label}`, answer: field.value, updated_at: new Date().toISOString() }))),
        ...browserFieldDrafts.map((field) => ({ question: `${browserSession?.title || "Final step"}: ${field.label}`, answer: browserFieldDisplayValue(field, tailoredCvVersions), updated_at: new Date().toISOString() })),
      ].filter((detail) => detail.answer.trim()).filter((detail, index, all) => all.findIndex((candidate) => candidate.question === detail.question && candidate.answer === detail.answer) === index).slice(0, 50);
      const result = await submitBrowserApplication(selectedApplication.id, true, browserSession?.url, submittedDetails);
      setBrowserSession((current) => current ? { ...current, url: result.url, title: result.title, submit_available: false } : current);
      setBrowserSubmitApproved(false);
      if (result.confirmation_detected) {
        const all = await getApplications();
        setApplications(all.applications);
        const updated = all.applications.find((item) => item.id === selectedApplication.id);
        if (updated) selectApplication(updated);
      }
      setNotice(result.message);
      if (!result.confirmation_detected) setError("Check the employer's page before updating the status. No successful application confirmation was detected.");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not safely submit this application.");
      setNotice("");
    } finally { setBrowserSubmitting(false); }
  }

  async function handleCloseBrowserAssistant() {
    try {
      await closeBrowserSession();
      setBrowserSession(null);
      setBrowserFieldDrafts([]);
      setBrowserPreparedSteps([]);
      setBrowserSubmitApproved(false);
      setNotice("Browser session closed. Drafts stay local to this browser workspace.");
      setError("");
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not close the browser session.");
    }
  }

  function updateBrowserField(fieldId: string, changes: Partial<BrowserFieldDraft>) {
    setBrowserFieldDrafts((current) => current.map((field) => {
      if (field.field_id !== fieldId) return field;
      const valueChanged = Object.prototype.hasOwnProperty.call(changes, "value");
      const manuallyReviewed = valueChanged || changes.include === true;
      const nextValue = valueChanged ? String(changes.value ?? "") : field.value;
      const nextInclude = valueChanged
        ? Boolean(nextValue.trim())
        : changes.include ?? field.include;
      return {
        ...field,
        ...changes,
        include: nextInclude,
        reviewed: manuallyReviewed ? true : field.reviewed,
        value_source: manuallyReviewed ? "manual" : field.value_source,
        filled: false,
      };
    }));
  }

  function selectAllBrowserProposals() {
    setBrowserFieldDrafts((current) => current.map((field) => ({
      ...field,
      include: Boolean(field.value.trim()) && !["radio", "checkbox"].includes(field.kind),
    })));
    setNotice("All non-empty proposed values are selected for your review. Radio/checkbox choices still require an explicit selection.");
    setError("");
  }

  function editApplicationAnswer(index: number, answer: string) {
    setApplicationAnswers((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, answer } : item));
  }

  function updatePersonal<K extends keyof CandidatePersonal>(field: K, value: string) {
    setProfile((current) => current ? {
      ...current,
      personal: { ...current.personal, [field]: value },
    } : current);
    setProfileSaved(false);
  }

  function updateSummary(value: string) {
    setProfile((current) => current ? { ...current, summary: value } : current);
    setProfileSaved(false);
  }

  function updateList(field: "skills" | "certifications" | "languages" | "achievements", value: string) {
    const values = value.split("\n").map((item) => item.trim()).filter(Boolean);
    setProfile((current) => current ? { ...current, [field]: values } : current);
    setProfileSaved(false);
  }

  function addExperience() {
    const blank: Experience = {
      job_title: "", company: "", location: "", start_date: "", end_date: "", description: [],
    };
    setProfile((current) => current ? { ...current, experience: [...current.experience, blank] } : current);
    setProfileSaved(false);
  }

  function updateExperience(index: number, field: Exclude<keyof Experience, "description">, value: string) {
    setProfile((current) => {
      if (!current) return current;
      const experience = [...current.experience];
      experience[index] = { ...experience[index], [field]: value };
      return { ...current, experience };
    });
    setProfileSaved(false);
  }

  function updateExperienceDescription(index: number, value: string) {
    setProfile((current) => {
      if (!current) return current;
      const experience = [...current.experience];
      experience[index] = {
        ...experience[index],
        description: value.split("\n").map((item) => item.trim()).filter(Boolean),
      };
      return { ...current, experience };
    });
    setProfileSaved(false);
  }

  function removeExperience(index: number) {
    setProfile((current) => current ? {
      ...current,
      experience: current.experience.filter((_, itemIndex) => itemIndex !== index),
    } : current);
    setProfileSaved(false);
  }

  function addEducation() {
    const blank: Education = {
      degree: "", institution: "", location: "", start_date: "", end_date: "",
    };
    setProfile((current) => current ? { ...current, education: [...current.education, blank] } : current);
    setProfileSaved(false);
  }

  function updateEducation(index: number, field: keyof Education, value: string) {
    setProfile((current) => {
      if (!current) return current;
      const education = [...current.education];
      education[index] = { ...education[index], [field]: value };
      return { ...current, education };
    });
    setProfileSaved(false);
  }

  function removeEducation(index: number) {
    setProfile((current) => current ? {
      ...current,
      education: current.education.filter((_, itemIndex) => itemIndex !== index),
    } : current);
    setProfileSaved(false);
  }

  const savedCountLabel = jobs.length.toLocaleString();
  const canAnalyzeMatches = Boolean(profile && selectedMatchJobIds.some((id) => availableMatchJobs.some((job) => job.id === id)) && !matchLoading && !jobLoading && !cvLoading && !saving);
  const matchByJobId = new Map<string, JobMatchResult>(matches.map((match) => [match.id, match] as const));
  const availableMatchJobOrder = new Map<string, number>(availableMatchJobs.map((job, index) => [job.id, index] as const));
  const matchSelectionCandidates = availableMatchJobs.filter((job) => {
    const query = matchSelectionSearch.trim().toLocaleLowerCase();
    return !query || `${job.title} ${job.company} ${job.location} ${job.source}`.toLocaleLowerCase().includes(query);
  }).sort((first, second) => {
    const firstMatch = matchByJobId.get(first.id);
    const secondMatch = matchByJobId.get(second.id);
    // Put all analyzed jobs first, ordered by evidence-coverage score from highest to lowest.
    if (Boolean(firstMatch) !== Boolean(secondMatch)) return firstMatch ? -1 : 1;
    if (firstMatch && secondMatch) {
      const firstScore = firstMatch.match_score ?? -1;
      const secondScore = secondMatch.match_score ?? -1;
      if (firstScore !== secondScore) return secondScore - firstScore;
    }
    return (availableMatchJobOrder.get(first.id) ?? 0) - (availableMatchJobOrder.get(second.id) ?? 0);
  });
  const activeInsight = activeInsightJobId ? matchByJobId.get(activeInsightJobId) ?? null : null;

  const toggleMatchSelection = (jobId: string, checked: boolean) => {
    setSelectedMatchJobIds((current) => checked
      ? (current.includes(jobId) || current.length >= 20 ? current : [...current, jobId])
      : current.filter((id) => id !== jobId));
  };
  const applicationForJob = (jobId: string) => applications.find((application) => application.job_id === jobId);
  const hasAppliedToJob = (jobId: string) => {
    const application = applicationForJob(jobId);
    return Boolean(application?.applied_at) || Boolean(application && ["applied", "interview", "offer", "rejected", "withdrawn"].includes(application.status));
  };
  const profileCompletionFields = profile ? [
    profile.personal?.name,
    profile.personal?.email,
    profile.personal?.location,
    profile.summary,
    profile.skills.length ? "skills" : "",
    profile.experience.length ? "experience" : "",
    profile.education.length ? "education" : "",
  ] : [];
  const profileCompletion = profile ? Math.round((profileCompletionFields.filter((value) => Boolean(value?.trim())).length / profileCompletionFields.length) * 100) : 0;
  // Hide legacy/global-feed records from Explore. This view is intentionally
  // limited to active employer boards configured in Portals and selected for
  // the current search; legacy records remain preserved in local storage.
  // A completed search response is already scoped by FastAPI to selected,
  // enabled portal IDs. Trust that server-side decision: filtering it again in
  // the browser caused valid coverage matches to disappear from the result list.
  // Before a search (initial workspace load), keep filtering saved records locally.
  const explorePortalJobs = activeSearch
    ? jobs
    : jobs.filter((job) => isJobFromEnabledPortal(job, sourceConfig, selectedPortalIds));
  const filteredJobs = explorePortalJobs.filter((job) => {
    const needle = jobFilter.trim().toLocaleLowerCase();
    if (!needle) return true;
    return [job.title, job.company, job.location, job.description, ...(job.search_roles ?? [])]
      .some((value) => (value ?? "").toLocaleLowerCase().includes(needle));
  });
  const selectedExploreJobs = filteredJobs.filter((job) =>
    workflowInboxData?.items.some((item) => item.job.id === job.id && item.triage.stage === "shortlisted"),
  );
  const appliedExploreJobs = filteredJobs.filter((job) => hasAppliedToJob(job.id));
  const exploreTabJobs = exploreResultTab === "selected"
    ? selectedExploreJobs
    : exploreResultTab === "applied" ? appliedExploreJobs : filteredJobs;
  const sortedExploreJobs = [...exploreTabJobs].sort((first, second) => {
    if (exploreSort === "company") return first.company.localeCompare(second.company);
    if (exploreSort === "newest") {
      const firstDate = Date.parse(first.published_at || "") || 0;
      const secondDate = Date.parse(second.published_at || "") || 0;
      return secondDate - firstDate || first.company.localeCompare(second.company);
    }
    return 0;
  });
  const explorePageSize = activeSearch?.limit ?? pageSize;
  const explorePageCount = Math.max(1, Math.ceil(sortedExploreJobs.length / explorePageSize));
  const exploreCurrentPage = Math.min(Math.floor(searchOffset / explorePageSize) + 1, explorePageCount);
  const explorePageStart = (exploreCurrentPage - 1) * explorePageSize;
  const visibleExploreJobs = exploreResultTab === "results"
    ? sortedExploreJobs.slice(explorePageStart, explorePageStart + explorePageSize)
    : sortedExploreJobs;
  const portalMatchesFilteredByAdvancedFilters = portalCoverage.some((portal) => portal.eligible_matches > 0)
    && portalCoverage.every((portal) => portal.returned_count === 0);
  const selectedApplication = applications.find((application) => application.id === selectedApplicationId) ?? null;
  const exploreTailorJob = selectedJob ?? sortedExploreJobs[0] ?? null;
  const exploreBrowserFields = selectedApplication && browserSession?.application_id === selectedApplication.id
    ? browserFieldDrafts
    : [];
  const exploreAnsweredFields = exploreBrowserFields.filter((field) => !browserFieldNeedsUserInput(field)).length;
  const exploreRequiredFields = exploreBrowserFields.filter(browserFieldNeedsUserInput).length;
  const activeApplicationCount = applications.filter((application) => !["rejected", "withdrawn", "offer"].includes(application.status)).length;
  const submittedApplicationCount = applications.filter((application) => ["applied", "interview", "offer", "rejected", "withdrawn"].includes(application.status)).length;
  const visibleApplications = applications.filter((application) => {
    if (applicationListTab === "active") return ["saved", "preparing"].includes(application.status);
    if (applicationListTab === "submitted") return ["applied", "interview", "offer", "rejected", "withdrawn"].includes(application.status);
    if (applicationListTab === "offers") return ["interview", "offer"].includes(application.status);
    return true;
  });
  const canGenerateApplicationDraft = Boolean(selectedApplication && profile && !applicationSaving && !draftingAnswer && !draftingCoverLetter);
  const configuredEmployerPortals = BOARD_PROVIDERS.flatMap((provider) => sourceConfig[provider].map((board, index) => ({
    provider,
    board,
    index,
    id: employerPortalId(provider, board),
  }))).filter((portal) => employerBoardIdentifier(portal.provider, portal.board));
  const portalHealthById = new Map<string, PortalHealthItem>((portalHealth?.items ?? []).map((item) => [item.id, item] as const));
  const enabledPortalCount = configuredEmployerPortals.filter((portal) => portal.board.enabled).length;
  const pausedPortalCount = configuredEmployerPortals.length - enabledPortalCount;
  const sortedEmployerPortals = [...configuredEmployerPortals].sort((a, b) => {
    if (a.board.enabled !== b.board.enabled) return Number(b.board.enabled) - Number(a.board.enabled);
    return (a.board.company || employerBoardIdentifier(a.provider, a.board)).localeCompare(
      b.board.company || employerBoardIdentifier(b.provider, b.board),
      undefined,
      { sensitivity: "base" },
    );
  });
  const portalLiveCount = configuredEmployerPortals.filter(({ board, id }) => board.enabled && portalHealthById.get(id)?.status === "live").length;
  const portalEmptyCount = configuredEmployerPortals.filter(({ board, id }) => board.enabled && portalHealthById.get(id)?.status === "empty").length;
  const portalAttentionCount = configuredEmployerPortals.filter(({ board, id }) => board.enabled && ["broken", "needs_setup"].includes(portalHealthById.get(id)?.status ?? "")).length;
  const portalNotCheckedCount = configuredEmployerPortals.filter(({ board, id }) => board.enabled && (portalHealthById.get(id)?.status ?? "not_checked") === "not_checked").length;
  const visibleEmployerPortals = sortedEmployerPortals.filter(({ provider, board, id }) => {
    const health = portalHealthById.get(id);
    const status: PortalHealthStatus = board.enabled ? (health?.status ?? "not_checked") : "paused";
    const haystack = `${board.company ?? ""} ${employerPortalDomain(provider, board)} ${BOARD_PROVIDER_LABELS[provider]} ${board.country ?? ""}`.toLowerCase();
    const matchesSearch = haystack.includes(portalSearch.trim().toLowerCase());
    const matchesFilter = portalFilter === "all"
      || (portalFilter === "enabled" && board.enabled)
      || (portalFilter === "paused" && !board.enabled)
      || (portalFilter === "attention" && (status === "broken" || status === "needs_setup"));
    return matchesSearch && matchesFilter;
  });
  const pageMeta: Record<WorkspaceView, { title: string; eyebrow: string; description: string }> = {
    overview: {
      title: "Today",
      eyebrow: "YOUR WORKSPACE",
      description: "A focused view of new opportunities, next actions, application progress and recent activity.",
    },
    discover: {
      title: "Explore Opportunities",
      eyebrow: "EXPLORE OPPORTUNITIES",
      description: "Find new roles from your configured portals. Results are fetched only from the companies you monitor.",
    },
    platforms: {
      title: "Portals",
      eyebrow: "EMPLOYER PORTALS",
      description: "Monitor the employer career pages you follow and keep supported job boards healthy.",
    },
    matches: {
      title: "Know why a role fits",
      eyebrow: "MATCH INSIGHTS",
      description: "Review evidence-backed strengths and gaps before spending time on an application.",
    },
    applications: {
      title: "Pipeline",
      eyebrow: "APPLICATION MANAGEMENT",
      description: "Move each opportunity through preparation, submission, interviews and outcomes.",
    },
    inbox: {
      title: "Job inbox",
      eyebrow: "DISCOVERY TRIAGE",
      description: "Review every newly discovered opportunity before deciding whether it belongs in your pipeline.",
    },
    followups: {
      title: "Follow-ups",
      eyebrow: "KEEP CONVERSATIONS MOVING",
      description: "See which applications need attention and manage the next contact from one place.",
    },
    documents: {
      title: "Documents",
      eyebrow: "APPLICATION MATERIALS",
      description: "Find tailored CVs and application drafts associated with your opportunities.",
    },
    profile: {
      title: "CV",
      eyebrow: "YOUR CAREER PROFILE",
      description: "Maintain verified candidate information, manage your source CV and tailor documents to specific roles.",
    },
    ai: {
      title: "Choose your AI engine",
      eyebrow: "AI SETTINGS",
      description: "Choose local Ollama for private offline inference, OpenAI for hosted responses, or another OpenAI-compatible API.",
    },
    data: {
      title: "Manage your local data",
      eyebrow: "DATA MANAGEMENT",
      description: "Review what CareerMate stores on this computer, clear derived caches, or reset your workspace when you want a fresh start.",
    },
    analytics: {
      title: "See what is working",
      eyebrow: "CAREER ANALYTICS",
      description: "Understand your job-search funnel, matching quality, application progress and source effectiveness.",
    },
    automation: {
      title: "Scheduled scans",
      eyebrow: "DISCOVERY AUTOMATION",
      description: "Manage saved searches, recurring discovery checks and new opportunity alerts while keeping application decisions in your hands.",
    },
    settings: {
      title: "Config",
      eyebrow: "WORKSPACE PREFERENCES",
      description: "Configure your AI provider, connected employer portals, privacy and local workspace data.",
    },
  };
  const currentMeta = pageMeta[activeView];
  const currentActivity = jobLoading
    ? "Searching your selected employer portals…"
    : matchLoading
      ? "Comparing job requirements with your profile…"
      : cvLoading
        ? `Processing your CV with ${aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider"}…`
        : saving
          ? "Saving your profile locally…"
          : "";
  const sourceLabel = (source: string) => {
    const value = source.toLowerCase();
    if (value.includes("linkedin")) return "LinkedIn";
    if (value.includes("indeed")) return "Indeed";
    if (value.includes("glassdoor")) return "Glassdoor";
    if (value.includes("jobtech") || value.includes("arbetsformedlingen") || value.includes("platsbanken")) return "JobTech";
    if (value.includes("remoteok") || value.includes("remote ok")) return "Remote OK";
    if (value.includes("arbeitnow")) return "Arbeitnow";
    if (value.includes("greenhouse")) return "Greenhouse";
    if (value.includes("teamtailor")) return "Teamtailor";
    if (value.includes("smartrecruiters")) return "SmartRecruiters";
    if (value.includes("workable")) return "Workable";
    if (value.includes("recruitee")) return "Recruitee";
    if (value.includes("breezy")) return "Breezy HR";
    if (value.includes("personio")) return "Personio";
    if (value.includes("workday")) return "Workday";
    if (value.includes("ashby")) return "Ashby";
    if (value.includes("lever")) return "Lever";
    return source.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  };
  const workModeLabel = (mode?: string) => mode === "remote" ? "Remote" : mode === "hybrid" ? "Hybrid" : mode === "on_site" ? "On-site" : "Work mode unknown";
  const renderJobRow = (job: JobResult, compact = false) => {
    const sourceUrl = safeExternalUrl(job.apply_url || job.source_url);
    const match = matches.find((item) => item.id === job.id);
    const tracked = Boolean(applicationForJob(job.id));
    return (
      <article className={`job-row${compact ? " job-row-compact" : ""}`} data-company={job.company.trim().toLocaleLowerCase()} key={job.id}>
        <div className="company-avatar" aria-hidden="true">{(job.company || "?").trim().slice(0, 1).toUpperCase()}</div>
        <div className="job-row-main">
          <button className="job-title-button" type="button" onClick={() => setSelectedJob(job)}>{job.title}</button>
          <div className="job-row-meta"><strong>{job.company || "Company not listed"}</strong><i aria-hidden="true">·</i><span>{sourceLabel(job.source)}</span><i aria-hidden="true">·</i><span>{job.location || "Location not listed"}</span></div>
          <div className="job-badges">
            <span className={`job-mode-badge mode-${job.work_mode ?? "unknown"}`}>{workModeLabel(job.work_mode)}</span>
            {job.salary_min != null && job.salary_max != null && <span className="job-role-badge">{job.salary_currency || ""} {job.salary_min.toLocaleString()}–{job.salary_max.toLocaleString()}</span>}
            {(job.search_roles ?? []).slice(0, 2).map((role) => <span className="job-role-badge" key={role}>{role}</span>)}
            {match?.match_score !== undefined && match.match_score !== null && <span className="match-chip">{match.match_score}% CV match</span>}
            {hasAppliedToJob(job.id) && <span className="job-history-pill">Already applied{applicationForJob(job.id)?.status === "offer" ? " · Offer" : ""}</span>}
          </div>
          {!compact && job.description && <p className="job-row-description">{job.description}</p>}
        </div>
        <div className="job-row-actions">
          {match?.match_score !== undefined && match.match_score !== null && <span className="job-match-score">{Math.round(match.match_score)}<small>/100</small></span>}
          <button className="button button-secondary button-small" type="button" onClick={() => { if (match) openExistingInsight(job.id); else setSelectedJob(job); }}><Icon name="eye" /> {match ? "View insight" : "View details"}</button>
          <button className="job-track-button" type="button" disabled={tracked} onClick={() => void handleTrackJob(job.id)} aria-label={tracked ? "Already in pipeline" : `Add ${job.title} to pipeline`} title={tracked ? "Already in pipeline" : "Add to pipeline"}><Icon name={tracked ? "check" : "bookmark"} /></button>
          {sourceUrl && <a className="button button-primary button-small job-apply-button" href={sourceUrl} target="_blank" rel="noopener noreferrer">Apply <Icon name="arrow-up-right" /></a>}
        </div>
      </article>
    );
  };

  return (
    <>
    <WorkspaceShell
      activeView={activeView}
      meta={currentMeta}
      activity={currentActivity}
      status={profile && !profileSaved ? "Profile has unsaved edits" : "Local workspace ready"}
      avatar={profile?.personal?.name?.trim()?.charAt(0)?.toUpperCase() || "C"}
      candidateName={profile?.personal?.name?.trim() || "Complete your profile"}
      profileProgress={profileCompletion}
      hostedAi={Boolean(aiSettings?.provider && aiSettings.provider !== "ollama")}
      matchCount={matches.length}
      jobCount={jobs.length}
      applicationCount={applications.length}
      inboxCount={workflowInboxData?.counts ? workflowInboxData.counts.new + workflowInboxData.counts.reviewing + workflowInboxData.counts.shortlisted : 0}
      followupCount={applications.filter((application) => Boolean(application.follow_up_date) && !["rejected", "withdrawn", "offer"].includes(application.status) && new Date(`${application.follow_up_date}T00:00:00`) <= new Date(new Date().toDateString())).length}
      onNavigate={(view) => {
        setActiveView(view);
        setSelectedJob(null);
        setActiveInsightJobId(null);
        // The Inbox is derived from the backend job store. Refresh it whenever
        // the user returns to Inbox/Today so manual resets and data cleanup show immediately.
        if (view === "inbox" || view === "overview") void refreshWorkflowData();
      }}
      onGoHome={() => {
        setActiveView("overview");
        setSelectedJob(null);
        setActiveInsightJobId(null);
        void refreshWorkflowData();
      }}
    >
          {initialLoading && <div className="loading-line"><span className="spinner" /> Loading your local workspace…</div>}

          {(error || notice) && (
            <div className={`toast ${error ? "toast-error" : "toast-success"}`} role={error ? "alert" : "status"} aria-live={error ? "assertive" : "polite"}>
              <span className="toast-symbol">{error ? "!" : "✓"}</span>
              <span className="toast-message">{error || notice}</span>
              <button className="toast-dismiss" type="button" onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss notification">×</button>
            </div>
          )}

          {activeView === "overview" && (
            <TodayDashboard
              jobsCount={jobs.length}
              inbox={workflowInboxData?.items ?? []}
              counts={workflowInboxData?.counts ?? { new: 0, reviewing: 0, shortlisted: 0, skipped: 0 }}
              applications={applications}
              profileReady={Boolean(profile && profileSaved)}
              matchCount={matches.length}
              events={workflowEvents}
              onNavigate={(view) => {
                setActiveView(view);
                if (view === "inbox" || view === "overview") void refreshWorkflowData();
              }}
            />
          )}

          {activeView === "inbox" && (
            <JobInbox
              items={workflowInboxData?.items ?? []}
              counts={workflowInboxData?.counts ?? { new: 0, reviewing: 0, shortlisted: 0, skipped: 0 }}
              loading={workflowLoading}
              onReview={(job) => { setSelectedJob(job); if (workflowInboxData?.items.some((item) => item.job.id === job.id && item.triage.stage === "new")) void handleUpdateJobTriage(job.id, "reviewing"); }}
              onTriage={handleUpdateJobTriage}
              onPromote={handleTrackJob}
              onExplore={() => setActiveView("discover")}
            />
          )}

          {activeView === "followups" && (
            <FollowUps
              applications={applications}
              onOpen={(application) => { selectApplication(application); setActiveView("applications"); }}
              onPipeline={() => setActiveView("applications")}
            />
          )}

          {activeView === "documents" && (
            <DocumentsLibrary
              versions={tailoredCvVersions}
              applications={applications}
              onOpenApplication={(application) => { selectApplication(application); setActiveView("applications"); }}
              onOpenCv={() => setActiveView("profile")}
            />
          )}

          {activeView === "analytics" && (
            <AnalyticsStudio
              jobs={jobs}
              matches={matches}
              applications={applications}
              savedSearchCount={savedSearches.length}
              alertCount={jobAlerts.length}
              onNavigate={(view) => setActiveView(view)}
            />
          )}

          {activeView === "automation" && (
            <AutomationCenter
              sources={jobSources}
              searches={savedSearches}
              alerts={jobAlerts}
              checkingId={checkingAlertId}
              onCheckSearch={(id) => { void handleCheckSavedSearch(id); }}
              onOpenSources={() => setActiveView("platforms")}
              onOpenDiscover={() => setActiveView("discover")}
            />
          )}

          {activeView === "discover" && (
            <div className="view-stack explore-workspace">
              <div className="discover-layout explore-layout">
                <section className="panel search-filters-panel explore-search-panel">
                  <div className="explore-panel-heading">
                    <div><span className="explore-mini-label">SEARCH SETUP</span><h2>Find the right role</h2></div>
                    <span className="explore-panel-icon"><Icon name="sliders" /></span>
                  </div>
                  <form onSubmit={handleSearchJobs} className="explore-search-form">
                    <label className="field explore-role-field"><span>Search roles</span><div className="explore-role-input"><input value={jobRoles.replace(/\s*\n\s*/g, ", ")} onChange={(event) => setJobRoles(event.target.value.replace(/,\s*/g, "\n"))} placeholder="Software Engineer" aria-label="Search roles" /><Icon name="search" /></div></label>
                    <label className="field explore-location-field"><span>Location</span><div className="explore-location-input"><input value={[jobCity, jobCountry].filter(Boolean).join(", ")} onChange={(event) => { const parts = event.target.value.split(",").map((part) => part.trim()); if (parts.length > 1) { setJobCity(parts.slice(0, -1).join(", ")); setJobCountry(parts[parts.length - 1]); } else { setJobCity(event.target.value); } }} placeholder="e.g. Stockholm, Sweden" aria-label="Location" /><Icon name="chevron-down" /></div></label>
                    <label className="field"><span>Work arrangement</span><FloatingSelect ariaLabel="Work arrangement" value={workMode} onChange={(value) => setWorkMode(value as WorkMode)} options={[{ value: "any", label: "Any / not specified" }, { value: "remote", label: "Remote" }, { value: "hybrid", label: "Hybrid" }, { value: "on_site", label: "On-site" }]} /></label>

                    <details className="source-settings explore-advanced-filters">
                      <summary><span><Icon name="filter" /> Advanced filters</span><span className="source-settings-count">Salary · freshness · exclusions</span></summary>
                      <div className="platform-form-grid">
                        <label className="field"><span>Results per page</span><FloatingSelect ariaLabel="Results per page" value={String(pageSize)} onChange={(value) => { const nextSize = Number(value); setPageSize(nextSize); setSearchOffset(0); setActiveSearch((current) => current ? { ...current, limit: nextSize } : current); }} options={[{ value: "10", label: "10 jobs" }, { value: "20", label: "20 jobs" }, { value: "40", label: "40 jobs" }]} /></label>
                        <label className="field"><span>Country</span><input list="careermate-country-options" value={jobCountry} onChange={(event) => setJobCountry(event.target.value)} placeholder="Choose a country" maxLength={100} required /></label>
                        <datalist id="careermate-country-options"><option value="Sweden" /><option value="Norway" /><option value="Denmark" /><option value="Finland" /><option value="Germany" /><option value="Netherlands" /><option value="United Kingdom" /><option value="United States" /><option value="Canada" /><option value="France" /><option value="Switzerland" /><option value="Ireland" /><option value="Spain" /><option value="Italy" /><option value="Poland" /><option value="Australia" /><option value="India" /><option value="Singapore" /><option value="Japan" /><option value="Any country" /></datalist>
                        <label className="field"><span>Minimum salary</span><input type="number" min="0" value={minimumSalary} onChange={(event) => setMinimumSalary(event.target.value)} placeholder="e.g. 40000" /></label>
                        <label className="field"><span>Maximum salary</span><input type="number" min="0" value={maximumSalary} onChange={(event) => setMaximumSalary(event.target.value)} placeholder="e.g. 65000" /></label>
                        <label className="field"><span>Posted within</span><FloatingSelect ariaLabel="Posted within" value={freshnessDays} onChange={setFreshnessDays} options={[{ value: "7", label: "7 days" }, { value: "14", label: "14 days" }, { value: "30", label: "30 days" }, { value: "90", label: "90 days" }, { value: "any", label: "Any date" }]} /></label>
                        <label className="field"><span>Exclude companies</span><input value={excludedCompaniesText} onChange={(event) => setExcludedCompaniesText(event.target.value)} placeholder="Company names, separated by commas" /></label>
                      </div>
                      <p className="helper-text">Salary and freshness filters apply only when the original listing provides usable data.</p>
                    </details>

                    <section className="explore-portals-section" aria-labelledby="explore-portals-title">
                      <div className="explore-portals-heading">
                        <div><strong id="explore-portals-title">Portals ({enabledPortalCount})</strong><span>{selectedPortalIds.length} selected</span></div>
                        <small>{enabledPortalCount} connected</small>
                      </div>
                      {configuredEmployerPortals.length === 0 ? (
                        <div className="explore-portals-empty"><Icon name="radar" /><span>No company portals connected yet.</span><button type="button" onClick={() => setActiveView("platforms")}>Connect portals <Icon name="arrow-up-right" /></button></div>
                      ) : (
                        <div className="explore-portal-picker">
                          {sortedEmployerPortals.filter(({ board }) => board.enabled).map(({ provider, board, id }) => {
                            const selectable = canSelectSource(provider, jobSources[provider]);
                            const companyName = board.company || employerBoardIdentifier(provider, board) || BOARD_PROVIDER_LABELS[provider];
                            return (
                              <label className={`explore-portal-option${selectable ? "" : " is-unavailable"}`} key={id}>
                                <input type="checkbox" checked={selectedPortalIds.includes(id)} disabled={!selectable || jobLoading} onChange={(event) => toggleEmployerPortal(id, event.target.checked)} />
                                <span className={`explore-company-mark explore-mark-${provider}`} data-company={companyName.trim().toLocaleLowerCase()}>{companyName.trim().slice(0, 1).toUpperCase()}</span>
                                <span className="explore-portal-copy"><strong>{companyName}</strong><small>{BOARD_PROVIDER_LABELS[provider]}</small></span>
                                {!selectable && <span className="explore-portal-warning">Setup needed</span>}
                              </label>
                            );
                          })}
                        </div>
                      )}
                      <button type="button" className="explore-manage-portals" onClick={() => setActiveView("platforms")}>Manage portals <Icon name="arrow-up-right" /></button>
                    </section>

                    <button className="button button-primary button-full search-submit explore-search-submit" disabled={jobLoading || selectedPortalIds.length === 0} type="submit">
                      {jobLoading ? <><span className="spinner spinner-light" /> Searching portals…</> : <><Icon name="search" /> Search from my portals</>}
                    </button>
                  </form>

                  <div className="saved-search-controls explore-saved-search-controls">
                    <FloatingSelect ariaLabel="Saved search alert frequency" value={alertFrequency} onChange={(value) => setAlertFrequency(value as "manual" | "daily" | "weekly")} options={[{ value: "manual", label: "Manual checks" }, { value: "daily", label: "Daily alerts" }, { value: "weekly", label: "Weekly alerts" }]} />
                    <input value={savedSearchName} onChange={(event) => setSavedSearchName(event.target.value)} aria-label="Saved search name" placeholder="Name this search" />
                    <button type="button" className="button button-secondary button-small" disabled={!selectedPortalIds.length} onClick={() => void handleSaveCurrentSearch()}>Save search</button>
                  </div>
                  {savedSearches.length > 0 && <section className="saved-search-list explore-saved-search-list"><h3>Saved searches</h3>{savedSearches.map((item) => <div className="saved-search-row" key={item.id}><span><strong>{item.name}</strong><small>{item.roles.join(", ")} · {item.city}, {item.country} · {(item.portal_ids?.length ?? 0) || item.sources.length} portal(s)</small></span><button type="button" className="text-action" disabled={checkingAlertId === item.id} onClick={() => void handleCheckSavedSearch(item.id)}>{checkingAlertId === item.id ? "Checking…" : "Check new jobs"}</button><button type="button" className="text-action" onClick={async () => { await deleteSavedSearch(item.id); await refreshSavedSearches(); }}>Delete</button></div>)}</section>}
                  {jobAlerts.length > 0 && <section className="saved-search-list"><h3>New job alerts</h3>{jobAlerts.slice(0, 8).map((alert) => <div className="saved-search-row" key={alert.id}><span><strong>{alert.title}</strong><small>{alert.company} · {alert.location} · {alert.search_name}</small></span>{alert.url && <a className="text-action" href={alert.url} target="_blank" rel="noreferrer">Open job</a>}{!alert.read && <button type="button" className="text-action" onClick={async () => { await markJobAlertRead(alert.id); await refreshSavedSearches(); }}>Mark read</button>}</div>)}</section>}
                  <div className="filter-footnote"><Icon name="shield" /><span>Searches are user-initiated. Normal searches reuse a short 2-minute cache; use Refresh portals to bypass it and check the connected boards live.</span></div>
                </section>

                <section className="panel results-panel explore-results-panel">
                  <div className="explore-results-toolbar">
                    <div className="explore-results-tabs" role="tablist" aria-label="Explore result categories">
                      <button type="button" role="tab" aria-selected={exploreResultTab === "results"} className={exploreResultTab === "results" ? "is-active" : ""} onClick={() => setExploreResultTab("results")}>Results <span>{explorePortalJobs.length}</span></button>
                      <button type="button" role="tab" aria-selected={exploreResultTab === "selected"} className={exploreResultTab === "selected" ? "is-active" : ""} onClick={() => setExploreResultTab("selected")}>Selected <span>{selectedExploreJobs.length}</span></button>
                      <button type="button" role="tab" aria-selected={exploreResultTab === "applied"} className={exploreResultTab === "applied" ? "is-active" : ""} onClick={() => setExploreResultTab("applied")}>Applied <span>{appliedExploreJobs.length}</span></button>
                    </div>
                    <div className="explore-results-actions">
                      <button type="button" className="button button-secondary button-small explore-refresh-portals" disabled={jobLoading || !activeSearch || selectedPortalIds.length === 0} onClick={() => activeSearch && void executeJobSearch(activeSearch, true)} title="Bypass the short portal cache and fetch the latest published jobs" aria-label="Refresh connected portals now">
                        <Icon name="refresh" /> <span>Refresh portals</span>
                      </button>
                      <FloatingSelect ariaLabel="Sort job results" value={exploreSort} onChange={(value) => { setExploreSort(value as "relevance" | "newest" | "company"); setSearchOffset(0); }} options={[{ value: "relevance", label: "Sort: Relevance" }, { value: "newest", label: "Sort: Newest" }, { value: "company", label: "Sort: Company" }]} />
                      <div className="explore-view-switch" role="group" aria-label="Result layout">
                        <button type="button" className={exploreViewMode === "list" ? "is-active" : ""} onClick={() => setExploreViewMode("list")} aria-label="List view"><Icon name="files" /></button>
                        <button type="button" className={exploreViewMode === "grid" ? "is-active" : ""} onClick={() => setExploreViewMode("grid")} aria-label="Grid view"><Icon name="grid" /></button>
                      </div>
                    </div>
                  </div>
                  <div className="results-heading explore-results-heading"><div><p className="eyebrow">MATCHING EMPLOYER LISTINGS</p><h2>{exploreResultTab === "applied" ? "Applied opportunities" : exploreResultTab === "selected" ? "Shortlisted opportunities" : "Job results"} <span className="count-pill">{exploreResultTab === "applied" ? appliedExploreJobs.length : exploreResultTab === "selected" ? selectedExploreJobs.length : explorePortalJobs.length}</span></h2><p className="panel-description">Search results from the company portals you selected. Open a listing to review its details before applying.</p></div><div className="results-state"><span className="status-live-dot" /> {selectedPortalIds.length} portals selected</div></div>
                  {portalCoverage.length > 0 && exploreResultTab === "results" && <section className="explore-portal-coverage" aria-label="Portal search coverage">
                    <div className="explore-portal-coverage-heading"><strong>Portal coverage</strong><span>Each selected company board is checked independently</span></div>
                    <div className="explore-portal-coverage-grid">
                      {portalCoverage.map((portal) => <article className={`explore-coverage-card is-${portal.status.replace(/[^a-z0-9_-]/gi, "-")}`} key={portal.portal_id}>
                        <div className="explore-coverage-top"><strong>{portal.company}</strong><span>{portal.provider}</span></div>
                        <div className="explore-coverage-metrics"><span><b>{portal.fetched_count.toLocaleString()}</b><small>fetched</small></span><span><b>{portal.role_matches.toLocaleString()}</b><small>title matches</small></span><span><b>{portal.eligible_matches.toLocaleString()}</b><small>after location</small></span><span><b>{portal.returned_count.toLocaleString()}</b><small>in Explore</small></span></div>
                        <p>{portal.age_seconds != null ? `Updated ${portal.age_seconds < 60 ? `${portal.age_seconds}s` : `${Math.floor(portal.age_seconds / 60)}m`} ago. ` : "Freshness timestamp unavailable. "}{portal.warning || (portal.status === "matched" ? "Board retrieved and filtered successfully." : portal.status === "empty" ? "The provider returned no published listings." : portal.status === "no_role_matches" ? "No job titles matched the requested role." : portal.status === "filtered_by_location" ? "Role titles matched, but location/work-mode filters excluded them." : portal.status === "partial" ? "Only part of this board was retrieved. Review the warning." : portal.status === "stale" ? "Showing a previously saved snapshot. Live refresh failed." : portal.status === "error" ? "The board could not be refreshed." : "No confirmed matching listings yet.")}</p>
                      </article>)}
                    </div>
                  </section>}
                  <div className="results-toolbar"><label className="result-search"><Icon name="search" /><input type="search" value={jobFilter} onChange={(event) => { setJobFilter(event.target.value); setSearchOffset(0); }} placeholder="Filter by role, company or keyword" aria-label="Filter job results" /><kbd>⌕</kbd></label><span className="results-summary">{exploreTabJobs.length === 0 ? "0 jobs" : exploreResultTab === "results" ? `Showing ${explorePageStart + 1}–${Math.min(explorePageStart + explorePageSize, sortedExploreJobs.length)} of ${sortedExploreJobs.length}` : `${exploreTabJobs.length} shown`}</span></div>
                  {jobLoading && <div className="inline-progress"><span className="spinner" /><div><strong>Searching your company portals</strong><p>Fetching listings from each selected employer board and removing duplicates.</p></div></div>}
                  {!jobLoading && sortedExploreJobs.length === 0 ? <div className="empty-state results-empty"><span className="empty-icon"><Icon name="search" /></span><h3>{exploreResultTab === "applied" ? "No applied roles in these results" : exploreResultTab === "selected" ? "No shortlisted roles yet" : explorePortalJobs.length ? "No jobs match that filter" : portalMatchesFilteredByAdvancedFilters ? "Portal matches were excluded by advanced filters" : "No portal opportunities yet"}</h3><p>{exploreResultTab === "applied" ? "Roles you have applied to from your selected portals will appear here." : exploreResultTab === "selected" ? "Shortlist opportunities in your Inbox to keep them easy to find here." : explorePortalJobs.length ? "Try a different title, employer or keyword." : portalMatchesFilteredByAdvancedFilters ? "The selected portals found jobs matching your title and location, but the final advanced filters removed them. Review salary, freshness and company exclusions, then search again." : "Connect company career pages in Portals, select the companies you want to monitor, then search."}</p>{explorePortalJobs.length ? <button className="button button-secondary" type="button" onClick={() => { setJobFilter(""); setSearchOffset(0); setExploreResultTab("results"); }}>Clear filters</button> : portalMatchesFilteredByAdvancedFilters ? <button className="button button-secondary" type="button" onClick={() => { setMinimumSalary(""); setMaximumSalary(""); setFreshnessDays("any"); setExcludedCompaniesText(""); setJobFilter(""); setSearchOffset(0); if (activeSearch) void executeJobSearch({ ...activeSearch, min_salary: undefined, max_salary: undefined, posted_within_days: undefined, excluded_companies: [] }); }}>Clear advanced exclusions and search again</button> : <button className="button button-primary" type="button" onClick={() => setActiveView("platforms")}>Connect portals</button>}</div> : <div className={`job-results-list explore-job-results${exploreViewMode === "grid" ? " is-grid" : ""}`}>{visibleExploreJobs.map((job) => renderJobRow(job))}</div>}
                  {activeSearch && exploreResultTab === "results" && <><div className="search-pagination"><div><strong>Page {exploreCurrentPage} of {explorePageCount}</strong><span className="helper-text">{`${sortedExploreJobs.length.toLocaleString()} unique jobs after role, location and advanced filters. Sorting and keyword filtering apply to the complete returned inventory.`}</span></div><div className="button-row pagination-buttons"><button className="button button-secondary" type="button" onClick={() => changeSearchPage(-1)} disabled={jobLoading || searchOffset === 0}>Previous</button><button className="button button-secondary" type="button" onClick={() => changeSearchPage(1)} disabled={jobLoading || explorePageStart + explorePageSize >= sortedExploreJobs.length}>Next page</button></div></div>{searchFilterNote && <p className="search-filter-note">{searchFilterNote}</p>}</>}
                </section>
              </div>
              <div className="explore-lower-grid">
                <section className="panel explore-tailor-panel" aria-labelledby="explore-tailor-title">
                  <div className="explore-lower-heading">
                    <span className="explore-lower-icon"><Icon name="file" /></span>
                    <div>
                      <h2 id="explore-tailor-title">Tailor your CV for this role</h2>
                      <p>Generate a role-specific CV using your verified profile and the employer's job description.</p>
                    </div>
                  </div>
                  <div className="explore-tailor-body">
                    <div className="explore-tailor-controls">
                      <div className="explore-tailor-target">
                        <span>ROLE TO TARGET</span>
                        <strong>{exploreTailorJob?.title || "Choose a job from the results"}</strong>
                        <small>{exploreTailorJob ? `${exploreTailorJob.company || "Company not listed"} · ${exploreTailorJob.location || "Location not listed"}` : "Search your portals to choose a role."}</small>
                      </div>
                      <label className="field"><span>CV template</span><FloatingSelect ariaLabel="Explore CV template" value={cvTemplate} onChange={(value) => setCvTemplate(value as "classic" | "modern" | "compact" | "sectioned")} options={[{ value: "classic", label: "Classic ATS" }, { value: "modern", label: "Modern professional" }, { value: "compact", label: "Compact ATS" }, { value: "sectioned", label: "Sectioned professional · Recommended" }]} /></label>
                      <button className="button button-primary button-full explore-tailor-submit" type="button" disabled={!exploreTailorJob || !profile || tailoringCv} onClick={() => void handleTailorCvForSelectedJob(exploreTailorJob)}>
                        {tailoringCv ? <><span className="spinner spinner-light" /> Creating tailored CV…</> : <><Icon name="sparkles" /> Generate tailored CV and ATS score</>}
                      </button>
                      {cvTailorError && <p className="explore-tailor-error" role="alert">{cvTailorError}</p>}
                      {tailoredCv && <p className="explore-tailor-success" role="status"><Icon name="check" /> Tailored CV generated. Find it in Documents.</p>}
                    </div>
                    <div className="explore-cv-preview" aria-hidden="true">
                      <div className="explore-cv-paper">
                        <span className="explore-cv-name" />
                        <span className="explore-cv-headline" />
                        <span className="explore-cv-rule" />
                        {Array.from({ length: 3 }, (_, index) => <span className="explore-cv-section" key={index}><b /><i /><i /><i /></span>)}
                      </div>
                    </div>
                  </div>
                </section>

                <section className="panel explore-questions-panel" aria-labelledby="explore-questions-title">
                  <div className="explore-lower-heading explore-questions-heading">
                    <span className="explore-lower-icon"><Icon name="file" /></span>
                    <div>
                      <h2 id="explore-questions-title">Application questions</h2>
                      <p>{selectedApplication ? `${selectedApplication.company || "Selected employer"} · ${selectedApplication.title}` : "Review employer questions and prepared answers before submitting."}</p>
                    </div>
                    {exploreBrowserFields.length > 0 && <div className="explore-question-counts"><span>{exploreBrowserFields.length} questions</span><span className="is-complete">{exploreAnsweredFields} filled</span><span className="is-pending">{exploreRequiredFields} need input</span></div>}
                  </div>
                  {exploreBrowserFields.length > 0 ? (
                    <div className="explore-question-list">
                      {exploreBrowserFields.slice(0, 3).map((field) => {
                        const needsInput = browserFieldNeedsUserInput(field);
                        const answer = browserFieldDisplayValue(field, tailoredCvVersions);
                        return <div className={`explore-question-row${needsInput ? " is-pending" : " is-complete"}`} key={field.field_id}>
                          <span className="explore-question-status"><Icon name={needsInput ? "clock" : "check"} /></span>
                          <strong>{field.label}</strong>
                          <span className="explore-question-answer">{answer || (needsInput ? "Your input is required" : "Reviewed")}</span>
                          <span className={`explore-question-state${needsInput ? " is-pending" : " is-complete"}`}>{needsInput ? "Required" : "Reviewed"}</span>
                        </div>;
                      })}
                      {exploreBrowserFields.length > 3 && <p className="explore-question-more">+ {exploreBrowserFields.length - 3} more fields in the application assistant</p>}
                      <div className="explore-questions-footer"><span><Icon name="shield" /> Answers remain in your local workspace until you approve submission.</span><button type="button" className="text-action" onClick={() => setActiveView("applications")}>Review application <Icon name="arrow-up-right" /></button></div>
                    </div>
                  ) : (
                    <div className="explore-questions-empty">
                      <div><strong>{selectedApplication ? "No employer form is open" : "No application form is open"}</strong><p>{selectedApplication ? "Open the application assistant to scan the current employer step and review supported questions." : "Track a role and open its application form to prepare employer questions and answers here."}</p></div>
                      <button type="button" className="button button-secondary button-small" onClick={() => setActiveView("applications")}>Open Pipeline <Icon name="arrow-up-right" /></button>
                    </div>
                  )}
                </section>
              </div>
            </div>
          )}

          {activeView === "platforms" && (
            <div className="view-stack portals-view">
              <section className="portal-intro">
                <div className="portal-intro-copy">
                  <span className="portal-intro-icon"><Icon name="radar" /></span>
                  <div>
                    <p className="eyebrow">EMPLOYER MONITORING</p>
                    <h2>Employer boards you follow</h2>
                    <p>Keep your target companies in one place. Health checks show which public ATS boards are responding and which need attention.</p>
                  </div>
                </div>
                <div className="portal-intro-actions">
                  <button className="button button-secondary" type="button" onClick={() => { setPortalAddOpen(true); document.getElementById("portal-add-panel")?.scrollIntoView({ behavior: "smooth", block: "center" }); }}><Icon name="plus" /> Add portal</button>
                  <button className="button button-primary" type="button" onClick={() => void handleCheckPortals()} disabled={portalHealthChecking || enabledPortalCount === 0}>
                    {portalHealthChecking ? <><span className="spinner spinner-light" /> Checking portals…</> : <><Icon name="radar" /> Check portal health</>}
                  </button>
                  <button className="button button-secondary" type="button" onClick={() => void handleRefreshSourceConfig()} disabled={sourceConfigLoading || sourceConfigSaving}>
                    {sourceConfigLoading ? <><span className="spinner" /> Refreshing…</> : <><Icon name="refresh" /> Refresh config</>}
                  </button>
                </div>
              </section>

              <section className="portal-health-strip" aria-live="polite">
                <div className="portal-health-summary-copy">
                  <strong>{configuredEmployerPortals.length} employer portal{configuredEmployerPortals.length === 1 ? "" : "s"} configured</strong>
                  <span>{enabledPortalCount} enabled <i /> {pausedPortalCount} paused {portalHealth?.checked_at ? <> <i /> Last check {new Date(portalHealth.checked_at).toLocaleString()}</> : <><i /> Run a health check to verify availability</>}</span>
                </div>
                <div className="portal-health-summary-stats">
                  <span className="portal-health-stat is-live"><b>{portalLiveCount}</b> live</span>
                  <span className="portal-health-stat is-empty"><b>{portalEmptyCount}</b> empty</span>
                  <span className="portal-health-stat is-unchecked"><b>{portalNotCheckedCount}</b> not checked</span>
                  <span className="portal-health-stat is-warning"><b>{portalAttentionCount}</b> attention</span>
                </div>
              </section>

              <section className="panel portal-directory-panel">
                <div className="portal-section-heading">
                  <div>
                    <p className="eyebrow">MONITORED EMPLOYERS</p>
                    <h2>Monitored employers</h2>
                    <p className="panel-description">Live status, job availability and connection details for each company career page.</p>
                  </div>
                  <span className="portal-total-chip">{configuredEmployerPortals.length} portals</span>
                </div>

                {configuredEmployerPortals.length > 0 && <div className="portal-directory-tools">
                  <label className="portal-search"><Icon name="search" /><input type="search" value={portalSearch} onChange={(event) => setPortalSearch(event.target.value)} placeholder="Find a company or portal…" aria-label="Search monitored portals" /></label>
                  <div className="portal-filter-tabs" role="group" aria-label="Filter employer portals">
                    {([ ["all", "All", configuredEmployerPortals.length], ["enabled", "Active", enabledPortalCount], ["paused", "Paused", pausedPortalCount], ["attention", "Attention", portalAttentionCount] ] as const).map(([value, label, count]) => <button key={value} type="button" className={portalFilter === value ? "is-active" : ""} onClick={() => setPortalFilter(value)}>{label}<span>{count}</span></button>)}
                  </div>
                </div>}

                {configuredEmployerPortals.length === 0 ? (
                  <div className="portal-empty-state">
                    <span className="portal-empty-icon"><Icon name="radar" /></span>
                    <h3>Your portal directory is empty</h3>
                    <p>Add the career page of a company you want to follow. CareerMate will identify the supported ATS board and check whether its public jobs endpoint is responding.</p>
                    <button className="button button-primary" type="button" onClick={() => setPortalAddOpen(true)}><Icon name="plus" /> Add your first portal</button>
                  </div>
                ) : (
                  <div className="portal-list">
                    {visibleEmployerPortals.map(({ provider, board, index, id }) => {
                      const health = portalHealthById.get(id);
                      const status: PortalHealthStatus = board.enabled ? (health?.status ?? "not_checked") : "paused";
                      const message = !board.enabled ? "Paused. This portal is excluded from searches." : health?.message ?? "Not checked yet. Run a health check to verify this board.";
                      const identifier = employerBoardIdentifier(provider, board);
                      const careerPageUrl = safeExternalUrl(board.career_url?.trim() ?? "");
                      const jobsBoardUrl = employerPortalJobsUrl(provider, board);
                      const primaryValue = provider === "greenhouse" ? board.board_token ?? "" : provider === "lever" ? board.site ?? "" : provider === "teamtailor" ? board.api_key_env ?? "" : board.slug ?? "";
                      const primaryLabel = provider === "greenhouse" ? "Board token" : provider === "lever" ? "Site slug" : provider === "teamtailor" ? "API key environment variable" : provider === "workday" ? "Careers URL" : "Employer board slug";
                      return (
                        <article className={`portal-row portal-row-${status}`} key={id}>
                          <span className="portal-brand-mark" aria-label={`${board.company || identifier || BOARD_PROVIDER_LABELS[provider]} on ${BOARD_PROVIDER_LABELS[provider]}`}><span className={`portal-company-monogram portal-monogram-${provider}`}>{(board.company || identifier || BOARD_PROVIDER_LABELS[provider]).trim().slice(0, 2).toUpperCase()}</span><span className="portal-provider-mini"><SourceMark source={provider} /></span></span>
                          <div className="portal-row-main">
                            <div className="portal-row-titleline"><strong>{board.company || identifier || BOARD_PROVIDER_LABELS[provider]}</strong>{board.starter_sample && <span className="portal-starter-chip">Starter</span>}<span className={`portal-status-badge status-${status}`}><i />{portalStatusLabel(status)}</span></div>
                            <span className="portal-domain-line">{employerPortalDomain(provider, board)} <span>·</span> {BOARD_PROVIDER_LABELS[provider]}{board.country ? ` · ${board.country}` : ""}</span>
                            <small className="portal-row-message">{message}{health?.duration_ms != null ? ` · ${health.duration_ms} ms` : ""}</small>
                            {(careerPageUrl || jobsBoardUrl) && <div className="portal-url-actions">
                              {careerPageUrl && <a href={careerPageUrl} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right" /> Career page</a>}
                              {jobsBoardUrl && <a href={jobsBoardUrl} target="_blank" rel="noopener noreferrer"><Icon name="files" /> Public jobs board</a>}
                            </div>}
                          </div>
                          {health?.job_count != null && <span className="portal-job-count"><strong>{health.job_count.toLocaleString()}</strong><small>jobs</small></span>}
                          <label className="portal-enable-toggle" title={board.enabled ? "Pause this portal" : "Enable this portal"}>
                            <input type="checkbox" checked={board.enabled} onChange={(event) => updateEmployerBoard(provider, index, { enabled: event.target.checked })} />
                            <span>{board.enabled ? "Enabled" : "Paused"}</span>
                          </label>
                          <details className="portal-row-manage">
                            <summary>Manage</summary>
                            <div className="portal-row-editor">
                              <div className="portal-row-editor-grid">
                                <label className="field"><span>Company name</span><input value={board.company ?? ""} onChange={(event) => updateEmployerBoard(provider, index, { company: event.target.value })} maxLength={200} /></label>
                                <label className="field"><span>Country</span><input value={board.country ?? ""} onChange={(event) => updateEmployerBoard(provider, index, { country: event.target.value })} maxLength={100} /></label>
                                <label className="field"><span>{primaryLabel}</span><input value={primaryValue} onChange={(event) => provider === "greenhouse" ? updateEmployerBoard(provider, index, { board_token: event.target.value }) : provider === "lever" ? updateEmployerBoard(provider, index, { site: event.target.value }) : provider === "teamtailor" ? updateEmployerBoard(provider, index, { api_key_env: event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_") }) : updateEmployerBoard(provider, index, { slug: event.target.value })} maxLength={1000} /></label>
                                <label className="field"><span>Company career page URL</span><input type="url" value={board.career_url ?? ""} onChange={(event) => updateEmployerBoard(provider, index, { career_url: event.target.value })} placeholder="https://careers.example.com" maxLength={1000} /></label>
                                <label className="field"><span>Public jobs board URL</span><input type="url" value={board.jobs_url ?? ""} onChange={(event) => updateEmployerBoard(provider, index, { jobs_url: event.target.value })} placeholder="https://jobs.example.com" maxLength={1000} /></label>
                                {(provider === "lever" || provider === "teamtailor") && <label className="field"><span>API region</span><FloatingSelect ariaLabel="API region" value={board.region ?? (provider === "lever" ? "global" : "eu")} onChange={(value) => updateEmployerBoard(provider, index, { region: value })} options={(provider === "lever" ? [{ value: "global", label: "Global" }, { value: "eu", label: "Europe" }] : [{ value: "eu", label: "Europe" }, { value: "na", label: "North America" }, { value: "apac", label: "Asia Pacific" }])} /></label>}
                              </div>
                              <label className="field portal-notes-field"><span>Portal notes</span><textarea value={board.notes ?? ""} onChange={(event) => updateEmployerBoard(provider, index, { notes: event.target.value })} rows={2} maxLength={1000} placeholder="Optional notes about the company portal or setup." /></label>
                              {provider === "teamtailor" && <p className="helper-text">Store the API key in backend/.env. CareerMate only saves the environment variable name here.</p>}
                              <div className="portal-row-editor-actions"><button className="button button-danger button-small" type="button" onClick={() => removeEmployerBoard(provider, index)}><Icon name="trash" /> Remove portal</button></div>
                            </div>
                          </details>
                        </article>
                      );
                    })}
                    {visibleEmployerPortals.length === 0 && <div className="portal-filter-empty"><strong>No portals match this view</strong><span>Try another filter or search term.</span><button className="text-action" type="button" onClick={() => { setPortalFilter("all"); setPortalSearch(""); }}>Clear filters</button></div>}
                  </div>
                )}
                <div className="portal-directory-footer">
                  <span><Icon name="shield" /> Health checks contact supported public ATS endpoints. Credentials are never shown in this directory.</span>
                  <button className="button button-secondary button-small" type="button" onClick={() => void handleSaveSourceConfig()} disabled={sourceConfigSaving}>{sourceConfigSaving ? <><span className="spinner" /> Saving…</> : <><Icon name="check" /> Save portal changes</>}</button>
                </div>
              </section>

              <details id="portal-add-panel" className={`panel portal-add-panel${portalAddOpen ? " is-open" : ""}`} open={portalAddOpen} onToggle={(event) => setPortalAddOpen(event.currentTarget.open)}>
                <summary>
                  <span className="portal-add-symbol"><Icon name="plus" /></span>
                  <span className="portal-add-copy"><strong>Add an employer portal</strong><small>Connect a public Greenhouse, Lever, Teamtailor or supported ATS board.</small></span>
                  <span className="portal-add-chevron"><Icon name="chevron-down" /></span>
                </summary>
                <div className="portal-add-content">
                  <div className="platform-form-grid">
                    <label className="field"><span>ATS provider</span><FloatingSelect ariaLabel="ATS provider" value={newBoardProvider} onChange={(value) => { const provider = value as EmployerBoardProvider; setNewBoardProvider(provider); setNewBoardRegion(provider === "teamtailor" ? "eu" : "global"); }} options={[{ value: "greenhouse", label: "Greenhouse" }, { value: "lever", label: "Lever" }, { value: "teamtailor", label: "Teamtailor" }, { value: "ashby", label: "Ashby" }, { value: "smartrecruiters", label: "SmartRecruiters" }, { value: "workable", label: "Workable" }, { value: "recruitee", label: "Recruitee" }, { value: "breezy", label: "Breezy HR" }, { value: "personio", label: "Personio" }, { value: "workday", label: "Workday" }]} /></label>
                    {newBoardProvider !== "teamtailor" && <label className="field"><span>{newBoardProvider === "greenhouse" ? "Board token" : newBoardProvider === "lever" ? "Site slug" : newBoardProvider === "workday" ? "Full Workday careers URL" : "Employer board slug"}</span><input value={newBoardIdentifier} onChange={(event) => setNewBoardIdentifier(event.target.value)} placeholder={newBoardProvider === "workday" ? "https://acme.wd5.myworkdayjobs.com/en-US/External" : "e.g. acme"} maxLength={1000} /></label>}
                    <label className="field"><span>Company display name</span><input value={newBoardCompany} onChange={(event) => setNewBoardCompany(event.target.value)} placeholder="e.g. Example AB" maxLength={200} /></label>
                    <label className="field"><span>Country</span><input value={newBoardCountry} onChange={(event) => setNewBoardCountry(event.target.value)} placeholder="e.g. Sweden" maxLength={100} /></label>
                    <label className="field"><span>Company career page URL</span><input type="url" value={newBoardCareerUrl} onChange={(event) => setNewBoardCareerUrl(event.target.value)} placeholder="https://careers.example.com" maxLength={1000} /></label>
                    <label className="field"><span>Public jobs board URL</span><input type="url" value={newBoardJobsUrl} onChange={(event) => setNewBoardJobsUrl(event.target.value)} placeholder="https://jobs.example.com" maxLength={1000} /></label>
                    {(newBoardProvider === "lever" || newBoardProvider === "teamtailor") && <label className="field"><span>API region</span><FloatingSelect ariaLabel="API region" value={newBoardRegion} onChange={setNewBoardRegion} options={(newBoardProvider === "lever" ? [{ value: "global", label: "Global" }, { value: "eu", label: "Europe" }] : [{ value: "eu", label: "Europe" }, { value: "na", label: "North America" }, { value: "apac", label: "Asia Pacific" }])} /></label>}
                    {newBoardProvider === "teamtailor" && <label className="field"><span>API key environment variable</span><input value={newBoardApiKeyEnv} onChange={(event) => setNewBoardApiKeyEnv(event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))} placeholder="CAREERMATE_TEAMTAILOR_API_KEY" maxLength={100} /><small>Enter the variable name, not the secret. Add its value to backend/.env.</small></label>}
                  </div>
                  <label className="field portal-notes-field"><span>Setup notes</span><textarea value={newBoardNotes} onChange={(event) => setNewBoardNotes(event.target.value)} rows={2} maxLength={1000} placeholder="Optional information about the portal or its configuration." /></label>
                  <div className="portal-add-actions"><button type="button" className="button button-secondary" onClick={addEmployerBoard}><Icon name="plus" /> Add to directory</button><button type="button" className="button button-primary" onClick={() => void handleSaveSourceConfig()} disabled={sourceConfigSaving}>{sourceConfigSaving ? "Saving…" : "Save portal settings"}</button></div>
                </div>
              </details>

            </div>
          )}

          {activeView === "matches" && (
            <div className="view-stack">
              <section className="match-toolbar panel">
                <div className="match-toolbar-copy"><span className="match-toolbar-symbol"><Icon name="sparkles" /></span><div><p className="eyebrow">EVIDENCE-BASED COMPARISON</p><h2>Understand the fit, not just the score</h2><p className="panel-description">CareerMate compares requirements with facts in your reviewed profile. Scores estimate evidence coverage, not your chance of being hired.</p></div></div>
                <div className="match-controls"><span className="selected-job-count">{selectedMatchJobIds.filter((id) => availableMatchJobs.some((job) => job.id === id)).length} selected · max 20</span><button className="button button-primary" onClick={handleMatchJobs} disabled={!canAnalyzeMatches} type="button">{matchLoading ? <><span className="spinner spinner-light" /> Analyzing…</> : <><Icon name="sparkles" /> Analyze selected jobs</>}</button></div>
              </section>
              <section className="panel match-job-picker">
                <div className="match-job-picker-heading"><div><p className="eyebrow">CHOOSE ROLES TO ANALYSE</p><h3>Find jobs and select the roles you care about</h3><p>Choose from the jobs currently loaded or saved in your Find jobs history. New search results are added to this list. The first three results are preselected as a starting point.</p></div><span className="count-pill">{selectedMatchJobIds.filter((id) => availableMatchJobs.some((job) => job.id === id)).length} / 20</span></div>
                <div className="match-job-picker-tools"><input className="match-job-search" type="search" aria-label="Search jobs to analyze" value={matchSelectionSearch} onChange={(event) => setMatchSelectionSearch(event.target.value)} placeholder="Search title, company, location or source…" /><button type="button" className="text-action" onClick={() => setSelectedMatchJobIds((current) => [...new Set([...current, ...matchSelectionCandidates.map((job) => job.id)])].slice(0, 20))} disabled={selectedMatchJobIds.length >= 20 || !matchSelectionCandidates.some((job) => !selectedMatchJobIds.includes(job.id))}>Select visible</button><button type="button" className="text-action" onClick={() => setSelectedMatchJobIds([])} disabled={selectedMatchJobIds.length === 0}>Clear</button></div>
                {availableMatchJobs.length ? <div className="match-job-picker-list">{matchSelectionCandidates.map((job) => {
                  const existing = applicationForJob(job.id);
                  const applied = hasAppliedToJob(job.id);
                  const checked = selectedMatchJobIds.includes(job.id);
                  const insight = matchByJobId.get(job.id);
                  const isAnalyzing = analyzingJobIds.includes(job.id);
                  const scoreClass = insight?.match_score == null ? "score-unavailable" : insight.match_score >= 75 ? "score-strong" : insight.match_score >= 50 ? "score-medium" : "score-low";
                  const actionLabel = isAnalyzing ? "Analyzing…" : insight && insight.match_score !== null ? "View insight" : insight ? "Retry analysis" : "Analyze job";
                  return <div className={`match-job-option${checked ? " selected" : ""}${insight ? " has-insight" : ""}`} key={job.id}>
                    <div className="match-job-option-main">
                      <input type="checkbox" aria-label={`Select ${job.title} for bulk analysis`} checked={checked} disabled={(!checked && selectedMatchJobIds.length >= 20) || matchLoading || isAnalyzing} onChange={(event) => toggleMatchSelection(job.id, event.target.checked)} />
                      <span className="match-job-option-copy"><button type="button" className="match-job-title-button" onClick={() => { if (insight) openExistingInsight(job.id); else void handleAnalyzeSingleJob(job); }} disabled={isAnalyzing || matchLoading || !profile} aria-label={`${insight ? "View insight for" : "Analyze"} ${job.title}`}>{job.title}</button><small>{job.company || "Company not listed"} · {job.location || "Location not listed"}</small><small className="match-job-row-status">{insight ? `${insight.requirements?.length ?? 0} criteria assessed · ${insight.match_confidence || "confidence unavailable"}` : "Not analysed yet · Select Analyze job to view a report"}</small></span>
                    </div>
                    <div className="match-job-option-actions">
                      {insight && <span className={`match-list-score ${scoreClass}`} title="Evidence-coverage score, not a hiring probability">{insight.match_score === null ? "N/A" : `${insight.match_score}/100`}</span>}
                      {applied ? <span className="job-history-pill">Already applied{existing?.status === "offer" ? " · Offer" : ""}</span> : null}
                      <button className={`button button-small ${insight && insight.match_score !== null ? "button-secondary" : "button-primary"} match-job-insight-action`} type="button" disabled={matchLoading || isAnalyzing || jobLoading || cvLoading || saving || !profile} onClick={() => { if (insight && insight.match_score !== null) openExistingInsight(job.id); else void handleAnalyzeSingleJob(job); }} title={!profile ? "Analyze your CV and save your profile first" : undefined}>
                        {isAnalyzing ? <><span className="spinner" /> {actionLabel}</> : insight && insight.match_score !== null ? <><Icon name="eye" /> {actionLabel}</> : <><Icon name="sparkles" /> {actionLabel}</>}
                      </button>
                    </div>
                  </div>;
                })}{matchSelectionCandidates.length === 0 && <p className="helper-text">No jobs match that search.</p>}</div> : <div className="match-job-picker-empty"><p>No job results are loaded yet.</p><button className="button button-secondary button-small" type="button" onClick={() => setActiveView("discover")}>Find jobs first <Icon name="arrow" /></button></div>}
              </section>
              {!profile && <div className="inline-hint setup-hint"><Icon name="user" /><div><strong>Your profile is the starting point</strong><p>Upload and analyze your CV, review the extracted facts, and save the profile before running match analysis.</p><button className="button button-secondary" type="button" onClick={() => setActiveView("profile")}>Set up profile <Icon name="arrow" /></button></div></div>}
              {profile && !profileSaved && <div className="inline-hint"><Icon name="info" /><span>Your profile has unsaved edits. CareerMate saves the reviewed version before matching.</span><button className="text-action" type="button" onClick={() => setActiveView("profile")}>Review profile</button></div>}
              {matchLoading && <div className="inline-progress match-progress"><span className="spinner" /><div><strong>Retrieving full job descriptions and comparing requirements</strong><p>CareerMate first tries to read the public original listing when the saved description is only a short snippet, then checks the requirements against your profile. Results are cached for repeat runs.</p></div></div>}
              {matches.length === 0 && !matchLoading && <p className="match-list-empty-hint">Your analysis reports open in a separate panel. Choose <strong>Analyze job</strong> on any row to create the first report.</p>}
              {activeInsight && createPortal(<div className="match-insight-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setActiveInsightJobId(null); }}>
                <section className="match-insight-drawer" role="dialog" aria-modal="true" aria-labelledby="active-match-report-title">
                  <header className="match-insight-drawer-header"><div><p className="eyebrow">MATCH INSIGHT</p><h2 id="active-match-report-title">{activeInsight.title}</h2><p>{activeInsight.company || "Company not listed"} · {activeInsight.location || "Location not listed"}</p></div><button type="button" className="match-insight-close" onClick={() => setActiveInsightJobId(null)} aria-label="Close match insight">×</button></header>
                  <div className="match-insight-drawer-body"><article className="match-card">
                <div className="match-card-header"><div><p className="eyebrow">MATCH REPORT</p><h3>{activeInsight.title}</h3><p>{activeInsight.company} · {activeInsight.location}</p>{activeInsight.description_fetch_message?.startsWith("Manually pasted advert text") ? <span className="manual-advert-label">USER-PASTED ADVERT · VERIFY SOURCE</span> : activeInsight.description_source !== "original_listing" && <span className="provisional-score-label">PRELIMINARY SCORE · FULL ADVERT NOT RETRIEVED</span>}</div><div className={`score-badge ${activeInsight.match_score === null ? "score-unavailable" : activeInsight.match_score >= 75 ? "score-strong" : activeInsight.match_score >= 50 ? "score-medium" : "score-low"}`}><strong>{activeInsight.match_score === null ? "N/A" : activeInsight.match_score}</strong><span>{activeInsight.match_score === null ? "Score unavailable" : "/ 100"}</span></div></div>
                {activeInsight.match_score !== null ? <div className="score-track"><span style={{ width: `${Math.max(0, Math.min(100, activeInsight.match_score))}%` }} /></div> : <div className="score-unavailable-explainer"><strong>No reliable score was produced</strong><p>{activeInsight.match_confidence === "unavailable" ? activeInsight.match_explanation || "The AI provider did not return a reliable requirement assessment." : (activeInsight.requirements ?? []).length === 0 ? "CareerMate could not extract usable requirements from the text available for this role. The score is intentionally withheld rather than guessing." : activeInsight.match_explanation || "The extracted requirements could not be weighted reliably, so CareerMate has withheld the score."}</p></div>}
                <div className="match-meta"><span>Confidence: {activeInsight.match_confidence}</span><span>Requirements found: {(activeInsight.requirements ?? []).length}</span><span>{activeInsight.description_fetch_message?.startsWith("Manually pasted advert text") ? "Pasted advert analysed" : activeInsight.job_description_source === "original_listing" ? "Full listing analysed" : "Search snippet analysed"}</span><button className="text-action" type="button" onClick={() => { setSelectedJob(activeInsight); setActiveInsightJobId(null); }}>Open role details <Icon name="arrow" /></button></div>
                <section className={`decision-panel ${activeInsight.recommendation === "review_critical_gaps" || activeInsight.recommendation === "significant_gaps" ? "decision-panel-warning" : activeInsight.recommendation === "incomplete_description" ? "decision-panel-incomplete" : activeInsight.recommendation === "strong_potential_fit" ? "decision-panel-positive" : "decision-panel-neutral"}`}>
                  <div className="decision-panel-heading"><div><p className="eyebrow">APPLICATION GUIDANCE</p><h4>{activeInsight.recommendation_label ?? "Review the requirements"}</h4></div><span className={`decision-gap-count${(activeInsight.critical_gaps?.length ?? 0) > 0 ? " has-critical-gaps" : ""}`}>{activeInsight.critical_gaps?.length ?? 0} critical gaps</span></div>
                  <p>{activeInsight.recommendation_explanation ?? activeInsight.match_explanation}</p>
                  {(activeInsight.critical_gaps?.length ?? 0) > 0 && <div className="critical-gap-list">{(activeInsight.critical_gaps ?? []).map((item, index) => <div className="critical-gap-item" key={`${item.requirement}-${index}`}><span>CRITICAL GAP</span><div><strong>{item.requirement}</strong><p>{item.status === "partially_supported" ? "Only partly supported by the current profile." : "Not evidenced in the current profile; verify against the full CV before deciding."} {item.explanation}</p></div></div>)}</div>}
                </section>
                <p className="match-explanation">{activeInsight.match_explanation}</p>
                {activeInsight.description_source !== "original_listing" && <div className="match-incomplete-notice"><div><strong>Don't decide from this score yet</strong><p>{activeInsight.description_fetch_message || "The original employer advert has not been retrieved. The requirements below may be incomplete, so this score is provisional."}</p></div><div className="match-incomplete-actions"><button className="button button-secondary button-small" type="button" onClick={() => void handleEnrichAndReanalyze(activeInsight)} disabled={enrichingJobId === activeInsight.id || matchLoading}>{enrichingJobId === activeInsight.id ? <><span className="spinner" /> Fetching…</> : <><Icon name="refresh" /> Fetch &amp; reanalyse</>}</button><button className="button button-secondary button-small" type="button" onClick={() => { setManualAdvertJobId(manualAdvertJobId === activeInsight.id ? null : activeInsight.id); setManualAdvertText(""); }} disabled={matchLoading}>{manualAdvertJobId === activeInsight.id ? "Close paste form" : "Paste advert text"}</button></div></div>}
                {manualAdvertJobId === activeInsight.id && <div className="manual-advert-entry"><div><strong>Paste the original advert</strong><p>Open “Review original job advert”, copy the job description and paste it here. It will be stored in your local CareerMate workspace; it is not independently verified.</p></div><textarea aria-label="Paste original job advert text" value={manualAdvertText} onChange={(event) => setManualAdvertText(event.target.value)} rows={8} maxLength={30000} placeholder="Paste responsibilities, requirements, qualifications and bonus skills…" /><div className="manual-advert-actions"><span>{manualAdvertText.trim().length.toLocaleString()} / 30,000 characters · at least 300 required</span><button className="button button-primary button-small" type="button" onClick={() => void handleSaveManualAdvert(activeInsight)} disabled={manualAdvertSavingId === activeInsight.id || manualAdvertText.trim().length < 300}>{manualAdvertSavingId === activeInsight.id ? <><span className="spinner spinner-light" /> Saving &amp; analysing…</> : "Save advert & reanalyse"}</button></div></div>}
                <div className="requirement-summary-bar"><span><strong>{(activeInsight.requirements ?? []).length}</strong> criteria extracted</span><span><strong>{(activeInsight.requirements ?? []).filter((item) => item.status === "supported").length}</strong> evidenced</span><span className={(activeInsight.critical_gaps?.length ?? 0) > 0 ? "requirement-summary-alert" : ""}><strong>{activeInsight.critical_gaps?.length ?? 0}</strong> critical gaps</span></div>
                <div className="requirement-grid"><RequirementList title="Supported · evidence found" kind="supported" items={(activeInsight.requirements ?? []).filter((item) => item.status === "supported")} /><RequirementList title="Partially supported · review" kind="partial" items={(activeInsight.requirements ?? []).filter((item) => item.status === "partially_supported")} /><RequirementList title="Missing from CV evidence" kind="missing" items={(activeInsight.requirements ?? []).filter((item) => item.status === "not_evidenced")} /></div>
                <details className="match-job-description"><summary>Read full job description used for this analysis</summary><p className="description-source-note">{activeInsight.description_fetch_message?.startsWith("Manually pasted advert text") ? "Pasted by you from the advert page; CareerMate has not independently verified the text." : activeInsight.job_description_source === "original_listing" ? `Retrieved from the public original listing${activeInsight.description_fetched_at ? ` · ${activeInsight.description_fetched_at}` : ""}.` : "Only the search-result description was available. Fetch the original listing from role details for a more complete analysis."}</p><div className="full-job-description">{activeInsight.description?.trim() || "No job description was provided by the source."}</div></details>
                <p className="score-note">{activeInsight.score_note}</p>
                {safeExternalUrl(activeInsight.source_url || activeInsight.apply_url) && <a className="text-link" href={safeExternalUrl(activeInsight.source_url || activeInsight.apply_url) ?? undefined} target="_blank" rel="noopener noreferrer">Review original job advert <Icon name="arrow" /></a>}
                  </article></div>
                  <footer className="match-insight-drawer-footer"><button className="button button-secondary" type="button" onClick={() => { setActiveInsightJobId(null); setActiveView("discover"); }}>Find more jobs</button><button className="button button-primary" type="button" onClick={() => { setSelectedJob(activeInsight); setActiveInsightJobId(null); }}>Open job details <Icon name="arrow" /></button></footer>
                </section>
              </div>, document.body)}
            </div>
          )}

          {activeView === "applications" && (
            <div className="view-stack applications-view">
              <div className="application-stats-grid">
                <article className="application-stat-card"><span className="application-stat-label">Tracked roles</span><strong>{applications.length}</strong><small>Saved in local JSON</small></article>
                <article className="application-stat-card"><span className="application-stat-label">In progress</span><strong>{activeApplicationCount}</strong><small>Saved, preparing or active</small></article>
                <article className="application-stat-card"><span className="application-stat-label">Submitted or beyond</span><strong>{submittedApplicationCount}</strong><small>Applied, interview, offer or closed</small></article>
              </div>
              {applications.length > 0 && <PipelineBoard
                applications={applications}
                selectedId={selectedApplicationId}
                onSelect={selectApplication}
                onStatusChange={handlePipelineStatusChange}
                onExplore={() => setActiveView("discover")}
              />}
              {applications.length === 0 ? (
                <section className="panel empty-state applications-empty"><span className="empty-icon"><Icon name="briefcase" /></span><p className="eyebrow">APPLICATION TRACKER</p><h2>Your application workspace is ready</h2><p>Save a role from its details panel to track progress, keep notes, create a cover-letter draft, and prepare answers to employer questions.</p><button className="button button-primary" type="button" onClick={() => setActiveView("discover")}>Find roles to track <Icon name="arrow" /></button><p className="helper-text">No application is submitted automatically. You review and submit through the employer’s own website.</p></section>
              ) : (
                <div className="applications-layout workflow-application-editor-layout">
                  <section className="panel application-list-panel">
                    <div className="panel-titlebar"><div><p className="eyebrow">YOUR PIPELINE</p><h2>Tracked applications <span className="count-pill">{applications.length}</span></h2><p>Choose a role to update its stage or prepare materials.</p></div></div>
                    <div className="application-list-tabs" role="tablist" aria-label="Filter applications">
                      <button type="button" role="tab" aria-selected={applicationListTab === "all"} className={applicationListTab === "all" ? "active" : ""} onClick={() => setApplicationListTab("all")}>All <span>{applications.length}</span></button>
                      <button type="button" role="tab" aria-selected={applicationListTab === "active"} className={applicationListTab === "active" ? "active" : ""} onClick={() => setApplicationListTab("active")}>To do <span>{applications.filter((item) => ["saved", "preparing"].includes(item.status)).length}</span></button>
                      <button type="button" role="tab" aria-selected={applicationListTab === "submitted"} className={applicationListTab === "submitted" ? "active" : ""} onClick={() => setApplicationListTab("submitted")}>Submitted / completed <span>{submittedApplicationCount}</span></button>
                      <button type="button" role="tab" aria-selected={applicationListTab === "offers"} className={applicationListTab === "offers" ? "active" : ""} onClick={() => setApplicationListTab("offers")}>Interviews & offers <span>{applications.filter((item) => ["interview", "offer"].includes(item.status)).length}</span></button>
                    </div>
                    <div className="application-list">
                      {visibleApplications.map((application) => (
                        <button type="button" key={application.id} className={`application-list-item${application.id === selectedApplicationId ? " selected" : ""}`} onClick={() => selectApplication(application)} aria-pressed={application.id === selectedApplicationId}>
                          <span className="application-company-avatar">{(application.company || "?").trim().charAt(0).toUpperCase()}</span>
                          <span className="application-list-copy"><strong>{application.title}</strong><small>{application.company || "Company not listed"} · {application.location || "Location not listed"}</small><span className={`application-status-pill status-${application.status}`}>{APPLICATION_STATUS_LABELS[application.status]}</span></span>
                          <Icon name="chevron" />
                        </button>
                      ))}
                      {visibleApplications.length === 0 && <div className="application-filter-empty"><strong>No applications in this view yet.</strong><p>Applications move here when you update their stage in the details panel.</p></div>}
                    </div>
                  </section>
                  {selectedApplication ? (
                    <section className="panel application-editor-panel">
                      <div className="application-editor-header"><div><p className="eyebrow">APPLICATION DETAILS</p><h2>{selectedApplication.title}</h2><p>{selectedApplication.company || "Company not listed"} · {selectedApplication.location || "Location not listed"}</p></div>{safeExternalUrl(selectedApplication.source_url || selectedApplication.job_url) && <a className="button button-secondary button-small" href={safeExternalUrl(selectedApplication.source_url || selectedApplication.job_url) ?? undefined} target="_blank" rel="noopener noreferrer">Original listing <Icon name="arrow" /></a>}</div>
                      <div className="form-grid application-metadata-grid">
                        <label className="field"><span>Application stage</span><FloatingSelect ariaLabel="Application stage" value={applicationStatus} onChange={(value) => setApplicationStatus(value as ApplicationStatus)} options={[
                          { value: "saved", label: "Saved" }, { value: "preparing", label: "Preparing application" }, { value: "applied", label: "Applied" }, { value: "interview", label: "Interview" }, { value: "offer", label: "Offer" }, { value: "rejected", label: "Rejected" }, { value: "withdrawn", label: "Withdrawn" },
                        ]} /></label>
                        <Field label="Follow-up date" type="date" value={applicationFollowUpDate} onChange={setApplicationFollowUpDate} />
                      </div>
                      <TextAreaField label="Notes and next actions" value={applicationNotes} onChange={setApplicationNotes} placeholder="Recruiter contact, application deadline, interview notes, next action…" rows={3} />
                      <section className="application-job-description-panel">
                        <div className="application-section-heading"><div><p className="eyebrow">SOURCE DETAILS</p><h3>Job description</h3><p>{selectedApplication.job_description_source === "original_listing" ? "Fuller text from the original public listing is saved with this application." : "This record may contain only the short text returned by job search. Fetch the full listing before drafting."}</p></div><button className="button button-secondary button-small" type="button" onClick={() => void handleRefreshApplicationDescription()} disabled={enrichingApplicationId === selectedApplication.id}>{enrichingApplicationId === selectedApplication.id ? <><span className="spinner" /> Fetching…</> : selectedApplication.job_description_source === "original_listing" ? "Refresh details" : "Fetch full details"}</button></div>
                        <details><summary>Review saved job description ({selectedApplication.job_description.length.toLocaleString()} characters)</summary><div className="full-job-description">{selectedApplication.job_description || "No description saved yet."}</div></details>
                        {selectedApplication.job_description_fetch_status === "failed" && selectedApplication.job_description_fetch_message && <p className="description-fetch-warning">{selectedApplication.job_description_fetch_message}</p>}
                      </section>
                      <section className="application-draft-section">
                        <div className="application-section-heading"><div><p className="eyebrow">DRAFTING ASSISTANT</p><h3>Cover letter</h3><p>Generated from your reviewed profile and this role’s description.</p></div><button className="button button-secondary button-small" type="button" onClick={() => void handleDraftCoverLetter()} disabled={!canGenerateApplicationDraft || !profile}>{draftingCoverLetter ? <><span className="spinner" /> Generating…</> : <><Icon name="sparkles" /> {applicationCoverLetter ? "Regenerate draft" : "Generate draft"}</>}</button></div>
                        <TextAreaField label="Edit the draft before use" value={applicationCoverLetter} onChange={setApplicationCoverLetter} placeholder="Generate a first draft, then edit it to reflect your own voice and confirm every claim." rows={10} />
                        <p className="helper-text">The draft is not a verified statement. Review every detail and remove anything that does not reflect your experience.</p>
                      </section>
                      <section className="application-draft-section">
                        <div className="application-section-heading"><div><p className="eyebrow">EMPLOYER QUESTIONS</p><h3>Prepare an answer</h3><p>Paste one application question to create a factual first-person draft.</p></div></div>
                        <TextAreaField label="Application question" value={applicationQuestion} onChange={setApplicationQuestion} placeholder="e.g. Why are you interested in this role?" rows={3} />
                        <div className="application-question-action"><button className="button button-secondary" type="button" onClick={() => void handleDraftAnswer()} disabled={!canGenerateApplicationDraft || !profile || applicationQuestion.trim().length < 5}>{draftingAnswer ? <><span className="spinner" /> Drafting answer…</> : <><Icon name="sparkles" /> Draft answer</>}</button></div>
                        {applicationAnswers.length > 0 && <div className="application-answers-list">{applicationAnswers.map((answer, index) => <div className="application-answer-editor" key={`${answer.question}-${index}`}><div className="application-answer-question"><strong>{answer.question}</strong><button className="text-action" type="button" onClick={() => setApplicationAnswers((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></div><TextAreaField label="Edit answer" value={answer.answer} onChange={(value) => editApplicationAnswer(index, value)} rows={5} /></div>)}</div>}
                      </section>
                      {selectedApplication.submitted_details?.length ? <section className="application-draft-section"><div className="application-section-heading"><div><p className="eyebrow">APPLICATION HISTORY</p><h3>Details captured at submission</h3><p>Locally stored snapshot of the answers CareerMate had prepared when submission was confirmed. Use this as a reference during interviews or offers.</p></div></div><details className="submitted-details-panel"><summary>Show submitted details ({selectedApplication.submitted_details.length})</summary><div className="submitted-details-list">{selectedApplication.submitted_details.map((detail, index) => <div key={`${detail.question}-${index}`}><strong>{detail.question}</strong><p>{detail.answer || "(empty)"}</p></div>)}</div></details></section> : null}
                      <section className="application-draft-section browser-assist-section">
                        <div className="application-section-heading"><div><p className="eyebrow">AUTO APPLY · REVIEW FIRST</p><h3>Prepare and submit the employer application</h3><p>CareerMate can follow supported Apply and Continue steps, draft answers from your saved profile, fill approved fields, and submit only after your final confirmation.</p></div></div>
                        <div className="browser-assist-safety"><Icon name="shield" /><span>Every proposed value is editable. CareerMate never guesses salary, work authorization, identity, financial, password, verification, or legal-consent answers. Login and CAPTCHA must be completed by you. The final submit button is separate and requires explicit approval.</span></div>
                        <div className="browser-setup-line"><span><Icon name="info" /> Visible browser setup</span><button className="text-action" type="button" onClick={() => void handleCheckBrowserSetup()} disabled={browserDiagnosticsLoading}>{browserDiagnosticsLoading ? "Checking…" : "Check Playwright / Chromium"}</button>{browserDiagnostics && <small className={browserDiagnostics.playwright_installed && browserDiagnostics.chromium_installed ? "browser-setup-ok" : "browser-setup-error"}>{browserDiagnostics.message}{!browserDiagnostics.chromium_installed && ` Install with: ${browserDiagnostics.install_command}`}</small>}</div>
                        <div className="browser-assist-actions">
                          <button className="button button-secondary button-small" type="button" onClick={() => void handleOpenBrowserAssistant()} disabled={!selectedApplication.job_url || browserOpening || browserScanning || browserFilling || browserNavigating || browserAutoPreparing}>{browserOpening ? <><span className="spinner" /> Opening browser…</> : "Open application page"}</button>
                          <button className="button button-primary button-small" type="button" onClick={() => void handleAutoPrepareApplication()} disabled={!selectedApplication.job_url || browserOpening || browserScanning || browserFilling || browserNavigating || browserSubmitting || browserAutoPreparing}>{browserAutoPreparing ? <><span className="spinner spinner-light" /> Preparing full application…</> : "Auto prepare entire application"}</button>
                          {browserSession?.application_id === selectedApplication.id && <>
                            {browserSession.has_apply_action && <button className="button button-secondary button-small" type="button" onClick={() => void handleAdvanceBrowserStep("apply")} disabled={browserNavigating || browserOpening || browserScanning || browserFilling || browserAutoPreparing}>{browserNavigating ? <><span className="spinner spinner-light" /> Opening application…</> : "Find application form automatically"}</button>}
                            <button className="button button-secondary button-small" type="button" onClick={() => void handleScanBrowserForm()} disabled={browserOpening || browserScanning || browserFilling || browserNavigating || browserAutoPreparing}>{browserScanning ? <><span className="spinner" /> Scanning…</> : "Refresh current step"}</button>
                            <button className="button button-quiet button-small" type="button" onClick={() => void handleCloseBrowserAssistant()} disabled={browserFilling || browserSubmitting || browserNavigating || browserAutoPreparing}>Close browser session</button>
                          </>}
                        </div>
                        <p className="browser-auto-prepare-help">Auto prepare follows supported Apply/Continue steps across tabs and scans supported embedded forms. It fills profile-backed values and eligible AI drafts, then stops for missing required answers, unsupported controls, or security checks. It never submits without the separate final approval below.</p>
                        {browserSession?.application_id === selectedApplication.id && <>
                          <div className="browser-assist-page"><strong>{browserSession.title || "Employer page"}</strong><span>{browserSession.url}</span><small>Multi-tab Chromium session · CareerMate automatically switches to newly opened application tabs and scans supported embedded forms. Final submission still requires your approval.</small>
                            {(browserSession.open_pages?.length ?? 0) > 1 && <div className="browser-page-selector"><span>Open application tabs</span><FloatingSelect ariaLabel="Open application tabs" className="browser-field-select" value={String(browserSession.active_page_index ?? 0)} onChange={(value) => void handleSelectBrowserPage(Number(value))} disabled={browserScanning || browserOpening || browserFilling || browserNavigating} options={(browserSession.open_pages ?? []).map((page) => ({ value: String(page.page_index), label: `${page.active ? "Current · " : ""}${page.title || "Untitled tab"}`, description: page.url }))} /><small>Choose the tab that currently contains the employer's application form.</small></div>}
                            {browserSession.cookie_action && <small>Cookie preference applied: {browserSession.cookie_action}</small>}
                          </div>
                          {browserPreparedSteps.length > 0 && <section className="browser-prepared-summary">
                            <div className="browser-field-heading"><strong>Full application preparation preview</strong><span>{browserPreparedSteps.length} step(s) visited · {browserPreparedSteps.reduce((sum, step) => sum + step.filled_count, 0)} field(s) filled · nothing submitted yet</span></div>
                            {browserPreparedSteps.map((step) => <details className="browser-prepared-step" key={`${step.step}-${step.url}`} open={step.status === "needs_attention" || step.status === "ready"}>
                              <summary><span>Step {step.step}: {step.title}</span><em className={`browser-prepared-status ${step.status}`}>{step.status === "ready" ? "Ready for final review" : step.status === "needs_attention" ? "Needs attention" : "Prepared"}</em></summary>
                              <small className="browser-prepared-url">{step.url}</small>
                              <p>{step.note}</p>
                              <div className="browser-prepared-values">{step.fields.map((field, index) => <div key={`${step.step}-${index}`}><span>{field.label}{field.required ? " *" : ""}</span><code>{field.value || "(empty)"}</code><small>{field.filled ? "Filled" : "Not filled"}</small></div>)}</div>
                            </details>)}
                            <p className="browser-auto-prepare-help">Previous-step entries are a record of what CareerMate filled. To change an earlier answer, use Chromium Back or select that earlier tab, then refresh the step and edit/refill it. The editable controls for the currently selected step remain below.</p>
                          </section>}
                          {browserFieldDrafts.length > 0 ? <>
                            <div className="browser-field-heading"><strong>Review this step ({browserFieldDrafts.length} fields)</strong><span>Checked rows are the only values CareerMate will apply to the employer page.</span><button className="text-action" type="button" onClick={selectAllBrowserProposals}>Select all proposed values</button></div>
                            <div className="browser-field-list">{browserFieldDrafts.map((field) => { const needsUserInput = browserFieldNeedsUserInput(field); const fieldAccepted = Boolean(field.reviewed && (field.value.trim() || field.kind === "checkbox") && !needsUserInput); const fieldFilled = Boolean(field.filled); const fieldSuggested = Boolean(field.value.trim() && !field.reviewed && !fieldFilled); const suggestedLabel = field.kind === "file" ? "CV selected · review filename" : field.value_source === "profile" ? "Profile value · review" : field.value_source === "existing" ? "Existing value · review" : "AI suggestion · review"; const suggestedHint = field.kind === "file" ? (field.value ? "Check that this CV matches the employer and role, then approve the attachment." : "Choose a CV for this application. CareerMate does not silently reuse a tailored CV from another employer.") : field.value_source === "profile" ? "Prefilled from your saved profile. Confirm it is accurate for this employer." : field.value_source === "existing" ? "Already present on the employer page. Confirm it is still accurate." : "AI-generated draft. Review and correct it before using."; const stateLabel = needsUserInput ? "Needs your input" : fieldFilled ? "Filled in employer form" : fieldAccepted ? "Accepted" : fieldSuggested ? suggestedLabel : "Optional"; const stateClass = needsUserInput ? "needs-input" : fieldFilled || fieldAccepted ? "accepted" : fieldSuggested ? "suggested" : "optional"; const stateHint = needsUserInput ? "Required before continuing. Enter or choose an accurate answer." : fieldFilled ? "CareerMate filled this field. Verify it in the employer form." : fieldAccepted ? "Reviewed by you and ready to fill." : fieldSuggested ? suggestedHint : "Optional field. Leave blank when it does not apply."; return <article className={`browser-field-card state-${stateClass}`} key={field.field_id}>
                              <div className="browser-field-card-header"><label className="browser-field-include"><input type="checkbox" checked={field.include} onChange={(event) => updateBrowserField(field.field_id, { include: event.target.checked })} /><span>{field.label}{field.required && <em>Required</em>}<em className={`browser-field-state-badge ${stateClass}`}>{stateLabel}</em></span></label><span className="browser-field-kind">{field.kind}</span></div>
                              <p className={`browser-field-status-note ${stateClass}`}>{stateHint}</p>
                              {field.suggestion_source ? <small className={`browser-field-source${field.suggestion_source.startsWith("Local fallback") ? " browser-field-source-warning" : ""}`}>{field.suggestion_source}</small> : field.suggested_key && <small className="browser-field-source">Suggested from: {suggestedBrowserValueLabel(field.suggested_key)}</small>}
                              {field.kind === "file" ? <div className="browser-file-picker"><label className="browser-control-label">CV document to attach<FloatingSelect ariaLabel={`Choose CV attachment for ${field.label}`} className="browser-field-select" value={field.value} placeholder="Choose a CV document…" onChange={(value) => updateBrowserField(field.field_id, { value, include: true, reviewed: true, value_source: "manual" })} options={[
                                { value: "__CAREERMATE_CURRENT_CV__", label: "Original uploaded CV · current.pdf", description: "Your base CV before role-specific tailoring." },
                                ...tailoredCvVersions.map((version) => ({ value: `__CAREERMATE_TAILORED_CV__:${version.filename}`, label: `${version.job_title || version.template} · ${version.company || "Target company"}`, description: `${version.pdf_filename || version.filename.replace(/\.docx$/i, ".pdf")} · ${version.ats_score ?? "—"}/100 ATS estimate` })),
                              ]} /></label><div className={`browser-file-selected${field.value ? " has-file" : " no-file"}`}><Icon name="file" /><span><strong>{browserFieldDisplayValue(field, tailoredCvVersions)}</strong><small>{field.value.startsWith("__CAREERMATE_TAILORED_CV__:") ? "Role-specific tailored CV" : field.value === "__CAREERMATE_CURRENT_CV__" ? "Original uploaded CV" : "Select a document from the list above"}</small></span><em>{field.value ? "Exact filename preserved" : "Selection required"}</em></div><p className="browser-file-guidance">CareerMate attaches the selected PDF using its actual filename. Tailored CVs are matched to this application by role/company where possible; you can change the selection above.</p></div>
                                : field.kind === "select" || field.kind === "radio" ? <label className="browser-control-label">Review selection<FloatingSelect ariaLabel={`Review selection for ${field.label}`} className="browser-field-select" value={field.value} placeholder="Choose an option…" onChange={(value) => updateBrowserField(field.field_id, { value, include: true })} options={[{ value: "", label: "Choose an option…", disabled: true }, ...(field.options ?? []).map((option) => ({ value: option.value, label: option.label || option.value }))]} /></label>
                                : field.kind === "checkbox" ? <label className="browser-control-label">Set checkbox value<FloatingSelect ariaLabel={`Set checkbox value for ${field.label}`} className="browser-field-select" value={field.value || "false"} onChange={(value) => updateBrowserField(field.field_id, { value, include: true })} options={[{ value: "true", label: "Yes / checked", description: "Select only when this statement is accurate." }, { value: "false", label: "No / unchecked" }]} /><small>Only applies if the row is checked above. Legal consent controls are excluded from automatic suggestions; decide these yourself.</small></label>
                                : field.kind === "textarea" || field.value.length > 160 ? <TextAreaField label="Proposed value — review and edit" value={field.value} onChange={(value) => updateBrowserField(field.field_id, { value })} rows={field.kind === "textarea" || field.value.length > 160 ? 4 : 2} placeholder={field.suggested_key ? "Review the suggested value" : "Use AI suggestions or enter a value after reviewing the question"} />
                                : <label className="browser-control-label">Proposed value — review and edit<input className="browser-field-input" type={(["email", "tel", "url", "date", "number", "search"].includes(field.kind) ? field.kind : "text")} value={field.value} onChange={(event) => updateBrowserField(field.field_id, { value: event.target.value })} placeholder={field.placeholder || (field.suggested_key ? "Review suggested value" : "Enter a value or request an AI suggestion")} /></label>}
                            </article>; })}</div>
                            <div className="browser-review-actions">
                              <button className="button button-secondary" type="button" onClick={() => void handleSuggestBrowserAnswers()} disabled={browserSuggesting || browserFilling || browserNavigating || !browserFieldDrafts.some((field) => ["text", "textarea"].includes(field.kind))}>{browserSuggesting ? <><span className="spinner" /> Drafting answers…</> : "Generate AI suggestions for questions"}</button>
                              <button className="button button-primary" type="button" onClick={() => void handleFillBrowserForm(false)} disabled={browserFilling || browserOpening || browserScanning || browserNavigating || !browserFieldDrafts.some((field) => field.include && field.value.trim())}>{browserFilling ? <><span className="spinner spinner-light" /> Filling reviewed values…</> : "Approve & fill this step"}</button>
                              {browserSession.has_continue_action && browserFieldDrafts.some((field) => field.include && field.value.trim()) && <button className="button button-primary" type="button" onClick={() => void handleFillBrowserForm(true)} disabled={browserFilling || browserOpening || browserScanning || browserNavigating}>{browserFilling ? <><span className="spinner spinner-light" /> Filling & continuing…</> : "Approve, fill & continue automatically"}</button>}
                              {browserSession.has_continue_action && !browserFieldDrafts.some((field) => field.include && field.value.trim()) && <button className="button button-secondary" type="button" onClick={() => void handleAdvanceBrowserStep("continue")} disabled={browserNavigating || browserFilling}>{browserNavigating ? "Continuing…" : "Continue to next step"}</button>}
                            </div>
                          </> : <div className="browser-no-fields"><strong>No supported application fields on this page yet.</strong><p>{browserSession.has_apply_action ? "CareerMate detected an Apply control. Choose Find application form automatically to open the next page." : browserSession.has_continue_action ? "A Continue control was detected. Use it after completing any required manual checks." : "If the employer requires sign-in or security verification, complete it manually in Chromium, then choose Refresh current step."}</p></div>}
                          {browserSession.submit_available && <div className="browser-final-submit"><div><p className="eyebrow">FINAL STEP</p><h4>Review and approve submission</h4><p>CareerMate detected a likely final application control. The application will not be sent until you check the confirmation below and press the submit button.</p></div><label className="browser-submit-confirm"><input type="checkbox" checked={browserSubmitApproved} onChange={(event) => setBrowserSubmitApproved(event.target.checked)} /><span>I reviewed the completed form and all attached documents, and I authorize CareerMate to submit this application to the employer.</span></label><button className="button button-danger" type="button" onClick={() => void handleSubmitBrowserApplication()} disabled={!browserSubmitApproved || browserSubmitting || browserFilling || browserNavigating}>{browserSubmitting ? <><span className="spinner spinner-light" /> Submitting after approval…</> : "Submit application to employer"}</button><small>If CAPTCHA, login, or verification is required, complete it yourself first. If CareerMate cannot verify the result, check the employer page before marking the application as applied.</small></div>}
                        </>}
                      </section>
                      <div className="application-save-row"><p className="helper-text">Saved locally in <code>data/applications/applications.json</code>. Nothing is submitted automatically.</p><button className="button button-primary" type="button" onClick={() => void handleSaveApplication()} disabled={applicationSaving || draftingAnswer || draftingCoverLetter}>{applicationSaving ? <><span className="spinner spinner-light" /> Saving…</> : <><Icon name="check" /> Save application</>}</button></div>
                    </section>
                  ) : <section className="panel empty-state"><h3>Select an application</h3><p>Choose a role from your tracked applications.</p></section>}
                </div>
              )}
            </div>
          )}

          {activeView === "settings" && (
            <div className="view-stack settings-hub">
              <div className="settings-hub-grid">
                <button type="button" className="settings-hub-card" onClick={() => setActiveView("ai")}><span className="settings-hub-icon"><Icon name="cpu" /></span><strong>AI provider</strong><small>Choose Ollama, OpenAI, or a compatible endpoint. Test your model and review data-sharing settings.</small><span className="settings-hub-action">Configure AI <Icon name="arrow" /></span></button>
                <button type="button" className="settings-hub-card" onClick={() => setActiveView("platforms")}><span className="settings-hub-icon"><Icon name="layers" /></span><strong>Employer portals</strong><small>Connect company career pages, manage board settings and check portal health.</small><span className="settings-hub-action">Manage portals <Icon name="arrow" /></span></button>
                <button type="button" className="settings-hub-card" onClick={() => setActiveView("profile")}><span className="settings-hub-icon"><Icon name="file" /></span><strong>CV extraction and profile</strong><small>Upload a source CV, extract its content, review every field, and save your profile.</small><span className="settings-hub-action">Open CV Studio <Icon name="arrow" /></span></button>
                <button type="button" className="settings-hub-card" onClick={() => { setActiveView("data"); void refreshDataSummary(); }}><span className="settings-hub-icon"><Icon name="shield" /></span><strong>Local data and privacy</strong><small>Review stored files, cache controls, and workspace reset options.</small><span className="settings-hub-action">Manage data <Icon name="arrow" /></span></button>
              </div>
              <section className="panel settings-process"><p className="eyebrow">HOW CAREERMATE WORKS</p><h2>Four steps from CV to application</h2><ol><li><strong>Upload and extract</strong><span>Your PDF, DOCX, or TXT is parsed locally into text.</span></li><li><strong>Analyze and verify</strong><span>The selected AI provider organizes facts. You review and correct the candidate profile before saving.</span></li><li><strong>Discover and compare</strong><span>Search configured sources and compare job requirements against your evidence.</span></li><li><strong>Tailor and review</strong><span>Generate a role-specific CV, inspect the preview and ATS coverage estimate, then download it for your own review.</span></li></ol></section>
            </div>
          )}

          {activeView === "ai" && (
            <div className="view-stack ai-settings-view">
              <section className="panel ai-settings-panel">
                <div className="panel-titlebar">
                  <div>
                    <p className="eyebrow">PROVIDER CONFIGURATION</p>
                    <h2>Choose how CareerMate thinks</h2>
                  </div>
                  <span className="filter-icon"><Icon name="cpu" /></span>
                </div>
                <p className="panel-description">The selected provider is used for CV analysis, job matching, cover letters, and employer-question drafts. Your files and settings remain on this computer.</p>
                <form className="ai-provider-form" onSubmit={handleSaveAiSettings}>
                  <label className="field">
                    <span>AI provider</span>
                    <FloatingSelect ariaLabel="AI provider" value={aiProviderDraft} onChange={(value) => selectAiProvider(value as AIProviderId)} options={[
                      { value: "ollama", label: "Ollama — local and private" },
                      { value: "openai", label: "OpenAI API — hosted models" },
                      { value: "openai_compatible", label: "OpenAI-compatible API — other providers" },
                    ]} />
                  </label>
                  <Field label="Model ID" value={aiModelDraft} onChange={(value) => { setAiModelDraft(value); setAiTestMessage(""); }} placeholder={aiProviderDraft === "ollama" ? "e.g. qwen3:4b" : aiProviderDraft === "openai" ? "documented API model ID" : "Model ID supplied by your API provider"} />
                  {aiProviderDraft !== "openai" && <Field label={aiProviderDraft === "ollama" ? "Ollama host URL" : "API base URL"} value={aiBaseUrlDraft} onChange={(value) => { setAiBaseUrlDraft(value); setAiTestMessage(""); }} placeholder={aiProviderDraft === "ollama" ? "http://127.0.0.1:11434" : "https://your-provider.example/v1"} />}

                  {aiProviderDraft === "ollama" && <>
                    <div className="ai-info-note"><Icon name="shield" /><div><strong>Local processing</strong><p>CV text, profile details, job descriptions, and drafts are sent to your local Ollama instance. It runs on your computer and can use significant memory and CPU.</p></div></div>
                    <div className="ai-info-note"><Icon name="cpu" /><div><strong>Lower-resource local model</strong><p>For faster matching on a CPU-limited computer, try <code>qwen3:4b</code> instead of <code>gemma4:e4b</code>. First run <code>ollama pull qwen3:4b</code> in a terminal, then use the button below. This smaller model may be less capable on nuanced requirements, so verify critical results.</p><button className="text-action" type="button" onClick={() => { setAiModelDraft("qwen3:4b"); setAiTestMessage(""); }}>Use qwen3:4b</button></div></div>
                  </>}
                  {aiProviderDraft === "openai" && <div className="ai-info-note ai-info-cloud"><Icon name="info" /><div><strong>OpenAI API credentials</strong><p>Add an API key to <code>backend/.env</code> using <code>OPENAI_API_KEY</code>. Your ChatGPT subscription does not include API usage; API usage is billed separately.</p><a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer">Open OpenAI API keys <Icon name="arrow" /></a></div></div>}
                  {aiProviderDraft === "openai_compatible" && <div className="ai-info-note ai-info-cloud"><Icon name="info" /><div><strong>Bring a compatible provider</strong><p>Enter the API base URL and model ID supplied by your provider. Add its key as <code>CAREERMATE_OPENAI_COMPATIBLE_API_KEY</code> in <code>backend/.env</code>. The endpoint must support the OpenAI Chat Completions-compatible API; structured responses are validated locally.</p></div></div>}

                  {aiProviderDraft !== "ollama" && <label className="ai-consent-row"><input type="checkbox" checked={cloudAiConsent} onChange={(event) => setCloudAiConsent(event.target.checked)} /><span><strong>I understand this provider is online.</strong><small>CareerMate may send CV text, profile fields, selected job descriptions, and draft prompts to this provider for processing. Do not switch to a hosted provider unless you are comfortable sharing that task data.</small></span></label>}

                  <div className="ai-settings-actions">
                    <button className="button button-secondary" type="button" onClick={() => void handleTestAiProvider()} disabled={aiTesting || !aiModelDraft.trim()}>{aiTesting ? <><span className="spinner" /> Testing…</> : <><Icon name="target" /> Test connection</>}</button>
                    <button className="button button-primary" type="submit" disabled={aiSaving || !aiModelDraft.trim() || (aiProviderDraft !== "ollama" && !cloudAiConsent)}>{aiSaving ? <><span className="spinner spinner-light" /> Saving…</> : <><Icon name="check" /> Save AI settings</>}</button>
                  </div>
                  {aiTestMessage && <div className={`ai-test-result ${aiTestMessage.toLowerCase().includes("connection successful") ? "ai-test-success" : "ai-test-error"}`} role="status">{aiTestMessage}</div>}
                </form>
              </section>

              <section className="ai-provider-status-grid">
                {(["ollama", "openai", "openai_compatible"] as AIProviderId[]).map((providerId) => {
                  const provider = aiSettings?.providers[providerId];
                  const isActive = aiSettings?.provider === providerId;
                  return <article className={`panel ai-provider-status-card${isActive ? " ai-provider-active" : ""}`} key={providerId}>
                    <div className="ai-provider-status-top"><span className="filter-icon"><Icon name={providerId === "ollama" ? "shield" : providerId === "openai" ? "sparkles" : "layers"} /></span><span className={`ai-config-status ${provider?.configured ? "ready" : "needs-setup"}`}>{provider?.configured ? "Configured" : "Setup needed"}</span></div>
                    <h3>{provider?.label ?? providerId}</h3>
                    <p>{providerId === "ollama" ? "Runs on your machine with no API usage charges, but speed depends on hardware, available memory, and the local model." : providerId === "openai" ? "Avoids local model inference and can reduce CPU/RAM load. Actual speed, limits, and cost depend on the selected model and provider." : "Connect compatible endpoints from other API providers using their supplied HTTPS URL, key, and model ID. Speed and pricing depend on that provider."}</p>
                    <small>{isActive ? "Currently active" : provider?.configured ? "Available to select" : providerId === "ollama" ? "Test whether Ollama is running" : provider?.api_key_configured ? "Check model and endpoint settings" : "API key is not configured in backend/.env"}</small>
                  </article>;
                })}
              </section>
              <p className="ai-settings-disclaimer">CareerMate stores CVs, profile, jobs, and application records in local files. When a cloud AI provider is active, the text required for the specific AI operation is sent to that provider. API keys are read from <code>backend/.env</code> and are never returned by the settings API or stored in the JSON preferences.</p>
            </div>
          )}

          {activeView === "profile" && (
            <div className="view-stack profile-view">
              {!profile && <section className="panel cv-setup-panel"><div className="cv-setup-visual"><div className="cv-illustration"><span className="cv-illustration-fold" /><span /><span /><span /><b><Icon name="check" /></b></div></div><div className="cv-setup-content"><p className="eyebrow">STEP 1 · BUILD YOUR PROFILE</p><h2>Start with your CV</h2><p className="panel-description">Upload a PDF, Word document, or text file. CareerMate extracts the text and uses your selected AI provider to organize it into a profile you can edit and review. Online providers receive the CV text for processing.</p><label className="upload-dropzone"><input type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span className="upload-icon"><Icon name="file" /></span><strong>{file ? file.name : "Choose your CV file"}</strong><span className="helper-text">PDF, DOCX or TXT · up to 10 MB</span><span className="upload-prompt">Browse files <Icon name="arrow" /></span></label><div className="button-row"><button className="button button-secondary" onClick={handleUploadCv} disabled={cvLoading || !file} type="button">{cvLoading ? <><span className="spinner" /> Uploading…</> : "Upload & extract text"}</button><button className="button button-primary" onClick={handleAnalyzeCv} disabled={cvLoading || !cvStatus.uploaded} type="button">{cvLoading ? <><span className="spinner spinner-light" /> Working…</> : <><Icon name="sparkles" /> Analyze CV</>}</button></div><div className="cv-footnote"><span className={`status-dot ${cvStatus.uploaded ? "good" : "muted-dot"}`} />{cvStatus.uploaded ? `Text extracted · ${cvStatus.extracted_text_characters.toLocaleString()} characters` : "No CV text extracted yet"}</div><div className="local-note profile-local-note"><Icon name="shield" /><span><strong>Privacy-first processing</strong><small>Review extracted fields before use. When a hosted provider is selected, CV text is sent to that provider for analysis.</small></span></div></div></section>}

              {profile && <>
                <EvidenceVault />
                <section className="profile-summary-card panel"><div className="profile-summary-avatar">{profile.personal?.name?.trim()?.charAt(0)?.toUpperCase() || "C"}</div><div className="profile-summary-copy"><p className="eyebrow">CANDIDATE PROFILE</p><h2>{profile.personal?.name?.trim() || "Your professional profile"}</h2><p>{[profile.personal?.location, profile.personal?.email].filter(Boolean).join(" · ") || "Add your contact details and professional information below."}</p></div><div className={`save-state ${profileSaved ? "saved" : "unsaved"}`}>{profileSaved ? "✓ Saved locally" : "● Review changes"}</div><div className="profile-completion"><div className="profile-completion-label"><span>Profile completeness</span><strong>{profileCompletion}%</strong></div><div className="completion-track"><span style={{ width: `${profileCompletion}%` }} /></div></div></section>
                <section className="panel profile-editor-panel"><div className="panel-titlebar"><div><p className="eyebrow">EDIT & VERIFY</p><h2>Career details</h2><p className="panel-description">AI extraction is a starting point. Keep every field truthful and specific.</p></div><span className="subtle-label">Local file · profile.json</span></div>
                  <details className="profile-accordion" open><summary><span className="accordion-icon"><Icon name="user" /></span><span className="accordion-title">Personal details<small>Name, contact details and professional links</small></span><span className="summary-count">8 fields</span></summary><div className="form-grid profile-form-grid"><Field label="Full name" value={profile.personal?.name ?? ""} onChange={(value) => updatePersonal("name", value)} /><Field label="CV headline / target title" value={profile.personal?.headline ?? ""} onChange={(value) => updatePersonal("headline", value)} placeholder="e.g. Backend Engineer" /><Field label="Email" type="email" value={profile.personal?.email ?? ""} onChange={(value) => updatePersonal("email", value)} /><Field label="Phone" value={profile.personal?.phone ?? ""} onChange={(value) => updatePersonal("phone", value)} /><Field label="Location" value={profile.personal?.location ?? ""} onChange={(value) => updatePersonal("location", value)} /><Field label="LinkedIn URL" value={profile.personal?.linkedin ?? ""} onChange={(value) => updatePersonal("linkedin", value)} /><Field label="GitHub URL" value={profile.personal?.github ?? ""} onChange={(value) => updatePersonal("github", value)} /><Field label="Portfolio URL" value={profile.personal?.portfolio ?? ""} onChange={(value) => updatePersonal("portfolio", value)} /></div></details>
                  <details className="profile-accordion" open><summary><span className="accordion-icon"><Icon name="file" /></span><span className="accordion-title">Summary & skills<small>Your professional story, languages and credentials</small></span><span className="summary-count">{profile.skills.length} skills</span></summary><TextAreaField label="Professional summary" value={profile.summary} onChange={updateSummary} rows={5} /><div className="form-grid profile-form-grid"><TextAreaField label="Skills — one per line" value={profile.skills.join("\n")} onChange={(value) => updateList("skills", value)} /><TextAreaField label="Languages — one per line" value={profile.languages.join("\n")} onChange={(value) => updateList("languages", value)} /><TextAreaField label="Certifications — one per line" value={profile.certifications.join("\n")} onChange={(value) => updateList("certifications", value)} /><TextAreaField label="Projects — one project per line (name, year, description, URL)" value={profile.projects.map((project) => [project.name, project.year, project.description.join("; "), project.url].filter(Boolean).join(" | ")).join("\n")} onChange={(value) => { const projects = value.split("\n").map((line) => line.split("|").map((part) => part.trim())).filter((parts) => parts[0]).map((parts) => ({ name: parts[0] || "", year: parts[1] || "", description: parts[2] ? [parts[2]] : [], url: parts[3] || "" })); setProfile((current) => current ? { ...current, projects } : current); setProfileSaved(false); }} /><TextAreaField label="Achievements — one per line" value={profile.achievements.join("\n")} onChange={(value) => updateList("achievements", value)} /></div></details>
                  <details className="profile-accordion"><summary><span className="accordion-icon"><Icon name="briefcase" /></span><span className="accordion-title">Professional experience<small>Roles, responsibilities and achievements</small></span><span className="summary-count">{profile.experience.length}</span></summary><div className="record-list">{profile.experience.map((item, index) => <div className="editable-record" key={`experience-${index}`}><div className="editable-record-title"><strong>{item.job_title || `Experience ${index + 1}`}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeExperience(index)}>Remove</button></div><div className="form-grid profile-form-grid"><Field label="Job title" value={item.job_title} onChange={(value) => updateExperience(index, "job_title", value)} /><Field label="Company" value={item.company} onChange={(value) => updateExperience(index, "company", value)} /><Field label="Location" value={item.location} onChange={(value) => updateExperience(index, "location", value)} /><Field label="Start date" value={item.start_date} onChange={(value) => updateExperience(index, "start_date", value)} /><Field label="End date" value={item.end_date} onChange={(value) => updateExperience(index, "end_date", value)} /></div><TextAreaField label="Responsibilities and achievements — one per line" value={item.description.join("\n")} onChange={(value) => updateExperienceDescription(index, value)} /></div>)}{profile.experience.length === 0 && <p className="helper-text">No experience entries have been extracted.</p>}</div><button className="button button-secondary" type="button" onClick={addExperience}><Icon name="plus" /> Add experience</button></details>
                  <details className="profile-accordion"><summary><span className="accordion-icon"><Icon name="graduation" /></span><span className="accordion-title">Education<small>Degrees, institutions and study dates</small></span><span className="summary-count">{profile.education.length}</span></summary><div className="record-list">{profile.education.map((item, index) => <div className="editable-record" key={`education-${index}`}><div className="editable-record-title"><strong>{item.degree || `Education ${index + 1}`}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeEducation(index)}>Remove</button></div><div className="form-grid profile-form-grid"><Field label="Degree" value={item.degree} onChange={(value) => updateEducation(index, "degree", value)} /><Field label="Institution" value={item.institution} onChange={(value) => updateEducation(index, "institution", value)} /><Field label="Location" value={item.location} onChange={(value) => updateEducation(index, "location", value)} /><Field label="Start date" value={item.start_date} onChange={(value) => updateEducation(index, "start_date", value)} /><Field label="End date" value={item.end_date} onChange={(value) => updateEducation(index, "end_date", value)} /></div></div>)}{profile.education.length === 0 && <p className="helper-text">No education entries have been extracted.</p>}</div><button className="button button-secondary" type="button" onClick={addEducation}><Icon name="plus" /> Add education</button></details>
                  <div className="profile-save-row"><p className="helper-text">Saved to <code>data/cv/profile.json</code> on this computer. Match analysis will use the profile after saving.</p><button className="button button-primary" type="button" onClick={handleSaveProfile} disabled={saving || cvLoading || matchLoading}>{saving ? <><span className="spinner spinner-light" /> Saving…</> : <><Icon name="check" /> Save reviewed profile</>}</button></div>
                </section>
              </>}
              {profile && <section className="panel cv-studio-tailor-panel">
                <div className="panel-titlebar"><div><p className="eyebrow">ROLE SPECIFIC CV</p><h2>Tailor your CV</h2><p className="panel-description">Paste a complete job description or open a role from Find Jobs. Your source profile remains unchanged.</p></div></div>
                <TextAreaField label="Job description" value={cvStudioJobDescription} onChange={setCvStudioJobDescription} placeholder="Paste the complete job description here…" rows={8} />
                <div className="cv-studio-target-grid"><Field label="Target role (for the filename)" value={cvStudioTargetTitle} onChange={setCvStudioTargetTitle} placeholder="e.g. Backend Engineer" /><Field label="Company (for the filename)" value={cvStudioTargetCompany} onChange={setCvStudioTargetCompany} placeholder="e.g. Spotify" /></div>
                <div className="cv-studio-controls"><label className="field"><span>CV template</span><FloatingSelect ariaLabel="CV template" value={cvTemplate} onChange={(value) => setCvTemplate(value as "classic" | "modern" | "compact" | "sectioned")} options={[{ value: "classic", label: "Classic ATS" }, { value: "modern", label: "Modern professional" }, { value: "compact", label: "Compact ATS" }, { value: "sectioned", label: "Sectioned professional · centered header and grouped skills" }]} /></label><button className="button button-primary" type="button" disabled={tailoringCv || cvStudioJobDescription.trim().length < 100} onClick={async () => { setTailoringCv(true); setCvTailorError(""); setTailoredCv(null); try { setTailoredCv(await tailorCvForJob(cvStudioJobDescription, cvTemplate, { job_title: cvStudioTargetTitle, company: cvStudioTargetCompany })); const versions = await getTailoredCvVersions(); setTailoredCvVersions(versions.versions); } catch (e) { const message = e instanceof Error ? e.message : "Could not tailor the CV."; setCvTailorError(message.includes("Input should be 'classic', 'modern' or 'compact'") ? "The running FastAPI backend is older than this CareerMate frontend. Restart it from the CareerMate 3.7 backend folder to enable Sectioned Professional." : message); } finally { setTailoringCv(false); } }}>{tailoringCv ? "Creating tailored CV…" : "Generate tailored CV"}</button></div>
                {cvTemplate === "sectioned" && <details className="cv-template-layout-preview"><summary>Preview the structured CV layout</summary><div className="cv-template-layout-paper"><header><h4>{profile.personal.name || "Your name"}</h4><strong>{(profile.personal.headline || profile.experience[0]?.job_title || "Professional headline").toUpperCase()}</strong><p className="cv-template-layout-contact">{[profile.personal.location, profile.personal.phone, profile.personal.email].filter(Boolean).join("  |  ") || "Location  |  Phone  |  Email"}</p><p className="cv-template-layout-contact">{[profile.personal.linkedin ? `LinkedIn: ${profile.personal.linkedin}` : "", profile.personal.github ? `GitHub: ${profile.personal.github}` : "", profile.personal.portfolio ? `Portfolio: ${profile.personal.portfolio}` : ""].filter(Boolean).join("  |  ") || "LinkedIn  |  GitHub  |  Portfolio"}</p></header><div className="cv-template-layout-accent" />{["PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE", "PROJECTS", "EDUCATION", "ACHIEVEMENTS"].map((heading) => <section key={heading}><strong>{heading}</strong><div /></section>)}</div><small>Single-column, ATS-readable layout based on your CV structure: centered name and headline, two contact rows, grouped technical skills, experience, projects, education and achievements.</small></details>}
                {cvTailorError && <p className="form-error">{cvTailorError}</p>}
                {tailoredCv && <div className="cv-studio-result"><div className="cv-generated-filename"><Icon name="file" /><span><strong>Generated CV filename</strong><code>{tailoredCv.filename}</code><small>The attached PDF keeps this name with a .pdf extension.</small></span></div><div className="cv-score-line"><strong>Requirement coverage estimate</strong><strong className={tailoredCv.ats.score >= 70 ? "cv-score-good" : "cv-score-low"}>{tailoredCv.ats.score}/100</strong></div><p className="helper-text">{tailoredCv.ats.detected_requirement_count} identifiable technical or role requirements detected. This is not a vendor ATS score.</p><div className="cv-studio-actions"><a className="button button-secondary" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}`} target="_blank" rel="noreferrer">Download DOCX</a><a className="button button-secondary" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}/pdf`} target="_blank" rel="noreferrer">Download PDF</a><a className="button button-primary" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}/preview`} target="_blank" rel="noreferrer">Preview PDF</a></div><details className="cv-studio-preview"><summary>Preview inside CareerMate</summary><iframe title="Tailored CV PDF preview" src={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}/preview`} /></details><p className="helper-text">Matched: {tailoredCv.ats.matched_keywords.join(", ") || "No known terms detected"}</p>{tailoredCv.ats.missing_keywords.length > 0 && <p className="helper-text">Not evidenced: {tailoredCv.ats.missing_keywords.join(", ")}</p>}<small>{tailoredCv.ats.disclaimer}</small></div>}
                {tailoredCvVersions.length > 0 && <details className="cv-studio-history"><summary>Saved CV versions ({tailoredCvVersions.length})</summary>{tailoredCvVersions.map((version) => <div className="saved-search-row cv-version-row" key={version.filename}><span><strong>{[version.job_title, version.company].filter(Boolean).join(" · ") || `${version.template} CV`} · ${version.ats_score ?? "—"}/100</strong><small><code>{version.pdf_filename || version.filename.replace(/\.docx$/i, ".pdf")}</code><br />{new Date(version.created_at).toLocaleString()}</small></span><div className="cv-version-actions"><a className="text-action" href={`${TAILORED_CV_DOWNLOAD_BASE}/api/cv/tailored/${encodeURIComponent(version.filename)}`} target="_blank" rel="noreferrer">DOCX</a><a className="text-action" href={`${TAILORED_CV_DOWNLOAD_BASE}/api/cv/tailored/${encodeURIComponent(version.filename)}/pdf`} target="_blank" rel="noreferrer">PDF</a></div></div>)}</details>}
              </section>}
              {profile && <div className="profile-privacy-footer"><Icon name="shield" /><span>CareerMate stores your profile in local files and excludes contact details from job-match prompts. Hosted providers receive the content needed for each requested task.</span></div>}
            </div>
          )}

          {activeView === "data" && (
            <div className="view-stack data-management-view">
              <section className="panel data-summary-panel">
                <div className="panel-titlebar">
                  <div><p className="eyebrow">LOCAL WORKSPACE</p><h2>Your data, your control</h2><p className="panel-description">CareerMate stores workspace records under the local <code>data/</code> folder. This page never displays your CV text or other private file contents.</p></div>
                  <button className="button button-secondary button-small" type="button" onClick={() => void refreshDataSummary()} disabled={dataLoading}>{dataLoading ? <><span className="spinner" /> Refreshing…</> : <><Icon name="refresh" /> Refresh summary</>}</button>
                </div>
                <div className="data-count-grid">
                  <article className="data-count-card"><span className="data-count-icon"><Icon name="file" /></span><div><strong>{dataSummary?.counts.cv_files ?? "—"}</strong><span>CV and profile files</span><small>{dataSummary?.counts.profile_saved ? "Profile saved" : "No saved profile"}</small></div></article>
                  <article className="data-count-card"><span className="data-count-icon"><Icon name="search" /></span><div><strong>{dataSummary?.counts.saved_jobs ?? "—"}</strong><span>Saved jobs</span><small>Local job listings</small></div></article>
                  <article className="data-count-card"><span className="data-count-icon"><Icon name="briefcase" /></span><div><strong>{dataSummary?.counts.applications ?? "—"}</strong><span>Applications</span><small>Statuses, notes and drafts</small></div></article>
                  <article className="data-count-card"><span className="data-count-icon"><Icon name="cpu" /></span><div><strong>{dataSummary?.counts.cache_files ?? "—"}</strong><span>Cache files</span><small>Derived results, safe to rebuild</small></div></article>
                </div>
                <p className="data-summary-footnote">{dataSummary?.counts.total_data_files ?? "—"} local data file(s) found · {dataSummary?.counts.settings_files ?? "—"} local settings/config file(s)</p>
              </section>

              <section className="panel data-action-card">
                <div className="data-action-icon data-action-icon-blue"><Icon name="refresh" /></div>
                <div className="data-action-copy"><h3>Clear search and match caches</h3><p>Remove downloaded job-source caches and saved AI match calculations. Your CV, candidate profile, saved jobs and application tracker stay untouched. CareerMate will fetch or recompute these items when needed.</p><p className="helper-text"><strong>This does not empty your Job Inbox.</strong> Inbox items are saved job records. Use <em>Clean everything</em> below when you want to remove all jobs and application data.</p></div>
                <button className="button button-secondary" type="button" onClick={() => void handleClearCaches()} disabled={cacheClearBusy || dataResetBusy || jobLoading || matchLoading || cvLoading || saving || applicationSaving || draftingCoverLetter || draftingAnswer}>{cacheClearBusy ? <><span className="spinner" /> Clearing…</> : "Clear caches"}</button>
              </section>

              <section className="panel data-action-card data-action-danger">
                <div className="data-action-icon data-action-icon-red"><Icon name="trash" /></div>
                <div className="data-action-copy"><p className="eyebrow">DESTRUCTIVE ACTION</p><h3>Clean everything</h3><p>Permanently delete the current CV and extracted text, reviewed profile, saved jobs, match results, source caches, application records and local provider/source preferences. Example configuration templates are kept.</p><div className="data-preserved-note"><Icon name="shield" /><span><strong>Kept safely:</strong> <code>backend/.env</code> (including API keys), your source code, and your Python virtual environment.</span></div></div>
                <button className="button button-danger" type="button" onClick={() => { setResetConfirmationText(""); setShowResetConfirmation(true); setError(""); }} disabled={dataResetBusy || cacheClearBusy || jobLoading || matchLoading || cvLoading || saving || applicationSaving || draftingCoverLetter || draftingAnswer}><Icon name="trash" /> Clean everything</button>
              </section>

              <section className="local-note data-management-note"><Icon name="info" /><span><strong>Before you reset</strong><small>This action cannot be undone. Export or back up any information you want to keep. The reset closes CareerMate's visible browser session first and preserves API keys in <code>backend/.env</code>.</small></span></section>

              {showResetConfirmation && createPortal(<div className="reset-confirm-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !dataResetBusy) setShowResetConfirmation(false); }}><section className="reset-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="reset-confirm-title"><span className="reset-confirm-icon"><Icon name="trash" /></span><p className="eyebrow">PERMANENT LOCAL RESET</p><h2 id="reset-confirm-title">Clean all CareerMate data?</h2><p>This removes your CV, profile, saved opportunities, match cache, applications, AI preferences and source configuration from the local <code>data/</code> folder. It does not remove <code>backend/.env</code>, API keys, source code, or the virtual environment.</p><label className="field"><span>Type DELETE ALL LOCAL DATA to confirm</span><input autoComplete="off" value={resetConfirmationText} onChange={(event) => setResetConfirmationText(event.target.value)} placeholder="DELETE ALL LOCAL DATA" /></label><div className="reset-confirm-actions"><button className="button button-secondary" type="button" onClick={() => setShowResetConfirmation(false)} disabled={dataResetBusy}>Cancel</button><button className="button button-danger" type="button" onClick={() => void handleResetEverything()} disabled={dataResetBusy || resetConfirmationText.trim() !== "DELETE ALL LOCAL DATA"}>{dataResetBusy ? <><span className="spinner spinner-light" /> Cleaning…</> : "Yes, clean everything"}</button></div></section></div>, document.body)}
            </div>
          )}

    </WorkspaceShell>

      {selectedJob && createPortal(<div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedJob(null); }}>
        <aside className="job-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="job-detail-title">
          <div className="drawer-header"><div><p className="eyebrow">OPPORTUNITY DETAILS</p><span className="source-chip"><SourceMark source={selectedJob.source} sourceUrl={selectedJob.source_url || selectedJob.apply_url} /><span>{sourceLabel(selectedJob.source)}</span></span></div><button className="drawer-close" type="button" onClick={() => setSelectedJob(null)} aria-label="Close job details"><span aria-hidden="true">×</span><span className="drawer-close-label">Close</span></button></div>
          <div className="job-detail-content">
          <div className="drawer-company-mark">{(selectedJob.company || "?").trim().charAt(0).toUpperCase()}</div>
          <h2 id="job-detail-title" className="drawer-job-title">{selectedJob.title}</h2>
          <p className="drawer-company">{selectedJob.company || "Company not listed"}</p>
          <div className="drawer-meta"><span><Icon name="pin" />{selectedJob.location || "Location not listed"}</span><span><Icon name="briefcase" />{workModeLabel(selectedJob.work_mode)}</span>{selectedJob.published_at && <span><Icon name="clock" />{selectedJob.published_at}</span>}</div>
          {selectedJob.search_roles?.length ? <div className="drawer-tags">{selectedJob.search_roles.map((role) => <span className="job-role-badge" key={role}>{role}</span>)}</div> : null}
          {hasAppliedToJob(selectedJob.id) && <div className="drawer-application-history"><div><strong>Already applied</strong><span>{APPLICATION_STATUS_LABELS[applicationForJob(selectedJob.id)?.status ?? "applied"]} · application details saved locally</span></div><button type="button" className="text-action" onClick={() => void handleTrackJob(selectedJob.id)}>Open tracker <Icon name="arrow" /></button></div>}
          {matches.find((item) => item.id === selectedJob.id) && <div className="drawer-match-summary"><span className="drawer-match-score">{matches.find((item) => item.id === selectedJob.id)?.match_score ?? "—"}<small>/ 100</small></span><span><strong>CV match estimate</strong><small>Evidence coverage, not a hiring probability</small></span><button type="button" className="text-action" onClick={() => { setSelectedJob(null); setActiveView("matches"); }}>View analysis <Icon name="arrow" /></button></div>}
          <div className="drawer-section"><div className="drawer-section-heading"><h3>About this role</h3><span className={`description-quality-pill ${selectedJob.description_source === "original_listing" ? "description-quality-full" : "description-quality-snippet"}`}>{selectedJob.description_fetch_message?.startsWith("Manually pasted advert text") ? "Pasted advert" : selectedJob.description_source === "original_listing" ? "Full listing" : "Search snippet"}</span></div>{(() => { const description = selectedJob.description?.trim() || "The source did not provide a description in the search response. Fetch the original public listing or open it below."; const longDescription = description.length > 900; return longDescription ? <><div className="drawer-description drawer-description-preview">{description.slice(0, 760).trimEnd()}…</div><details className="drawer-description-more"><summary>Show full job description ({description.length.toLocaleString()} characters)</summary><div className="drawer-description">{description}</div></details></> : <div className="drawer-description">{description}</div>; })()}{selectedJob.description_source !== "original_listing" && <button type="button" className="button button-secondary button-full fetch-description-button" onClick={() => void handleEnrichJobDetails(selectedJob)} disabled={enrichingJobId === selectedJob.id}>{enrichingJobId === selectedJob.id ? <><span className="spinner" /> Fetching full job details…</> : "Fetch full job description"}</button>}{selectedJob.description_fetch_status === "failed" && selectedJob.description_fetch_message && <p className="description-fetch-warning">{selectedJob.description_fetch_message}</p>}</div>
          <section className="drawer-section cv-tailor-workspace">
            <div className="drawer-section-heading"><h3>Tailor your CV for this role</h3><span className="source-chip">AI assisted</span></div>
            <p className="helper-text">Uses your saved candidate profile and this job description. AI can reorganise and rephrase evidence, but must not invent experience or qualifications.</p>
            <label className="field"><span>CV template</span><FloatingSelect ariaLabel="CV template" value={cvTemplate} onChange={(value) => setCvTemplate(value as "classic" | "modern" | "compact" | "sectioned")} options={[{ value: "classic", label: "Harvard style · Classic ATS" }, { value: "modern", label: "Stanford style · Modern professional" }, { value: "compact", label: "Compact ATS" }, { value: "sectioned", label: "Sectioned professional · centered header and grouped skills" }]} /></label>
            <button type="button" className="button button-primary button-full" onClick={()=>void handleTailorCvForSelectedJob()} disabled={tailoringCv || !profile}>{tailoringCv ? "Creating tailored CV…" : tailoredCv ? "Regenerate tailored CV" : "Generate tailored CV and ATS score"}</button>
            {!profile && <p className="description-fetch-warning">Upload and analyse your original CV first.</p>}
            {cvTailorError && <p className="description-fetch-warning">{cvTailorError}</p>}
            {tailoredCv && <div className="cv-tailor-result">
              <div className="cv-generated-filename"><Icon name="file" /><span><strong>Saved as</strong><code>{tailoredCv.filename}</code><small>Role and company are included in the filename and saved metadata.</small></span></div>
              <div className="cv-score-line"><strong>ATS compatibility estimate</strong><strong className={tailoredCv.ats.score>=70?"cv-score-good":"cv-score-low"}>{tailoredCv.ats.score}/100</strong></div>
              <div className="cv-score-track"><span style={{width:`${tailoredCv.ats.score}%`}} /></div>
              <p className="helper-text">{tailoredCv.ats.score>=70?"Above the 70-point review threshold. Review before applying.":"Below 70. Review missing keywords, update your candidate profile with truthful evidence, then regenerate."}</p>
              {tailoredCv.ats.score<70 && <button type="button" className="button button-secondary button-full" onClick={()=>{setSelectedJob(null);setActiveView("profile");}}>Improve my candidate profile</button>}
              <div className="cv-score-breakdown"><span>Keyword overlap <strong>{tailoredCv.ats.keyword_match_score}%</strong></span><span>Section completeness <strong>{tailoredCv.ats.section_completeness_score}%</strong></span></div>
              {tailoredCv.ats.missing_keywords.length>0 && <details><summary>Missing job keywords ({tailoredCv.ats.missing_keywords.length})</summary><p>{tailoredCv.ats.missing_keywords.slice(0,30).join(", ")}</p></details>}
              <details><summary>ATS structure checks</summary>{tailoredCv.ats.checks.map((check)=><p key={check.name}>{check.passed?"✓":"○"} {check.name}</p>)}</details>
              <a className="button button-secondary button-full" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}`} target="_blank" rel="noreferrer">Download DOCX <Icon name="download" /></a>
              <a className="button button-secondary button-full" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}/preview`} target="_blank" rel="noreferrer">Preview PDF <Icon name="eye" /></a>
              <a className="button button-secondary button-full" href={`${TAILORED_CV_DOWNLOAD_BASE}${tailoredCv.download_url}/pdf`} target="_blank" rel="noreferrer">Download PDF <Icon name="download" /></a>
              {tailoredCvVersions.length>1 && <details><summary>Previous CV versions ({tailoredCvVersions.length-1})</summary>{tailoredCvVersions.slice(1,8).map((version)=><div className="saved-search-row cv-version-row" key={version.filename}><span><strong>{[version.job_title, version.company].filter(Boolean).join(" · ") || `${version.template} CV`} · ${version.ats_score ?? "—"}/100</strong><small><code>{version.pdf_filename || version.filename.replace(/\.docx$/i, ".pdf")}</code><br />{new Date(version.created_at).toLocaleString()}</small></span><div className="cv-version-actions"><a className="text-action" href={`${TAILORED_CV_DOWNLOAD_BASE}/api/cv/tailored/${encodeURIComponent(version.filename)}`} target="_blank" rel="noreferrer">DOCX</a><a className="text-action" href={`${TAILORED_CV_DOWNLOAD_BASE}/api/cv/tailored/${encodeURIComponent(version.filename)}/pdf`} target="_blank" rel="noreferrer">PDF</a></div></div>)}</details>}
              <small>{tailoredCv.ats.disclaimer}</small>
            </div>}
          </section>
          <div className="drawer-facts"><div><span>Work arrangement</span><strong>{workModeLabel(selectedJob.work_mode)}</strong></div><div><span>Source</span><strong>{sourceLabel(selectedJob.source)}</strong></div><div><span>Published</span><strong>{selectedJob.published_at || "Not provided"}</strong></div></div>
          <div className="drawer-footer"><p>Review the original description and requirements before applying.</p><button type="button" className="button button-secondary button-full" onClick={() => void handleTrackJob(selectedJob.id)}>{hasAppliedToJob(selectedJob.id) ? "Already applied · open tracker" : applications.some((application) => application.job_id === selectedJob.id) ? "Open in application tracker" : "Add to application tracker"} <Icon name="briefcase" /></button>{safeExternalUrl(selectedJob.source_url) ? <a className="button button-primary button-full" href={safeExternalUrl(selectedJob.source_url) ?? undefined} target="_blank" rel="noopener noreferrer">View original listing · {sourceLabel(selectedJob.source)} <Icon name="arrow" /></a> : null}{safeExternalUrl(selectedJob.apply_url) && selectedJob.apply_url !== selectedJob.source_url ? <a className="button button-secondary button-full" href={safeExternalUrl(selectedJob.apply_url) ?? undefined} target="_blank" rel="noopener noreferrer">{hasAppliedToJob(selectedJob.id) ? "Reopen application website (already applied)" : "Open application website"} <Icon name="arrow" /></a> : !safeExternalUrl(selectedJob.source_url) && !safeExternalUrl(selectedJob.apply_url) ? <span className="helper-text">No public listing URL was provided for this job.</span> : null}</div>
          </div>
        </aside>
      </div>, document.body)}
    </>
  );
}

function RequirementList({
  title,
  kind,
  items,
}: {
  title: string;
  kind: "supported" | "partial" | "missing";
  items: RequirementAssessment[];
}) {
  return (
    <div className={`requirement-list requirement-${kind}`}>
      <h4><span className="requirement-mark">{kind === "supported" ? "✓" : kind === "partial" ? "~" : "?"}</span>{title}<span className="requirement-count">{items.length}</span></h4>
      {items.length > 0 ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${kind}-${index}`} className={`${item.criticality === "critical" && item.status !== "supported" ? "requirement-critical" : ""}`}>
              <strong>{item.requirement}</strong>
              <span className={`requirement-priority priority-${item.criticality ?? "important"}`}>{item.criticality === "critical" ? "Critical requirement" : item.criticality === "nice_to_have" ? "Nice to have" : item.importance === "required" ? "Required" : item.importance === "preferred" ? "Preferred" : "Priority not explicit"}</span>
              {item.evidence && <q className="requirement-evidence">{item.evidence}</q>}
              {item.explanation && <span className="requirement-explanation">{item.explanation}</span>}
            </li>
          ))}
        </ul>
      ) : <p>None identified</p>}
    </div>
  );
}

export default App;
