import { formatStatusLabel } from "../config/casePresentation";

const STATUS_STYLES = {
  PENDING: "bg-amber-100 text-amber-900 ring-amber-200",
  UNDER_REVIEW: "bg-sky-100 text-sky-900 ring-sky-200",
  DEC_REVIEW: "bg-violet-100 text-violet-900 ring-violet-200",
  EXAM_DEPARTMENT_REVIEW: "bg-indigo-100 text-indigo-900 ring-indigo-200",
  UFM_COMMITTEE_REVIEW: "bg-fuchsia-100 text-fuchsia-900 ring-fuchsia-200",
  APPROVED: "bg-emerald-100 text-emerald-900 ring-emerald-200",
  REJECTED: "bg-rose-100 text-rose-900 ring-rose-200",
  HELD: "bg-amber-100 text-amber-900 ring-amber-200",
  RELEASED: "bg-emerald-100 text-emerald-900 ring-emerald-200",
  BLOCKED: "bg-rose-100 text-rose-900 ring-rose-200",
  ALLOWED: "bg-emerald-100 text-emerald-900 ring-emerald-200",
  SUBMITTED: "bg-sky-100 text-sky-900 ring-sky-200",
  CLOSED: "bg-slate-200 text-slate-800 ring-slate-300",
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || "bg-slate-100 text-slate-800 ring-slate-200";
  const label = formatStatusLabel(status);
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${style}`}
      title={label}
    >
      {label}
    </span>
  );
}
