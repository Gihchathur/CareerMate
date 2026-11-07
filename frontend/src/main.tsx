import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/floating-select.css";
import "./styles/pages/overview.css";
import "./styles/pages/discover.css";
import "./styles/pages/platforms.css";
import "./styles/pages/matches.css";
import "./styles/pages/applications.css";
import "./styles/pages/browser-assistance.css";
import "./styles/pages/profile.css";
import "./styles/pages/settings.css";
import "./styles/pages/detail-patterns.css";
import "./styles/pages/responsive.css";
import "./careermate-v2.css";
import "./ux-hardening.css";
import "./ux-experience.css";
import "./ux-readability.css";
import "./portals-workspace.css";
import "./navigation-overflow.css";
import "./quality-fixes.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
