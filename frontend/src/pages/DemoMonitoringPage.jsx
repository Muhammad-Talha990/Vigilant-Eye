/**
 * Demo / Testing Mode — authorized developers only.
 * Allows YOLO/persist toggles and source overrides.
 * All persisted records are marked is_demo and stay out of production queues.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { MONITOR_ROLES, roleIn } from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import {
  fetchCameras,
  fetchLiveStatus,
  liveMjpegUrl,
  startLiveCamera,
  stopLiveCamera,
} from "../services/api";

const SAMPLE_CLIP = "ai/samples/sample_exam_clip.mp4";

export default function DemoMonitoringPage() {
  const { user } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [sessions, setSessions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [detectById, setDetectById] = useState({});
  const [persistById, setPersistById] = useState({});
  const [overrideById, setOverrideById] = useState({});
  const [streamKey, setStreamKey] = useState({});
  const [toast, setToast] = useState("");

  const allowed = roleIn(user?.role, MONITOR_ROLES);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await fetchLiveStatus();
      const map = {};
      for (const s of status.sessions || []) {
        map[s.camera_id] = s;
      }
      setSessions(map);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!allowed) return undefined;
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
    const id = setInterval(refreshStatus, 2500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [allowed, refreshStatus]);

  const sampleCam = useMemo(
    () =>
      cameras.find((c) =>
        String(c.stream_url || "").includes("sample_exam_clip")
      ) || cameras[0],
    [cameras]
  );

  if (user?.role === "STUDENT") {
    return <Navigate to="/app/help" replace />;
  }
  if (!allowed) {
    return <Navigate to="/app/monitoring" replace />;
  }

  async function handleStart(cam, sourceOverride = null, opts = {}) {
    setBusyId(cam.id);
    setError("");
    setToast("");
    try {
      const detect =
        opts.detect !== undefined ? opts.detect : detectById[cam.id] !== false;
      const persist =
        opts.persist !== undefined
          ? opts.persist
          : Boolean(persistById[cam.id]);
      const override =
        sourceOverride ?? (overrideById[cam.id] || "").trim() || null;
      const res = await startLiveCamera(cam.id, {
        mode: "demo",
        detect,
        persist,
        source_override: override,
      });
      setStreamKey((p) => ({ ...p, [cam.id]: Date.now() }));
      setDetectById((p) => ({ ...p, [cam.id]: detect }));
      setPersistById((p) => ({ ...p, [cam.id]: persist }));
      await refreshStatus();
      setToast(
        `[DEMO] Live on ${cam.name} · detect ${detect ? "on" : "off"} · persist ${
          persist ? "test-only" : "off"
        } · ${res.weights_mode || "—"}`
      );
    } catch (err) {
      setError(err.message || "Failed to start demo session");
    } finally {
      setBusyId(null);
    }
  }

  async function handleStop(cam) {
    setBusyId(cam.id);
    try {
      await stopLiveCamera(cam.id);
      await refreshStatus();
      setToast(`[DEMO] Stopped ${cam.name}`);
    } catch (err) {
      setError(err.message || "Failed to stop");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border-2 border-amber-400 bg-amber-100 px-4 py-3 text-amber-950 shadow-sm">
        <p className="text-sm font-bold uppercase tracking-wide">
          Demo / Testing Mode
        </p>
        <p className="mt-1 text-sm">
          Sessions and saved detections are marked as <strong>test data</strong>.
          They do not enter production case queues, result holds, or institutional
          notification types. Return to{" "}
          <Link to="/app/monitoring" className="font-semibold underline">
            Live Monitoring
          </Link>{" "}
          for exam operations.
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Monitoring / Demo</p>
          <h1 className="text-2xl font-semibold text-au-navy">
            Demo / Testing Controls
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!sampleCam || busyId != null}
            onClick={() =>
              handleStart(sampleCam, SAMPLE_CLIP, {
                detect: true,
                persist: true,
              })
            }
            className="rounded-lg bg-au-blue px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            Sample clip + detect (test persist)
          </button>
          <button
            type="button"
            disabled={!sampleCam || busyId != null}
            onClick={() =>
              handleStart(sampleCam, "webcam:0", {
                detect: true,
                persist: false,
              })
            }
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 disabled:opacity-50"
          >
            Webcam preview (no persist)
          </button>
        </div>
      </div>

      {toast ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {toast}
        </div>
      ) : null}
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-slate-500" role="status">
          Loading demo monitoring…
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cameras.map((cam) => {
            const sess = sessions[cam.id];
            const running = Boolean(sess?.running);
            const detectOn = detectById[cam.id] !== false;
            const persistOn = Boolean(persistById[cam.id]);
            const busy = busyId === cam.id;
            const mjpeg =
              running &&
              liveMjpegUrl(cam.id, { cacheBust: streamKey[cam.id] || 0 });

            return (
              <div
                key={cam.id}
                className="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-sm"
              >
                <div className="relative flex h-52 items-center justify-center bg-slate-900 text-slate-400">
                  {mjpeg ? (
                    <img
                      src={mjpeg}
                      alt={cam.name}
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <span className="text-sm">Demo session stopped</span>
                  )}
                  <span className="absolute left-3 top-3 rounded bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
                    DEMO
                  </span>
                </div>
                <div className="space-y-3 px-4 py-3">
                  <div>
                    <p className="font-semibold text-au-navy">{cam.name}</p>
                    <p className="text-xs text-slate-500">{cam.camera_id}</p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <label className="flex items-center gap-2 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={detectOn}
                        disabled={running || busy}
                        onChange={(e) =>
                          setDetectById((p) => ({
                            ...p,
                            [cam.id]: e.target.checked,
                          }))
                        }
                      />
                      YOLO detect
                    </label>
                    <label className="flex items-center gap-2 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={persistOn}
                        disabled={running || busy}
                        onChange={(e) =>
                          setPersistById((p) => ({
                            ...p,
                            [cam.id]: e.target.checked,
                          }))
                        }
                      />
                      Test-record persist
                    </label>
                  </div>
                  <input
                    className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Override (webcam:0 or ai/samples/...)"
                    value={overrideById[cam.id] || ""}
                    disabled={running || busy}
                    onChange={(e) =>
                      setOverrideById((p) => ({
                        ...p,
                        [cam.id]: e.target.value,
                      }))
                    }
                  />
                  <div className="flex flex-wrap gap-2">
                    {running ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => handleStop(cam)}
                        className="rounded bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                      >
                        Stop
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStart(cam)}
                          className="rounded bg-au-blue px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                        >
                          Start demo
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStart(cam, "webcam:0")}
                          className="rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold"
                        >
                          Webcam
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStart(cam, SAMPLE_CLIP)}
                          className="rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold"
                        >
                          Sample clip
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
