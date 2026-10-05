/** Role-aware dashboard KPIs, queues, and quick actions — derived from real API data only. */

import {
  formatStatusLabel,
  formatViolationLabel,
} from "./casePresentation";
import { apiDateTimeMs } from "./dateTime.js";

export const OPEN_STATUSES = new Set([
  "PENDING",
  "UNDER_REVIEW",
  "DEC_REVIEW",
  "EXAM_DEPARTMENT_REVIEW",
  "UFM_COMMITTEE_REVIEW",
]);

/** Primary status(es) each reviewing role acts on */
export const ROLE_QUEUE_STATUSES = {
  HOD: ["PENDING", "UNDER_REVIEW"],
  DEC: ["DEC_REVIEW"],
  EXAM_DEPARTMENT: ["EXAM_DEPARTMENT_REVIEW"],
  UFM_COMMITTEE: ["UFM_COMMITTEE_REVIEW"],
};

export function casesForRoleQueue(cases, role, userId) {
  let list;
  if (role === "INVIGILATOR") {
    list = cases.filter(
      (c) => c.reported_by === userId && OPEN_STATUSES.has(c.status)
    );
  } else if (role === "STUDENT") {
    list = cases.filter((c) => OPEN_STATUSES.has(c.status));
  } else {
    const statuses = ROLE_QUEUE_STATUSES[role];
    list = statuses
      ? cases.filter((c) => statuses.includes(c.status))
      : cases.filter((c) => OPEN_STATUSES.has(c.status));
  }
  // Preserve latest-first even if upstream order changes (created_at DESC, id DESC).
  return [...list].sort((a, b) => {
    const ta = apiDateTimeMs(a.created_at) || 0;
    const tb = apiDateTimeMs(b.created_at) || 0;
    if (tb !== ta) return tb - ta;
    return (Number(b.id) || 0) - (Number(a.id) || 0);
  });
}

function byStatus(cases, status) {
  return cases.filter((c) => c.status === status);
}

function heldControls(resultControls) {
  return (resultControls || []).filter((r) => r.result_status === "HELD");
}

function releasedControls(resultControls) {
  return (resultControls || []).filter((r) => r.result_status === "RELEASED");
}

export function buildRoleKpis({
  role,
  cases,
  detections,
  cameras,
  unread,
  resultControls,
  userId,
  adminStats,
}) {
  const open = cases.filter((c) => OPEN_STATUSES.has(c.status));
  const approved = byStatus(cases, "APPROVED");
  const rejected = byStatus(cases, "REJECTED");
  const online = cameras.filter((c) => c.is_active).length;
  const offline = Math.max(0, cameras.length - online);
  const held = heldControls(resultControls);
  const released = releasedControls(resultControls);

  if (role === "ADMINISTRATOR") {
    const s = adminStats || {};
    const by = s.by_role || {};
    return [
      {
        title: "Total portal users",
        value: s.total ?? 0,
        hint: "Authorized Google identities",
        accent: "border-l-slate-600",
      },
      {
        title: "Active",
        value: s.active ?? 0,
        hint: `${s.inactive ?? 0} inactive`,
        accent: "border-l-emerald-500",
      },
      {
        title: "Students",
        value: by.STUDENT ?? 0,
        hint: `${s.students_linked ?? 0} linked`,
        accent: "border-l-sky-500",
      },
      {
        title: "Administrators",
        value: by.ADMINISTRATOR ?? 0,
        hint: "University admins",
        accent: "border-l-violet-500",
      },
    ];
  }

  if (role === "HOD") {
    const pending = cases.filter((c) =>
      ROLE_QUEUE_STATUSES.HOD.includes(c.status)
    );
    return [
      {
        title: "Pending department review",
        value: pending.length,
        hint: "Awaiting HOD action",
        accent: "border-l-violet-500",
      },
      {
        title: "Forwarded to DEC",
        value: byStatus(cases, "DEC_REVIEW").length,
        hint: "In DEC queue",
        accent: "border-l-sky-500",
      },
      {
        title: "Open cases",
        value: open.length,
        hint: "All in-progress statuses",
        accent: "border-l-orange-500",
      },
      {
        title: "Unread notifications",
        value: unread.length,
        hint: "Requires attention",
        accent: "border-l-rose-500",
      },
    ];
  }

  if (role === "DEC") {
    return [
      {
        title: "Cases received",
        value: byStatus(cases, "DEC_REVIEW").length,
        hint: "Awaiting DEC review",
        accent: "border-l-violet-500",
      },
      {
        title: "Forwarded to Exam Dept.",
        value: byStatus(cases, "EXAM_DEPARTMENT_REVIEW").length,
        hint: "Next workflow stage",
        accent: "border-l-sky-500",
      },
      {
        title: "At UFM Committee",
        value: byStatus(cases, "UFM_COMMITTEE_REVIEW").length,
        hint: "Awaiting decision",
        accent: "border-l-orange-500",
      },
      {
        title: "Unread notifications",
        value: unread.length,
        hint: "Requires attention",
        accent: "border-l-rose-500",
      },
    ];
  }

  if (role === "EXAM_DEPARTMENT") {
    return [
      {
        title: "Department queue",
        value: byStatus(cases, "EXAM_DEPARTMENT_REVIEW").length,
        hint: "Cases requiring processing",
        accent: "border-l-violet-500",
      },
      {
        title: "At committee",
        value: byStatus(cases, "UFM_COMMITTEE_REVIEW").length,
        hint: "Forwarded to UFM",
        accent: "border-l-sky-500",
      },
      {
        title: "Active result holds",
        value: held.length,
        hint: `${released.length} released · open Result Holds for students`,
        accent: "border-l-rose-500",
      },
      {
        title: "Unread notifications",
        value: unread.length,
        hint: "Requires attention",
        accent: "border-l-orange-500",
      },
    ];
  }

  if (role === "UFM_COMMITTEE") {
    return [
      {
        title: "Final review queue",
        value: byStatus(cases, "UFM_COMMITTEE_REVIEW").length,
        hint: "Awaiting APPROVE / REJECT",
        accent: "border-l-violet-500",
      },
      {
        title: "Approved",
        value: approved.length,
        hint: "Committee decisions",
        accent: "border-l-emerald-500",
      },
      {
        title: "Rejected",
        value: rejected.length,
        hint: "Not upheld",
        accent: "border-l-rose-500",
      },
      {
        title: "Active result holds",
        value: held.length,
        hint: `${released.length} released · open Result Holds for students`,
        accent: "border-l-orange-500",
      },
    ];
  }

  if (role === "STUDENT") {
    return [
      {
        title: "My UFM cases",
        value: cases.length,
        hint: "Linked student profile",
        accent: "border-l-sky-500",
      },
      {
        title: "Open cases",
        value: open.length,
        hint: "Still in workflow",
        accent: "border-l-orange-500",
      },
      {
        title: "Decisions recorded",
        value: approved.length + rejected.length,
        hint: "Approved or rejected",
        accent: "border-l-violet-500",
      },
      {
        title: "Unread notifications",
        value: unread.length,
        hint: "Portal inbox",
        accent: "border-l-rose-500",
      },
    ];
  }

  // INVIGILATOR
  const myOpen = cases.filter(
    (c) => c.reported_by === userId && OPEN_STATUSES.has(c.status)
  );
  const myClosed = cases.filter(
    (c) =>
      c.reported_by === userId &&
      (c.status === "APPROVED" || c.status === "REJECTED")
  );
  return [
    {
      title: "Ready cameras",
      value: online,
      hint: `${cameras.length} registered · ${offline} offline`,
      accent: "border-l-emerald-500",
    },
    {
      title: "Confirmed detections",
      value: detections.length,
      hint: "System-assisted alerts",
      accent: "border-l-orange-500",
    },
    {
      title: "My open cases",
      value: myOpen.length,
      hint: "Reported UFM cases",
      accent: "border-l-sky-500",
    },
    {
      title: "Unread notifications",
      value: unread.length,
      hint: `${myClosed.length} closed cases`,
      accent: "border-l-violet-500",
    },
  ];
}

export function queueMetaForRole(role) {
  if (role === "ADMINISTRATOR") {
    return {
      title: "Authorization overview",
      empty: "No authorization items require attention.",
      action: "Open",
      viewAll: "/app/admin/users",
    };
  }
  if (role === "INVIGILATOR") {
    return {
      title: "Open UFM cases",
      empty: "No open UFM cases on record.",
      action: "Open case",
      viewAll: "/app/cases",
    };
  }
  if (role === "STUDENT") {
    return {
      title: "UFM cases requiring attention",
      empty: "No open UFM cases on the linked student profile.",
      action: "View case",
      viewAll: "/app/cases",
    };
  }
  if (role === "HOD") {
    return {
      title: "Pending department review",
      empty: "No UFM cases require HOD attention.",
      action: "Review",
      viewAll: "/app/cases?scope=active",
    };
  }
  if (role === "DEC") {
    return {
      title: "Cases Received from HOD",
      empty: "No UFM cases require DEC attention.",
      action: "Review",
      viewAll: "/app/cases?status=DEC_REVIEW",
    };
  }
  if (role === "EXAM_DEPARTMENT") {
    return {
      title: "Cases requiring processing",
      empty: "No UFM cases in the Exam Department queue.",
      action: "Open",
      viewAll: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
    };
  }
  if (role === "UFM_COMMITTEE") {
    return {
      title: "Final review queue",
      empty: "No UFM cases await committee decision.",
      action: "Decide",
      viewAll: "/app/cases?status=UFM_COMMITTEE_REVIEW",
    };
  }
  return {
    title: "Review queue",
    empty: "No UFM cases require attention.",
    action: "Open",
    viewAll: "/app/cases",
  };
}

export function dashboardIntro(role) {
  switch (role) {
    case "ADMINISTRATOR":
      return "Manage system users, access, configuration, and administrative controls.";
    case "HOD":
      return "Review and process UFM cases submitted for departmental consideration.";
    case "DEC":
      return "Review cases received from the department and prepare them for examination department processing.";
    case "EXAM_DEPARTMENT":
      return "Institution-wide UFM case oversight, investigations, result controls, and records.";
    case "UFM_COMMITTEE":
      return "Final review of UFM cases, evidence, recommendations, and disciplinary decisions.";
    case "STUDENT":
      return "View case status, submitted clarification, notifications, and recorded outcomes.";
    default:
      return "Live examination monitoring, AI-assisted detections, and reported UFM incidents.";
  }
}

export function quickActionsForRole(role) {
  if (role === "ADMINISTRATOR") {
    return [
      { to: "/app/admin/users", label: "Manage Users", tone: "violet" },
      { to: "/app/admin/import", label: "Import CSV", tone: "sky" },
      { to: "/app/admin/audit", label: "Admin Audit Log", tone: "slate" },
    ];
  }
  if (role === "INVIGILATOR") {
    return [
      { to: "/app/cases/new", label: "Create UFM Case", tone: "sky" },
      { to: "/app/cases", label: "My Cases", tone: "slate" },
      { to: "/app/evidence", label: "Evidence Library", tone: "violet" },
      { to: "/app/monitoring", label: "Live Monitoring", tone: "emerald" },
      { to: "/app/detections", label: "Detections & Alerts", tone: "orange" },
      { to: "/app/reports", label: "Reports", tone: "sky" },
    ];
  }
  if (role === "HOD") {
    return [
      {
        to: "/app/cases?scope=active",
        label: "Pending Cases",
        tone: "violet",
      },
      { to: "/app/evidence", label: "Evidence", tone: "sky" },
      { to: "/app/cases", label: "All UFM Cases", tone: "slate" },
      { to: "/app/reports", label: "Reports", tone: "orange" },
      { to: "/app/audit", label: "Audit Trail", tone: "emerald" },
    ];
  }
  if (role === "DEC") {
    return [
      {
        to: "/app/cases?status=DEC_REVIEW",
        label: "Cases Received from HOD",
        tone: "violet",
      },
      { to: "/app/cases", label: "All UFM Cases", tone: "slate" },
      { to: "/app/evidence", label: "Evidence Library", tone: "emerald" },
      { to: "/app/reports", label: "Reports", tone: "sky" },
      { to: "/app/audit", label: "Audit Trail", tone: "orange" },
    ];
  }
  if (role === "EXAM_DEPARTMENT") {
    return [
      {
        to: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
        label: "Department Queue",
        tone: "violet",
      },
      { to: "/app/result-controls", label: "Result Holds", tone: "rose" },
      { to: "/app/cases", label: "All Cases", tone: "slate" },
      { to: "/app/reports", label: "Reports", tone: "orange" },
      { to: "/app/audit", label: "Audit Trail", tone: "emerald" },
    ];
  }
  if (role === "UFM_COMMITTEE") {
    return [
      {
        to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
        label: "Final Review",
        tone: "violet",
      },
      { to: "/app/cases", label: "All Cases", tone: "slate" },
      { to: "/app/result-controls", label: "Result Holds", tone: "rose" },
      { to: "/app/evidence", label: "Evidence", tone: "emerald" },
      { to: "/app/audit", label: "Audit Trail", tone: "orange" },
    ];
  }
  return [
    { to: "/app/cases", label: "My Cases", tone: "violet" },
    {
      to: "/app/clarification",
      label: "Clarification / Required Actions",
      tone: "orange",
    },
    { to: "/app/notifications", label: "Notifications", tone: "emerald" },
    { to: "/app/help", label: "Help and Guidance", tone: "sky" },
  ];
}

export const ACTION_TONES = {
  sky: "border-sky-300 bg-sky-50 text-sky-800",
  orange: "border-orange-300 bg-orange-50 text-orange-800",
  slate: "border-slate-300 bg-slate-50 text-slate-700",
  violet: "border-violet-300 bg-violet-50 text-violet-800",
  emerald: "border-emerald-300 bg-emerald-50 text-emerald-800",
  rose: "border-rose-300 bg-rose-50 text-rose-800",
};

const CHART_COLORS = [
  "#7c3aed",
  "#2563eb",
  "#ea580c",
  "#059669",
  "#e11d48",
  "#0891b2",
  "#ca8a04",
];

export function countByField(items, field, { formatLabel } = {}) {
  const map = new Map();
  for (const item of items) {
    const raw = item[field] || "Unknown";
    map.set(raw, (map.get(raw) || 0) + 1);
  }
  return [...map.entries()]
    .map(([raw, count], i) => ({
      label: formatLabel ? formatLabel(raw) : String(raw).replaceAll("_", " "),
      count,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }))
    .sort((a, b) => b.count - a.count);
}

export function statusChartSegments(cases) {
  return countByField(cases, "status", { formatLabel: formatStatusLabel });
}

export function violationChartSegments(cases) {
  return countByField(cases, "violation_type", {
    formatLabel: formatViolationLabel,
  });
}
