import type { SVGProps } from "react";

export type IconName =
  | "search" | "file" | "sparkles" | "briefcase" | "check" | "arrow"
  | "grid" | "user" | "shield" | "target" | "chevron" | "sliders"
  | "layers" | "plus" | "info" | "graduation" | "pin" | "clock"
  | "cpu" | "refresh" | "trash" | "filter" | "download" | "eye"
  | "chart" | "bolt" | "activity" | "calendar" | "database" | "command" | "bell" | "wand" | "arrow-up-right" | "menu";

const paths: Record<IconName, string> = {
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
  refresh: "M20 7v5h-5M4 17v-5h5M5.6 9a7 7 0 0 1 11.7-2L20 12M4 12l2.7 5a7 7 0 0 0 11.7-2",
  trash: "M3 6h18M8 6V4h8v2m-10 0 1 14h10l1-14M10 10v6m4-6v6",
  filter: "M4 5h16M7 12h10m-7 7h4",
  download: "M12 3v12m-5-5 5 5 5-5M5 21h14",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  chart: "M3 3v18h18M8 15l4-4 4 3 5-7",
  bolt: "m13 2-3 9h7l-6 11 2-9H6l7-11Z",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  calendar: "M8 2v4m8-4v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z",
  database: "M12 3c5 0 9 1.3 9 3s-4 3-9 3-9-1.3-9-3 4-3 9-3Zm-9 3v12c0 1.7 4 3 9 3s9-1.3 9-3V6M3 12c0 1.7 4 3 9 3s9-1.3 9-3",
  command: "M9 9V5a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v14a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V9Z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12a2 2 0 0 0 4 0",
  wand: "m15 4 5 5M4 20l11-11m-9 1 2 2m6-8 2 2m-9 9 2 2M18 2l.8 2.2L21 5l-2.2.8L18 8l-.8-2.2L15 5l2.2-.8L18 2Z",
  "arrow-up-right": "M7 17 17 7M7 7h10v10",
  menu: "M4 6h16M4 12h16M4 18h16",
};

export function Icon({ name, className, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg aria-hidden="true" className={className ? `icon ${className}` : "icon"} viewBox="0 0 24 24" fill="none" {...props}>
      <path d={paths[name]} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
