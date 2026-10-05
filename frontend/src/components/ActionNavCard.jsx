import { Link } from "react-router-dom";

/** Small line icons — resting-state navigation cue (not decoration). */
const ICONS = {
  cases: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  ),
  queue: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 6h16M4 12h16M4 18h10" />
      <circle cx="18" cy="18" r="2" />
    </svg>
  ),
  evidence: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <circle cx="10" cy="11" r="2.5" />
      <path d="M4 16l4-3 3 2 4-4 5 5" />
    </svg>
  ),
  reports: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M5 19V9M10 19V5M15 19v-7M20 19V8" />
    </svg>
  ),
  audit: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z" />
      <path d="M9.5 12l2 2 3.5-3.5" />
    </svg>
  ),
  monitor: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="5" width="18" height="12" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  ),
  detections: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M12 4v3M12 17v3M4 12h3M17 12h3" />
      <circle cx="12" cy="12" r="4" />
    </svg>
  ),
  results: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M7 4h10v4H7zM9 8v12M15 8v12M6 20h12" />
    </svg>
  ),
  clarification: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M5 5h14v10H9l-4 4V5z" />
      <path d="M9 9h6M9 12h4" />
    </svg>
  ),
  notifications: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M6 16V10a6 6 0 1 1 12 0v6l2 2H4l2-2zM10 20h4" />
    </svg>
  ),
  help: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.1.8-1.1 1.8M12 17h.01" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="9" cy="8" r="3" />
      <path d="M3 19c0-3 2.5-5 6-5s6 2 6 5" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M21 19c0-2.2-1.5-3.8-3.5-4.4" />
    </svg>
  ),
  import: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M12 4v10M8 10l4 4 4-4M5 18h14" />
    </svg>
  ),
  roles: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="8" cy="8" r="3" />
      <circle cx="16" cy="8" r="3" />
      <path d="M3 19c0-2.5 2-4.5 5-4.5M21 19c0-2.5-2-4.5-5-4.5M10.5 14.5h3" />
    </svg>
  ),
  create: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M12 5v14M5 12h14" />
      <rect x="3" y="3" width="18" height="18" rx="2" />
    </svg>
  ),
  default: (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M9 12h6M12 9v6" />
    </svg>
  ),
};

export function resolveActionIcon(to = "", label = "") {
  const hay = `${to} ${label}`.toLowerCase();
  if (
    hay.includes("cases/new") ||
    hay.includes("create ufm") ||
    (hay.includes("report") && (hay.includes("ufm") || hay.includes("incident")))
  )
    return "create";
  if (hay.includes("pending") || hay.includes("queue") || hay.includes("review"))
    return "queue";
  if (hay.includes("evidence")) return "evidence";
  if (hay.includes("report") && !hay.includes("ufm") && !hay.includes("incident"))
    return "reports";
  if (hay.includes("audit") || hay.includes("security")) return "audit";
  if (hay.includes("monitor")) return "monitor";
  if (hay.includes("detection")) return "detections";
  if (hay.includes("result")) return "results";
  if (hay.includes("clarification")) return "clarification";
  if (hay.includes("notification")) return "notifications";
  if (hay.includes("help")) return "help";
  if (hay.includes("import")) return "import";
  if (hay.includes("role")) return "roles";
  if (hay.includes("student")) return "users";
  if (hay.includes("user") || hay.includes("add user")) return "users";
  if (hay.includes("case") || hay.includes("incident") || hay.includes("ufm"))
    return "cases";
  return "default";
}

/**
 * Clickable navigation/action card — C13-FIX resting-state interactive language.
 * Structure: [icon] title + action hint [chevron]
 * Do not use for KPI/statistics (see KpiCard).
 */
export default function ActionNavCard({
  to,
  label,
  hint = "Open →",
  primary = false,
  icon,
  className = "",
}) {
  const iconKey = icon || resolveActionIcon(to, label);
  const glyph = ICONS[iconKey] || ICONS.default;

  return (
    <Link
      to={to}
      className={["portal-action-tile", primary ? "primary" : "", className]
        .filter(Boolean)
        .join(" ")}
      data-affordance="interactive"
    >
      <span className="tile-icon" aria-hidden="true">
        {glyph}
      </span>
      <span className="tile-body">
        <span className="tile-label">{label}</span>
        {hint ? <span className="tile-hint">{hint}</span> : null}
      </span>
      <span className="tile-chevron" aria-hidden="true">
        ›
      </span>
    </Link>
  );
}
