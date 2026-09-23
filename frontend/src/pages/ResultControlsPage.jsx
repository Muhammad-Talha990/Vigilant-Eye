import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import { fetchResultControls, releaseResultControl } from "../services/api";

export default function ResultControlsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchResultControls();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load result controls");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onRelease(id) {
    setMessage("");
    setError("");
    setBusyId(id);
    try {
      await releaseResultControl(id);
      setMessage(`Released control #${id}`);
      await load();
    } catch (err) {
      setError(err.message || "Release failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-slate-500">Home / Result Control</p>
        <h1 className="text-2xl font-semibold text-au-navy">Result Control</h1>
        <p className="mt-1 text-sm text-slate-600">
          Holds applied when a case is APPROVED (or created manually). Exam
          Dept / UFM can release.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-slate-500">Loading...</p>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Result</th>
                <th className="px-4 py-3">Transcript</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-slate-600" colSpan={7}>
                    <p className="font-semibold text-au-navy">No result holds yet</p>
                    <p className="mt-1 text-sm">
                      Holds appear automatically when a case is{" "}
                      <strong>APPROVED</strong> by the UFM Committee.
                    </p>
                    <Link
                      to="/app/cases"
                      className="mt-3 inline-flex rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
                    >
                      View cases
                    </Link>
                  </td>
                </tr>
              ) : (
                items.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="px-4 py-3">{r.id}</td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/app/cases/${r.case_id}`}
                        className="font-medium text-au-blue"
                      >
                        #{r.case_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{r.student_id}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.result_status} />
                    </td>
                    <td className="px-4 py-3">{r.transcript_status}</td>
                    <td className="max-w-xs truncate px-4 py-3 text-slate-600">
                      {r.reason}
                    </td>
                    <td className="px-4 py-3">
                      {r.result_status === "RELEASED" ? (
                        <span className="text-xs text-slate-400">Released</span>
                      ) : (
                        <button
                          type="button"
                          disabled={busyId === r.id}
                          onClick={() => onRelease(r.id)}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                        >
                          {busyId === r.id ? "..." : "Release"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
