import { useCallback, useEffect, useState, type FormEvent, type HTMLInputTypeAttribute } from "react";
import {
  analyzeCv,
  closeBrowserSession,
  createApplication,
  fillBrowserForm,
  generateApplicationAnswer,
  generateCoverLetter,
  getApplications,
  getAiSettings,
  saveAiSettings,
  testAiProvider,
  getCvStatus,
  getProfile,
  getSavedJobs,
  getJobSources,
  openApplicationBrowser,
  scanBrowserForm,
  matchJobs,
  saveProfile,
  searchJobs,
  updateApplication,
  uploadCv,
} from "./api";
import type {
  ApplicationAnswer,
  AIProviderId,
  AISettingsResponse,
  ApplicationRecord,
  BrowserFieldDraft,
  BrowserFormSession,
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
  WorkMode,
} from "./types";

const EMPTY_STATUS: CvStatus = {
  uploaded: false,
  extracted_text_characters: 0,
  profile_saved: false,
};

const SOURCE_OPTIONS: { id: JobSourceId; title: string }[] = [
  { id: "jobtech_links", title: "JobAd Links" },
  { id: "remoteok", title: "Remote OK" },
  { id: "arbeitnow", title: "Arbeitnow" },
  { id: "greenhouse", title: "Greenhouse" },
  { id: "lever", title: "Lever" },
  { id: "teamtailor", title: "Teamtailor" },
];

const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved",
  preparing: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const EMPTY_SOURCE_STATUS: Record<JobSourceId, JobSourceStatus> = {
  jobtech_links: { configured: true, employers: null, requires_api_key: false },
  remoteok: { configured: true, employers: null, requires_api_key: false },
  arbeitnow: { configured: true, employers: null, requires_api_key: false },
  greenhouse: { configured: false, employers: 0, requires_api_key: false },
  lever: { configured: false, employers: 0, requires_api_key: false },
  teamtailor: { configured: false, employers: 0, requires_api_key: true, credentials_ready: false, missing_credentials: 0 },
};

function canSelectSource(source: JobSourceId, status: JobSourceStatus): boolean {
  if (source === "jobtech_links") return true;
  if (!status.configured) return false;
  return source !== "teamtailor" || status.credentials_ready === true;
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

function suggestedBrowserValue(key: string, profile: CandidateProfile | null, application: ApplicationRecord | null): string {
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

function suggestedBrowserValueLabel(key: string): string {
  const labels: Record<string, string> = {
    "personal.name": "Full name",
    "personal.first_name": "First name from profile",
    "personal.last_name": "Last name from profile",
    "personal.email": "Email address",
    "personal.phone": "Phone number",
    "personal.location": "Profile location",
    "personal.linkedin": "LinkedIn URL",
    "personal.github": "GitHub URL",
    "personal.portfolio": "Portfolio URL",
    summary: "Professional summary",
    skills: "Skills",
    languages: "Languages",
    certifications: "Certifications",
    cover_letter: "Saved cover-letter draft",
    latest_answer: "Latest saved employer answer",
  };
  return labels[key] ?? "No automatic suggestion";
}

function makeBrowserFieldDrafts(session: BrowserFormSession, profile: CandidateProfile | null, application: ApplicationRecord | null): BrowserFieldDraft[] {
  return session.fields.map((field) => {
    const value = suggestedBrowserValue(field.suggested_key, profile, application);
    return { ...field, value, include: Boolean(value.trim()) };
  });
}

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

function Icon({ name }: { name: "search" | "file" | "sparkles" | "briefcase" | "check" | "arrow" | "grid" | "user" | "shield" | "target" | "chevron" | "sliders" | "layers" | "plus" | "info" | "graduation" | "pin" | "clock" | "cpu" }) {
  const paths: Record<typeof name, string> = {
    search: "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm10 2-4.35-4.35",
    file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8M8 17h8",
    sparkles: "m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Zm7 12 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z",
    briefcase: "M3 7h18v13H3zM8 7V4h8v3M3 12h18M10 12v2h4v-2",
    check: "m5 12 4 4L19 6",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    user: "M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
    shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Zm-3-11 2 2 4-4",
    target: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-5a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-5h.01",
    chevron: "m9 18 6-6-6-6",
    sliders: "M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M1 14h6m2-6h6m2 8h6",
    layers: "m12 2 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 17l9 5 9-5",
    plus: "M12 5v14M5 12h14",
    info: "M12 16v-4m0-4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
    graduation: "m2 10 10-5 10 5-10 5-10-5Zm4 2v5c4 3 8 3 12 0v-5M22 10v6",
    pin: "M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Zm-5 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-16v6l4 2",
    cpu: "M8 8h8v8H8zM9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3M8 5H5v14h14V5h-3",
  };

  return <svg aria-hidden="true" className="icon" viewBox="0 0 24 24" fill="none"><path d={paths[name]} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

type WorkspaceView = "overview" | "discover" | "matches" | "applications" | "profile" | "ai";

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
  const [jobSources, setJobSources] = useState<Record<JobSourceId, JobSourceStatus>>(EMPTY_SOURCE_STATUS);
  const [selectedSources, setSelectedSources] = useState<JobSourceId[]>(["jobtech_links"]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [aiSettings, setAiSettings] = useState<AISettingsResponse | null>(null);
  const [aiProviderDraft, setAiProviderDraft] = useState<AIProviderId>("ollama");
  const [aiModelDraft, setAiModelDraft] = useState("gemma4:e4b");
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
  const [searchHasMore, setSearchHasMore] = useState(false);
  const [searchTotalReported, setSearchTotalReported] = useState(0);
  const [searchTotalApproximate, setSearchTotalApproximate] = useState(false);
  const [searchFilterNote, setSearchFilterNote] = useState("");
  const [activeSearch, setActiveSearch] = useState<JobSearchCriteria | null>(null);
  const [jobs, setJobs] = useState<JobResult[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [matchLimit, setMatchLimit] = useState(3);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [selectedJob, setSelectedJob] = useState<JobResult | null>(null);
  const [jobFilter, setJobFilter] = useState("");
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
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

  const refreshStatus = useCallback(async () => {
    const status = await getCvStatus();
    setCvStatus(status);
    setProfileSaved(status.profile_saved);
    return status;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [status, savedJobs, sourceResponse, applicationResponse, aiResponse] = await Promise.all([
          getCvStatus(),
          getSavedJobs(),
          getJobSources().catch(() => null),
          getApplications().catch((applicationsError) => {
            if (!cancelled) setError(applicationsError instanceof Error ? applicationsError.message : "Could not load application records.");
            return null;
          }),
          getAiSettings().catch(() => null),
        ]);
        if (cancelled) return;
        setCvStatus(status);
        setProfileSaved(status.profile_saved);
        setJobs(savedJobs);
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
        if (sourceResponse) {
          const mergedStatus = { ...EMPTY_SOURCE_STATUS, ...sourceResponse.sources };
          setJobSources(mergedStatus);
          const availableSources = SOURCE_OPTIONS
            .map((source) => source.id)
            .filter((source) => canSelectSource(source, mergedStatus[source]));
          setSelectedSources(availableSources.length > 0 ? availableSources : ["jobtech_links"]);
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
    };
  }, []);

  useEffect(() => {
    if (!error && !notice) return;
    const timeout = window.setTimeout(() => {
      setError("");
      setNotice("");
    }, error ? 9000 : 6500);
    return () => window.clearTimeout(timeout);
  }, [error, notice]);

  useEffect(() => {
    if (!selectedJob) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedJob(null);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selectedJob]);

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
    setAiModelDraft(config?.model ?? (provider === "ollama" ? "gemma4:e4b" : provider === "openai" ? "gpt-6-luna" : ""));
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

  async function executeJobSearch(criteria: JobSearchCriteria, offset: number) {
    setJobLoading(true);
    setError("");
    setNotice("Searching the selected job sources.");

    try {
      const result = await searchJobs({ ...criteria, offset });
      setActiveSearch(criteria);
      setJobs(result.jobs);
      setSelectedJob(null);
      setMatches([]);
      setSearchOffset(result.offset);
      setSearchHasMore(result.has_more);
      setSearchTotalReported(result.total_reported);
      setSearchTotalApproximate(result.total_is_approximate);
      setSearchFilterNote(result.filter_note);

      const warningText = result.warnings.length
        ? ` Some source searches had warnings: ${result.warnings.join("; ")}`
        : "";
      const totalLabel = `Selected sources reported ${result.total_reported.toLocaleString()} raw matches before local filtering${result.total_is_approximate ? " (approximate when multiple roles, employer boards, or a work-mode filter are used)" : ""}.`;
      setNotice(
        `Showing ${result.returned} unique jobs on page ${Math.floor(offset / criteria.limit) + 1}. ` +
        `${result.saved_total.toLocaleString()} unique job records are saved locally. ${totalLabel}${warningText}`
      );

      if (result.returned === 0 && result.filtered_out > 0) {
        setNotice(
          `No jobs on this page matched the selected work mode. ${result.filtered_out} listing(s) were excluded because their detected work mode did not match. Try Any or move to the next page.`
        );
      }
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Job search failed.");
      setNotice("");
    } finally {
      setJobLoading(false);
    }
  }

  function toggleJobSource(source: JobSourceId, checked: boolean) {
    setSelectedSources((current) => {
      if (checked) return current.includes(source) ? current : [...current, source];
      return current.filter((item) => item !== source);
    });
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

    if (selectedSources.length === 0) {
      setError("Select at least one job source.");
      setNotice("");
      return;
    }

    const criteria: JobSearchCriteria = {
      roles,
      country: jobCountry,
      city: jobCity.trim(),
      work_mode: workMode,
      sources: selectedSources,
      limit: pageSize,
    };

    await executeJobSearch(criteria, 0);
  }

  async function changeSearchPage(direction: -1 | 1) {
    if (!activeSearch || jobLoading) return;
    const nextOffset = searchOffset + direction * activeSearch.limit;
    if (nextOffset < 0 || nextOffset > 2000) return;
    await executeJobSearch(activeSearch, nextOffset);
  }


  async function handleMatchJobs() {
    if (!profile) {
      setError("Analyze your CV first so CareerMate has a candidate profile to compare.");
      setNotice("");
      return;
    }
    if (jobs.length === 0) {
      setError("Search for jobs before analyzing matches.");
      setNotice("");
      return;
    }

    setMatchLoading(true);
    setError("");
    const activeProviderLabel = aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider";
    setNotice(aiSettings?.provider === "ollama"
      ? `Analyzing up to ${Math.min(matchLimit, jobs.length)} jobs with local Ollama. The first run can take time on this computer.`
      : `Analyzing up to ${Math.min(matchLimit, jobs.length)} jobs with ${activeProviderLabel}. Selected jobs can run concurrently; API usage may be billed.`);
    try {
      // Always persist the current, user-reviewed version before matching.
      await saveProfile(profile);
      setProfileSaved(true);
      setCvStatus((current) => ({ ...current, profile_saved: true }));

      const selectedJobs = jobs.slice(0, matchLimit);
      const result = await matchJobs(matchLimit, selectedJobs.map((job) => job.id));
      setMatches(result.jobs);
      setNotice(`Analyzed ${result.analyzed} job(s) with ${activeProviderLabel}. Results are evidence-coverage estimates, not hiring probabilities.`);
    } catch (matchError) {
      setError(matchError instanceof Error ? matchError.message : "Could not analyze job matches.");
      setNotice("");
    } finally {
      setMatchLoading(false);
    }
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

  async function handleTrackJob(jobId: string) {
    setError("");
    setNotice("");
    try {
      const result = await createApplication(jobId);
      acceptUpdatedApplication(result.application);
      setSelectedJob(null);
      setActiveView("applications");
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

  async function handleOpenBrowserAssistant() {
    if (!selectedApplication) return;
    setBrowserOpening(true);
    setError("");
    setNotice("Opening a visible browser at the tracked job link. Review the page and navigate to the application form manually if needed.");
    try {
      const session = await openApplicationBrowser(selectedApplication.id);
      setBrowserSession(session);
      setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication));
      setNotice(session.field_count > 0
        ? `Browser opened and ${session.field_count} supported fields scanned. Review suggested values before filling.`
        : "Browser opened. If this is a job listing, navigate to its application form manually and then scan the fields.");
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not open browser assistance.");
      setNotice("");
    } finally {
      setBrowserOpening(false);
    }
  }

  async function handleScanBrowserForm() {
    setBrowserScanning(true);
    setError("");
    setNotice("Scanning visible form fields. Password, verification, CAPTCHA, file upload and submit controls are excluded.");
    try {
      const session = await scanBrowserForm();
      setBrowserSession(session);
      setBrowserFieldDrafts(makeBrowserFieldDrafts(session, profile, selectedApplication));
      setNotice(`Scanned ${session.field_count} supported field(s). Choose and review values before filling.`);
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not scan the current form.");
      setNotice("");
    } finally {
      setBrowserScanning(false);
    }
  }

  async function handleFillBrowserForm() {
    if (!selectedApplication) return;
    const selectedFields = browserFieldDrafts.filter((field) => field.include && field.value.trim());
    if (selectedFields.length === 0) {
      setError("Select at least one field and review its value before filling.");
      setNotice("");
      return;
    }
    setBrowserFilling(true);
    setError("");
    setNotice(`Filling ${selectedFields.length} reviewed field(s). CareerMate will not submit the form.`);
    try {
      const result = await fillBrowserForm(selectedApplication.id, selectedFields);
      setNotice(`${result.message} Filled ${result.filled_count} field(s); skipped ${result.skipped.length}.`);
      if (result.skipped.length) {
        setError(result.skipped.map((item) => `${item.field_id}: ${item.reason}`).join(" "));
      }
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not fill the reviewed fields.");
      setNotice("");
    } finally {
      setBrowserFilling(false);
    }
  }

  async function handleCloseBrowserAssistant() {
    try {
      await closeBrowserSession();
      setBrowserSession(null);
      setBrowserFieldDrafts([]);
      setNotice("Browser session closed. Form values were not stored in CareerMate.");
      setError("");
    } catch (browserError) {
      setError(browserError instanceof Error ? browserError.message : "Could not close the browser session.");
    }
  }

  function updateBrowserField(fieldId: string, changes: Partial<BrowserFieldDraft>) {
    setBrowserFieldDrafts((current) => current.map((field) => field.field_id === fieldId ? { ...field, ...changes } : field));
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

  function updateList(field: "skills" | "certifications" | "languages", value: string) {
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
  const canAnalyzeMatches = Boolean(profile && jobs.length && !matchLoading && !jobLoading && !cvLoading && !saving);
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
  const filteredJobs = jobs.filter((job) => {
    const needle = jobFilter.trim().toLocaleLowerCase();
    if (!needle) return true;
    return [job.title, job.company, job.location, job.description, ...(job.search_roles ?? [])]
      .some((value) => (value ?? "").toLocaleLowerCase().includes(needle));
  });
  const selectedApplication = applications.find((application) => application.id === selectedApplicationId) ?? null;
  const activeApplicationCount = applications.filter((application) => !["rejected", "withdrawn", "offer"].includes(application.status)).length;
  const submittedApplicationCount = applications.filter((application) => ["applied", "interview", "offer", "rejected", "withdrawn"].includes(application.status)).length;
  const canGenerateApplicationDraft = Boolean(selectedApplication && profile && !applicationSaving && !draftingAnswer && !draftingCoverLetter);
  const pageMeta: Record<WorkspaceView, { title: string; eyebrow: string; description: string }> = {
    overview: {
      title: "Your career command center",
      eyebrow: "OVERVIEW",
      description: "A clear view of your search, your profile readiness, and the opportunities worth your attention.",
    },
    discover: {
      title: "Find your next opportunity",
      eyebrow: "JOB DISCOVERY",
      description: "Search the sources you have configured, compare options, and open a focused view of each role.",
    },
    matches: {
      title: "Know why a role fits",
      eyebrow: "MATCH INSIGHTS",
      description: "Review evidence-backed strengths and gaps before spending time on an application.",
    },
    applications: {
      title: "Your application workspace",
      eyebrow: "APPLICATION TRACKER",
      description: "Keep your shortlist, draft materials, follow-ups, and application progress organized in local files.",
    },
    profile: {
      title: "Your professional profile",
      eyebrow: "CV & PROFILE",
      description: "Keep your career facts accurate. The selected AI provider uses this reviewed profile when assessing opportunities.",
    },
    ai: {
      title: "Choose your AI engine",
      eyebrow: "AI SETTINGS",
      description: "Choose local Ollama for private offline inference, OpenAI for hosted responses, or another OpenAI-compatible API.",
    },
  };
  const currentMeta = pageMeta[activeView];
  const currentActivity = jobLoading
    ? "Searching the selected job sources…"
    : matchLoading
      ? "Comparing job requirements with your profile…"
      : cvLoading
        ? `Processing your CV with ${aiSettings?.providers[aiSettings.provider]?.label ?? "the selected AI provider"}…`
        : saving
          ? "Saving your profile locally…"
          : "";
  const sourceLabel = (source: string) => source === "jobtech_links" ? "JobAd Links" : source === "remoteok" ? "Remote OK" : source === "arbeitnow" ? "Arbeitnow" : source === "greenhouse" ? "Greenhouse" : source === "lever" ? "Lever" : source === "teamtailor" ? "Teamtailor" : source;
  const workModeLabel = (mode?: string) => mode === "remote" ? "Remote" : mode === "hybrid" ? "Hybrid" : mode === "on_site" ? "On-site" : "Work mode unknown";
  const renderJobRow = (job: JobResult, compact = false) => {
    const sourceUrl = safeExternalUrl(job.source_url || job.apply_url);
    const match = matches.find((item) => item.id === job.id);
    return (
      <article className={`job-row${compact ? " job-row-compact" : ""}`} key={job.id}>
        <div className="company-avatar">{(job.company || "?").trim().charAt(0).toUpperCase()}</div>
        <div className="job-row-main">
          <button className="job-title-button" type="button" onClick={() => setSelectedJob(job)}>{job.title}</button>
          <div className="job-row-meta"><span>{job.company || "Company not listed"}</span><i aria-hidden="true">·</i><span>{job.location || "Location not listed"}</span></div>
          <div className="job-badges">
            <span className={`job-mode-badge mode-${job.work_mode ?? "unknown"}`}>{workModeLabel(job.work_mode)}</span>
            <span className="source-chip">{sourceLabel(job.source)}</span>
            {(job.search_roles ?? []).slice(0, 2).map((role) => <span className="job-role-badge" key={role}>{role}</span>)}
            {match?.match_score !== undefined && match.match_score !== null && <span className="match-chip">{match.match_score}% CV match</span>}
          </div>
          {!compact && job.description && <p className="job-row-description">{job.description}</p>}
        </div>
        <div className="job-row-actions">
          {job.published_at && <span className="job-date">{job.published_at}</span>}
          <button className="button button-secondary button-small" type="button" onClick={() => setSelectedJob(job)}>Details</button>
          {sourceUrl && <a className="icon-link" href={sourceUrl} target="_blank" rel="noopener noreferrer" aria-label={`Open ${job.title} at source`}><Icon name="arrow" /></a>}
        </div>
      </article>
    );
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CareerMate home" onClick={(event) => { event.preventDefault(); setActiveView("overview"); setSelectedJob(null); }}>
          <span className="brand-mark">C</span>
          <span className="brand-wordmark">CareerMate<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-context"><span className="topbar-context-dot" />Personal job search workspace</div>
        <div className="topbar-right">
          <span className="privacy-chip"><span className="privacy-dot" /> {aiSettings?.provider && aiSettings.provider !== "ollama" ? "Hosted AI selected" : "Ollama selected"}</span>
          <span className="topbar-avatar">{profile?.personal?.name?.trim()?.charAt(0)?.toUpperCase() || "C"}</span>
        </div>
      </header>

      <div className="workspace-shell" id="top">
        <aside className="sidebar">
          <div className="sidebar-label">WORKSPACE</div>
          <nav className="sidebar-nav" aria-label="Main navigation">
            <button type="button" className={`nav-item${activeView === "overview" ? " active" : ""}`} onClick={() => { setActiveView("overview"); setSelectedJob(null); }}><Icon name="grid" /><span>Overview</span></button>
            <button type="button" className={`nav-item${activeView === "discover" ? " active" : ""}`} onClick={() => { setActiveView("discover"); setSelectedJob(null); }}><Icon name="search" /><span>Find jobs</span><span className="nav-count">{jobs.length}</span></button>
            <button type="button" className={`nav-item${activeView === "matches" ? " active" : ""}`} onClick={() => { setActiveView("matches"); setSelectedJob(null); }}><Icon name="sparkles" /><span>Match insights</span>{matches.length > 0 && <span className="nav-count">{matches.length}</span>}</button>
            <button type="button" className={`nav-item${activeView === "applications" ? " active" : ""}`} onClick={() => { setActiveView("applications"); setSelectedJob(null); }}><Icon name="briefcase" /><span>Applications</span>{applications.length > 0 && <span className="nav-count">{applications.length}</span>}</button>
            <button type="button" className={`nav-item${activeView === "profile" ? " active" : ""}`} onClick={() => { setActiveView("profile"); setSelectedJob(null); }}><Icon name="user" /><span>My profile</span><span className={`nav-status ${profile && profileSaved ? "nav-status-ready" : ""}`} /></button>
            <button type="button" className={`nav-item${activeView === "ai" ? " active" : ""}`} onClick={() => { setActiveView("ai"); setSelectedJob(null); }}><Icon name="cpu" /><span>AI provider</span><span className={`nav-status ${aiSettings?.providers[aiSettings.provider]?.configured ? "nav-status-ready" : ""}`} /></button>
          </nav>
          <div className="sidebar-divider" />
          <div className="sidebar-label">WORKFLOW</div>
          <div className="workflow-checks">
            <div className="workflow-check"><span className={`workflow-check-mark${cvStatus.uploaded ? " complete" : ""}`}>{cvStatus.uploaded ? "✓" : "1"}</span><span><strong>CV uploaded</strong><small>{cvStatus.uploaded ? "Text extracted locally" : "Add your CV to begin"}</small></span></div>
            <div className="workflow-check"><span className={`workflow-check-mark${profileSaved ? " complete" : ""}`}>{profileSaved ? "✓" : "2"}</span><span><strong>Profile reviewed</strong><small>{profileSaved ? "Ready for job matching" : "Review facts before matching"}</small></span></div>
            <div className="workflow-check"><span className={`workflow-check-mark${matches.length ? " complete" : ""}`}>{matches.length ? "✓" : "3"}</span><span><strong>Compare roles</strong><small>{matches.length ? `${matches.length} match insights ready` : "Find jobs, then compare"}</small></span></div>
          </div>
          <div className="sidebar-spacer" />
          <div className="privacy-card">
            <div className="privacy-card-icon"><Icon name="shield" /></div>
            <strong>Your data stays yours</strong>
            <p>Project files stay local. Hosted AI receives prompt content only when you select an online provider.</p>
            <span><span className="privacy-dot" /> {aiSettings?.providers[aiSettings.provider]?.label ?? "Loading AI provider"}</span>
          </div>
          <div className="sidebar-footer"><span className="brand-mark sidebar-brand-mark">C</span><span><strong>CareerMate</strong><small>Personal edition</small></span><span className="version-dot" title="Local workspace" /></div>
        </aside>

        <section className="workspace-main">
          <div className="workspace-heading">
            <div>
              <p className="eyebrow">{currentMeta.eyebrow}</p>
              <h1>{currentMeta.title}</h1>
              <p className="workspace-description">{currentMeta.description}</p>
            </div>
            <div className="workspace-heading-actions">
              {currentActivity ? <span className="activity-pill"><span className="activity-spinner" />{currentActivity}</span> : <span className="quiet-status"><span className="quiet-status-dot" />{profile && !profileSaved ? "Profile has unsaved edits" : "Local workspace ready"}</span>}
              {activeView !== "discover" && <button className="button button-primary" type="button" onClick={() => setActiveView("discover")}><Icon name="search" /> Find jobs</button>}
            </div>
          </div>

          {initialLoading && <div className="loading-line"><span className="spinner" /> Loading your local workspace…</div>}

          {(error || notice) && (
            <div className={`toast ${error ? "toast-error" : "toast-success"}`} role={error ? "alert" : "status"} aria-live={error ? "assertive" : "polite"}>
              <span className="toast-symbol">{error ? "!" : "✓"}</span>
              <span className="toast-message">{error || notice}</span>
              <button className="toast-dismiss" type="button" onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss notification">×</button>
            </div>
          )}

          {activeView === "overview" && (
            <div className="view-stack overview-view">
              <section className="welcome-banner">
                <div className="welcome-banner-copy">
                  <span className="welcome-label"><span className="welcome-sparkle">✦</span> YOUR NEXT CHAPTER STARTS HERE</span>
                  <h2>{profile?.personal?.name?.trim() ? `Welcome back, ${profile.personal.name.trim().split(/\s+/)[0]}.` : "Make your next move with intent."}</h2>
                  <p>Find roles worth your time, see how your experience aligns, and prepare your next step with more clarity.</p>
                  <div className="welcome-actions">
                    <button className="button button-light" type="button" onClick={() => setActiveView("discover")}><Icon name="search" /> Explore opportunities <Icon name="arrow" /></button>
                    <button className="button button-ghost-light" type="button" onClick={() => setActiveView("profile")}>{profile ? "Review my profile" : "Set up my CV"} <Icon name="arrow" /></button>
                  </div>
                </div>
                <div className="welcome-orbit" aria-hidden="true"><div className="welcome-ring ring-one" /><div className="welcome-ring ring-two" /><div className="welcome-orb"><Icon name="sparkles" /></div><span className="orbit-tag orbit-tag-one"><Icon name="check" /> Evidence-led</span><span className="orbit-tag orbit-tag-two"><Icon name="shield" /> Private by design</span></div>
              </section>

              <div className="overview-stat-grid">
                <article className="overview-stat-card"><span className="overview-stat-icon icon-blue"><Icon name="briefcase" /></span><div><span className="overview-stat-label">Opportunities collected</span><strong>{savedCountLabel}</strong><small>{activeSearch ? "From your latest search" : "Search to find roles"}</small></div><button type="button" onClick={() => setActiveView("discover")} aria-label="View job opportunities"><Icon name="arrow" /></button></article>
                <article className="overview-stat-card"><span className="overview-stat-icon icon-violet"><Icon name="user" /></span><div><span className="overview-stat-label">CV profile</span><strong>{profile ? `${profileCompletion}% ready` : "Not configured"}</strong><small>{profileSaved ? "Reviewed and saved" : profile ? "Edits need review" : "Upload your CV to start"}</small></div><button type="button" onClick={() => setActiveView("profile")} aria-label="Open profile"><Icon name="arrow" /></button></article>
                <article className="overview-stat-card"><span className="overview-stat-icon icon-green"><Icon name="sparkles" /></span><div><span className="overview-stat-label">Match insights</span><strong>{matches.length ? `${matches.length} analyzed` : "Ready when you are"}</strong><small>{matches.length ? "Evidence-based comparison" : "Compare jobs against your profile"}</small></div><button type="button" onClick={() => setActiveView("matches")} aria-label="Open match insights"><Icon name="arrow" /></button></article>
              </div>

              <div className="overview-grid">
                <section className="panel recent-panel">
                  <div className="panel-titlebar"><div><p className="eyebrow">YOUR OPPORTUNITIES</p><h2>Recently collected jobs</h2><p>Open any role for a focused review.</p></div><button className="text-action" type="button" onClick={() => setActiveView("discover")}>View all <Icon name="arrow" /></button></div>
                  {jobs.length ? <div className="recent-job-list">{jobs.slice(0, 4).map((job) => renderJobRow(job, true))}</div> : <div className="empty-state compact-empty"><span className="empty-icon"><Icon name="search" /></span><h3>Your shortlist will appear here</h3><p>Run a search to bring relevant roles into your workspace.</p><button className="button button-primary" type="button" onClick={() => setActiveView("discover")}>Search opportunities <Icon name="arrow" /></button></div>}
                </section>
                <aside className="panel readiness-panel">
                  <div className="panel-titlebar"><div><p className="eyebrow">STAY ORGANIZED</p><h2>Ready for your next application?</h2></div><span className="readiness-icon"><Icon name="target" /></span></div>
                  <p className="panel-description">A strong workflow starts with an accurate profile and a shortlist of roles you actually want.</p>
                  <div className="readiness-steps">
                    <button type="button" className="readiness-step" onClick={() => setActiveView("profile")}><span className={`readiness-check${cvStatus.uploaded ? " done" : ""}`}>{cvStatus.uploaded ? "✓" : "1"}</span><span><strong>Upload and review your CV</strong><small>{cvStatus.uploaded ? `${cvStatus.extracted_text_characters.toLocaleString()} characters extracted` : "PDF, DOCX or TXT up to 10 MB"}</small></span><Icon name="chevron" /></button>
                    <button type="button" className="readiness-step" onClick={() => setActiveView("discover")}><span className={`readiness-check${jobs.length ? " done" : ""}`}>{jobs.length ? "✓" : "2"}</span><span><strong>Discover relevant roles</strong><small>{jobs.length ? `${jobs.length} job records available` : "Search public job sources"}</small></span><Icon name="chevron" /></button>
                    <button type="button" className="readiness-step" onClick={() => setActiveView("matches")}><span className={`readiness-check${matches.length ? " done" : ""}`}>{matches.length ? "✓" : "3"}</span><span><strong>Compare evidence and gaps</strong><small>{matches.length ? "Review your match results" : `${aiSettings?.providers[aiSettings.provider]?.label ?? "Selected AI provider"} · no hiring probability claims`}</small></span><Icon name="chevron" /></button>
                  </div>
                  <div className="local-note"><Icon name="shield" /><span><strong>Private by design</strong><small>Your data remains in local files. No account or cloud workspace is required.</small></span></div>
                </aside>
              </div>
            </div>
          )}

          {activeView === "discover" && (
            <div className="view-stack">
              <div className="discover-layout">
                <section className="panel search-filters-panel">
                  <div className="panel-titlebar filter-titlebar"><div><p className="eyebrow">SEARCH SETTINGS</p><h2>Shape your search</h2></div><span className="filter-icon"><Icon name="sliders" /></span></div>
                  <p className="panel-description">Search up to five job titles or keywords. One title per line.</p>
                  <form onSubmit={handleSearchJobs}>
                    <TextAreaField label="Job titles or keywords" value={jobRoles} onChange={setJobRoles} placeholder={"Platform Engineer\nDevOps Engineer\nSite Reliability Engineer"} rows={4} />
                    <label className="field"><span>Country</span><select value={jobCountry} onChange={(event) => setJobCountry(event.target.value)}><option value="Sweden">Sweden</option><option value="Norway">Norway</option><option value="Denmark">Denmark</option><option value="Finland">Finland</option><option value="Germany">Germany</option><option value="Netherlands">Netherlands</option><option value="United Kingdom">United Kingdom</option><option value="United States">United States</option><option value="Canada">Canada</option><option value="France">France</option><option value="Switzerland">Switzerland</option><option value="Any country">Any country</option></select></label>
                    <Field label="City or location" value={jobCity} onChange={setJobCity} placeholder="e.g. Stockholm" />
                    <label className="field"><span>Work arrangement</span><select value={workMode} onChange={(event) => setWorkMode(event.target.value as WorkMode)}><option value="any">Any / not specified</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on_site">On-site</option></select></label>
                    <label className="field"><span>Results per page</span><select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}><option value={10}>10 jobs</option><option value={20}>20 jobs</option><option value={40}>40 jobs</option></select></label>
                    <details className="source-settings"><summary><span><Icon name="layers" /> Job sources</span><span className="source-settings-count">{selectedSources.length} selected</span></summary>
                      <fieldset className="source-picker" disabled={jobLoading}>
                        <div className="source-option-grid">
                          {SOURCE_OPTIONS.map((source) => {
                            const status = jobSources[source.id];
                            const selectable = canSelectSource(source.id, status);
                            const countLabel = source.id === "jobtech_links" ? "Connected · Sweden-focused" : source.id === "remoteok" ? "Public feed · remote roles" : source.id === "arbeitnow" ? "Public feed · European listings" : !status.configured ? "Not configured · data/sources.json" : source.id === "teamtailor" && !status.credentials_ready ? "API key missing" : `${status.employers ?? 0} employer board${status.employers === 1 ? "" : "s"}`;
                            return <label className={`source-option${selectable ? "" : " source-option-disabled"}`} key={source.id}><input type="checkbox" checked={selectedSources.includes(source.id)} disabled={!selectable} onChange={(event) => toggleJobSource(source.id, event.target.checked)} /><span className="source-option-copy"><strong>{source.title}</strong><small>{countLabel}</small></span></label>;
                          })}
                        </div>
                        <p className="helper-text">Company boards are configured locally. CareerMate does not crawl every company on these platforms.</p>
                      </fieldset>
                    </details>
                    <button className="button button-primary button-full search-submit" disabled={jobLoading} type="submit">{jobLoading ? <><span className="spinner spinner-light" /> Searching jobs…</> : <><Icon name="search" /> Search opportunities</>}</button>
                  </form>
                  <div className="filter-footnote"><Icon name="shield" /><span>Searches are user-initiated. Results are stored in local JSON files.</span></div>
                </section>

                <section className="panel results-panel">
                  <div className="results-heading"><div><p className="eyebrow">OPPORTUNITIES</p><h2>Job results <span className="count-pill">{jobs.length}</span></h2><p className="panel-description">Select a role to review its details. Apply links open the employer’s own website.</p></div><div className="results-state"><span className="status-live-dot" /> Saved locally</div></div>
                  <div className="results-toolbar"><label className="result-search"><Icon name="search" /><input type="search" value={jobFilter} onChange={(event) => setJobFilter(event.target.value)} placeholder="Filter by role, company or keyword" aria-label="Filter job results" /><kbd>⌕</kbd></label><span className="results-summary">{filteredJobs.length} of {jobs.length} shown</span></div>
                  {jobLoading && <div className="inline-progress"><span className="spinner" /><div><strong>Searching job sources</strong><p>Collecting listings, normalizing fields, and removing duplicates.</p></div></div>}
                  {!jobLoading && filteredJobs.length === 0 ? <div className="empty-state results-empty"><span className="empty-icon"><Icon name="search" /></span><h3>{jobs.length ? "No jobs match that filter" : "No opportunities yet"}</h3><p>{jobs.length ? "Try a different title, employer, or keyword." : "Choose your target roles and location, then run your first search."}</p>{jobs.length ? <button className="button button-secondary" type="button" onClick={() => setJobFilter("")}>Clear filter</button> : <button className="button button-primary" type="button" onClick={() => document.querySelector<HTMLInputElement>('.search-filters-panel textarea')?.focus()}>Start searching</button>}</div> : <div className="job-results-list">{filteredJobs.map((job) => renderJobRow(job))}</div>}
                  {activeSearch && <><div className="search-pagination"><div><strong>Page {Math.floor(searchOffset / activeSearch.limit) + 1}</strong><span className="helper-text">{`${searchTotalReported.toLocaleString()} raw source matches before local filtering${searchTotalApproximate ? " (approximate when multiple roles or work-mode filters are used)" : ""}`}</span></div><div className="button-row pagination-buttons"><button className="button button-secondary" type="button" onClick={() => void changeSearchPage(-1)} disabled={jobLoading || searchOffset === 0}>Previous</button><button className="button button-secondary" type="button" onClick={() => void changeSearchPage(1)} disabled={jobLoading || !searchHasMore || searchOffset >= 2000}>Next page</button></div></div>{searchFilterNote && <p className="search-filter-note">{searchFilterNote}</p>}</>}
                </section>
              </div>
            </div>
          )}

          {activeView === "matches" && (
            <div className="view-stack">
              <section className="match-toolbar panel">
                <div className="match-toolbar-copy"><span className="match-toolbar-symbol"><Icon name="sparkles" /></span><div><p className="eyebrow">EVIDENCE-BASED COMPARISON</p><h2>Understand the fit, not just the score</h2><p className="panel-description">CareerMate compares requirements with facts in your reviewed profile. Scores estimate evidence coverage, not your chance of being hired.</p></div></div>
                <div className="match-controls"><label className="compact-field"><span>Analyze</span><select value={matchLimit} onChange={(event) => setMatchLimit(Number(event.target.value))} disabled={matchLoading}><option value={1}>1 job</option><option value={3}>3 jobs</option><option value={5}>5 jobs</option><option value={10}>10 jobs</option><option value={20}>20 jobs</option></select></label><button className="button button-primary" onClick={handleMatchJobs} disabled={!canAnalyzeMatches} type="button">{matchLoading ? <><span className="spinner spinner-light" /> Analyzing…</> : <><Icon name="sparkles" /> Analyze matches</>}</button></div>
              </section>
              {!profile && <div className="inline-hint setup-hint"><Icon name="user" /><div><strong>Your profile is the starting point</strong><p>Upload and analyze your CV, review the extracted facts, and save the profile before running match analysis.</p><button className="button button-secondary" type="button" onClick={() => setActiveView("profile")}>Set up profile <Icon name="arrow" /></button></div></div>}
              {profile && !profileSaved && <div className="inline-hint"><Icon name="info" /><span>Your profile has unsaved edits. CareerMate saves the reviewed version before matching.</span><button className="text-action" type="button" onClick={() => setActiveView("profile")}>Review profile</button></div>}
              {matchLoading && <div className="inline-progress match-progress"><span className="spinner" /><div><strong>Local model is comparing requirements</strong><p>First-time analysis may take several minutes. Results are cached for repeat runs.</p></div></div>}
              {!matchLoading && matches.length === 0 && <div className="panel empty-state match-empty"><span className="empty-icon"><Icon name="sparkles" /></span><h3>Your fit report will appear here</h3><p>Search for jobs and make sure your CV profile has been reviewed. Then analyze the roles you want to compare.</p><div className="empty-state-actions"><button className="button button-primary" type="button" onClick={() => setActiveView("discover")}>Find jobs <Icon name="arrow" /></button>{!profile && <button className="button button-secondary" type="button" onClick={() => setActiveView("profile")}>Review CV profile</button>}</div></div>}
              {matches.length > 0 && <div className="match-results">{matches.map((job) => <article className="match-card" key={job.id}>
                <div className="match-card-header"><div><p className="eyebrow">MATCH REPORT</p><h3>{job.title}</h3><p>{job.company} · {job.location}</p></div><div className={`score-badge ${job.match_score === null ? "score-unavailable" : job.match_score >= 75 ? "score-strong" : job.match_score >= 50 ? "score-medium" : "score-low"}`}><strong>{job.match_score === null ? "—" : job.match_score}</strong><span>{job.match_score === null ? "No score" : "/ 100"}</span></div></div>
                {job.match_score !== null && <div className="score-track"><span style={{ width: `${Math.max(0, Math.min(100, job.match_score))}%` }} /></div>}
                <div className="match-meta"><span>Confidence: {job.match_confidence}</span><span>Method: evidence-weighted AI</span><button className="text-action" type="button" onClick={() => { setSelectedJob(job); }}>Open role details <Icon name="arrow" /></button></div>
                <p className="match-explanation">{job.match_explanation}</p>
                <div className="requirement-grid"><RequirementList title="Supported" kind="supported" items={(job.requirements ?? []).filter((item) => item.status === "supported")} /><RequirementList title="Partially supported" kind="partial" items={(job.requirements ?? []).filter((item) => item.status === "partially_supported")} /><RequirementList title="Not evidenced in profile" kind="missing" items={(job.requirements ?? []).filter((item) => item.status === "not_evidenced")} /></div>
                <p className="score-note">{job.score_note}</p>
                {safeExternalUrl(job.apply_url || job.source_url) && <a className="text-link" href={safeExternalUrl(job.apply_url || job.source_url) ?? undefined} target="_blank" rel="noopener noreferrer">Review full job advert <Icon name="arrow" /></a>}
              </article>)}</div>}
            </div>
          )}

          {activeView === "applications" && (
            <div className="view-stack applications-view">
              <div className="application-stats-grid">
                <article className="application-stat-card"><span className="application-stat-label">Tracked roles</span><strong>{applications.length}</strong><small>Saved in local JSON</small></article>
                <article className="application-stat-card"><span className="application-stat-label">In progress</span><strong>{activeApplicationCount}</strong><small>Saved, preparing or active</small></article>
                <article className="application-stat-card"><span className="application-stat-label">Submitted or beyond</span><strong>{submittedApplicationCount}</strong><small>Applied, interview, offer or closed</small></article>
              </div>
              {applications.length === 0 ? (
                <section className="panel empty-state applications-empty"><span className="empty-icon"><Icon name="briefcase" /></span><p className="eyebrow">APPLICATION TRACKER</p><h2>Your application workspace is ready</h2><p>Save a role from its details panel to track progress, keep notes, create a cover-letter draft, and prepare answers to employer questions.</p><button className="button button-primary" type="button" onClick={() => setActiveView("discover")}>Find roles to track <Icon name="arrow" /></button><p className="helper-text">No application is submitted automatically. You review and submit through the employer’s own website.</p></section>
              ) : (
                <div className="applications-layout">
                  <section className="panel application-list-panel">
                    <div className="panel-titlebar"><div><p className="eyebrow">YOUR PIPELINE</p><h2>Tracked applications <span className="count-pill">{applications.length}</span></h2><p>Choose a role to update its stage or prepare materials.</p></div></div>
                    <div className="application-list">
                      {applications.map((application) => (
                        <button type="button" key={application.id} className={`application-list-item${application.id === selectedApplicationId ? " selected" : ""}`} onClick={() => selectApplication(application)} aria-pressed={application.id === selectedApplicationId}>
                          <span className="application-company-avatar">{(application.company || "?").trim().charAt(0).toUpperCase()}</span>
                          <span className="application-list-copy"><strong>{application.title}</strong><small>{application.company || "Company not listed"} · {application.location || "Location not listed"}</small><span className={`application-status-pill status-${application.status}`}>{APPLICATION_STATUS_LABELS[application.status]}</span></span>
                          <Icon name="chevron" />
                        </button>
                      ))}
                    </div>
                  </section>
                  {selectedApplication ? (
                    <section className="panel application-editor-panel">
                      <div className="application-editor-header"><div><p className="eyebrow">APPLICATION DETAILS</p><h2>{selectedApplication.title}</h2><p>{selectedApplication.company || "Company not listed"} · {selectedApplication.location || "Location not listed"}</p></div>{safeExternalUrl(selectedApplication.job_url) && <a className="button button-secondary button-small" href={safeExternalUrl(selectedApplication.job_url) ?? undefined} target="_blank" rel="noopener noreferrer">Original listing <Icon name="arrow" /></a>}</div>
                      <div className="form-grid application-metadata-grid">
                        <label className="field"><span>Application stage</span><select value={applicationStatus} onChange={(event) => setApplicationStatus(event.target.value as ApplicationStatus)}>{[
                          ["saved", "Saved"], ["preparing", "Preparing application"], ["applied", "Applied"], ["interview", "Interview"], ["offer", "Offer"], ["rejected", "Rejected"], ["withdrawn", "Withdrawn"],
                        ].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                        <Field label="Follow-up date" type="date" value={applicationFollowUpDate} onChange={setApplicationFollowUpDate} />
                      </div>
                      <TextAreaField label="Notes and next actions" value={applicationNotes} onChange={setApplicationNotes} placeholder="Recruiter contact, application deadline, interview notes, next action…" rows={3} />
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
                      <section className="application-draft-section browser-assist-section">
                        <div className="application-section-heading"><div><p className="eyebrow">STEP 14 · BROWSER ASSISTANCE</p><h3>Prepare the employer form</h3><p>Open a visible browser, review suggested values, then choose which fields to fill.</p></div></div>
                        <div className="browser-assist-safety"><Icon name="shield" /><span>CareerMate never clicks Submit, uploads files, fills password/verification fields, or bypasses CAPTCHA or sign-in checks. Form values stay in browser memory and are not saved to the JSON tracker.</span></div>
                        <div className="browser-assist-actions">
                          <button className="button button-secondary button-small" type="button" onClick={() => void handleOpenBrowserAssistant()} disabled={!selectedApplication.job_url || browserOpening || browserScanning || browserFilling}>{browserOpening ? <><span className="spinner" /> Opening browser…</> : "Open application page"}</button>
                          {browserSession?.application_id === selectedApplication.id && <>
                            <button className="button button-secondary button-small" type="button" onClick={() => void handleScanBrowserForm()} disabled={browserOpening || browserScanning || browserFilling}>{browserScanning ? <><span className="spinner" /> Scanning…</> : "Refresh form fields"}</button>
                            <button className="button button-quiet button-small" type="button" onClick={() => void handleCloseBrowserAssistant()} disabled={browserFilling}>Close browser session</button>
                          </>}
                        </div>
                        {browserSession?.application_id === selectedApplication.id && <>
                          <div className="browser-assist-page"><strong>{browserSession.title || "Employer page"}</strong><span>{browserSession.url}</span><small>Visible Chromium session · page navigation and sign-in remain manual</small></div>
                          {browserFieldDrafts.length > 0 ? <>
                            <div className="browser-field-heading"><strong>Review fields ({browserFieldDrafts.length})</strong><span>Only checked fields with a value will be filled</span></div>
                            <div className="browser-field-list">{browserFieldDrafts.map((field) => <article className="browser-field-card" key={field.field_id}>
                              <div className="browser-field-card-header"><label className="browser-field-include"><input type="checkbox" checked={field.include} onChange={(event) => updateBrowserField(field.field_id, { include: event.target.checked })} /><span>{field.label}{field.required && <em>Required</em>}</span></label><span className="browser-field-kind">{field.kind}</span></div>
                              {field.suggested_key && <small className="browser-field-source">Suggested from: {suggestedBrowserValueLabel(field.suggested_key)}</small>}
                              <TextAreaField label="Proposed value — review and edit" value={field.value} onChange={(value) => updateBrowserField(field.field_id, { value })} rows={field.kind === "textarea" || field.value.length > 160 ? 3 : 2} placeholder={field.suggested_key ? "Review the suggested value" : "Enter a value yourself after reviewing the form label"} />
                            </article>)}</div>
                            <button className="button button-primary" type="button" onClick={() => void handleFillBrowserForm()} disabled={browserFilling || browserOpening || browserScanning || !browserFieldDrafts.some((field) => field.include && field.value.trim())}>{browserFilling ? <><span className="spinner spinner-light" /> Filling reviewed fields…</> : "Fill selected fields — do not submit"}</button>
                          </> : <p className="helper-text">No supported fields found yet. If the browser is showing a listing page, manually open its application form and select “Refresh form fields”. Password, file, CAPTCHA and submit fields are deliberately excluded.</p>}
                        </>}
                      </section>
                      <div className="application-save-row"><p className="helper-text">Saved locally in <code>data/applications/applications.json</code>. Nothing is submitted automatically.</p><button className="button button-primary" type="button" onClick={() => void handleSaveApplication()} disabled={applicationSaving || draftingAnswer || draftingCoverLetter}>{applicationSaving ? <><span className="spinner spinner-light" /> Saving…</> : <><Icon name="check" /> Save application</>}</button></div>
                    </section>
                  ) : <section className="panel empty-state"><h3>Select an application</h3><p>Choose a role from your tracked applications.</p></section>}
                </div>
              )}
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
                    <select value={aiProviderDraft} onChange={(event) => selectAiProvider(event.target.value as AIProviderId)}>
                      <option value="ollama">Ollama — local and private</option>
                      <option value="openai">OpenAI API — hosted models</option>
                      <option value="openai_compatible">OpenAI-compatible API — other providers</option>
                    </select>
                  </label>
                  <Field label="Model ID" value={aiModelDraft} onChange={(value) => { setAiModelDraft(value); setAiTestMessage(""); }} placeholder={aiProviderDraft === "ollama" ? "e.g. gemma4:e4b" : aiProviderDraft === "openai" ? "e.g. gpt-6-luna" : "Model ID supplied by your API provider"} />
                  {aiProviderDraft !== "openai" && <Field label={aiProviderDraft === "ollama" ? "Ollama host URL" : "API base URL"} value={aiBaseUrlDraft} onChange={(value) => { setAiBaseUrlDraft(value); setAiTestMessage(""); }} placeholder={aiProviderDraft === "ollama" ? "http://127.0.0.1:11434" : "https://your-provider.example/v1"} />}

                  {aiProviderDraft === "ollama" && <div className="ai-info-note"><Icon name="shield" /><div><strong>Local processing</strong><p>CV text, profile details, job descriptions, and drafts are sent to your local Ollama instance. It runs on your computer and can use significant memory and CPU.</p></div></div>}
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
                <section className="profile-summary-card panel"><div className="profile-summary-avatar">{profile.personal?.name?.trim()?.charAt(0)?.toUpperCase() || "C"}</div><div className="profile-summary-copy"><p className="eyebrow">CANDIDATE PROFILE</p><h2>{profile.personal?.name?.trim() || "Your professional profile"}</h2><p>{[profile.personal?.location, profile.personal?.email].filter(Boolean).join(" · ") || "Add your contact details and professional information below."}</p></div><div className={`save-state ${profileSaved ? "saved" : "unsaved"}`}>{profileSaved ? "✓ Saved locally" : "● Review changes"}</div><div className="profile-completion"><div className="profile-completion-label"><span>Profile completeness</span><strong>{profileCompletion}%</strong></div><div className="completion-track"><span style={{ width: `${profileCompletion}%` }} /></div></div></section>
                <section className="panel profile-editor-panel"><div className="panel-titlebar"><div><p className="eyebrow">EDIT & VERIFY</p><h2>Career details</h2><p className="panel-description">AI extraction is a starting point. Keep every field truthful and specific.</p></div><span className="subtle-label">Local file · profile.json</span></div>
                  <details className="profile-accordion" open><summary><span className="accordion-icon"><Icon name="user" /></span><span className="accordion-title">Personal details<small>Name, contact details and professional links</small></span><span className="summary-count">7 fields</span></summary><div className="form-grid profile-form-grid"><Field label="Full name" value={profile.personal?.name ?? ""} onChange={(value) => updatePersonal("name", value)} /><Field label="Email" type="email" value={profile.personal?.email ?? ""} onChange={(value) => updatePersonal("email", value)} /><Field label="Phone" value={profile.personal?.phone ?? ""} onChange={(value) => updatePersonal("phone", value)} /><Field label="Location" value={profile.personal?.location ?? ""} onChange={(value) => updatePersonal("location", value)} /><Field label="LinkedIn URL" value={profile.personal?.linkedin ?? ""} onChange={(value) => updatePersonal("linkedin", value)} /><Field label="GitHub URL" value={profile.personal?.github ?? ""} onChange={(value) => updatePersonal("github", value)} /><Field label="Portfolio URL" value={profile.personal?.portfolio ?? ""} onChange={(value) => updatePersonal("portfolio", value)} /></div></details>
                  <details className="profile-accordion" open><summary><span className="accordion-icon"><Icon name="file" /></span><span className="accordion-title">Summary & skills<small>Your professional story, languages and credentials</small></span><span className="summary-count">{profile.skills.length} skills</span></summary><TextAreaField label="Professional summary" value={profile.summary} onChange={updateSummary} rows={5} /><div className="form-grid profile-form-grid"><TextAreaField label="Skills — one per line" value={profile.skills.join("\n")} onChange={(value) => updateList("skills", value)} /><TextAreaField label="Languages — one per line" value={profile.languages.join("\n")} onChange={(value) => updateList("languages", value)} /><TextAreaField label="Certifications — one per line" value={profile.certifications.join("\n")} onChange={(value) => updateList("certifications", value)} /></div></details>
                  <details className="profile-accordion"><summary><span className="accordion-icon"><Icon name="briefcase" /></span><span className="accordion-title">Professional experience<small>Roles, responsibilities and achievements</small></span><span className="summary-count">{profile.experience.length}</span></summary><div className="record-list">{profile.experience.map((item, index) => <div className="editable-record" key={`experience-${index}`}><div className="editable-record-title"><strong>{item.job_title || `Experience ${index + 1}`}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeExperience(index)}>Remove</button></div><div className="form-grid profile-form-grid"><Field label="Job title" value={item.job_title} onChange={(value) => updateExperience(index, "job_title", value)} /><Field label="Company" value={item.company} onChange={(value) => updateExperience(index, "company", value)} /><Field label="Location" value={item.location} onChange={(value) => updateExperience(index, "location", value)} /><Field label="Start date" value={item.start_date} onChange={(value) => updateExperience(index, "start_date", value)} /><Field label="End date" value={item.end_date} onChange={(value) => updateExperience(index, "end_date", value)} /></div><TextAreaField label="Responsibilities and achievements — one per line" value={item.description.join("\n")} onChange={(value) => updateExperienceDescription(index, value)} /></div>)}{profile.experience.length === 0 && <p className="helper-text">No experience entries have been extracted.</p>}</div><button className="button button-secondary" type="button" onClick={addExperience}><Icon name="plus" /> Add experience</button></details>
                  <details className="profile-accordion"><summary><span className="accordion-icon"><Icon name="graduation" /></span><span className="accordion-title">Education<small>Degrees, institutions and study dates</small></span><span className="summary-count">{profile.education.length}</span></summary><div className="record-list">{profile.education.map((item, index) => <div className="editable-record" key={`education-${index}`}><div className="editable-record-title"><strong>{item.degree || `Education ${index + 1}`}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeEducation(index)}>Remove</button></div><div className="form-grid profile-form-grid"><Field label="Degree" value={item.degree} onChange={(value) => updateEducation(index, "degree", value)} /><Field label="Institution" value={item.institution} onChange={(value) => updateEducation(index, "institution", value)} /><Field label="Location" value={item.location} onChange={(value) => updateEducation(index, "location", value)} /><Field label="Start date" value={item.start_date} onChange={(value) => updateEducation(index, "start_date", value)} /><Field label="End date" value={item.end_date} onChange={(value) => updateEducation(index, "end_date", value)} /></div></div>)}{profile.education.length === 0 && <p className="helper-text">No education entries have been extracted.</p>}</div><button className="button button-secondary" type="button" onClick={addEducation}><Icon name="plus" /> Add education</button></details>
                  <div className="profile-save-row"><p className="helper-text">Saved to <code>data/cv/profile.json</code> on this computer. Match analysis will use the profile after saving.</p><button className="button button-primary" type="button" onClick={handleSaveProfile} disabled={saving || cvLoading || matchLoading}>{saving ? <><span className="spinner spinner-light" /> Saving…</> : <><Icon name="check" /> Save reviewed profile</>}</button></div>
                </section>
              </>}
              {profile && <div className="profile-privacy-footer"><Icon name="shield" /><span>CareerMate stores your profile in local files and excludes contact details from job-match prompts. Hosted providers receive the content needed for each requested task.</span></div>}
            </div>
          )}

          <footer className="workspace-footer"><div><span className="brand-mark footer-mark">C</span><strong>CareerMate</strong><span className="footer-separator">/</span><span>Local-first job search assistant</span></div><span>Open source · Local files, configurable AI provider</span></footer>
        </section>
      </div>

      {selectedJob && <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedJob(null); }}>
        <aside className="job-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="job-detail-title">
          <div className="drawer-header"><div><p className="eyebrow">OPPORTUNITY DETAILS</p><span className="source-chip">{sourceLabel(selectedJob.source)}</span></div><button className="drawer-close" type="button" onClick={() => setSelectedJob(null)} aria-label="Close job details">×</button></div>
          <div className="drawer-company-mark">{(selectedJob.company || "?").trim().charAt(0).toUpperCase()}</div>
          <h2 id="job-detail-title" className="drawer-job-title">{selectedJob.title}</h2>
          <p className="drawer-company">{selectedJob.company || "Company not listed"}</p>
          <div className="drawer-meta"><span><Icon name="pin" />{selectedJob.location || "Location not listed"}</span><span><Icon name="briefcase" />{workModeLabel(selectedJob.work_mode)}</span>{selectedJob.published_at && <span><Icon name="clock" />{selectedJob.published_at}</span>}</div>
          {selectedJob.search_roles?.length ? <div className="drawer-tags">{selectedJob.search_roles.map((role) => <span className="job-role-badge" key={role}>{role}</span>)}</div> : null}
          {matches.find((item) => item.id === selectedJob.id) && <div className="drawer-match-summary"><span className="drawer-match-score">{matches.find((item) => item.id === selectedJob.id)?.match_score ?? "—"}<small>/ 100</small></span><span><strong>CV match estimate</strong><small>Evidence coverage, not a hiring probability</small></span><button type="button" className="text-action" onClick={() => { setSelectedJob(null); setActiveView("matches"); }}>View analysis <Icon name="arrow" /></button></div>}
          <div className="drawer-section"><h3>About this role</h3><div className="drawer-description">{selectedJob.description?.trim() || "The source did not provide a description in the search response. Open the original listing for the full job advert."}</div></div>
          <div className="drawer-facts"><div><span>Work arrangement</span><strong>{workModeLabel(selectedJob.work_mode)}</strong></div><div><span>Source</span><strong>{sourceLabel(selectedJob.source)}</strong></div><div><span>Published</span><strong>{selectedJob.published_at || "Not provided"}</strong></div></div>
          <div className="drawer-footer"><p>Review the original description and requirements before applying.</p><button type="button" className="button button-secondary button-full" onClick={() => void handleTrackJob(selectedJob.id)}>{applications.some((application) => application.job_id === selectedJob.id) ? "Open in application tracker" : "Add to application tracker"} <Icon name="briefcase" /></button>{safeExternalUrl(selectedJob.source_url) ? <a className="button button-primary button-full" href={safeExternalUrl(selectedJob.source_url) ?? undefined} target="_blank" rel="noopener noreferrer">View original listing · {sourceLabel(selectedJob.source)} <Icon name="arrow" /></a> : null}{safeExternalUrl(selectedJob.apply_url) && selectedJob.apply_url !== selectedJob.source_url ? <a className="button button-secondary button-full" href={safeExternalUrl(selectedJob.apply_url) ?? undefined} target="_blank" rel="noopener noreferrer">Open application website <Icon name="arrow" /></a> : !safeExternalUrl(selectedJob.source_url) && !safeExternalUrl(selectedJob.apply_url) ? <span className="helper-text">No public listing URL was provided for this job.</span> : null}<button type="button" className="button button-quiet button-full" onClick={() => setSelectedJob(null)}>Back to results</button></div>
        </aside>
      </div>}
    </main>
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
            <li key={`${kind}-${index}`}>
              <strong>{item.requirement}</strong>
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
