/**
 * Live Monitoring — production screen.
 * Start Monitoring always enables AI detection + validated incident persistence.
 * Demo/testing controls live on /app/monitoring/demo.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { DEMO_HELPERS_ENABLED } from "../config/demoMode";
import {
  MASTER_DATA_VIEW_ROLES,
  MONITOR_ROLES,
  roleIn,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import {
  fetchAuthConfig,
  fetchCameras,
  fetchLiveStatus,
  liveMjpegUrl,
  startLiveCamera,
  stopLiveCamera,
} from "../services/api";

function aiBadge(status) {
  const map = {
    active: { label: "AI Active", className: "bg-emerald-600" },
    starting: { label: "AI Starting", className: "bg-sky-600" },
    unavailable: { label: "AI Unavailable", className: "bg-slate-500" },
    error: { label: "AI Error", className: "bg-rose-600" },
    idle: { label: "AI Idle", className: "bg-slate-400" },
  };
  return map[status] || map.idle;
}

export default function MonitoringPage() {
  const { user } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [sessions, setSessions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [streamKey, setStreamKey] = useState({});
  const [toast, setToast] = useState("");

  const [demoHelpers, setDemoHelpers] = useState(DEMO_HELPERS_ENABLED);
  const canControl = roleIn(user?.role, MONITOR_ROLES);
  const canDemo = demoHelpers && DEMO_HELPERS_ENABLED && canControl;
  const canOpenExamSetup = roleIn(user?.role, MASTER_DATA_VIEW_ROLES);

  useEffect(() => {
    let cancelled = false;
    fetchAuthConfig()
      .then((cfg) => {
        if (!cancelled) {
          setDemoHelpers(Boolean(cfg?.demo_helpers_enabled));
        }
      })
      .catch(() => {
        if (!cancelled) setDemoHelpers(DEMO_HELPERS_ENABLED);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await fetchLiveStatus();
      const map = {};
      for (const s of status.sessions || []) {
        map[s.camera_id] = s;
      }
      setSessions(map);
      return map;
    } catch {
      return {};
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchCameras();
        if (!cancelled) setCameras(Array.isArray(data) ? data : []);
        await refreshStatus();
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load cameras");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshStatus]);

  useEffect(() => {
    const id = setInterval(refreshStatus, 2500);
    return () => clearInterval(id);
  }, [refreshStatus]);

  const activeCount = useMemo(
    () => Object.values(sessions).filter((s) => s.running).length,
    [sessions]
  );

  if (!canControl) {
    return <Navigate to="/app/dashboard" replace />;
  }

  if (user?.role === "STUDENT") {
    return <Navigate to="/app/help" replace />;
  }

  async function handleStart(cam) {
    setBusyId(cam.id);
    setError("");
    setToast("");
    try {
      const res = await startLiveCamera(cam.id, { mode: "production" });
      setStreamKey((p) => ({ ...p, [cam.id]: Date.now() }));
      // Poll briefly so webcam open failures are not toasted as success
      let map = await refreshStatus();
      for (let i = 0; i < 6; i += 1) {
        const s = map[cam.id];
        if (s?.running || s?.error) break;
        await new Promise((r) => setTimeout(r, 400));
        map = await refreshStatus();
      }
      const s = map[cam.id] || {};
      if (s.error && !s.running) {
        setError(s.error);
        setToast("");
        return;
      }
      if (!s.running && !res.running) {
        setError(
          res.error ||
            "Camera did not start. Check the source in Master Data (try an approved sample clip if no webcam is connected)."
        );
        return;
      }
      const ai = s.ai_status || res.ai_status || "starting";
      setToast(
        `Monitoring started on ${cam.name}. AI: ${ai}${
          s.model_ready || res.model_ready
            ? ""
            : " (model still loading or degraded)"
        }. Validated incidents will save automatically.`
      );
    } catch (err) {
      setError(err.message || "Failed to start monitoring");
    } finally {
      setBusyId(null);
    }
  }

  async function handleStop(cam) {
    setBusyId(cam.id);
    setError("");
    try {
      await stopLiveCamera(cam.id);
      await refreshStatus();
      setToast(`Stopped monitoring ${cam.name}`);
    } catch (err) {
      setError(err.message || "Failed to stop monitoring");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        breadcrumb="Home / Live Monitoring"
        title="Live Examination Monitoring"
        description="Real-time examination feeds, AI-assisted detections, and confirmed monitoring events."
        actions={
          <>
            <div className="portal-card px-4 py-2 text-sm">
              Active:{" "}
              <span className="font-semibold tabular-nums text-au-navy">
                {activeCount}
              </span>
            </div>
            {canDemo ? (
              <Link
                to="/app/monitoring/demo"
                className="btn-secondary btn-sm border-amber-300 bg-amber-50 text-amber-900"
              >
                Demo / Testing Mode
              </Link>
            ) : null}
          </>
        }
      />

      {toast ? (
        <div
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800"
        >
          {toast}
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : null}

      {activeCount > 0 ? (
        <div className="portal-card space-y-2 px-4 py-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            AI engine status
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            {(() => {
              const live = Object.values(sessions).find((s) => s.running);
              if (!live) return <span>No active inference session</span>;
              const ms = live.infer_latency_ms;
              const fps = live.infer_fps;
              return (
                <>
                  <span>
                    Model:{" "}
                    <span className="font-semibold text-slate-800">
                      {live.model_version || live.weights_mode || "—"}
                    </span>
                  </span>
                  <span>
                    Device:{" "}
                    <span className="font-semibold text-slate-800">
                      {live.device || "cpu"}
                    </span>
                  </span>
                  <span>
                    Inference:{" "}
                    <span className="font-semibold text-slate-800">
                      {ms != null ? `${ms} ms` : "—"}
                      {fps != null ? ` · ~${fps} FPS` : ""}
                    </span>
                  </span>
                  <span>
                    Status:{" "}
                    <span className="font-semibold text-slate-800">
                      {aiBadge(live.ai_status || "idle").label}
                    </span>
                  </span>
                </>
              );
            })()}
          </div>
          <p className="text-[11px] text-slate-500">
            Detection confidence is model certainty for the detected class — not
            a measure of student guilt. Confirmed AI events still require human
            review before any UFM case action.
          </p>
        </div>
      ) : null}

      {loading ? (
        <p className="text-slate-500">Loading cameras...</p>
      ) : cameras.length === 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-950 shadow-sm">
          <p className="font-semibold">No cameras registered</p>
          <p className="mt-1">
            {canOpenExamSetup ? (
              <>
                Authorized staff can register cameras under{" "}
                <Link
                  to="/app/master-data"
                  className="font-semibold text-au-blue"
                >
                  Exam Setup
                </Link>
                .
              </>
            ) : (
              <>
                No cameras are registered for monitoring. Ask an authorized
                administrator to provision camera records before starting a
                live session.
              </>
            )}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
          {cameras.map((cam) => {
            const sess = sessions[cam.id];
            const running = Boolean(sess?.running);
            const camFailed =
              Boolean(sess?.error) && !running;
            const busy = busyId === cam.id;
            const mjpeg =
              running &&
              liveMjpegUrl(cam.id, { cacheBust: streamKey[cam.id] || 0 });
            const ai = aiBadge(sess?.ai_status || (running ? "starting" : "idle"));
            const watchHits = (sess?.latest_labels || []).filter(
              (l) => l.decision === "CONFIRM" || l.decision === "REVIEW"
            );
            const hall =
              cam.room_label ||
              sess?.room_label ||
              (cam.room_id ? `Room #${cam.room_id}` : "Hall");
            const camBadge = running
              ? { label: "LIVE", className: "bg-emerald-500" }
              : camFailed
                ? { label: "ERROR", className: "bg-rose-600" }
                : cam.is_active
                  ? { label: "READY", className: "bg-amber-500" }
                  : { label: "OFFLINE", className: "bg-rose-500" };

            return (
              <div
                key={cam.id}
                className="portal-card overflow-hidden"
              >
                <div className="relative flex h-56 items-center justify-center bg-slate-900 text-slate-400">
                  {mjpeg ? (
                    <img
                      src={mjpeg}
                      alt={cam.name}
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <span className="px-4 text-center text-sm">
                      {sess?.error
                        ? sess.error
                        : canControl
                          ? "Not monitoring — press Start Monitoring"
                          : "Not monitoring"}
                    </span>
                  )}
                  <span
                    className={`absolute right-3 top-3 rounded-full px-2 py-0.5 text-[10px] font-bold text-white ${camBadge.className}`}
                  >
                    {camBadge.label}
                  </span>
                  {running || sess?.model_error || sess?.ai_status === "error" ? (
                    <span
                      className={`absolute left-3 top-3 rounded px-2 py-0.5 text-[10px] font-bold text-white ${ai.className}`}
                    >
                      {ai.label}
                    </span>
                  ) : null}
                  {watchHits.length ? (
                    <span
                      className={[
                        "absolute bottom-3 left-3 rounded px-2 py-0.5 text-[10px] font-bold text-white",
                        watchHits.some((l) => l.decision === "CONFIRM")
                          ? "bg-rose-600"
                          : "bg-amber-500",
                      ].join(" ")}
                    >
                      {watchHits.some((l) => l.decision === "CONFIRM")
                        ? "UFM"
                        : "REVIEW"}
                      :{" "}
                      {watchHits
                        .map((l) => l.category || l.label)
                        .slice(0, 3)
                        .join(", ")}
                    </span>
                  ) : null}
                </div>

                <div className="space-y-3 px-4 py-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {hall}
                    </p>
                    <p className="font-semibold text-au-navy">{cam.name}</p>
                    <p className="text-xs text-slate-500">{cam.camera_id}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Source: {cam.source_kind || "configured"}
                      {cam.stream_display ? ` · ${cam.stream_display}` : ""}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Monitoring:{" "}
                      <span className="font-semibold text-slate-700">
                        {sess?.monitoring_status || (running ? "monitoring" : "stopped")}
                      </span>
                      {sess?.weights_mode ? (
                        <span className="ml-2">
                          · weights{" "}
                          <span className="font-semibold text-slate-700">
                            {sess.weights_mode}
                          </span>
                        </span>
                      ) : null}
                      {sess?.infer_latency_ms != null ? (
                        <span className="ml-2">
                          · {sess.infer_latency_ms} ms
                        </span>
                      ) : null}
                      {sess?.persist_error ? (
                        <span className="ml-2 font-semibold text-rose-600">
                          Save failed
                          {sess.pending_persists
                            ? ` (${sess.pending_persists} pending retry)`
                            : ""}
                        </span>
                      ) : null}
                      {sess?.model_error ? (
                        <span className="ml-2 font-semibold text-rose-600">
                          {sess.model_error}
                        </span>
                      ) : null}
                      {running && sess?.posture_engine?.fallback ? (
                        <span className="mt-1 block text-[11px] text-slate-500">
                          Posture: OpenCV fallback (MediaPipe not installed)
                        </span>
                      ) : null}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {canControl ? (
                      running ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStop(cam)}
                          className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
                        >
                          {busy ? "…" : "Stop Monitoring"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={busy || !cam.is_active}
                          onClick={() => handleStart(cam)}
                          className="rounded-lg bg-au-navy px-3 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
                        >
                          {busy ? "Starting…" : "Start Monitoring"}
                        </button>
                      )
                    ) : (
                      <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                        View only
                      </span>
                    )}
                    <Link
                      to="/app/detections"
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Alerts
                    </Link>
                    <Link
                      to="/app/evidence"
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Evidence
                    </Link>
                  </div>

                  {sess?.recent_events?.length ? (
                    <div>
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        Confirmed / review AI events
                      </p>
                      <ul className="max-h-28 space-y-1 overflow-auto rounded-lg bg-slate-50 p-2 text-[11px] text-slate-600">
                        {sess.recent_events
                          .slice()
                          .reverse()
                          .slice(0, 6)
                          .map((ev, i) => (
                            <li key={`${ev.timestamp}-${i}`}>
                              <span
                                className={
                                  ev.decision === "REVIEW"
                                    ? "font-medium text-amber-600"
                                    : "font-medium text-rose-600"
                                }
                              >
                                {ev.decision === "REVIEW"
                                  ? "REVIEW candidate"
                                  : "Confirmed event"}{" "}
                                · {ev.label}
                              </span>{" "}
                              (det. conf. {Number(ev.confidence).toFixed(2)})
                              {ev.persisted_id
                                ? ` · evidence #${ev.persisted_id}`
                                : ev.save_status === "pending"
                                  ? " · saving…"
                                  : ev.save_status === "failed"
                                    ? " · save failed"
                                    : ""}
                              {ev.timestamp ? (
                                <span className="text-slate-400">
                                  {" "}
                                  · {String(ev.timestamp).replace("T", " ")}
                                </span>
                              ) : null}
                            </li>
                          ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
