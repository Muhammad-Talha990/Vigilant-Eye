import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  createCase,
  fetchDetections,
  fetchEvidence,
  fetchExams,
  fetchStudents,
  loadEvidenceObjectUrl,
  openEvidenceFile,
  downloadEvidenceFile,
} from "../services/api";
import { useAuth } from "../context/AuthContext";

const VIOLATION_TYPES = [
  "MOBILE_PHONE",
  "SMART_WATCH",
  "NOTES_PAPER",
  "ELECTRONIC_GADGET",
  "SUSPICIOUS_OBJECT",
  "OTHER",
];

function mapDetectionToViolation(detectionType) {
  const t = String(detectionType || "").toLowerCase();
  if (t.includes("phone") || t.includes("cell")) return "MOBILE_PHONE";
  if (t.includes("watch")) return "SMART_WATCH";
  if (t.includes("note") || t.includes("paper") || t.includes("book")) {
    return "NOTES_PAPER";
  }
  if (t.includes("remote") || t.includes("laptop") || t.includes("tablet")) {
    return "ELECTRONIC_GADGET";
  }
  return "MOBILE_PHONE";
}

export default function CreateCasePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const detectionId = searchParams.get("detection_id");
  const [students, setStudents] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [detection, setDetection] = useState(null);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [previews, setPreviews] = useState({}); // id -> { url, mime }
  const [evidenceStatus, setEvidenceStatus] = useState(""); // loading | ready | empty
  const [form, setForm] = useState({
    student_id: "",
    exam_id: "",
    violation_type: "MOBILE_PHONE",
    description: "",
    remarks: "",
    signer_name: user?.name || "",
    signature_ack: false,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, e] = await Promise.all([fetchStudents(), fetchExams()]);
        if (cancelled) return;
        setStudents(Array.isArray(s) ? s : []);
        setExams(Array.isArray(e) ? e : []);

        let linkedDetection = null;
        if (detectionId) {
          const all = await fetchDetections(false).catch(() => []);
          linkedDetection = (all || []).find(
            (d) => String(d.id) === String(detectionId)
          );
          if (!cancelled) setDetection(linkedDetection || null);
        }

        const demoStudent = (s || []).find((st) => st.student_id === "DEMO001");
        const linkedStudentId =
          linkedDetection?.student_id != null
            ? String(linkedDetection.student_id)
            : null;

        setForm((prev) => ({
          ...prev,
          student_id:
            linkedStudentId ||
            (demoStudent
              ? String(demoStudent.id)
              : s?.[0]?.id
                ? String(s[0].id)
                : ""),
          exam_id: e?.[0]?.id ? String(e[0].id) : "",
          signer_name: prev.signer_name || user?.name || "",
          violation_type: linkedDetection
            ? mapDetectionToViolation(linkedDetection.detection_type)
            : prev.violation_type,
          description: detectionId
            ? `Case filed from confirmed AI detection #${detectionId}${
                linkedDetection
                  ? ` (${linkedDetection.detection_type}, conf ${(
                      linkedDetection.confidence * 100
                    ).toFixed(0)}%).`
                  : "."
              }`
            : prev.description,
        }));
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load form data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [detectionId, user?.name]);

  // Load auto evidence for linked detection; retry briefly if still generating
  useEffect(() => {
    if (!detectionId) return undefined;

    let cancelled = false;
    let attempt = 0;
    const objectUrls = [];
    let retryTimer = null;

    async function loadOnce() {
      setEvidenceStatus((prev) => (prev === "ready" ? prev : "loading"));
      try {
        const rows = await fetchEvidence(null, detectionId);
        if (cancelled) return false;
        const list = Array.isArray(rows) ? rows : [];
        setEvidenceItems(list);

        if (list.length === 0) {
          setEvidenceStatus("empty");
          return false;
        }

        const next = {};
        for (const ev of list) {
          try {
            // Prefer /file (works even if /preview route not loaded); preview tried first inside helper
            const { url, mime } = await loadEvidenceObjectUrl(ev.id, {
              preview: true,
            });
            if (cancelled) {
              URL.revokeObjectURL(url);
              continue;
            }
            objectUrls.push(url);
            next[ev.id] = { url, mime };
          } catch {
            // keep metadata; Open full / Download still work
          }
        }
        if (!cancelled) {
          setPreviews((prev) => {
            Object.values(prev).forEach((p) => {
              if (p?.url) URL.revokeObjectURL(p.url);
            });
            return next;
          });
          setEvidenceStatus("ready");
        }
        return true;
      } catch {
        if (!cancelled) setEvidenceStatus("empty");
        return false;
      }
    }

    (async () => {
      const ok = await loadOnce();
      if (ok || cancelled) return;
      retryTimer = setInterval(async () => {
        attempt += 1;
        const found = await loadOnce();
        if (found || attempt >= 6 || cancelled) {
          clearInterval(retryTimer);
          retryTimer = null;
        }
      }, 2000);
    })();

    return () => {
      cancelled = true;
      if (retryTimer) clearInterval(retryTimer);
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [detectionId]);

  function onChange(event) {
    const { name, value, type, checked } = event.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    if (!form.signature_ack) {
      setError("You must acknowledge the digital sign-off certificate.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createCase({
        student_id: Number(form.student_id),
        exam_id: Number(form.exam_id),
        violation_type: form.violation_type,
        description: form.description.trim(),
        remarks: form.remarks.trim() || null,
        detection_id: detectionId ? Number(detectionId) : null,
        signer_name: form.signer_name.trim(),
        signature_ack: true,
      });
      navigate(`/app/cases/${created.id}`);
    } catch (err) {
      setError(err.message || "Could not create case");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-slate-500">Loading form...</p>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <p className="text-sm text-slate-500">Home / Cases / Create</p>
        <h1 className="text-2xl font-semibold text-au-navy">Create UFM Case</h1>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {students.length === 0 || exams.length === 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Add at least one student and one exam under Master Data before creating
          a case.
        </div>
      ) : detectionId ? (
        <div className="space-y-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
          <p>
            Linking confirmed detection <strong>#{detectionId}</strong>
            {detection ? (
              <>
                {" "}
                — {detection.detection_type.replaceAll("_", " ")} (
                {(detection.confidence * 100).toFixed(0)}%
                {detection.camera_id != null
                  ? ` · camera ${detection.camera_id}`
                  : ""}
                )
              </>
            ) : null}
            . Review the auto evidence below, identify the student, then complete
            the form.
          </p>

          {evidenceStatus === "loading" ? (
            <p className="text-xs text-sky-700">Loading evidence preview…</p>
          ) : null}
          {evidenceStatus === "empty" ? (
            <p className="text-xs text-amber-800">
              No snapshot/clip yet for this detection. It may still be generating
              — wait a few seconds and refresh, or file the case and attach
              evidence later.
            </p>
          ) : null}

          {evidenceItems.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {evidenceItems.map((ev) => {
                const preview = previews[ev.id];
                const isImage = preview?.mime?.startsWith("image/");
                const isVideo = preview?.mime?.startsWith("video/");
                return (
                  <div
                    key={ev.id}
                    className="overflow-hidden rounded-lg border border-sky-200 bg-white"
                  >
                    <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-1.5">
                      <span className="text-xs font-semibold uppercase tracking-wide text-au-navy">
                        {ev.evidence_type}
                      </span>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          className="text-xs font-semibold text-au-blue hover:underline"
                          onClick={async () => {
                            try {
                              await openEvidenceFile(ev.id);
                            } catch (err) {
                              setError(err.message || "Could not open evidence");
                            }
                          }}
                        >
                          Open full
                        </button>
                        <button
                          type="button"
                          className="text-xs font-semibold text-slate-700 hover:underline"
                          onClick={async () => {
                            try {
                              await downloadEvidenceFile(ev.id);
                            } catch (err) {
                              setError(
                                err.message || "Could not download evidence"
                              );
                            }
                          }}
                        >
                          Download
                        </button>
                      </div>
                    </div>                    <div className="bg-slate-100">
                      {isImage ? (
                        <button
                          type="button"
                          className="block w-full"
                          title="Click to open full size"
                          onClick={async () => {
                            try {
                              await openEvidenceFile(ev.id);
                            } catch (err) {
                              setError(err.message || "Could not open evidence");
                            }
                          }}
                        >
                          <img
                            src={preview.url}
                            alt={`${ev.evidence_type} from detection ${detectionId}`}
                            className="max-h-56 w-full object-contain"
                          />
                        </button>
                      ) : isVideo ? (
                        <video
                          src={preview.url}
                          controls
                          className="max-h-56 w-full bg-black"
                        />
                      ) : (
                        <div className="flex h-28 items-center justify-center px-3 text-center text-xs text-slate-600">
                          Preview unavailable in-browser. Use{" "}
                          <span className="font-semibold">Open full</span> or{" "}
                          <span className="font-semibold">Download</span>.
                        </div>                      )}
                    </div>
                    {ev.confidence != null ? (
                      <p className="px-3 py-1 text-[11px] text-slate-500">
                        Confidence {(ev.confidence * 100).toFixed(0)}%
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Student</span>
          <select
            name="student_id"
            required
            value={form.student_id}
            onChange={onChange}
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
          >
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.student_id} — {s.name} ({s.department})
              </option>
            ))}
          </select>
          {detectionId ? (
            <span className="mt-1 block text-xs text-slate-500">
              Use the snapshot/clip above to confirm which student is shown, then
              select them here.
            </span>
          ) : null}
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Exam</span>
          <select
            name="exam_id"
            required
            value={form.exam_id}
            onChange={onChange}
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
          >
            {exams.map((e) => (
              <option key={e.id} value={e.id}>
                {e.course_code} — {e.course_name} ({e.exam_date})
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Violation type
          </span>
          <select
            name="violation_type"
            value={form.violation_type}
            onChange={onChange}
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
          >
            {VIOLATION_TYPES.map((v) => (
              <option key={v} value={v}>
                {v.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Description
          </span>
          <textarea
            name="description"
            required
            rows={4}
            value={form.description}
            onChange={onChange}
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
            placeholder="Describe the incident..."
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Remarks (optional)
          </span>
          <textarea
            name="remarks"
            rows={2}
            value={form.remarks}
            onChange={onChange}
            className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5"
          />
        </label>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
          <p className="text-sm font-semibold text-au-navy">Digital sign-off</p>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">
              Full name (typed signature)
            </span>
            <input
              name="signer_name"
              required
              minLength={2}
              value={form.signer_name}
              onChange={onChange}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5"
              placeholder="Type your full name"
            />
          </label>
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              name="signature_ack"
              checked={form.signature_ack}
              onChange={onChange}
              className="mt-1"
            />
            <span>
              I certify that the information in this UFM case is accurate to the
              best of my knowledge (auditable acknowledgment, not PKI).
            </span>
          </label>
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting || !students.length || !exams.length}
            className="rounded-xl bg-au-navy px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {submitting ? "Creating..." : "Create Case"}
          </button>
          <Link
            to="/app/cases"
            className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
