import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const STUDENT_GUIDELINES = [
  "Respond to clarification requests within 3 working days when notified.",
  "Provide accurate information — false statements may worsen the case.",
  "All portal communications are recorded in the audit trail.",
  "You can view your own cases and submit clarifications; you cannot access camera monitoring.",
  "Contact your department office if you cannot access a listed case.",
];

const STUDENT_FAQ = [
  {
    q: "Why do I see a UFM case?",
    a: "Staff filed a case linked to your student record (manually or after an AI detection review). You can view its status and submit a clarification.",
  },
  {
    q: "Can I see Live Monitoring?",
    a: "No. Live Monitoring is for invigilators and authorized staff only. Students use Cases, Clarification, and Notifications.",
  },
  {
    q: "Who reads my clarification?",
    a: "HOD and the reporting invigilator are notified. Further reviewers can also see case history.",
  },
  {
    q: "Can I delete a clarification?",
    a: "Not in this release. Clarifications remain on record for audit integrity.",
  },
];

const STAFF_GUIDELINES = [
  "Use Live Monitoring for authorized exam halls. Start Monitoring enables AI detection and validated incident saving automatically.",
  "Configure camera sources (webcam, RTSP, approved sample clip) in Master Data — not on the monitoring cards.",
  "Use Demo / Testing Mode only for development trials; demo records stay out of production case queues.",
  "Confirm detections before filing cases; prefer draft case from detections when evidence is attached.",
  "Digital sign-off (typed name + acknowledgment) is required on case create and reviews.",
  "All portal actions are recorded in the audit trail.",
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
    a: "Invigilator, HOD, and Exam Department can start/stop sessions. DEC can view Live Monitoring status. Students cannot access camera streams.",
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

export default function HelpPage() {
  const { user } = useAuth();
  const isStudent = user?.role === "STUDENT";
  const guidelines = isStudent ? STUDENT_GUIDELINES : STAFF_GUIDELINES;
  const faq = isStudent ? STUDENT_FAQ : STAFF_FAQ;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-sm text-slate-500">Home / Help & Support</p>
        <h1 className="text-2xl font-semibold text-au-navy">Help & Support</h1>
        <p className="mt-1 text-sm text-slate-600">
          {isStudent
            ? "Guidance for students using the UFM portal."
            : "Guidance for staff using the UFM portal."}
        </p>
      </div>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-au-navy px-5 py-3">
          <h2 className="font-semibold text-white">Important Guidelines</h2>
        </div>
        <ul className="space-y-3 px-5 py-4 text-sm text-slate-700">
          {guidelines.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-au-blue" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold text-au-navy">Quick Links</h2>
        <div className="mt-3 flex flex-wrap gap-3">
          <Link
            to="/app/cases"
            className="rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-medium text-sky-800"
          >
            {isStudent ? "My Cases" : "Cases"}
          </Link>
          {isStudent ? (
            <Link
              to="/app/clarification"
              className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-800"
            >
              Submit Clarification
            </Link>
          ) : (
            <Link
              to="/app/monitoring"
              className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800"
            >
              Live Monitoring
            </Link>
          )}
          <Link
            to="/app/notifications"
            className="rounded-lg border border-violet-300 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-800"
          >
            Notifications
          </Link>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-au-navy">FAQ</h2>
        </div>
        <ul className="divide-y divide-slate-100">
          {faq.map((item) => (
            <li key={item.q} className="px-5 py-4 text-sm">
              <p className="font-semibold text-au-navy">{item.q}</p>
              <p className="mt-1 text-slate-600">{item.a}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
