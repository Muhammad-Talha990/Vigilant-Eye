/** Role-based sidebar menus (grouped sections). Routes must already exist in App.jsx. */
/* C11-B — role access + navigation cleanup */

export const ROLE_LABELS = {
  ADMINISTRATOR: "Administrator",
  STUDENT: "Student",
  INVIGILATOR: "Invigilator",
  HOD: "HOD",
  DEC: "DEC",
  EXAM_DEPARTMENT: "Exam Department",
  UFM_COMMITTEE: "UFM Committee",
};

/**
 * Each role is an ordered list of sections.
 * Item shape: { to, label, badgeKey? }
 * badgeKey only when AppLayout supplies a real count (notifications / detections).
 *
 * Demo / Testing (/app/monitoring/demo) remains routed and linked from Live Monitoring;
 * it is intentionally omitted from production role navigation.
 */
export const NAV_BY_ROLE = {
  ADMINISTRATOR: [
    {
      section: "Overview",
      items: [{ to: "/app/admin/dashboard", label: "Dashboard" }],
    },
    {
      section: "User & Access Management",
      items: [
        { to: "/app/admin/users", label: "Users" },
        { to: "/app/admin/import", label: "Import Users" },
      ],
    },
    {
      section: "Security & Audit",
      items: [
        { to: "/app/admin/audit", label: "Audit Log" },
        { to: "/app/admin/roles", label: "Roles & Permissions" },
      ],
    },
    {
      section: "Directory",
      items: [{ to: "/app/admin/students", label: "Students" }],
    },
    {
      section: "System",
      items: [{ to: "/app/admin/system", label: "System" }],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/admin/profile", label: "Profile" }],
    },
  ],

  INVIGILATOR: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "Examination / Monitoring",
      items: [
        { to: "/app/monitoring", label: "Live Monitoring" },
        {
          to: "/app/detections",
          label: "Detections & Alerts",
          badgeKey: "detections",
        },
      ],
    },
    {
      section: "UFM Cases",
      items: [
        { to: "/app/cases", label: "My Cases" },
        { to: "/app/cases/new", label: "Report UFM Incident" },
        { to: "/app/evidence", label: "Evidence Library" },
      ],
    },
    {
      section: "Records",
      items: [{ to: "/app/reports", label: "Reports" }],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],

  HOD: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "UFM Review",
      items: [
        { to: "/app/cases?scope=active", label: "Cases for Review" },
        { to: "/app/cases", label: "All UFM Cases" },
        { to: "/app/evidence", label: "Evidence Library" },
      ],
    },
    {
      section: "Records",
      items: [
        { to: "/app/reports", label: "Reports" },
        { to: "/app/audit", label: "Audit Trail" },
      ],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],

  DEC: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "UFM Review",
      items: [
        {
          to: "/app/cases?status=DEC_REVIEW",
          label: "Cases Received from HOD",
        },
        { to: "/app/cases", label: "All UFM Cases" },
        { to: "/app/evidence", label: "Evidence Library" },
      ],
    },
    {
      section: "Records",
      items: [
        { to: "/app/reports", label: "Reports" },
        { to: "/app/audit", label: "Audit Trail" },
      ],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],

  EXAM_DEPARTMENT: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "Case Processing",
      items: [
        {
          to: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
          label: "Cases for Processing",
        },
        {
          to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
          label: "At UFM Committee",
        },
        { to: "/app/cases", label: "All Cases" },
      ],
    },
    {
      section: "Result Controls",
      items: [{ to: "/app/result-controls", label: "Result Holds" }],
    },
    {
      section: "Records",
      items: [
        { to: "/app/reports", label: "Reports" },
        { to: "/app/audit", label: "Audit Trail" },
      ],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],

  UFM_COMMITTEE: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "Review",
      items: [
        {
          to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
          label: "Cases for Final Review",
        },
        { to: "/app/cases?status=APPROVED", label: "Approved Cases" },
        { to: "/app/cases?status=REJECTED", label: "Rejected Cases" },
        { to: "/app/cases", label: "All Cases" },
        { to: "/app/evidence", label: "Evidence Library" },
      ],
    },
    {
      section: "Result Controls",
      items: [{ to: "/app/result-controls", label: "Result Holds" }],
    },
    {
      section: "Records",
      items: [
        { to: "/app/reports", label: "Reports" },
        { to: "/app/audit", label: "Audit Trail" },
      ],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],

  STUDENT: [
    {
      section: "Overview",
      items: [{ to: "/app/dashboard", label: "Dashboard" }],
    },
    {
      section: "UFM Cases",
      items: [{ to: "/app/cases", label: "My Cases" }],
    },
    {
      section: "Required Actions",
      items: [
        {
          to: "/app/clarification",
          label: "Clarification / Required Actions",
        },
      ],
    },
    {
      section: "Communication",
      items: [
        {
          to: "/app/notifications",
          label: "Notifications",
          badgeKey: "notifications",
        },
      ],
    },
    {
      section: "Information",
      items: [{ to: "/app/help", label: "Help and Guidance" }],
    },
    {
      section: "Account",
      items: [{ to: "/app/profile", label: "Profile" }],
    },
  ],
};

/** Paths Invigilator must never see in chrome navigation (defense-in-depth). */
const INVIGILATOR_NAV_DENY_PATHS = new Set([
  "/app/master-data",
  "/app/students",
]);

/** Paths / shortcuts HOD must never see in chrome navigation (defense-in-depth). */
const HOD_NAV_DENY_PATHS = new Set([
  "/app/master-data",
  "/app/students",
  "/app/cases?status=DEC_REVIEW",
  "/app/cases/new",
  "/app/monitoring",
  "/app/detections",
]);

/** Paths / shortcuts DEC must never see in chrome navigation (defense-in-depth). */
const DEC_NAV_DENY_PATHS = new Set([
  "/app/students",
  "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
  "/app/monitoring",
  "/app/detections",
  "/app/cases/new",
]);

/** Paths Exam Department must never see in chrome navigation (defense-in-depth). */
const EXAM_DEPARTMENT_NAV_DENY_PATHS = new Set([
  "/app/students",
  "/app/master-data",
  "/app/monitoring",
  "/app/detections",
  "/app/cases/new",
]);

/** Paths UFM Committee must never see in chrome navigation (defense-in-depth). */
const UFM_COMMITTEE_NAV_DENY_PATHS = new Set([
  "/app/students",
  "/app/monitoring",
  "/app/detections",
  "/app/cases/new",
]);

function sanitizeNavForRole(roleKey, sections) {
  const deny =
    roleKey === "INVIGILATOR"
      ? INVIGILATOR_NAV_DENY_PATHS
      : roleKey === "HOD"
        ? HOD_NAV_DENY_PATHS
        : roleKey === "DEC"
          ? DEC_NAV_DENY_PATHS
          : roleKey === "EXAM_DEPARTMENT"
            ? EXAM_DEPARTMENT_NAV_DENY_PATHS
            : roleKey === "UFM_COMMITTEE"
              ? UFM_COMMITTEE_NAV_DENY_PATHS
              : null;
  if (!deny) return sections;
  return sections
    .map((group) => ({
      ...group,
      items: (group.items || []).filter((item) => !deny.has(item.to)),
    }))
    .filter((group) => (group.items || []).length > 0);
}

export function getNavForRole(role) {
  const key = typeof role === "string" ? role.trim().toUpperCase() : "";
  if (key && NAV_BY_ROLE[key]) return sanitizeNavForRole(key, NAV_BY_ROLE[key]);
  // Never fall back to INVIGILATOR for unknown/missing roles — empty nav is safer.
  return [];
}

export function dashboardTitle(role) {
  switch (role) {
    case "ADMINISTRATOR":
      return "System Administration";
    case "INVIGILATOR":
      return "Examination Monitoring";
    case "HOD":
      return "Departmental UFM Review";
    case "DEC":
      return "UFM Case Review";
    case "EXAM_DEPARTMENT":
      return "Examination Department";
    case "UFM_COMMITTEE":
      return "UFM Committee Review";
    case "STUDENT":
      return "UFM Case Status";
    default:
      return "Examination Operations Overview";
  }
}
