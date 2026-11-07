import { useMemo, useState } from "react";
import { Icon } from "../ui/Icon";
import { SourceMark } from "../ui/SourceMark";
import type { JobInboxItem, JobResult, JobTriageStage } from "../../types";

const STAGES: { id: "all" | JobTriageStage; label: string }[] = [
  { id: "all", label: "All jobs" }, { id: "new", label: "New" }, { id: "reviewing", label: "Reviewing" }, { id: "shortlisted", label: "Shortlisted" }, { id: "skipped", label: "Skipped" },
];
const dateText = (value: string) => {
  if (!value) return "Date unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
};

type Props = {
  items: JobInboxItem[];
  counts: Record<JobTriageStage, number>;
  loading?: boolean;
  onReview: (job: JobResult) => void;
  onTriage: (jobId: string, stage: JobTriageStage) => Promise<void>;
  onPromote: (jobId: string) => Promise<void>;
  onExplore: () => void;
};

export function JobInbox({ items, counts, loading = false, onReview, onTriage, onPromote, onExplore }: Props) {
  const [stage, setStage] = useState<"all" | JobTriageStage>("all");
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const filtered = useMemo(() => items.filter(({ job, triage }) => {
    if (stage !== "all" && triage.stage !== stage) return false;
    const text = `${job.title} ${job.company} ${job.location} ${job.source}`.toLowerCase();
    return text.includes(query.trim().toLowerCase());
  }), [items, query, stage]);
  const countFor = (id: "all" | JobTriageStage) => id === "all" ? items.length : counts[id];
  const run = async (jobId: string, action: () => Promise<void>) => {
    setBusyId(jobId);
    try { await action(); } finally { setBusyId(null); }
  };

  return <div className="workflow-page inbox-page">
    <section className="workflow-page-intro"><div><p className="workflow-eyebrow">DISCOVERY TRIAGE</p><h2>Your job inbox</h2><p>Every discovered opportunity lands here first. Review it, shortlist it, or skip it before it enters your application pipeline.</p></div><button className="workflow-primary-action" type="button" onClick={onExplore}><Icon name="search" /> Explore more jobs</button></section>
    <section className="workflow-inbox-summary">
      <div><strong>{items.length}</strong><span>Untracked opportunities</span></div>
      <div><strong>{counts.new}</strong><span>Awaiting review</span></div>
      <div><strong>{counts.shortlisted}</strong><span>Shortlisted</span></div>
      <div><strong>{counts.skipped}</strong><span>Skipped</span></div>
    </section>
    <section className="workflow-panel workflow-inbox-panel">
      <div className="workflow-inbox-toolbar"><div className="workflow-tabs" role="tablist" aria-label="Filter inbox jobs">{STAGES.map((item) => <button key={item.id} type="button" role="tab" aria-selected={stage === item.id} className={stage === item.id ? "is-active" : ""} onClick={() => setStage(item.id)}>{item.label}<span>{countFor(item.id)}</span></button>)}</div><label className="workflow-search-field"><Icon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, company or source" aria-label="Search inbox" /></label></div>
      {loading ? <div className="workflow-state"><span className="workflow-spinner"/><strong>Loading your job inbox…</strong></div> : filtered.length ? <div className="workflow-job-list">{filtered.map(({ job, triage }) => <article className="workflow-job-card" key={job.id}>
        <div className="workflow-job-card-main"><div className="workflow-job-source"><SourceMark source={job.source} sourceUrl={job.source_url} /><span>{job.source}</span><span className={`workflow-stage stage-${triage.stage}`}>{STAGES.find((item) => item.id === triage.stage)?.label ?? triage.stage}</span></div><button type="button" className="workflow-job-title" onClick={() => onReview(job)}>{job.title}</button><p className="workflow-job-meta">{job.company || "Company not listed"} <span>·</span> {job.location || "Location not listed"}</p><p className="workflow-job-description">{job.description?.trim() || "No description was provided by the source. Open the listing to review the original requirements."}</p><div className="workflow-job-facts"><span><Icon name="calendar"/>{dateText(job.published_at)}</span><span><Icon name="briefcase"/>{job.work_mode === "remote" ? "Remote" : job.work_mode === "hybrid" ? "Hybrid" : job.work_mode === "on_site" ? "On-site" : "Work mode not specified"}</span></div></div>
        <div className="workflow-job-actions"><button className="workflow-button-quiet" type="button" onClick={() => onReview(job)}><Icon name="eye"/> Review details</button><button className="workflow-button-quiet" type="button" disabled={busyId === job.id || triage.stage === "shortlisted"} onClick={() => void run(job.id, () => onTriage(job.id, "shortlisted"))}><Icon name="bookmark"/> Shortlist</button><button className="workflow-button-primary" type="button" disabled={busyId === job.id} onClick={() => void run(job.id, () => onPromote(job.id))}>{busyId === job.id ? "Adding…" : "Add to pipeline"}<Icon name="arrow"/></button>{triage.stage !== "skipped" && <button className="workflow-button-danger" type="button" disabled={busyId === job.id} onClick={() => void run(job.id, () => onTriage(job.id, "skipped"))}>Skip</button>}</div>
      </article>)}</div> : <div className="workflow-empty-state"><span><Icon name="inbox"/></span><h3>{query || stage !== "all" ? "No jobs match this view" : "Your inbox is clear"}</h3><p>{query || stage !== "all" ? "Adjust the filters to see more opportunities." : "Search your connected company portals in Explore to bring new opportunities into CareerMate. Jobs appear here before you decide whether to track them."}</p><button className="workflow-primary-action" type="button" onClick={onExplore}><Icon name="search"/> Explore opportunities <Icon name="arrow"/></button></div>}
    </section>
  </div>;
}
