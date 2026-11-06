type Props = { source: string; sourceUrl?: string };

type Brand = { key: string; label: string; mark: string; variant: "linkedin" | "indeed" | "glassdoor" | "jobtech" | "remoteok" | "arbeitnow" | "greenhouse" | "lever" | "teamtailor" | "ashby" | "smartrecruiters" | "workable" | "recruitee" | "breezy" | "personio" | "workday" | "generic" };

const BRANDS: Record<string, Brand> = {
  linkedin: { key: "linkedin", label: "LinkedIn", mark: "in", variant: "linkedin" },
  indeed: { key: "indeed", label: "Indeed", mark: "i", variant: "indeed" },
  glassdoor: { key: "glassdoor", label: "Glassdoor", mark: "G", variant: "glassdoor" },
  jobtech_links: { key: "jobtech", label: "JobTech", mark: "J", variant: "jobtech" },
  jobtech: { key: "jobtech", label: "JobTech", mark: "J", variant: "jobtech" },
  remoteok: { key: "remoteok", label: "Remote OK", mark: "R", variant: "remoteok" },
  arbeitnow: { key: "arbeitnow", label: "Arbeitnow", mark: "A", variant: "arbeitnow" },
  greenhouse: { key: "greenhouse", label: "Greenhouse", mark: "g", variant: "greenhouse" },
  lever: { key: "lever", label: "Lever", mark: "L", variant: "lever" },
  teamtailor: { key: "teamtailor", label: "Teamtailor", mark: "t", variant: "teamtailor" },
  ashby: { key: "ashby", label: "Ashby", mark: "A", variant: "ashby" },
  smartrecruiters: { key: "smartrecruiters", label: "SmartRecruiters", mark: "S", variant: "smartrecruiters" },
  workable: { key: "workable", label: "Workable", mark: "W", variant: "workable" },
  recruitee: { key: "recruitee", label: "Recruitee", mark: "R", variant: "recruitee" },
  breezy: { key: "breezy", label: "Breezy HR", mark: "B", variant: "breezy" },
  personio: { key: "personio", label: "Personio", mark: "p", variant: "personio" },
  workday: { key: "workday", label: "Workday", mark: "w", variant: "workday" },
};

function sourceKey(source: string, sourceUrl?: string): string {
  const value = `${source} ${sourceUrl ?? ""}`.toLowerCase();
  if (value.includes("linkedin")) return "linkedin";
  if (value.includes("indeed")) return "indeed";
  if (value.includes("glassdoor")) return "glassdoor";
  if (value.includes("greenhouse")) return "greenhouse";
  if (value.includes("teamtailor")) return "teamtailor";
  if (value.includes("smartrecruiters")) return "smartrecruiters";
  if (value.includes("workable")) return "workable";
  if (value.includes("recruitee")) return "recruitee";
  if (value.includes("breezy")) return "breezy";
  if (value.includes("personio")) return "personio";
  if (value.includes("workday")) return "workday";
  if (value.includes("ashby")) return "ashby";
  if (value.includes("lever")) return "lever";
  if (value.includes("arbeitnow")) return "arbeitnow";
  if (value.includes("remoteok") || value.includes("remote ok")) return "remoteok";
  if (value.includes("jobtech") || value.includes("jobad") || value.includes("arbetsformedlingen") || value.includes("platsbanken")) return "jobtech_links";
  return source.toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

export function SourceMark({ source, sourceUrl }: Props) {
  const key = sourceKey(source, sourceUrl);
  const brand = BRANDS[key] ?? {
    key: "generic",
    label: source || "Job source",
    mark: (source || "?").trim().charAt(0).toUpperCase() || "?",
    variant: "generic" as const,
  };

  return (
    <span className={`source-brand-mark source-brand-${brand.variant}`} role="img" aria-label={`${brand.label} source`} title={brand.label}>
      {brand.variant === "linkedin" ? <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5.2 8.6H2.4V21h2.8V8.6ZM3.8 2.8a1.65 1.65 0 1 0 0 3.3 1.65 1.65 0 0 0 0-3.3ZM21.6 13.9c0-3.7-1.9-5.5-4.5-5.5-2.1 0-3.1 1.1-3.7 1.9V8.6h-2.8V21h2.8v-6.1c0-1.6.3-3.1 2.3-3.1s2 1.8 2 3.2V21h2.9v-7.1Z" /></svg>
        : brand.variant === "indeed" ? <span className="source-brand-letter">i</span>
        : brand.variant === "glassdoor" ? <span className="source-brand-letter source-brand-gd">G</span>
        : brand.variant === "jobtech" ? <span className="source-brand-letter source-brand-jt">J</span>
        : <span className="source-brand-letter">{brand.mark}</span>}
    </span>
  );
}
