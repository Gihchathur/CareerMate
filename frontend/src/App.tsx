import { useCallback, useEffect, useState, type FormEvent, type HTMLInputTypeAttribute } from "react";
import {
  analyzeCv,
  getCvStatus,
  getProfile,
  getSavedJobs,
  matchJobs,
  saveProfile,
  searchJobs,
  uploadCv,
} from "./api";
import type {
  CandidatePersonal,
  CandidateProfile,
  Education,
  Experience,
  CvStatus,
  JobMatchResult,
  JobResult,
  RequirementAssessment,
} from "./types";

const EMPTY_STATUS: CvStatus = {
  uploaded: false,
  extracted_text_characters: 0,
  profile_saved: false,
};

function safeExternalUrl(value: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
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

function Icon({ name }: { name: "search" | "file" | "sparkles" | "briefcase" | "check" | "arrow" }) {
  const paths: Record<typeof name, string> = {
    search: "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm10 2-4.35-4.35",
    file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8M8 17h8",
    sparkles: "m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Zm7 12 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z",
    briefcase: "M3 7h18v13H3zM8 7V4h8v3M3 12h18M10 12v2h4v-2",
    check: "m5 12 4 4L19 6",
    arrow: "M5 12h14m-6-6 6 6-6 6",
  };

  return (
    <svg aria-hidden="true" className="icon" viewBox="0 0 24 24" fill="none">
      <path d={paths[name]} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [jobQuery, setJobQuery] = useState("Software Engineer");
  const [jobLocation, setJobLocation] = useState("Stockholm");
  const [jobs, setJobs] = useState<JobResult[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [matchLimit, setMatchLimit] = useState(3);

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
        const [status, savedJobs] = await Promise.all([
          getCvStatus(),
          getSavedJobs(),
        ]);
        if (cancelled) return;
        setCvStatus(status);
        setProfileSaved(status.profile_saved);
        setJobs(savedJobs);

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
    setNotice("CareerMate is asking Ollama to structure the CV. The first run may take a while.");
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

  async function handleSearchJobs(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!jobQuery.trim()) {
      setError("Enter a job title or keyword.");
      setNotice("");
      return;
    }

    setJobLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await searchJobs(jobQuery.trim(), jobLocation.trim(), 20);
      setJobs(result.jobs);
      setMatches([]);
      setNotice(`Found ${result.returned} results in this search. ${result.saved_total} unique job records are saved locally.`);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Job search failed.");
    } finally {
      setJobLoading(false);
    }
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
    setNotice(`Analyzing up to ${Math.min(matchLimit, jobs.length)} jobs with the local model. This may take several minutes on the first run.`);
    try {
      // Always persist the current, user-reviewed version before matching.
      await saveProfile(profile);
      setProfileSaved(true);
      setCvStatus((current) => ({ ...current, profile_saved: true }));

      const selectedJobs = jobs.slice(0, matchLimit);
      const result = await matchJobs(matchLimit, selectedJobs.map((job) => job.id));
      setMatches(result.jobs);
      setNotice(`Analyzed ${result.analyzed} job(s). Results are evidence-coverage estimates, not hiring probabilities.`);
    } catch (matchError) {
      setError(matchError instanceof Error ? matchError.message : "Could not analyze job matches.");
      setNotice("");
    } finally {
      setMatchLoading(false);
    }
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CareerMate home">
          <span className="brand-mark">C</span>
          <span>CareerMate</span>
        </a>
        <div className="topbar-right">
          <span className="privacy-chip"><span className="privacy-dot" /> Local workspace</span>
          <span className="version-label">Personal edition</span>
        </div>
      </header>

      <div className="page" id="top">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">YOUR PRIVATE JOB SEARCH WORKSPACE</p>
            <h1>Make your next move<br /><span>with more confidence.</span></h1>
            <p className="hero-description">
              Discover roles, compare requirements with your CV, and prepare your next application — with your data stored locally.
            </p>
          </div>
          <div className="hero-illustration" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="hero-document"><span /><span /><span /><i /></div>
            <div className="floating-check"><Icon name="check" /></div>
            <div className="floating-star"><Icon name="sparkles" /></div>
          </div>
        </section>

        <section className="stats-grid" aria-label="Workspace status">
          <div className="stat-card">
            <span className="stat-icon blue"><Icon name="file" /></span>
            <div><span className="stat-label">Candidate profile</span><strong>{profile ? (profileSaved ? "Saved" : "Review needed") : "Not ready"}</strong></div>
            <span className={`status-dot ${profile ? (profileSaved ? "good" : "pending") : "muted-dot"}`} />
          </div>
          <div className="stat-card">
            <span className="stat-icon violet"><Icon name="briefcase" /></span>
            <div><span className="stat-label">Jobs in view</span><strong>{savedCountLabel}</strong></div>
          </div>
          <div className="stat-card">
            <span className="stat-icon green"><Icon name="sparkles" /></span>
            <div><span className="stat-label">AI matching</span><strong>Local via Ollama</strong></div>
          </div>
        </section>

        {(error || notice) && (
          <div className={`notice ${error ? "notice-error" : "notice-success"}`} role={error ? "alert" : "status"}>
            <span className="notice-symbol">{error ? "!" : "✓"}</span>
            <span>{error || notice}</span>
            <button className="notice-dismiss" onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss notification">×</button>
          </div>
        )}

        {initialLoading && <div className="loading-line"><span className="spinner" /> Loading your local workspace…</div>}

        <section className="workflow-grid">
          <article className="panel search-panel">
            <div className="panel-heading">
              <div className="step-number">01</div>
              <div><p className="eyebrow">DISCOVER</p><h2>Find your next role</h2></div>
            </div>
            <p className="panel-description">Search public Swedish job listings by role and location. Your search results are saved in local JSON files.</p>
            <form onSubmit={handleSearchJobs}>
              <Field label="Job title or keywords" value={jobQuery} onChange={setJobQuery} placeholder="e.g. Platform Engineer" />
              <Field label="City or location" value={jobLocation} onChange={setJobLocation} placeholder="e.g. Stockholm" />
              <button className="button button-primary button-full" disabled={jobLoading} type="submit">
                {jobLoading ? <><span className="spinner spinner-light" /> Searching jobs…</> : <><Icon name="search" /> Search jobs</>}
              </button>
            </form>
            <p className="helper-text">Source: Arbetsförmedlingen JobAd Links · Search initiated by you</p>
          </article>

          <article className="panel cv-panel">
            <div className="panel-heading">
              <div className="step-number">02</div>
              <div><p className="eyebrow">PREPARE</p><h2>Your CV profile</h2></div>
            </div>
            <p className="panel-description">Upload your CV, extract the text, and let the local model organize its contents into an editable profile.</p>
            <label className="upload-dropzone">
              <input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              <span className="upload-icon"><Icon name="file" /></span>
              <strong>{file ? file.name : "Choose your CV"}</strong>
              <span className="helper-text">PDF, DOCX or TXT · up to 10 MB</span>
            </label>
            <div className="button-row">
              <button className="button button-secondary" onClick={handleUploadCv} disabled={cvLoading || !file} type="button">Upload & extract</button>
              <button className="button button-primary" onClick={handleAnalyzeCv} disabled={cvLoading || !cvStatus.uploaded} type="button">
                {cvLoading ? <><span className="spinner spinner-light" /> Working…</> : <><Icon name="sparkles" /> Analyze CV</>}
              </button>
            </div>
            <div className="cv-footnote">
              <span className={`status-dot ${cvStatus.uploaded ? "good" : "muted-dot"}`} />
              {cvStatus.uploaded
                ? `Text extracted · ${cvStatus.extracted_text_characters.toLocaleString()} characters`
                : "No CV text extracted yet"}
            </div>
          </article>
        </section>

        <section className="panel results-panel">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">OPPORTUNITIES</p>
              <h2>Job listings <span className="count-pill">{jobs.length}</span></h2>
              <p className="panel-description">Open the original listing to review the full details and apply on the employer's website.</p>
            </div>
            <span className="subtle-label">Saved locally</span>
          </div>

          {jobs.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon"><Icon name="search" /></span>
              <h3>Your next opportunity starts here</h3>
              <p>Search by role and location to populate this list with relevant public job adverts.</p>
            </div>
          ) : (
            <div className="job-grid">
              {jobs.map((job) => {
                const sourceUrl = safeExternalUrl(job.apply_url || job.source_url);
                return (
                  <article className="job-card" key={job.id}>
                    <div className="job-card-top">
                      <span className="company-avatar">{(job.company || "?").trim().charAt(0).toUpperCase()}</span>
                      {job.published_at && <span className="job-date">{job.published_at}</span>}
                    </div>
                    <h3>{job.title}</h3>
                    <p className="job-company">{job.company}</p>
                    <p className="job-location"><span>⌖</span>{job.location}</p>
                    {job.description && <p className="job-description">{job.description}</p>}
                    <div className="job-card-bottom">
                      <span className="source-label">{job.source === "jobtech_links" ? "JobAd Links" : job.source}</span>
                      {sourceUrl ? <a className="text-link" href={sourceUrl} target="_blank" rel="noopener noreferrer">View original <Icon name="arrow" /></a> : <span className="helper-text">No source URL provided</span>}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="panel match-panel">
          <div className="section-title-row match-heading-row">
            <div>
              <p className="eyebrow">PERSONALIZED INSIGHT</p>
              <h2><span className="title-icon"><Icon name="sparkles" /></span> Match jobs to your CV</h2>
              <p className="panel-description">CareerMate extracts requirements from each advert, checks them against evidence in your profile, and calculates a weighted coverage score.</p>
            </div>
            <div className="match-controls">
              <label className="compact-field"><span>Analyze</span><select value={matchLimit} onChange={(event) => setMatchLimit(Number(event.target.value))} disabled={matchLoading}>
                <option value={1}>1 job</option><option value={3}>3 jobs</option><option value={5}>5 jobs</option><option value={10}>10 jobs</option><option value={20}>20 jobs</option>
              </select></label>
              <button className="button button-primary" onClick={handleMatchJobs} disabled={!canAnalyzeMatches} type="button">
                {matchLoading ? <><span className="spinner spinner-light" /> Analyzing…</> : "Analyze matches"}
              </button>
            </div>
          </div>
          {!profile && <p className="inline-hint">Analyze your CV first to create a candidate profile. Review it before using it for matching.</p>}
          {profile && !profileSaved && <p className="inline-hint">Your profile has unsaved edits. CareerMate will save the current version before matching.</p>}
          {matchLoading && <div className="progress-notice"><span className="spinner" /><div><strong>Local model is comparing requirements</strong><p>First-time analysis may take several minutes. Results are cached for repeat runs.</p></div></div>}

          {!matchLoading && matches.length === 0 && (
            <div className="match-empty"><span className="match-empty-icon"><Icon name="sparkles" /></span><div><strong>Understand why a role may fit</strong><p>After searching for jobs and reviewing your CV profile, run matching to see evidence-backed strengths and gaps.</p></div></div>
          )}

          {matches.length > 0 && <div className="match-results">
            {matches.map((job) => (
              <article className="match-card" key={job.id}>
                <div className="match-card-header">
                  <div><h3>{job.title}</h3><p>{job.company} · {job.location}</p></div>
                  <div className={`score-badge ${job.match_score === null ? "score-unavailable" : job.match_score >= 75 ? "score-strong" : job.match_score >= 50 ? "score-medium" : "score-low"}`}>
                    <strong>{job.match_score === null ? "—" : job.match_score}</strong><span>{job.match_score === null ? "No score" : "/ 100"}</span>
                  </div>
                </div>
                {job.match_score !== null && <div className="score-track"><span style={{ width: `${Math.max(0, Math.min(100, job.match_score))}%` }} /></div>}
                <div className="match-meta"><span>Confidence: {job.match_confidence}</span><span>Method: evidence-weighted AI</span></div>
                <p className="match-explanation">{job.match_explanation}</p>
                <div className="requirement-grid">
                  <RequirementList title="Supported" kind="supported" items={(job.requirements ?? []).filter((item) => item.status === "supported")} />
                  <RequirementList title="Partially supported" kind="partial" items={(job.requirements ?? []).filter((item) => item.status === "partially_supported")} />
                  <RequirementList title="Not evidenced in profile" kind="missing" items={(job.requirements ?? []).filter((item) => item.status === "not_evidenced")} />
                </div>
                <p className="score-note">{job.score_note}</p>
                {safeExternalUrl(job.apply_url || job.source_url) && <a className="text-link" href={safeExternalUrl(job.apply_url || job.source_url) ?? undefined} target="_blank" rel="noopener noreferrer">Review full job advert <Icon name="arrow" /></a>}
              </article>
            ))}
          </div>}
        </section>

        {profile && (
          <section className="panel profile-panel">
            <div className="section-title-row">
              <div><p className="eyebrow">SOURCE OF TRUTH</p><h2>Review your candidate profile</h2><p className="panel-description">AI extraction can make mistakes. Correct the facts here before generating application content.</p></div>
              <span className={`save-state ${profileSaved ? "saved" : "unsaved"}`}>{profileSaved ? "✓ Saved locally" : "● Unsaved changes"}</span>
            </div>

            <details open>
              <summary>Personal details</summary>
              <div className="form-grid profile-form-grid">
                <Field label="Full name" value={profile.personal?.name ?? ""} onChange={(value) => updatePersonal("name", value)} />
                <Field label="Email" type="email" value={profile.personal?.email ?? ""} onChange={(value) => updatePersonal("email", value)} />
                <Field label="Phone" value={profile.personal?.phone ?? ""} onChange={(value) => updatePersonal("phone", value)} />
                <Field label="Location" value={profile.personal?.location ?? ""} onChange={(value) => updatePersonal("location", value)} />
                <Field label="LinkedIn URL" value={profile.personal?.linkedin ?? ""} onChange={(value) => updatePersonal("linkedin", value)} />
                <Field label="GitHub URL" value={profile.personal?.github ?? ""} onChange={(value) => updatePersonal("github", value)} />
                <Field label="Portfolio URL" value={profile.personal?.portfolio ?? ""} onChange={(value) => updatePersonal("portfolio", value)} />
              </div>
            </details>

            <details open>
              <summary>Professional summary and skills</summary>
              <TextAreaField label="Professional summary" value={profile.summary} onChange={updateSummary} rows={5} />
              <div className="form-grid profile-form-grid">
                <TextAreaField label="Skills — one per line" value={profile.skills.join("\n")} onChange={(value) => updateList("skills", value)} />
                <TextAreaField label="Languages — one per line" value={profile.languages.join("\n")} onChange={(value) => updateList("languages", value)} />
                <TextAreaField label="Certifications — one per line" value={profile.certifications.join("\n")} onChange={(value) => updateList("certifications", value)} />
              </div>
            </details>

            <details open>
              <summary>Professional experience <span className="summary-count">{profile.experience.length}</span></summary>
              <div className="record-list">
                {profile.experience.map((item, index) => <div className="editable-record" key={`experience-${index}`}>
                  <div className="editable-record-title"><strong>Experience {index + 1}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeExperience(index)}>Remove</button></div>
                  <div className="form-grid profile-form-grid">
                    <Field label="Job title" value={item.job_title} onChange={(value) => updateExperience(index, "job_title", value)} />
                    <Field label="Company" value={item.company} onChange={(value) => updateExperience(index, "company", value)} />
                    <Field label="Location" value={item.location} onChange={(value) => updateExperience(index, "location", value)} />
                    <Field label="Start date" value={item.start_date} onChange={(value) => updateExperience(index, "start_date", value)} />
                    <Field label="End date" value={item.end_date} onChange={(value) => updateExperience(index, "end_date", value)} />
                  </div>
                  <TextAreaField label="Responsibilities and achievements — one per line" value={item.description.join("\n")} onChange={(value) => updateExperienceDescription(index, value)} />
                </div>)}
                {profile.experience.length === 0 && <p className="helper-text">No experience entries have been extracted.</p>}
              </div>
              <button className="button button-secondary" type="button" onClick={addExperience}>+ Add experience</button>
            </details>

            <details open>
              <summary>Education <span className="summary-count">{profile.education.length}</span></summary>
              <div className="record-list">
                {profile.education.map((item, index) => <div className="editable-record" key={`education-${index}`}>
                  <div className="editable-record-title"><strong>Education {index + 1}</strong><button className="button button-quiet-danger" type="button" onClick={() => removeEducation(index)}>Remove</button></div>
                  <div className="form-grid profile-form-grid">
                    <Field label="Degree" value={item.degree} onChange={(value) => updateEducation(index, "degree", value)} />
                    <Field label="Institution" value={item.institution} onChange={(value) => updateEducation(index, "institution", value)} />
                    <Field label="Location" value={item.location} onChange={(value) => updateEducation(index, "location", value)} />
                    <Field label="Start date" value={item.start_date} onChange={(value) => updateEducation(index, "start_date", value)} />
                    <Field label="End date" value={item.end_date} onChange={(value) => updateEducation(index, "end_date", value)} />
                  </div>
                </div>)}
                {profile.education.length === 0 && <p className="helper-text">No education entries have been extracted.</p>}
              </div>
              <button className="button button-secondary" type="button" onClick={addEducation}>+ Add education</button>
            </details>

            <div className="profile-save-row">
              <p className="helper-text">Stored in <code>data/cv/profile.json</code> on this computer.</p>
              <button className="button button-primary" type="button" onClick={handleSaveProfile} disabled={saving || cvLoading || matchLoading}>
                {saving ? <><span className="spinner spinner-light" /> Saving…</> : "Save reviewed profile"}
              </button>
            </div>
          </section>
        )}

        <footer className="footer">
          <div className="footer-brand"><span className="brand-mark small-mark">C</span><strong>CareerMate</strong></div>
          <p>Local-first by design. Review every AI-generated claim before using it in an application.</p>
          <span>Open-source personal project</span>
        </footer>
      </div>
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
