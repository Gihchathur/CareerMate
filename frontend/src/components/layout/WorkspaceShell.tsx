import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Icon, type IconName } from "../ui/Icon";

export type WorkspaceView = "overview" | "discover" | "inbox" | "platforms" | "matches" | "applications" | "followups" | "profile" | "documents" | "ai" | "data" | "settings" | "analytics" | "automation";
export type PageMeta = { title: string; eyebrow: string; description: string };

type Props = {
  activeView: WorkspaceView;
  meta: PageMeta;
  activity: string;
  status: string;
  avatar: string;
  candidateName: string;
  profileProgress: number;
  hostedAi: boolean;
  matchCount: number;
  jobCount: number;
  applicationCount: number;
  inboxCount?: number;
  followupCount?: number;
  onNavigate: (view: WorkspaceView) => void;
  onGoHome: () => void;
  children: ReactNode;
};

type NavLink = { id: WorkspaceView; label: string; icon: IconName; hint: string };
type NavGroup = { label: string; links: NavLink[] };


const PAGE_ICONS: Record<WorkspaceView, IconName> = {
  overview: "house",
  discover: "search",
  inbox: "inbox",
  platforms: "radar",
  matches: "target",
  applications: "kanban",
  followups: "mail",
  profile: "file",
  documents: "files",
  ai: "sparkles",
  data: "database",
  settings: "sliders",
  analytics: "chart",
  automation: "calendar-clock",
};

const NAV_GROUPS: NavGroup[] = [
  { label: "WORKSPACE", links: [{ id: "overview", label: "Today", icon: "house", hint: "Overview of your priorities, next actions and recent activity" }] },
  { label: "DISCOVER", links: [
    { id: "discover", label: "Explore", icon: "search", hint: "Find opportunities across connected company portals" },
    { id: "inbox", label: "Inbox", icon: "inbox", hint: "Triage newly discovered jobs" },
    { id: "matches", label: "Match intelligence", icon: "target", hint: "Understand fit and evidence gaps" },
    { id: "automation", label: "Scheduled scans", icon: "calendar-clock", hint: "Manage recurring job searches" },
  ] },
  { label: "MANAGE", links: [
    { id: "applications", label: "Pipeline", icon: "kanban", hint: "Move applications through each stage" },
    { id: "followups", label: "Follow-ups", icon: "mail", hint: "Keep recruiter conversations moving" },
    { id: "platforms", label: "Portals", icon: "radar", hint: "Monitor employer career pages" },
  ] },
  { label: "INSIGHTS", links: [{ id: "analytics", label: "Analytics", icon: "chart", hint: "Measure your search and conversion" }] },
  { label: "YOUR CAREER", links: [
    { id: "profile", label: "CV", icon: "file", hint: "Manage your candidate profile and evidence" },
    { id: "documents", label: "Documents", icon: "files", hint: "Find tailored CVs and application drafts" },
  ] },
  { label: "PREFERENCES", links: [{ id: "settings", label: "Config", icon: "sliders", hint: "Configure AI, privacy and workspace data" }] },
];

export function WorkspaceShell(props: Props) {
  const {
    activeView, meta, activity, status, avatar, candidateName, profileProgress, hostedAi,
    matchCount, jobCount, applicationCount,
    inboxCount = 0, followupCount = 0,
    onNavigate, onGoHome, children,
  } = props;
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [activeCommandIndex, setActiveCommandIndex] = useState(0);
  // Desktop navigation is a fixed, permanently expanded sidebar. Pointer
  // position must never change the workspace geometry or navigation width.
  const railExpanded = true;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const commandInput = useRef<HTMLInputElement>(null);
  const badgeFor = (id: WorkspaceView) => id === "discover" ? jobCount : id === "inbox" ? inboxCount : id === "matches" ? matchCount : id === "applications" ? applicationCount : id === "followups" ? followupCount : undefined;
  const commands = useMemo(
    () => NAV_GROUPS.flatMap((group) => group.links).filter((link) => `${link.label} ${link.hint}`.toLowerCase().includes(commandQuery.trim().toLowerCase())),
    [commandQuery],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((value) => !value);
        setCommandQuery("");
        setMobileNavOpen(false);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setMobileNavOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (commandOpen) {
      setActiveCommandIndex(0);
      commandInput.current?.focus();
    }
  }, [commandOpen]);

  useEffect(() => {
    setActiveCommandIndex((index) => Math.min(index, Math.max(0, commands.length - 1)));
  }, [commands.length]);

  const navigate = (view: WorkspaceView) => {
    onNavigate(view);
    setCommandOpen(false);
    setMobileNavOpen(false);
  };

  const renderFullNavigation = (className = "cm-mobile-nav-groups") => (
    <div className={className}>
      {NAV_GROUPS.map((group) => (
        <div className="cm-nav-popover-group" key={group.label}>
          <span className="cm-nav-popover-label">{group.label}</span>
          {group.links.map((link) => {
            const active = activeView === link.id || (link.id === "settings" && ["ai", "data"].includes(activeView));
            const badge = badgeFor(link.id);
            return (
              <button
                key={link.id}
                type="button"
                className={`cm-nav-popover-item ${active ? "is-active" : ""}`}
                onClick={() => navigate(link.id)}
                aria-current={active ? "page" : undefined}
              >
                <span className="cm-nav-popover-icon"><Icon name={link.icon} /></span>
                <span className="cm-nav-popover-copy"><strong>{link.label}</strong><small>{link.hint}</small></span>
                {typeof badge === "number" && badge > 0 && <span className="cm-nav-popover-count">{badge > 99 ? "99+" : badge}</span>}
                {active && <span className="cm-nav-popover-current"><Icon name="check" /></span>}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );


  return (
    <div className="cm-app-shell">
      <header className="cm-topbar">
        <div className="cm-topbar-context"><span className="cm-live-dot" /> <span>Your career workspace</span><span className="cm-context-divider">/</span><strong>{meta.title.toLowerCase()}</strong></div>
        <div className="cm-topbar-actions">
          <button className="cm-command-trigger" type="button" onClick={() => { setCommandOpen(true); setCommandQuery(""); }}><Icon name="search" /><span>Jump to anything</span><kbd>⌘ K</kbd></button>
          <span className="cm-privacy-indicator" title={hostedAi ? "Hosted AI is enabled" : "Local AI workspace"}><Icon name="shield" /><span>{hostedAi ? "Cloud AI" : "Local first"}</span></span>
          <button className="cm-notification-button" type="button" onClick={() => navigate("automation")} aria-label="Open job alerts and scheduled scans" title="Job alerts and scheduled scans"><Icon name="bell" /><i /></button>
          <button className="cm-avatar" type="button" onClick={() => navigate("profile")} aria-label="Open candidate profile">{avatar}</button>
        </div>
      </header>

      <div className={`cm-workspace ${railExpanded ? "is-nav-expanded" : ""}`}>
        <aside
          className={`cm-icon-rail ${railExpanded ? "is-expanded" : ""}`}
          aria-label="Primary navigation"
          data-state={railExpanded ? "expanded" : "compact"}
        >
          <div className="cm-rail-surface">
            <button className="cm-rail-brand" type="button" onClick={onGoHome} aria-label="CareerMate home">
              <img className="cm-brand-symbol-image cm-rail-brand-symbol" src="/careermate-symbol.svg" alt="" />
              <span className="cm-rail-brand-copy"><strong>CareerMate</strong><small>PERSONAL OS</small></span>
            </button>
            <nav className="cm-rail-navigation" aria-label="Workspace sections">
              {NAV_GROUPS.map((group, groupIndex) => (
                <div className="cm-rail-group" key={group.label}>
                  <span className="cm-rail-group-label">{group.label}</span>
                  {group.links.map((link) => {
                    const active = activeView === link.id || (link.id === "settings" && ["ai", "data"].includes(activeView));
                    const badge = badgeFor(link.id);
                    return (
                      <button
                        key={link.id}
                        type="button"
                        className={`cm-rail-item ${active ? "is-active" : ""}`}
                        onClick={() => navigate(link.id)}
                        aria-label={link.label}
                        aria-current={active ? "page" : undefined}
                        data-tooltip={link.label}
                        title={link.label}
                      >
                        <span className="cm-rail-icon-wrap"><Icon name={link.icon} /></span>
                        <span className="cm-rail-item-label">{link.label}</span>
                        {typeof badge === "number" && badge > 0 && <span className="cm-rail-item-badge">{badge > 99 ? "99+" : badge}</span>}
                        <span className="cm-rail-active-indicator" />
                      </button>
                    );
                  })}
                  {groupIndex < NAV_GROUPS.length - 1 && <span className="cm-rail-separator" />}
                </div>
              ))}
            </nav>
            <div className="cm-rail-bottom">
              <button className="cm-rail-profile" type="button" onClick={() => navigate("profile")} aria-label={`Candidate profile, ${profileProgress}% ready`} title={`Profile readiness ${profileProgress}%`}>
                <span className="cm-rail-profile-ring" style={{ "--progress": `${profileProgress}%` } as CSSProperties}>{avatar}</span>
                <span className="cm-rail-profile-copy"><strong>{candidateName || "Your profile"}</strong><small>Profile {profileProgress}% complete</small><i className="cm-rail-profile-track"><b style={{ width: `${profileProgress}%` }} /></i></span>
                <span className="cm-rail-profile-arrow"><Icon name="arrow-up-right" /></span>
              </button>
            </div>
          </div>
        </aside>

        <main className="cm-main" data-view={activeView}>
          <div className="cm-page-header">
            <span className="cm-page-icon" aria-hidden="true"><Icon name={PAGE_ICONS[activeView]} /></span>
            <div className="cm-page-heading-copy"><span className="cm-kicker">{meta.eyebrow}</span><h1>{meta.title}</h1><p>{meta.description}</p></div>
            <div className="cm-page-header-actions">{activity ? <span className="cm-activity-pill"><i />{activity}</span> : <span className="cm-status-pill"><i />{status}</span>}{activeView !== "discover" && <button type="button" className="cm-button cm-button-primary" onClick={() => navigate("discover")}><Icon name="search" /> Discover jobs <span>↗</span></button>}</div>
          </div>
          <div className="cm-content-frame" key={activeView}>{children}</div>
          <footer className="cm-footer"><span><b>career<span>mate</span>.</b> Your personal career operating system.</span><span><i /> Local-first · Human-approved applications</span></footer>
        </main>
      </div>

      <nav className="cm-mobile-bottom-nav" aria-label="Quick navigation">
        {(["overview", "discover", "inbox", "applications"] as WorkspaceView[]).map((view) => {
          const labels: Record<string, string> = { overview: "Today", discover: "Explore", inbox: "Inbox", applications: "Pipeline" };
          const icons: Record<string, IconName> = { overview: "grid", discover: "compass", inbox: "inbox", applications: "kanban" };
          return <button type="button" key={view} className={activeView === view ? "is-active" : ""} onClick={() => navigate(view)}><Icon name={icons[view]} /><span>{labels[view]}</span></button>;
        })}
        <button type="button" onClick={() => setMobileNavOpen(true)}><Icon name="layers" /><span>More</span></button>
      </nav>

      {mobileNavOpen && <div className="cm-mobile-nav-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setMobileNavOpen(false); }}>
        <section className="cm-mobile-nav-dialog" role="dialog" aria-modal="true" aria-label="CareerMate navigation">
          <header className="cm-mobile-nav-header"><div><span className="cm-nav-popover-eyebrow">YOUR WORKSPACE</span><strong>All sections</strong></div><button type="button" className="cm-nav-popover-close" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation"><Icon name="plus" /></button></header>
          {renderFullNavigation()}
          <footer className="cm-mobile-nav-footer"><Icon name="shield" /> Your workspace is {hostedAi ? "connected to hosted AI" : "local-first"}.</footer>
        </section>
      </div>}

      {commandOpen && <div className="cm-command-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setCommandOpen(false); }}>
        <section className="cm-command-dialog" role="dialog" aria-modal="true" aria-label="Quick navigation">
          <div className="cm-command-input-wrap"><Icon name="search" /><input
            ref={commandInput}
            value={commandQuery}
            onChange={(event) => { setCommandQuery(event.target.value); setActiveCommandIndex(0); }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") { event.preventDefault(); setActiveCommandIndex((index) => commands.length ? (index + 1) % commands.length : 0); }
              if (event.key === "ArrowUp") { event.preventDefault(); setActiveCommandIndex((index) => commands.length ? (index - 1 + commands.length) % commands.length : 0); }
              if (event.key === "Enter" && commands[activeCommandIndex]) { event.preventDefault(); navigate(commands[activeCommandIndex].id); }
            }}
            placeholder="Search pages and actions…"
            aria-label="Search navigation"
            aria-controls="cm-command-results-list"
            aria-activedescendant={commands[activeCommandIndex] ? `cm-command-${commands[activeCommandIndex].id}` : undefined}
          /><kbd>ESC</kbd></div>
          <div className="cm-command-results" id="cm-command-results-list"><span className="cm-nav-group-label">NAVIGATION</span>{commands.length ? commands.map((command, index) => <button id={`cm-command-${command.id}`} key={command.id} type="button" className={activeCommandIndex === index ? "is-selected" : ""} aria-selected={activeCommandIndex === index} onMouseEnter={() => setActiveCommandIndex(index)} onClick={() => navigate(command.id)}><Icon name={command.icon} /><span><strong>{command.label}</strong><small>{command.hint}</small></span><kbd>↵</kbd></button>) : <p>No pages match “{commandQuery}”.</p>}</div>
          <div className="cm-command-foot"><span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span><span><kbd>↵</kbd> Open page</span><span><kbd>ESC</kbd> Close</span></div>
        </section>
      </div>}
    </div>
  );
}
