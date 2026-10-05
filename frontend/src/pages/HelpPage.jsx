import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { MONITOR_ROLES, roleIn } from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";

const STUDENT_GUIDELINES = [
  "Submit a clarification when prompted — only one clarification is accepted per case.",
  "Provide accurate information — false statements may adversely affect the case.",
  "All portal communications are recorded in the audit trail.",
  "Students may view linked cases and submit clarifications; camera monitoring is not available.",
  "Contact the department office if a listed case cannot be accessed.",
];

const STUDENT_FAQ = [
  {
    q: "What information is shown for a UFM case?",
    a: "Cases linked to the student profile display current status, examination details, evidence on record, submitted clarification, and result-control status when a hold applies. Staff review actions such as Forward, Return, Approve, or Reject are not available to students.",
  },
  {
    q: "How is the current case status identified?",
    a: "Open the case from UFM Case Status. The status label shows the stage in the UFM review workflow — for example Pending, Under Review, DEC Review, Exam Department Review, UFM Committee Review, Approved, or Rejected.",
  },
  {
    q: "Can a clarification be submitted for a case?",
    a: "Yes, when the case is linked to the student account and a clarification has not already been submitted. Use Clarification / Required Actions, or open the case and follow the clarification prompt. The written statement is recorded on that case.",
  },
  {
    q: "Can clarification be submitted more than once?",
    a: "No. Each case allows one clarification. After submission, it remains on the case record and the portal will not accept another submission for the same case.",
  },
  {
    q: "What happens after clarification is submitted?",
    a: "The clarification is saved on the case and relevant staff are notified. Submission does not by itself finalize the case. Check case status and Notifications for updates as the review proceeds.",
  },
];

const STAFF_GUIDELINES = [
  "Live Monitoring and Detections are Invigilator-only operational tools.",
  "Invigilators file UFM cases and upload evidence; reviewing roles verify and advance the workflow.",
  "Use Demo / Testing Mode only for development trials; demo records stay out of production case queues.",
  "Confirm detections before filing cases; draft case from a detection attaches saved evidence when available.",
  "Digital sign-off (typed name + acknowledgment) is required on case create and reviews.",
  "All portal actions are recorded in the audit trail appropriate to the signed-in role.",
];

const ADMIN_GUIDELINES = [
  "This workspace manages portal authorization — users, roles, import, and administrative audit.",
  "Administrators do not perform operational UFM monitoring, case review, or result-hold actions.",
  "Use Admin Audit Log for security/admin events; operational staff use the separate Audit Trail.",
  "Google authenticates identity; VigilantEye database roles control access.",
];

const STAFF_FAQ = [
  {
    q: "What is digital sign-off?",
    a: "Staff type their full name and acknowledge a certificate checkbox. This is an auditable acknowledgment (name + timestamp), not a PKI e-signature.",
  },
  {
    q: "How does live monitoring create evidence?",
    a: "In normal monitoring, validated incidents (after temporal confirmation) save automatically with a JPEG snapshot and short clip when buffered. Raw frame predictions are not saved as cases. Draft/create case attaches that evidence.",
  },
  {
    q: "Who can use Live Monitoring?",
    a: "Invigilator only. HOD, DEC, Exam Department, UFM Committee, Students, and Administrators cannot operate live monitoring.",
  },
  {
    q: "What is Demo / Testing Mode?",
    a: "An authorized screen with YOLO/persist toggles and source overrides. Saved demo detections are marked is_demo and never enter production case queues or institutional notifications.",
  },
  {
    q: "Why does AI show Error or Unavailable while video plays?",
    a: "Camera connection and AI health are separate. A live feed alone does not mean detection is active — check the AI status badge on each card.",
  },
];

const ADMIN_FAQ = [
  {
    q: "Can I open UFM cases or monitoring?",
    a: "No. Administrator is isolated from operational UFM pages. Use Users, Import, Roles, Admin Audit, and System screens.",
  },
  {
    q: "Where is the audit log?",
    a: "Administrators use Security and Audit at /app/admin/audit. Operational staff use /app/audit.",
  },
];

export default function HelpPage() {
  const { user } = useAuth();
  const role = user?.role || "";
  const isStudent = role === "STUDENT";
  const isAdmin = role === "ADMINISTRATOR";
  const canMonitor = roleIn(role, MONITOR_ROLES);
  const guidelines = isStudent
    ? STUDENT_GUIDELINES
    : isAdmin
      ? ADMIN_GUIDELINES
      : STAFF_GUIDELINES;
  const faq = isStudent ? STUDENT_FAQ : isAdmin ? ADMIN_FAQ : STAFF_FAQ;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        breadcrumb="Home / Help and Guidance"
        title="Help and Guidance"
        description="Reference information for using the VigilantEye examination integrity system."
      />

      <section className="portal-card overflow-hidden">
        <div className="bg-au-navy px-5 py-3">
          <h2 className="font-semibold text-white">
            {isStudent
              ? "Student guidelines"
              : isAdmin
                ? "Administrator guidelines"
                : "Important guidelines"}
          </h2>
        </div>
        <ol className="list-decimal space-y-3 px-5 py-4 pl-10 text-sm text-slate-700">
          {guidelines.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>

      {!isStudent ? (
        <section className="portal-card p-5">
          <h2 className="portal-section-title">Quick links</h2>
          <p className="mt-1 text-sm text-slate-500">
            Shortcuts to pages available for this role.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            {isAdmin ? (
              <>
                <Link to="/app/admin/dashboard" className="btn-secondary">
                  Admin Dashboard
                </Link>
                <Link to="/app/admin/users" className="btn-secondary">
                  Manage Users
                </Link>
                <Link to="/app/admin/audit" className="btn-secondary">
                  Admin Audit
                </Link>
              </>
            ) : (
              <Link to="/app/cases" className="btn-secondary">
                UFM Cases
              </Link>
            )}
            {canMonitor ? (
              <Link to="/app/monitoring" className="btn-secondary">
                Live Monitoring
              </Link>
            ) : null}
            <Link to="/app/notifications" className="btn-secondary">
              Notifications
            </Link>
            <Link
              to={isAdmin ? "/app/admin/dashboard" : "/app/dashboard"}
              className="btn-secondary"
            >
              Dashboard
            </Link>
          </div>
        </section>
      ) : null}

      <section className="portal-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="portal-section-title">FAQ</h2>
        </div>
        <ul className="divide-y divide-slate-100">
          {faq.map((item) => (
            <li key={item.q} className="px-5 py-4">
              <p className="font-medium text-au-navy">{item.q}</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                {item.a}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
