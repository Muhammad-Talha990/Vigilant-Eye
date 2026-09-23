import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import {
  createDraftCaseFromDetection,
  fetchDetections,
  fetchExams,
  fetchStudents,
  markAllDetectionsSeen,
  markDetectionSeen,
} from "../services/api";

export default function DetectionsPage() {
  const navigate = useNavigate();
  const { refreshDetectionsBadge } = useOutletContext() || {};
  const [items, setItems] = useState([]);
  const [students, setStudents] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draftFor, setDraftFor] = useState(null);
  const [studentId, setStudentId] = useState("");
  const [examId, setExamId] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftError, setDraftError] = useState("");
  const [filter, setFilter] = useState("all"); // all | new

  const unseenCount = useMemo(
    () => items.filter((d) => !d.is_seen).length,
    [items]
  );

  const visible = useMemo(() => {
    if (filter === "new") return items.filter((d) => !d.is_seen);
    return items;
  }, [items, filter]);

  async function load({ silent = false } = {}) {
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      const [data, s, e] = await Promise.all([
        fetchDetections(true),
        silent
          ? Promise.resolve(null)
          : fetchStudents().catch(() => []),
        silent ? Promise.resolve(null) : fetchExams().catch(() => []),
      ]);
      setItems(Array.isArray(data) ? data : []);
      if (!silent) {
        setStudents(Array.isArray(s) ? s : []);
        setExams(Array.isArray(e) ? e : []);
        const demo = (s || []).find((st) => st.student_id === "DEMO001");
        setStudentId(
          demo ? String(demo.id) : s?.[0]?.id ? String(s[0].id) : ""
        );
        setExamId(e?.[0]?.id ? String(e[0].id) : "");
      }
      if (refreshDetectionsBadge) await refreshDetectionsBadge();
    } catch (err) {
      if (!silent) setError(err.message || "Failed to load detections");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(() => load({ silent: true }), 4000);
    const onFocus = () => load({ silent: true });
    const onVisible = () => {
      if (document.visibilityState === "visible") onFocus();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshBadge() {
    if (refreshDetectionsBadge) await refreshDetectionsBadge();
  }

  async function onMarkSeen(id) {
    try {
      await markDetectionSeen(id);
      setItems((prev) =>
        prev.map((d) => (d.id === id ? { ...d, is_seen: true } : d))
      );
      await refreshBadge();
    } catch (err) {
      setError(err.message || "Could not mark as seen");
    }
  }

  async function onMarkAllSeen() {
    try {
      await markAllDetectionsSeen();
      setItems((prev) => prev.map((d) => ({ ...d, is_seen: true })));
      await refreshBadge();
    } catch (err) {
      setError(err.message || "Could not mark all as seen");
    }
  }

  async function openDraft(d) {
    if (!d.is_seen) await onMarkSeen(d.id);
    setDraftFor(d);
  }

  async function submitDraft() {
    if (!draftFor) return;
    setDraftError("");
    setBusy(true);
    try {
      if (!draftFor.is_seen) await onMarkSeen(draftFor.id);
      const caseRow = await createDraftCaseFromDetection(draftFor.id, {
        student_id: Number(studentId),
        exam_id: Number(examId),
      });
      setDraftFor(null);
      navigate(`/app/cases/${caseRow.id}`);
    } catch (err) {
      setDraftError(err.message || "Could not create draft case");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Detections & Alerts</p>
          <h1 className="text-2xl font-semibold text-au-navy">
            Detections & Alerts
            <span className="ml-2 align-middle text-[10px] font-bold uppercase tracking-wide text-emerald-700">
              Live
            </span>
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Updates automatically — new alerts appear within a few seconds.
            {unseenCount > 0 ? (
              <span className="ml-1 font-semibold text-rose-600">
                {unseenCount} new
              </span>
            ) : (
              <span className="ml-1 text-slate-500">All caught up.</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold"
          >
            <option value="all">All alerts</option>
            <option value="new">New only</option>
          </select>
          <button
            type="button"
            disabled={unseenCount === 0}
            onClick={onMarkAllSeen}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
          >
            Mark all seen
          </button>
          <Link
            to="/app/monitoring"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Live Monitoring
          </Link>
          <Link
            to="/app/cases/new"
            className="rounded-lg bg-au-blue px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
          >
            Create Case
          </Link>
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
        ) : visible.length === 0 ? (
          <div className="space-y-2 p-6 text-sm text-slate-600">
            <p className="font-semibold text-au-navy">
              {filter === "new" ? "No new detections" : "No confirmed detections"}
            </p>
            <p>
              Start a session on{" "}
              <Link to="/app/monitoring" className="font-semibold text-au-blue">
                Live Monitoring
              </Link>{" "}
              with Persist enabled.
            </p>
          </div>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Camera</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((d) => {
                const isNew = !d.is_seen;
                return (
                  <tr
                    key={d.id}
                    className={[
                      "border-t border-slate-100",
                      isNew ? "bg-rose-50/70" : "bg-white",
                    ].join(" ")}
                  >
                    <td className="px-4 py-3">
                      {isNew ? (
                        <span className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                          New
                        </span>
                      ) : (
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                          Seen
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">{d.id}</td>
                    <td className="px-4 py-3 font-medium text-rose-600">
                      {d.detection_type}
                      {!d.is_confirmed ? (
                        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800">
                          review
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      {(d.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {d.camera_id ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {d.timestamp
                        ? new Date(d.timestamp).toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                      {isNew ? (
                        <button
                          type="button"
                          onClick={() => onMarkSeen(d.id)}
                          className="text-xs font-semibold text-slate-600 hover:underline"
                        >
                          Mark seen
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => openDraft(d)}
                        className="text-xs font-semibold text-au-navy hover:underline"
                      >
                        Create draft case
                      </button>
                      <Link
                        to={`/app/cases/new?detection_id=${d.id}`}
                        onClick={() => {
                          if (isNew) onMarkSeen(d.id);
                        }}
                        className="text-xs font-semibold text-au-blue hover:underline"
                      >
                        File case
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {draftFor ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl space-y-4">
            <h2 className="text-lg font-semibold text-au-navy">
              Draft case from detection #{draftFor.id}
            </h2>
            <p className="text-sm text-slate-600">
              {draftFor.detection_type} ·{" "}
              {(draftFor.confidence * 100).toFixed(1)}% — attaches any auto
              SNAPSHOT/CLIP evidence.
            </p>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Student</span>
              <select
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.student_id} — {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Exam</span>
              <select
                value={examId}
                onChange={(e) => setExamId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                {exams.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.course_code} — {e.course_name}
                  </option>
                ))}
              </select>
            </label>
            {draftError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {draftError}
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDraftFor(null)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !studentId || !examId}
                onClick={submitDraft}
                className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {busy ? "Creating..." : "Create draft"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
