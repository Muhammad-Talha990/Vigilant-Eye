import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchCases, fetchEvidence, openEvidenceFile, downloadEvidenceFile, uploadEvidence } from "../services/api";

export default function EvidencePage() {
  const [searchParams] = useSearchParams();
  const presetCaseId = searchParams.get("case_id") || "";

  const [items, setItems] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    case_id: presetCaseId,
    evidence_type: "SNAPSHOT",
    seat_location: "",
    confidence: "",
    file: null,
  });

  const caseOptions = useMemo(() => cases, [cases]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [evidence, caseList] = await Promise.all([
        fetchEvidence(presetCaseId || null),
        fetchCases(),
      ]);
      setItems(Array.isArray(evidence) ? evidence : []);
      setCases(Array.isArray(caseList) ? caseList : []);
      setForm((prev) => ({
        ...prev,
        case_id: prev.case_id || presetCaseId || (caseList?.[0]?.id ? String(caseList[0].id) : ""),
      }));
    } catch (err) {
      setError(err.message || "Failed to load evidence");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [presetCaseId]);

  async function onSubmit(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (!form.file) {
      setError("Choose a file to upload");
      return;
    }
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("case_id", form.case_id);
      body.append("evidence_type", form.evidence_type);
      body.append("file", form.file);
      if (form.seat_location.trim()) {
        body.append("seat_location", form.seat_location.trim());
      }
      if (form.confidence !== "") {
        body.append("confidence", form.confidence);
      }
      await uploadEvidence(body);
      setMessage("Evidence uploaded successfully.");
      setForm((prev) => ({ ...prev, file: null, seat_location: "", confidence: "" }));
      await load();
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-slate-500">Home / Evidence Library</p>
        <h1 className="text-2xl font-semibold text-au-navy">Evidence Library</h1>
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

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h2 className="font-semibold text-au-navy">Upload Evidence</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Case</span>
            <select
              required
              value={form.case_id}
              onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}
              className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
            >
              {caseOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} — {c.violation_type}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Type</span>
            <select
              value={form.evidence_type}
              onChange={(e) =>
                setForm((p) => ({ ...p, evidence_type: e.target.value }))
              }
              className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
            >
              <option value="SNAPSHOT">SNAPSHOT</option>
              <option value="VIDEO_CLIP">VIDEO_CLIP</option>
              <option value="DOCUMENT">DOCUMENT</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">
              Seat (optional)
            </span>
            <input
              value={form.seat_location}
              onChange={(e) =>
                setForm((p) => ({ ...p, seat_location: e.target.value }))
              }
              className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
              placeholder="A12"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">
              Confidence (optional)
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={form.confidence}
              onChange={(e) =>
                setForm((p) => ({ ...p, confidence: e.target.value }))
              }
              className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
              placeholder="0.91"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-slate-700">File</span>
            <input
              type="file"
              required
              onChange={(e) =>
                setForm((p) => ({ ...p, file: e.target.files?.[0] || null }))
              }
              className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={submitting || !caseOptions.length}
          className="rounded-xl bg-au-navy px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {submitting ? "Uploading..." : "Upload Evidence"}
        </button>
      </form>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-au-navy">Evidence Files</h2>
        </div>
        {loading ? (
          <p className="p-5 text-slate-500">Loading...</p>
        ) : items.length === 0 ? (
          <p className="p-5 text-slate-500">No evidence yet.</p>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">File</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{e.id}</td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/app/cases/${e.case_id}`}
                      className="font-medium text-au-blue"
                    >
                      #{e.case_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{e.evidence_type}</td>
                  <td className="max-w-[12rem] truncate px-4 py-3 text-xs text-slate-600">
                    {e.file_path}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {e.created_at
                      ? new Date(e.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        className="text-xs font-semibold text-au-blue hover:underline"
                        onClick={async () => {
                          try {
                            await openEvidenceFile(e.id);
                          } catch (err) {
                            setError(err.message || "Could not open file");
                          }
                        }}
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-slate-700 hover:underline"
                        onClick={async () => {
                          try {
                            await downloadEvidenceFile(e.id);
                          } catch (err) {
                            setError(err.message || "Could not download file");
                          }
                        }}
                      >
                        Download
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
