import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { fetchCases } from "../services/api";

export default function CasesPage() {
  const { user } = useAuth();
  const isStudent = user?.role === "STUDENT";
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") || "";

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchCases();
        if (!cancelled) setItems(Array.isArray(data) ? data : []);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load cases");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!statusFilter) return items;
    return items.filter((c) => c.status === statusFilter);
  }, [items, statusFilter]);

  const statuses = useMemo(() => {
    const set = new Set(items.map((c) => c.status));
    return [...set].sort();
  }, [items]);

  function onStatusChange(value) {
    if (!value) {
      setSearchParams({});
    } else {
      setSearchParams({ status: value });
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Cases</p>
          <h1 className="text-2xl font-semibold text-au-navy">
            {isStudent ? "My UFM Cases" : "UFM Cases"}
          </h1>
          {statusFilter ? (
            <p className="mt-1 text-sm text-slate-600">
              Filtered by status:{" "}
              <span className="font-semibold text-au-navy">{statusFilter}</span>
            </p>
          ) : null}
          {isStudent ? (
            <p className="mt-1 text-sm text-slate-500">
              Showing cases for the student profile linked to your login.
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Status
            <select
              value={statusFilter}
              onChange={(e) => onStatusChange(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">All</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          {isStudent ? (
            <Link
              to="/app/clarification"
              className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
            >
              Submit Clarification
            </Link>
          ) : (
            <Link
              to="/app/cases/new"
              className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
            >
              Create Case
            </Link>
          )}
        </div>
      </div>
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-slate-500">Loading...</p>
        ) : filtered.length === 0 ? (
          <div className="space-y-3 p-8 text-center">
            <p className="text-lg font-semibold text-au-navy">No cases yet</p>
            <p className="text-sm text-slate-600">
              {isStudent
                ? "When staff files a case for your linked roll, it appears here."
                : "Create a case manually or draft one from a confirmed detection."}
            </p>
            {!isStudent ? (
              <div className="flex flex-wrap justify-center gap-2">
                <Link
                  to="/app/cases/new"
                  className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
                >
                  Create Case
                </Link>
                <Link
                  to="/app/detections"
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
                >
                  View Detections
                </Link>
              </div>
            ) : (
              <Link
                to="/app/help"
                className="inline-flex rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                Help & Guidelines
              </Link>
            )}
          </div>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Case No.</th>
                <th className="px-4 py-3">Violation</th>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Exam / Room</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-medium text-au-navy">
                    {c.case_number}
                  </td>
                  <td className="px-4 py-3">{c.violation_type}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium">
                      {c.student_name || "—"}
                    </div>
                    <div className="text-xs text-slate-500">
                      {c.student_roll || c.student_id}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    <div>{c.exam_course_code || "—"}</div>
                    <div className="text-xs text-slate-500">
                      {c.room_number ? `Room ${c.room_number}` : ""}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {c.created_at
                      ? new Date(c.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/app/cases/${c.id}`}
                      className="font-semibold text-au-blue hover:underline"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
