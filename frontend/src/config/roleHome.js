/** Role home paths and operational route classification (Phase 19). */

export function homePathForRole(role) {
  if (role === "ADMINISTRATOR") return "/app/admin/dashboard";
  return "/app/dashboard";
}

/** Routes that are UFM/operational — administrators must not land here. */
export const OPERATIONAL_APP_PATHS = [
  "/app/cases",
  "/app/detections",
  "/app/evidence",
  "/app/monitoring",
  "/app/students",
  "/app/users",
  "/app/master-data",
  "/app/result-controls",
  "/app/reports",
  "/app/clarification",
  "/app/audit",
];

export function isOperationalPath(pathname) {
  if (!pathname) return false;
  return OPERATIONAL_APP_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
}
