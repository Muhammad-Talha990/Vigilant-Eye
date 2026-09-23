/** Role-based sidebar menus. */

export const ROLE_LABELS = {
  STUDENT: "Student",
  INVIGILATOR: "Invigilator",
  HOD: "HOD",
  DEC: "DEC",
  EXAM_DEPARTMENT: "Exam Department",
  UFM_COMMITTEE: "UFM Committee",
};

export const NAV_BY_ROLE = {
  INVIGILATOR: [
    { to: "/app/dashboard", label: "Dashboard" },
    { to: "/app/monitoring", label: "Live Monitoring" },
    { to: "/app/monitoring/demo", label: "Demo / Testing" },
    { to: "/app/detections", label: "Detections & Alerts", badgeKey: "detections" },
    { to: "/app/cases", label: "My Cases" },
    { to: "/app/cases/new", label: "Create Case" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/evidence", label: "Evidence Library" },
    { to: "/app/students", label: "Students" },
    { to: "/app/master-data", label: "Master Data" },
    { to: "/app/reports", label: "Reports" },
    { to: "/app/audit", label: "Audit Trail" },
  ],
  HOD: [
    { to: "/app/dashboard", label: "Dashboard" },
    { to: "/app/monitoring", label: "Live Monitoring" },
    { to: "/app/monitoring/demo", label: "Demo / Testing" },
    {
      to: "/app/cases?status=PENDING",
      label: "Cases for Review",
      badgeKey: "pending",
    },
    {
      to: "/app/cases?status=DEC_REVIEW",
      label: "Forwarded to DEC",
    },
    { to: "/app/cases", label: "All Department Cases" },
    { to: "/app/detections", label: "Detections & Alerts", badgeKey: "detections" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/evidence", label: "Evidence Library" },
    { to: "/app/students", label: "Students Involved" },
    { to: "/app/users", label: "Staff Users" },
    { to: "/app/master-data", label: "Master Data" },
    { to: "/app/reports", label: "Reports" },
    { to: "/app/audit", label: "Audit Trail" },
  ],
  DEC: [
    { to: "/app/dashboard", label: "Dashboard" },
    { to: "/app/monitoring", label: "Live Monitoring" },
    {
      to: "/app/cases?status=DEC_REVIEW",
      label: "Cases Received from HOD",
      badgeKey: "pending",
    },
    {
      to: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
      label: "Forwarded to Exam Dept.",
    },
    { to: "/app/cases", label: "All Department Cases" },
    { to: "/app/detections", label: "Detections & Alerts", badgeKey: "detections" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/evidence", label: "Evidence Library" },
    { to: "/app/students", label: "Students Involved" },
    { to: "/app/reports", label: "Reports" },
    { to: "/app/audit", label: "Audit Trail" },
  ],
  EXAM_DEPARTMENT: [
    { to: "/app/dashboard", label: "Dashboard" },
    { to: "/app/monitoring", label: "Live Monitoring" },
    { to: "/app/monitoring/demo", label: "Demo / Testing" },
    {
      to: "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
      label: "Cases from Departments",
      badgeKey: "pending",
    },
    { to: "/app/result-controls", label: "Result Control" },
    {
      to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
      label: "Forward to Committee",
    },
    { to: "/app/cases", label: "All Cases" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/students", label: "Students" },
    { to: "/app/users", label: "Staff Users" },
    { to: "/app/master-data", label: "Master Data" },
    { to: "/app/reports", label: "Reports" },
    { to: "/app/audit", label: "Audit Trail" },
  ],
  UFM_COMMITTEE: [
    { to: "/app/dashboard", label: "Dashboard" },
    {
      to: "/app/cases?status=UFM_COMMITTEE_REVIEW",
      label: "Cases for Final Review",
      badgeKey: "pending",
    },
    {
      to: "/app/cases?status=APPROVED",
      label: "Committee Decisions",
    },
    { to: "/app/cases", label: "All Committee Cases" },
    { to: "/app/result-controls", label: "Result Holds" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/students", label: "Students Involved" },
    { to: "/app/evidence", label: "Evidence Library" },
    { to: "/app/reports", label: "Reports" },
    { to: "/app/audit", label: "Audit Trail" },
  ],
  STUDENT: [
    { to: "/app/dashboard", label: "Dashboard" },
    { to: "/app/cases", label: "UFM Cases", badgeKey: "pending" },
    { to: "/app/clarification", label: "Submit Clarification" },
    { to: "/app/notifications", label: "Notifications", badgeKey: "notifications" },
    { to: "/app/help", label: "Help & Support" },
  ],
};

export function getNavForRole(role) {
  return NAV_BY_ROLE[role] || NAV_BY_ROLE.INVIGILATOR;
}

export function dashboardTitle(role) {
  const label = ROLE_LABELS[role] || role;
  return `${label} Dashboard`;
}
