import { Icon } from "../ui/Icon";
import type { ApplicationRecord, JobInboxItem, WorkflowEvent } from "../../types";

const dateLabel = (value: string) => {
  if (!value) return "Date not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
};

type Props = {
  jobsCount: number;
  inbox: JobInboxItem[];
  counts: { new: number; reviewing: number; shortlisted: number; skipped: number };
  applications: ApplicationRecord[];
  profileReady: boolean;
  matchCount: number;
  events: WorkflowEvent[];
  onNavigate: (view: "discover" | "inbox" | "applications" | "followups" | "profile" | "matches") => void;
};

export function TodayDashboard({ jobsCount, inbox, counts, applications, profileReady, matchCount, events, onNavigate }: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueFollowUps = applications.filter((application) => {
    if (!application.follow_up_date || ["rejected", "withdrawn", "offer"].includes(application.status)) return false;
    const date = new Date(`${application.follow_up_date}T00:00:00`);
    return !Number.isNaN(date.getTime()) && date <= today;
  });
  const needsPreparation = applications.filter((application) => ["saved", "preparing"].includes(application.status));
  const tasks = [
    ...(!profileReady ? [{ title: "Review your candidate profile", detail: "Verify your CV facts before matching and drafting.", action: "Open CV", target: "profile" as const, tone: "violet" }] : []),
    ...(counts.new ? [{ title: `Review ${counts.new} new opportunities`, detail: "Newly discovered jobs are waiting in your inbox.", action: "Open inbox", target: "inbox" as const, tone: "blue" }] : []),
    ...(dueFollowUps.length ? [{ title: `${dueFollowUps.length} follow-up${dueFollowUps.length === 1 ? "" : "s"} due`, detail: "Keep conversations moving with a timely follow-up.", action: "View follow-ups", target: "followups" as const, tone: "amber" }] : []),
    ...(needsPreparation.length ? [{ title: `${needsPreparation.length} application${needsPreparation.length === 1 ? "" : "s"} to progress`, detail: "Prepare documents or update the next application stage.", action: "Open pipeline", target: "applications" as const, tone: "green" }] : []),
  ].slice(0, 4);

  return <div className="workflow-page today-page">
    <section className="workflow-welcome">
      <div>
        <p className="workflow-eyebrow">YOUR CAREER, IN MOTION</p>
        <h2>Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"}. Here's your focus.</h2>
        <p>Your daily workspace brings new opportunities, application actions and follow-ups together.</p>
      </div>
      <button className="workflow-primary-action" type="button" onClick={() => onNavigate("discover")}><Icon name="search" /> Explore opportunities <Icon name="arrow" /></button>
    </section>

    <section className="workflow-kpi-grid" aria-label="Career search overview">
      <article className="workflow-kpi"><span className="workflow-kpi-icon icon-blue"><Icon name="search" /></span><div><span>Jobs collected</span><strong>{jobsCount}</strong><small>Across your connected sources</small></div></article>
      <article className="workflow-kpi"><span className="workflow-kpi-icon icon-violet"><Icon name="inbox" /></span><div><span>Inbox to review</span><strong>{counts.new + counts.reviewing + counts.shortlisted}</strong><small>{counts.new} new · {counts.shortlisted} shortlisted</small></div></article>
      <article className="workflow-kpi"><span className="workflow-kpi-icon icon-green"><Icon name="briefcase" /></span><div><span>In your pipeline</span><strong>{applications.length}</strong><small>{applications.filter((item) => ["applied", "interview", "offer"].includes(item.status)).length} submitted or progressing</small></div></article>
      <article className="workflow-kpi"><span className="workflow-kpi-icon icon-amber"><Icon name="calendar" /></span><div><span>Follow-ups due</span><strong>{dueFollowUps.length}</strong><small>Based on your recorded dates</small></div></article>
    </section>

    <div className="workflow-dashboard-grid">
      <section className="workflow-panel workflow-focus-panel">
        <div className="workflow-panel-heading"><div><p className="workflow-eyebrow">NEXT BEST ACTIONS</p><h3>Keep your search moving</h3><p>CareerMate highlights work that needs your attention.</p></div><span className="workflow-heading-icon"><Icon name="target" /></span></div>
        {tasks.length ? <div className="workflow-task-list">{tasks.map((task) => <article className="workflow-task" key={task.target}><span className={`workflow-task-icon tone-${task.tone}`}><Icon name={task.tone === "amber" ? "calendar" : task.tone === "green" ? "briefcase" : task.tone === "blue" ? "inbox" : "user"} /></span><div className="workflow-task-copy"><strong>{task.title}</strong><p>{task.detail}</p></div><button type="button" onClick={() => onNavigate(task.target)}>{task.action}<Icon name="arrow" /></button></article>)}</div> : <div className="workflow-all-clear"><span><Icon name="check" /></span><div><strong>You're up to date</strong><p>No urgent actions are waiting. Explore new roles or review your progress.</p></div></div>}
        <div className="workflow-shortcuts"><button type="button" onClick={() => onNavigate("inbox")}><Icon name="inbox" /> Review inbox <span>{counts.new + counts.reviewing + counts.shortlisted}</span></button><button type="button" onClick={() => onNavigate("applications")}><Icon name="kanban" /> Open pipeline <Icon name="arrow" /></button></div>
      </section>

      <section className="workflow-panel workflow-inbox-preview">
        <div className="workflow-panel-heading"><div><p className="workflow-eyebrow">RECENT OPPORTUNITIES</p><h3>Fresh in your inbox</h3><p>Jobs discovered by your latest searches.</p></div><button className="workflow-text-action" type="button" onClick={() => onNavigate("inbox")}>View inbox <Icon name="arrow" /></button></div>
        {inbox.length ? <div className="workflow-mini-job-list">{inbox.slice(0, 4).map(({ job, triage }) => <article key={job.id} className="workflow-mini-job"><span className="workflow-mini-avatar">{(job.company || "?").trim().charAt(0).toUpperCase()}</span><div><strong>{job.title}</strong><p>{job.company || "Company not listed"} · {job.location || "Location not listed"}</p></div><span className={`workflow-stage stage-${triage.stage}`}>{triage.stage === "new" ? "New" : triage.stage === "reviewing" ? "Reviewing" : "Shortlisted"}</span></article>)}</div> : <div className="workflow-empty-inline"><Icon name="search" /><strong>No new jobs in your inbox</strong><p>Run an Explore search to collect opportunities here.</p><button className="workflow-text-action" type="button" onClick={() => onNavigate("discover")}>Start exploring <Icon name="arrow" /></button></div>}
      </section>
    </div>

    <section className="workflow-panel workflow-activity-panel">
      <div className="workflow-panel-heading"><div><p className="workflow-eyebrow">WORKSPACE HISTORY</p><h3>Recent activity</h3><p>A running record of searches and application decisions.</p></div><span className="workflow-heading-icon"><Icon name="activity" /></span></div>
      {events.length ? <div className="workflow-activity-list">{events.slice(0, 6).map((event) => <article key={event.id} className="workflow-activity-item"><span className="workflow-activity-dot" /><div><strong>{event.title}</strong><p>{event.detail}</p></div><time dateTime={event.created_at}>{dateLabel(event.created_at)}</time></article>)}</div> : <div className="workflow-empty-inline compact"><Icon name="activity" /><span>Activity appears here as you discover jobs and move applications through your pipeline.</span></div>}
    </section>
  </div>;
}
