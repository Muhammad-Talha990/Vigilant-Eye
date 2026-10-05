/**
 * C30 — institutional datetime display.
 *
 * Contract:
 * - API/backend store and emit UTC (naive DB columns; JSON uses …Z).
 * - UI displays in Asia/Karachi (UTC+05:00, no DST).
 * - Ambiguous strings without offset are treated as UTC (never as local).
 */

export const DISPLAY_TIMEZONE = "Asia/Karachi";

const HAS_TZ = /[zZ]$|[+-]\d{2}:?\d{2}$/;

/**
 * Parse an API/business timestamp into a Date.
 * Naive ISO values are interpreted as UTC.
 */
export function parseApiDateTime(value) {
  if (value == null || value === "") return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const raw = String(value).trim();
  if (!raw) return null;
  // Space separator → ISO T for consistent parsing
  const isoish = raw.includes("T") ? raw : raw.replace(" ", "T");
  const normalized = HAS_TZ.test(isoish) ? isoish : `${isoish}Z`;
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Format a UTC API timestamp for portal display (Asia/Karachi).
 * Example: 2026-10-04T10:18:31Z → "04/10/2026, 15:18:31"
 */
export function formatDateTime(value) {
  const d = parseApiDateTime(value);
  if (!d) return "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: DISPLAY_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

/** Date-only institutional display (Asia/Karachi). */
export function formatDate(value) {
  const d = parseApiDateTime(value);
  if (!d) return "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: DISPLAY_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
}

/** Epoch ms for sorting/compare; naive strings treated as UTC. */
export function apiDateTimeMs(value) {
  const d = parseApiDateTime(value);
  return d ? d.getTime() : NaN;
}
