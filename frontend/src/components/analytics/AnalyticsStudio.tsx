import type { CSSProperties } from "react";
import type { ApplicationRecord, JobMatchResult, JobResult } from "../../types";
import { Icon } from "../ui/Icon";

type Props = {
  jobs: JobResult[];
  matches: JobMatchResult[];
  applications: ApplicationRecord[];
  savedSearchCount: number;
  alertCount: number;
  onNavigate: (view: "discover" | "matches" | "applications") => void;
};

const formatPercent = (value: number) => `${Math.round(value)}%`;

function Metric({ label, value, detail, tone = "violet" }: { label: string; value: string | number; detail: string; tone?: string }) {
  return (
    <article className={`cm-metric cm-metric-${tone}`}>
      <div className="cm-metric-top"><span>{label}</span><span className="cm-metric-spark" aria-hidden="true" /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function BarList({ title, subtitle, items }: { title: string; subtitle: string; items: { label: string; value: number; color?: string }[] }) {
  const max = Math.max(1, ...items.map((item) => item.value));
  return (
    <section className="cm-card cm-chart-card">
      <div className="cm-section-heading"><div><span className="cm-kicker">PERFORMANCE</span><h3>{title}</h3><p>{subtitle}</p></div><span className="cm-mini-icon"><Icon name="arrow-up-right" /></span></div>
      <div className="cm-bars" role="img" aria-label={`${title}: ${items.map((item) => `${item.label} ${item.value}`).join(", ")}`}>
        {items.map((item, index) => (
          <div className="cm-bar-row" key={item.label}>
            <span className="cm-bar-label">{item.label}</span>
            <div className="cm-bar-track"><span style={{ "--bar-width": `${(item.value / max) * 100}%`, "--bar-delay": `${index * 80}ms`, "--bar-color": item.color ?? "var(--cm-violet)" } as CSSProperties & Record<`--${string}`, string>} /></div>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

export function AnalyticsStudio({ jobs, matches, applications, savedSearchCount, alertCount, onNavigate }: Props) {
  const matchScores = matches.map((match) => match.match_score).filter((score): score is number => typeof score === "number");
  const strongMatches = matchScores.filter((score) => score >= 80).length;
  const prepared = applications.filter((item) => ["saved", "preparing"].includes(item.status)).length;
  const submitted = applications.filter((item) => ["applied", "interview", "offer", "rejected", "withdrawn"].includes(item.status)).length;
  const interviews = applications.filter((item) => ["interview", "offer"].includes(item.status)).length;
  const offers = applications.filter((item) => item.status === "offer").length;
  const rejected = applications.filter((item) => item.status === "rejected").length;
  const interviewRate = submitted ? (interviews / submitted) * 100 : 0;
  const sourceCounts = applications.reduce<Record<string, number>>((acc, item) => {
    const source = item.source?.trim() || "Manual / other";
    acc[source] = (acc[source] ?? 0) + 1;
    return acc;
  }, {});
  const sources = Object.entries(sourceCounts).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([label, value]) => ({ label: label.replaceAll("_", " "), value }));
  const scoreGroups = [
    { label: "90–100", value: matchScores.filter((score) => score >= 90).length },
    { label: "80–89", value: matchScores.filter((score) => score >= 80 && score < 90).length },
    { label: "70–79", value: matchScores.filter((score) => score >= 70 && score < 80).length },
    { label: "60–69", value: matchScores.filter((score) => score >= 60 && score < 70).length },
    { label: "Below 60", value: matchScores.filter((score) => score < 60).length },
  ];
  const funnel = [
    { label: "Prepared", value: prepared },
    { label: "Submitted", value: submitted },
    { label: "Interview", value: interviews },
    { label: "Offer", value: offers },
  ];

  return (
    <div className="cm-page-stack cm-analytics-page">
      <section className="cm-analytics-hero">
        <div><span className="cm-kicker">SEARCH INTELLIGENCE</span><h2>Measure what moves your career forward.</h2><p>Live metrics calculated from the jobs, match reports and applications stored in this workspace.</p></div>
        <div className="cm-analytics-hero-side"><span className="cm-hero-orbit cm-orbit-a" /><span className="cm-hero-orbit cm-orbit-b" /><span className="cm-hero-core"><Icon name="chart" /></span></div>
      </section>
      <section className="cm-metrics-grid">
        <Metric label="Jobs in workspace" value={jobs.length.toLocaleString()} detail="Currently loaded job records" tone="blue" />
        <Metric label="Strong matches" value={strongMatches.toLocaleString()} detail={`${matchScores.length} scored roles · score ≥ 80`} tone="green" />
        <Metric label="Applications submitted" value={submitted.toLocaleString()} detail={`${prepared} saved or being prepared`} tone="violet" />
        <Metric label="Interview rate" value={formatPercent(interviewRate)} detail={`${interviews} interviews from ${submitted} submissions`} tone="amber" />
      </section>
      <section className="cm-analytics-grid">
        <BarList title="Match score distribution" subtitle="How your analyzed opportunities are distributed by score." items={scoreGroups} />
        <BarList title="Application funnel" subtitle="Progress through your tracked application pipeline." items={funnel} />
        <BarList title="Applications by source" subtitle="Which discovery sources have produced applications." items={sources.length ? sources : [{ label: "No applications yet", value: 0 }]} />
        <section className="cm-card cm-insight-card">
          <div className="cm-section-heading"><div><span className="cm-kicker">WORKSPACE HEALTH</span><h3>Your next best actions</h3><p>Signals based on the information currently available.</p></div><span className="cm-mini-icon"><Icon name="activity" /></span></div>
          <div className="cm-insight-list">
            <button type="button" onClick={() => onNavigate("discover")}><span className="cm-insight-number">01</span><span><strong>Keep the pipeline fresh</strong><small>{savedSearchCount} saved searches · {alertCount} job alerts recorded</small></span><b><Icon name="arrow" /></b></button>
            <button type="button" onClick={() => onNavigate("matches")}><span className="cm-insight-number">02</span><span><strong>Review high-fit opportunities</strong><small>{strongMatches} matches currently score 80 or higher</small></span><b><Icon name="arrow" /></b></button>
            <button type="button" onClick={() => onNavigate("applications")}><span className="cm-insight-number">03</span><span><strong>Follow through consistently</strong><small>{rejected} rejections recorded · {offers} offers recorded</small></span><b><Icon name="arrow" /></b></button>
          </div>
          <div className="cm-data-note"><span><Icon name="info" /></span><p>Metrics reflect records currently loaded in CareerMate. Historical trends and time-saved measurements will become meaningful as activity events are collected over time.</p></div>
        </section>
      </section>
      <div className="cm-footnote"><span className="cm-live-dot" /> Analytics are local to this workspace. No interview or hiring probability is inferred from a match score.</div>
    </div>
  );
}
