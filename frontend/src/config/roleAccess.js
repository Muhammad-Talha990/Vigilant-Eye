/**
 * C11-B role access sets — frontend gates must match backend case_access / main.py.
 * Navigation hide alone is not sufficient; pages and App.jsx must use these sets.
 */

/** Live monitoring / CCTV control — Invigilator only (C26-FIX). */
export const MONITOR_ROLES = Object.freeze(["INVIGILATOR"]);

/** Operational detection inbox — Invigilator only (C26-FIX). */
export const DETECTION_ROLES = Object.freeze(["INVIGILATOR"]);

/** Case reports + CSV export — separate from MONITOR / DETECTION / CASE_CREATE (C27). */
export const REPORTS_ROLES = Object.freeze([
  "INVIGILATOR",
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
]);

export const OPERATIONAL_AUDIT_ROLES = Object.freeze([
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
]);

export const RESULT_CONTROL_ROLES = Object.freeze([
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
]);

export const CASE_CREATE_ROLES = Object.freeze(["INVIGILATOR"]);

/** Case-linked evidence upload — Invigilator only (C28). Reviewers use view roles. */
export const EVIDENCE_UPLOAD_ROLES = Object.freeze(["INVIGILATOR"]);

export const EVIDENCE_VIEW_ROLES = Object.freeze([
  "INVIGILATOR",
  "HOD",
  "DEC",
  "EXAM_DEPARTMENT",
  "UFM_COMMITTEE",
]);

/** Exam Setup page — DEC view only (standalone module removed for Exam Department). */
export const MASTER_DATA_VIEW_ROLES = Object.freeze(["DEC"]);

/** Master-data create UI — no operational portal role after Exam Department cleanup. */
export const MASTER_DATA_CREATE_ROLES = Object.freeze([]);

/** Standalone Students directory page — no operational portal role after cleanup. */
export const STUDENT_DIRECTORY_VIEW_ROLES = Object.freeze([]);

/** Create/link student academic records — no operational portal role after cleanup. */
export const STUDENT_DIRECTORY_MANAGE_ROLES = Object.freeze([]);

export function roleIn(role, allowed) {
  const key = typeof role === "string" ? role.trim().toUpperCase() : "";
  return Boolean(key && allowed.includes(key));
}
