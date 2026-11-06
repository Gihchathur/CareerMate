import type { ReactNode } from "react";
import { Icon, type IconName } from "../ui/Icon";

export type WorkspaceView = "overview" | "discover" | "platforms" | "matches" | "applications" | "profile" | "ai" | "data" | "settings";

export type PageMeta = { title: string; eyebrow: string; description: string };

type Props = {
  activeView: WorkspaceView;
  meta: PageMeta;
  activity: string;
  status: string;
  avatar: string;
  providerLabel: string;
  hostedAi: boolean;
  cvUploaded: boolean;
  profileSaved: boolean;
  matchCount: number;
  jobCount: number;
  applicationCount: number;
  onNavigate: (view: WorkspaceView) => void;
  onGoHome: () => void;
  children: ReactNode;
};

type NavLink = { id: WorkspaceView; label: string; icon: IconName; badge?: number | string; ready?: boolean };

export function WorkspaceShell(props: Props) {
  const {
    activeView, meta, activity, status, avatar, providerLabel, hostedAi,
    cvUploaded, profileSaved, matchCount, jobCount, applicationCount,
    onNavigate, onGoHome, children,
  } = props;

  const groups: { label: string; links: NavLink[] }[] = [
    { label: "Workspace", links: [{ id: "overview", label: "Overview", icon: "grid" }] },
    { label: "Career tools", links: [
      { id: "discover", label: "Find jobs", icon: "search", badge: jobCount || undefined },
      { id: "platforms", label: "Job sources", icon: "layers" },
      { id: "matches", label: "Match insights", icon: "sparkles", badge: matchCount || undefined },
      { id: "applications", label: "Applications", icon: "briefcase", badge: applicationCount || undefined },
    ] },
    { label: "Your profile", links: [{ id: "profile", label: "CV Studio", icon: "user", ready: profileSaved }] },
    { label: "Preferences", links: [{ id: "settings", label: "Settings", icon: "sliders" }] },
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="CareerMate home" onClick={(event) => { event.preventDefault(); onGoHome(); }}>
          <img className="brand-mark brand-mark-image" src="/careermate-mark.svg" alt="" />
          <span className="brand-wordmark">CareerMate<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-context"><span className="topbar-context-dot" />Your personal career workspace</div>
        <div className="topbar-right">
          <span className="privacy-chip"><span className="privacy-dot" />{hostedAi ? "Hosted AI enabled" : "Local AI workspace"}</span>
          <button className="topbar-avatar" type="button" onClick={() => onNavigate("profile")} aria-label="Open your profile">{avatar}</button>
        </div>
      </header>

      <div className="workspace-shell" id="workspace">
        <aside className="sidebar" aria-label="Main navigation">
          <div className="sidebar-brand-panel">
            <span className="sidebar-brand-orb"><Icon name="sparkles" /></span>
            <span><strong>CareerMate</strong><small>CAREER COMMAND CENTER</small></span>
          </div>
          <nav className="sidebar-navigation" aria-label="Primary">
            {groups.map((group) => (
              <div className="sidebar-group" key={group.label}>
                <span className="sidebar-label">{group.label}</span>
                <div className="sidebar-nav">
                  {group.links.map((link) => (
                    <button
                      key={link.id}
                      type="button"
                      className={`nav-item${activeView === link.id || (link.id === "settings" && ["ai", "data"].includes(activeView)) ? " active" : ""}`}
                      onClick={() => onNavigate(link.id)}
                      aria-current={activeView === link.id || (link.id === "settings" && ["ai", "data"].includes(activeView)) ? "page" : undefined}
                      title={link.label}
                    >
                      <span className="nav-icon-wrap"><Icon name={link.icon} /></span>
                      <span className="nav-item-label">{link.label}</span>
                      {link.badge !== undefined && <span className="nav-count">{link.badge}</span>}
                      {link.ready && <span className="nav-status nav-status-ready" aria-label="Profile saved" />}
                      <span className="nav-active-glow" aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </nav>

          <div className="sidebar-lower">
            <section className="workflow-card" aria-label="Setup progress">
              <div className="workflow-card-heading"><span>GETTING STARTED</span><span className="workflow-live-dot" /></div>
              <div className="workflow-progress-track"><span style={{ width: `${(Number(cvUploaded) + Number(profileSaved) + Number(matchCount > 0)) / 3 * 100}%` }} /></div>
              <div className="workflow-checks">
                <div className="workflow-check"><span className={`workflow-check-mark${cvUploaded ? " complete" : ""}`}>{cvUploaded ? "✓" : "1"}</span><span><strong>CV uploaded</strong><small>{cvUploaded ? "Text extracted locally" : "Add your CV to begin"}</small></span></div>
                <div className="workflow-check"><span className={`workflow-check-mark${profileSaved ? " complete" : ""}`}>{profileSaved ? "✓" : "2"}</span><span><strong>Profile reviewed</strong><small>{profileSaved ? "Ready for matching" : "Review extracted details"}</small></span></div>
                <div className="workflow-check"><span className={`workflow-check-mark${matchCount > 0 ? " complete" : ""}`}>{matchCount > 0 ? "✓" : "3"}</span><span><strong>Compare opportunities</strong><small>{matchCount ? `${matchCount} reports ready` : "Find roles and compare"}</small></span></div>
              </div>
            </section>
            <section className="privacy-card">
              <span className="privacy-card-icon"><Icon name="shield" /></span>
              <strong>Your data stays yours</strong>
              <p>CVs, profiles and applications stay in your local workspace. Hosted AI receives task content only when selected.</p>
              <span className="privacy-provider"><span className="privacy-dot" />{providerLabel}</span>
            </section>
            <div className="sidebar-footer"><span className="sidebar-footer-mark">C</span><span><strong>Personal edition</strong><small>Private by design</small></span><span className="version-dot" title="Local workspace" /></div>
          </div>
        </aside>

        <main className="workspace-main">
          <div className="workspace-heading">
            <div className="workspace-heading-copy">
              <p className="eyebrow">{meta.eyebrow}</p>
              <h1>{meta.title}</h1>
              <p className="workspace-description">{meta.description}</p>
            </div>
            <div className="workspace-heading-actions">
              {activity ? <span className="activity-pill"><span className="activity-spinner" />{activity}</span> : <span className="quiet-status"><span className="quiet-status-dot" />{status}</span>}
              {activeView !== "discover" && <button className="button button-primary header-cta" type="button" onClick={() => onNavigate("discover")}><Icon name="search" />Find jobs</button>}
            </div>
          </div>

          <div className="workspace-content">{children}</div>

          <footer className="workspace-footer">
            <div><img className="brand-mark brand-mark-image footer-mark" src="/careermate-mark.svg" alt="" /><strong>CareerMate</strong><span className="footer-separator">/</span><span>Local-first job search assistant</span></div>
            <span>Open source · Local files, configurable AI provider</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
