/** Report aggregations from authoritative UFM case payloads (GET /ufm-cases). */

export const UNKNOWN_NOT_RECORDED = "Unknown/Not recorded";

/**
 * Count cases by a string field. Null/blank → Unknown/Not recorded.
 * One case = one count; stable sort by count desc, then label.
 */
export function countCasesByField(cases, field) {
  const map = new Map();
  const list = Array.isArray(cases) ? cases : [];
  for (const item of list) {
    const raw = item?.[field];
    const key =
      raw == null || String(raw).trim() === ""
        ? UNKNOWN_NOT_RECORDED
        : String(raw).trim();
    map.set(key, (map.get(key) || 0) + 1);
  }
  return [...map.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function departmentWiseStats(cases) {
  return countCasesByField(cases, "student_department");
}

export function semesterWiseStats(cases) {
  return countCasesByField(cases, "exam_semester");
}
