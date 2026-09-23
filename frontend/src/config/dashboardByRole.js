/** Role-aware dashboard copy + queue filters (mockup-inspired). */

export const OPEN_STATUSES = new Set([
  "PENDING",
  "UNDER_REVIEW",
  "HOD_VERIFICATION",
  "DEC_REVIEW",
  "EXAM_DEPARTMENT_REVIEW",
  "UFM_COMMITTEE_REVIEW",
]);

/** Primary status each reviewing role acts on */
export const ROLE_QUEUE_STATUS = {
  HOD: "PENDING",
  DEC: "DEC_REVIEW",
  EXAM_DEPARTMENT: "EXAM_DEPARTMENT_REVIEW",
  UFM_COMMITTEE: "UFM_COMMITTEE_REVIEW",
};

export function casesForRoleQueue(cases, role, userId) {
  if (role === "INVIGILATOR") {
    return cases.filter(
      (c) => c.reported_by === userId && OPEN_STATUSES.has(c.status)
    );
  }
  if (role === "STUDENT") {
    return cases.filter((c) => OPEN_STATUSES.has(c.status));
  }
  const status = ROLE_QUEUE_STATUS[role];
  if (status) return cases.filter((c) => c.status === status);
  return cases.filter((c) => OPEN_STATUSES.has(c.status));
}

export function buildRoleKpis({
  role,
  cases,
  detections,
  cameras,
  unread,
  resultControls,
  userId,
}) {
  const pad = (n) => String(n).padStart(2, "0");
  const byStatus = (status) => cases.filter((c) => c.status === status);
  const open = cases.filter((c) => OPEN_STATUSES.has(c.status));
  const approved = byStatus("APPROVED");
  const rejected = byStatus("REJECTED");
  const online = cameras.filter((c) => c.is_active).length;
  const offline = cameras.length - online;
  const held = (resultControls || []).filter(
    (r) => r.result_status === "HELD" || r.transcript_status === "BLOCKED"
  );

  if (role === "HOD") {
    return [
      {
        title: "Pending Review",
        value: pad(byStatus("PENDING").length),
        hint: "Awaiting HOD forward",
        accent: "border-l-violet-500",
      },
      {
        title: "At DEC",
        value: pad(byStatus("DEC_REVIEW").length),
        hint: "Forwarded to DEC",
        accent: "border-l-sky-500",
      },
      {
        title: "Open Overall",
        value: pad(open.length),
        hint: "All in-progress statuses",
        accent: "border-l-orange-500",
      },
      {
        title: "Unread Alerts",
        value: pad(unread.length),
        hint: "Portal notifications",
        accent: "border-l-rose-500",
      },
      {
        title: "Closed Cases",
        value: pad(approved.length + rejected.length),
        hint: `${approved.length} approved · ${rejected.length} rejected`,
        accent: "border-l-emerald-500",
      },
    ];
  }

  if (role === "DEC") {
    return [
      {
        title: "Received from HOD",
        value: pad(byStatus("DEC_REVIEW").length),
        hint: "In DEC queue",
        accent: "border-l-violet-500",
      },
      {
        title: "At Exam Dept",
        value: pad(byStatus("EXAM_DEPARTMENT_REVIEW").length),
        hint: "Forwarded onward",
        accent: "border-l-sky-500",
      },
      {
        title: "At Committee",
        value: pad(byStatus("UFM_COMMITTEE_REVIEW").length),
        hint: "Awaiting decision",
        accent: "border-l-orange-500",
      },
      {
        title: "Unread Alerts",
        value: pad(unread.length),
        hint: "Portal notifications",
        accent: "border-l-rose-500",
      },
      {
        title: "Resolved",
        value: pad(approved.length + rejected.length),
        hint: "Approved / rejected",
        accent: "border-l-emerald-500",
      },
    ];
  }

  if (role === "EXAM_DEPARTMENT") {
    return [
      {
        title: "Dept Queue",
        value: pad(byStatus("EXAM_DEPARTMENT_REVIEW").length),
        hint: "From departments",
        accent: "border-l-violet-500",
      },
      {
        title: "At Committee",
        value: pad(byStatus("UFM_COMMITTEE_REVIEW").length),
        hint: "Forwarded to UFM",
        accent: "border-l-sky-500",
      },
      {
        title: "Result Holds",
        value: pad(held.length),
        hint: "HELD / BLOCKED",
        accent: "border-l-rose-500",
      },
      {
        title: "Unread Alerts",
        value: pad(unread.length),
        hint: "Portal notifications",
        accent: "border-l-orange-500",
      },
      {
        title: "Decisions",
        value: pad(approved.length + rejected.length),
        hint: "Final outcomes",
        accent: "border-l-emerald-500",
      },
    ];
  }

  if (role === "UFM_COMMITTEE") {
    return [
      {
        title: "Final Review",
        value: pad(byStatus("UFM_COMMITTEE_REVIEW").length),
        hint: "Awaiting APPROVE/REJECT",
        accent: "border-l-violet-500",
      },
      {
        title: "Approved",
        value: pad(approved.length),
        hint: "Committee decisions",
        accent: "border-l-emerald-500",
      },
      {
        title: "Rejected",
        value: pad(rejected.length),
        hint: "Not upheld",
        accent: "border-l-rose-500",
      },
      {
        title: "Result Holds",
        value: pad(held.length),
        hint: "Auto-hold on approve",
        accent: "border-l-orange-500",
      },
      {
        title: "Unread Alerts",
        value: pad(unread.length),
        hint: "Portal notifications",
        accent: "border-l-sky-500",
      },
    ];
  }

  if (role === "STUDENT") {
    return [
      {
        title: "UFM Cases",
        value: pad(cases.length),
        hint: "Linked to your profile",
        accent: "border-l-sky-500",
      },
      {
        title: "Open Cases",
        value: pad(open.length),
        hint: "Still in workflow",
        accent: "border-l-orange-500",
      },
      {
        title: "Decisions",
        value: pad(approved.length + rejected.length),
        hint: "Approved / rejected",
        accent: "border-l-violet-500",
      },
      {
        title: "Unread",
        value: pad(unread.length),
        hint: "Notifications",
        accent: "border-l-rose-500",
      },
      {
        title: "Help",
        value: "→",
        hint: "Guidelines & FAQ",
        accent: "border-l-emerald-500",
      },
    ];
  }

  // INVIGILATOR default
  const myOpen = cases.filter(
    (c) => c.reported_by === userId && OPEN_STATUSES.has(c.status)
  );
  return [
    {
      title: "Live Cameras",
      value: pad(online),
      hint: `${online} online, ${offline} offline`,
      accent: "border-l-rose-500",
    },
    {
      title: "Active Alerts",
      value: pad(detections.length),
      hint: "Confirmed detections",
      accent: "border-l-orange-500",
    },
    {
      title: "My Open Cases",
      value: pad(myOpen.length),
      hint: `${open.length} open overall`,
      accent: "border-l-sky-500",
    },
    {
      title: "Unread Alerts",
      value: pad(unread.length),
      hint: "Portal notifications",
      accent: "border-l-violet-500",
    },
    {
      title: "Closed Cases",
      value: pad(approved.length + rejected.length),
      hint: "Approved / rejected",
      accent: "border-l-emerald-500",
    },
  ];
}

export function quickActionsForRole(role) {
  const base = [
    { to: "/app/cases", label: "View Cases", tone: "slate" },
    { to: "/app/notifications", label: "Notifications", tone: "violet" },
  ];

  if (role === "INVIGILATOR") {
    return [
      { to: "/app/monitoring", label: "Live Monitoring", tone: "emerald" },
      { to: "/app/cases/new", label: "Create New Case", tone: "sky" },
      { to: "/app/detections", label: "View Detections", tone: "orange" },
      { to: "/app/evidence", label: "Evidence Library", tone: "violet" },
      ...base,
    ];
  }
  if (role === "HOD") {
    return [
      { to: "/app/monitoring", label: "Live Monitoring", tone: "emerald" },
      {
        to: "/app/cases?status=PENDING",
        label: "Cases for Review",
        tone: "violet",
      },
      { to: "/app/detections", label: "Detections", tone: "orange" },
      { to: "/app/evidence", label: "Evidence", tone: "sky" },
      { to: "/app/audit", label: "Audit Trail", tone: "slate" },
      ...base,
    ];
  }
  if (role === "DEC") {
    return [
      {
        to: "/app/cases?status=DEC_REVIEW",
        label: "Received from HOD",
        tone: "violet",
      },
      { to: "/app/evidence", label: "Evidence Library", tone: "emerald" },
      { to: "/app/students", label: "Students Involved", tone: "sky" },
      { to: "/app/audit", label: "Audit Trail", tone: "orange" },
      ...base,
    ];
  }
  if (role === "EXAM_DEPARTMENT") {
    return [
      {
        to: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
        label: "Department Queue",
        tone: "violet",
      },
      { to: "/app/result-controls", label: "Result Control", tone: "rose" },
      { to: "/app/students", label: "Students", tone: "sky" },
      { to: "/app/audit", label: "Audit Trail", tone: "orange" },
      ...base,
    ];
  }
  if (role === "UFM_COMMITTEE") {
    return [
      {
        to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
        label: "Final Review Queue",
        tone: "violet",
      },
      { to: "/app/result-controls", label: "Result Holds", tone: "rose" },
      { to: "/app/evidence", label: "Evidence", tone: "emerald" },
      { to: "/app/audit", label: "Audit Trail", tone: "orange" },
      ...base,
    ];
  }
  // STUDENT
  return [
    { to: "/app/cases", label: "My UFM Cases", tone: "violet" },
    { to: "/app/clarification", label: "Submit Clarification", tone: "orange" },
    { to: "/app/help", label: "Help & Support", tone: "sky" },
    { to: "/app/notifications", label: "Notifications", tone: "emerald" },
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

export function countByField(items, field) {
  const map = new Map();
  for (const item of items) {
    const key = item[field] || "Unknown";
    map.set(key, (map.get(key) || 0) + 1);
  }
  return [...map.entries()]
    .map(([label, count], i) => ({
      label,
      count,
      color: CHART_COLORS[i % CHART_COLORS.length],
    }))
    .sort((a, b) => b.count - a.count);
}
