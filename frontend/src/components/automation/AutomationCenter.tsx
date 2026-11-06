import type { CSSProperties } from "react";
import type { JobSourceId, JobSourceStatus } from "../../types";
import { Icon } from "../ui/Icon";
import { SourceMark } from "../ui/SourceMark";

type SavedSearch = { id: string; name: string; roles: string[]; country: string; city: string; frequency: "manual" | "daily" | "weekly"; created_at: string };
type JobAlert = { id: string; title: string; company: string; location: string; search_name: string; read: boolean; found_at: string; url: string };
type Props = {
  sources: Record<JobSourceId, JobSourceStatus>;
  searches: SavedSearch[];
  alerts: JobAlert[];
  checkingId: string | null;
  onCheckSearch: (id: string) => void;
  onOpenSources: () => void;
  onOpenDiscover: () => void;
};

const SOURCE_LABELS: Record<JobSourceId, string> = {
  jobtech_links: "JobTech / Platsbanken", remoteok: "Remote OK", arbeitnow: "Arbeitnow", greenhouse: "Greenhouse",
  lever: "Lever", teamtailor: "Teamtailor", ashby: "Ashby", smartrecruiters: "SmartRecruiters",
  workable: "Workable", recruitee: "Recruitee", breezy: "Breezy HR", personio: "Personio", workday: "Workday",
};

export function AutomationCenter({ sources, searches, alerts, checkingId, onCheckSearch, onOpenSources, onOpenDiscover }: Props) {
  const sourceEntries = Object.entries(sources) as [JobSourceId, JobSourceStatus][];
  const readySources = sourceEntries.filter(([, status]) => status.configured && (!status.requires_api_key || status.credentials_ready !== false));
  const configuredSources = sourceEntries.filter(([, status]) => status.configured);
  const unreadAlerts = alerts.filter((alert) => !alert.read).length;
  return (
    <div className="cm-page-stack cm-automation-page">
      <section className="cm-automation-hero">
        <div className="cm-automation-orb"><span><Icon name="bolt" /></span><i /><i /><i /></div>
        <div className="cm-automation-copy"><span className="cm-kicker">WORKFLOW CONTROL</span><h2>Let the repetitive work run itself.</h2><p>Monitor connected job sources, saved-search checks and new-opportunity alerts. Keep consequential application decisions under your control.</p><div className="cm-hero-actions"><button type="button" className="cm-button cm-button-primary" onClick={onOpenDiscover}>Run a discovery search <span>↗</span></button><button type="button" className="cm-button cm-button-glass" onClick={onOpenSources}>Manage integrations</button></div></div>
        <div className="cm-automation-status"><span className="cm-live-dot" /> LOCAL WORKSPACE <strong>ACTIVE</strong><small>No background cloud agent is assumed to be running.</small></div>
      </section>
      <section className="cm-automation-stats">
        <article><span>Integrated source connectors</span><strong>{configuredSources.length}</strong><small>of {sourceEntries.length} supported connector types configured</small></article>
        <article><span>Ready sources</span><strong>{readySources.length}</strong><small>Available for the current configuration</small></article>
        <article><span>Saved search workflows</span><strong>{searches.length}</strong><small>Manual, daily or weekly check preferences</small></article>
        <article><span>Unread opportunity alerts</span><strong>{unreadAlerts}</strong><small>{alerts.length} alerts recorded in total</small></article>
      </section>
      <section className="cm-automation-layout">
        <div className="cm-card cm-integrations-card">
          <div className="cm-section-heading"><div><span className="cm-kicker">SOURCE CONNECTIVITY</span><h3>Integration health</h3><p>Configured connectors and employer board sources.</p></div><button className="cm-inline-link" type="button" onClick={onOpenSources}>Configure all ↗</button></div>
          <div className="cm-connector-list">{sourceEntries.map(([id, source], index) => <div className="cm-connector-row" key={id} style={{ "--row-delay": `${index * 35}ms` } as CSSProperties & Record<`--${string}`, string>}><SourceMark source={id} /><span className="cm-connector-name"><strong>{SOURCE_LABELS[id]}</strong><small>{source.employers !== null ? `${source.employers} employer boards` : source.requires_api_key ? "Employer configuration / credentials" : "Public feed or source adapter"}</small></span><span className={`cm-connector-state ${source.configured ? "is-ready" : "is-idle"}`}><i />{source.configured ? "Configured" : "Not configured"}</span></div>)}</div>
        </div>
        <div className="cm-card cm-search-workflows-card">
          <div className="cm-section-heading"><div><span className="cm-kicker">RECURRING DISCOVERY</span><h3>Saved search workflows</h3><p>Run a check when you want to refresh a search.</p></div><span className="cm-mini-icon"><Icon name="calendar" /></span></div>
          {searches.length ? <div className="cm-saved-workflow-list">{searches.map((search) => <article className="cm-saved-workflow" key={search.id}><div><strong>{search.name}</strong><small>{search.roles.join(", ")} · {[search.city, search.country].filter(Boolean).join(", ")}</small><span className={`cm-frequency cm-frequency-${search.frequency}`}>{search.frequency}</span></div><button type="button" className="cm-button cm-button-secondary" disabled={checkingId === search.id} onClick={() => onCheckSearch(search.id)}>{checkingId === search.id ? "Checking…" : "Check now ↗"}</button></article>)}</div> : <div className="cm-empty-compact"><span><Icon name="search" /></span><strong>No saved searches yet</strong><p>Create a search in Discover and save it here for repeatable checks.</p><button type="button" className="cm-inline-link" onClick={onOpenDiscover}>Create first search →</button></div>}
          <div className="cm-automation-hint"><span><Icon name="info" /></span><p>Daily and weekly are saved alert preferences. The local scheduler needs the backend running, and this screen does not claim a run occurred until the API confirms it.</p></div>
        </div>
      </section>
      <section className="cm-card cm-alerts-card">
        <div className="cm-section-heading"><div><span className="cm-kicker">DISCOVERY ACTIVITY</span><h3>Recent opportunity alerts</h3><p>New listings surfaced by your saved-search checks.</p></div><span className="cm-alert-count">{alerts.length} total</span></div>
        {alerts.length ? <div className="cm-alert-list">{alerts.slice(0, 8).map((alert) => <article key={alert.id} className="cm-alert-row"><span className={`cm-alert-dot ${alert.read ? "is-read" : ""}`} /><div><strong>{alert.title}</strong><small>{alert.company} · {alert.location} · {alert.search_name}</small></div>{alert.url && <a href={alert.url} target="_blank" rel="noreferrer">Open role ↗</a>}</article>)}</div> : <div className="cm-empty-compact"><span><Icon name="bell" /></span><strong>Nothing new has been reported</strong><p>Run a saved search check to look for newly discovered opportunities.</p></div>}
      </section>
    </div>
  );
}
