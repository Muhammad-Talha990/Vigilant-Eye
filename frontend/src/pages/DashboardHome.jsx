import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import CaseQueueTable from "../components/CaseQueueTable";
import DonutChart from "../components/DonutChart";
import KpiCard from "../components/KpiCard";
import StatusBadge from "../components/StatusBadge";
import {
  ACTION_TONES,
  buildRoleKpis,
  casesForRoleQueue,
  countByField,
  quickActionsForRole,
} from "../config/dashboardByRole";
import { dashboardTitle } from "../config/navByRole";
import { useAuth } from "../context/AuthContext";
import {
  fetchCameras,
  fetchCases,
  fetchDetections,
  fetchNotifications,
  fetchResultControls,
} from "../services/api";

function formatWhen(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function DashboardHome() {
  const { user } = useAuth();
  const role = user?.role || "INVIGILATOR";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cases, setCases] = useState([]);
  const [detections, setDetections] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [unread, setUnread] = useState([]);
  const [resultControls, setResultControls] = useState([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const needResults = [
          "EXAM_DEPARTMENT",
          "UFM_COMMITTEE",
          "HOD",
          "DEC",
        ].includes(role);

        const [caseData, detectionData, cameraData, unreadData, resultData] =
          await Promise.all([
            fetchCases().catch(() => []),
            fetchDetections(true).catch(() => []),
            fetchCameras().catch(() => []),
            fetchNotifications(true).catch(() => []),
            needResults
              ? fetchResultControls().catch(() => [])
              : Promise.resolve([]),
          ]);

        if (cancelled) return;
        setCases(Array.isArray(caseData) ? caseData : []);
        setDetections(Array.isArray(detectionData) ? detectionData : []);
        setCameras(Array.isArray(cameraData) ? cameraData : []);
        setUnread(Array.isArray(unreadData) ? unreadData : []);
        setResultControls(Array.isArray(resultData) ? resultData : []);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load dashboard");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [role]);

  const kpiCards = useMemo(
    () =>
      buildRoleKpis({
        role,
        cases,
        detections,
        cameras,
        unread,
        resultControls,
        userId: user?.id,
      }),
    [role, cases, detections, cameras, unread, resultControls, user?.id]
  );

  const queueCases = useMemo(
    () => casesForRoleQueue(cases, role, user?.id).slice(0, 8),
    [cases, role, user?.id]
  );

  const statusSegments = useMemo(() => countByField(cases, "status"), [cases]);
  const violationSegments = useMemo(
    () => countByField(cases, "violation_type"),
    [cases]
  );

  const recentDetections = detections.slice(0, 6);
  const actions = quickActionsForRole(role);
  const showCameras = role === "INVIGILATOR" || role === "HOD";
  const showDetections =
    role === "INVIGILATOR" || role === "HOD" || role === "DEC";
  const showHolds =
    role === "EXAM_DEPARTMENT" || role === "UFM_COMMITTEE";

  const queueTitle =
    role === "INVIGILATOR"
      ? "My Open Cases"
      : role === "STUDENT"
        ? "My UFM Cases"
        : "Your Review Queue";

  const queueAction =
    role === "HOD"
      ? "Review"
      : role === "DEC"
        ? "Investigate"
        : role === "UFM_COMMITTEE"
          ? "Decide"
          : "Open";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Dashboard</p>
          <h1 className="text-2xl font-semibold text-au-navy">
            {dashboardTitle(role)}
          </h1>
          <p className="mt-1 text-slate-600">
            Welcome back, {user?.name}. Live data shaped for your role.
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
          {new Date().toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-slate-500">Loading dashboard...</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {kpiCards.map((card) => (
              <KpiCard key={card.title} {...card} />
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <DonutChart
              title="Cases by Status"
              segments={statusSegments}
              emptyLabel="No cases yet — create one to populate charts."
            />
            <DonutChart
              title="Violation Type Distribution"
              segments={violationSegments}
              emptyLabel="No violation data yet."
            />
          </div>

          {showCameras ? (
            <div className="grid gap-4 xl:grid-cols-3">
              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-2">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-au-navy">
                    Registered Cameras
                  </h2>
                  <Link
                    to="/app/monitoring"
                    className="text-xs font-semibold text-au-blue"
                  >
                    Open Live Monitoring
                  </Link>
                </div>
                {cameras.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No cameras yet. Run{" "}
                    <code className="rounded bg-slate-100 px-1 text-xs">
                      python seed_demo_cameras.py
                    </code>{" "}
                    or add them in Master Data, then open{" "}
                    <Link
                      to="/app/monitoring"
                      className="font-semibold text-au-blue"
                    >
                      Live Monitoring
                    </Link>
                    .
                  </p>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {cameras.slice(0, 6).map((cam) => (
                      <Link
                        key={cam.id}
                        to="/app/monitoring"
                        className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900 transition hover:ring-2 hover:ring-au-blue/40"
                      >
                        <div className="flex h-28 flex-col items-center justify-center gap-1 bg-gradient-to-br from-slate-800 to-slate-950 px-3 text-center text-slate-400">
                          <span className="text-xs font-medium text-slate-300">
                            {cam.name}
                          </span>
                          <span className="text-[10px] text-slate-500">
                            Go live →
                          </span>
                        </div>
                        <div className="flex items-center justify-between bg-white px-3 py-2 text-sm">
                          <div>
                            <p className="font-medium text-au-navy">
                              {cam.camera_id}
                            </p>
                            <p className="truncate text-xs text-slate-500">
                              {cam.stream_url}
                            </p>
                          </div>
                          <span
                            className={[
                              "rounded-full px-2 py-0.5 text-[10px] font-bold text-white",
                              cam.is_active ? "bg-emerald-500" : "bg-rose-500",
                            ].join(" ")}
                          >
                            {cam.is_active ? "READY" : "OFF"}
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </section>

              {showDetections ? (
                <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-au-navy">
                      Real-time Alerts
                    </h2>
                    <Link
                      to="/app/detections"
                      className="text-xs font-semibold text-au-blue"
                    >
                      View all
                    </Link>
                  </div>
                  {recentDetections.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      No confirmed detections yet. Run{" "}
                      <Link
                        to="/app/monitoring"
                        className="font-semibold text-au-blue"
                      >
                        Live Monitoring
                      </Link>{" "}
                      with Persist checked.
                    </p>
                  ) : (
                    <ul className="space-y-3">
                      {recentDetections.map((d) => (
                        <li
                          key={d.id}
                          className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm font-semibold text-rose-600">
                              {d.detection_type}
                            </p>
                            <span className="rounded bg-rose-500 px-1.5 text-[10px] font-bold text-white">
                              NEW
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            conf {(d.confidence * 100).toFixed(0)}% · frame{" "}
                            {d.frame_index ?? "—"}
                          </p>
                          <p className="text-xs text-slate-400">
                            {formatWhen(d.timestamp)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              ) : null}
            </div>
          ) : null}

          <div
            className={[
              "grid gap-4",
              showHolds ? "xl:grid-cols-2" : "",
            ].join(" ")}
          >
            <CaseQueueTable
              title={queueTitle}
              cases={queueCases}
              actionLabel={queueAction}
            />

            {showHolds ? (
              <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                  <h2 className="font-semibold text-au-navy">Result Holds</h2>
                  <Link
                    to="/app/result-controls"
                    className="text-xs font-semibold text-au-blue"
                  >
                    Manage
                  </Link>
                </div>
                {resultControls.length === 0 ? (
                  <p className="px-4 py-4 text-sm text-slate-500">
                    No holds yet. Approving a case auto-creates one.
                  </p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {resultControls.slice(0, 8).map((r) => (
                      <li key={r.id} className="px-4 py-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium text-au-navy">
                            Case #{r.case_id} · Student #{r.student_id}
                          </p>
                          <StatusBadge status={r.result_status} />
                        </div>
                        <p className="mt-1 text-slate-600">{r.reason}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ) : null}
          </div>

          {role === "DEC" || role === "EXAM_DEPARTMENT" ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <CaseQueueTable
                title={
                  role === "DEC"
                    ? "Forwarded to Exam Dept."
                    : "At UFM Committee"
                }
                cases={cases
                  .filter((c) =>
                    role === "DEC"
                      ? c.status === "EXAM_DEPARTMENT_REVIEW"
                      : c.status === "UFM_COMMITTEE_REVIEW"
                  )
                  .slice(0, 6)}
                emptyLabel="Nothing forwarded yet"
                actionLabel="Open"
              />
              <CaseQueueTable
                title="Closed / Decided"
                cases={cases
                  .filter(
                    (c) => c.status === "APPROVED" || c.status === "REJECTED"
                  )
                  .slice(0, 6)}
                emptyLabel="No final decisions yet"
                actionLabel="Open"
              />
            </div>
          ) : null}

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="font-semibold text-au-navy">Quick Actions</h2>
            <div className="mt-3 flex flex-wrap gap-3">
              {actions.map((a) => (
                <Link
                  key={`${a.to}-${a.label}`}
                  to={a.to}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium ${ACTION_TONES[a.tone] || ACTION_TONES.slate}`}
                >
                  {a.label}
                </Link>
              ))}
            </div>
          </section>

          {unread.length > 0 ? (
            <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <h2 className="font-semibold text-au-navy">
                  Recent Notifications
                </h2>
                <Link
                  to="/app/notifications"
                  className="text-xs font-semibold text-au-blue"
                >
                  Open
                </Link>
              </div>
              <ul className="divide-y divide-slate-100">
                {unread.slice(0, 5).map((n) => (
                  <li key={n.id}>
                    <Link
                      to={
                        n.case_id
                          ? `/app/cases/${n.case_id}`
                          : "/app/notifications"
                      }
                      className="block px-4 py-3 text-sm hover:bg-slate-50"
                    >
                      <p className="font-medium text-au-navy">{n.title}</p>
                      <p className="line-clamp-2 text-slate-600">{n.message}</p>
                      {n.case_number ? (
                        <p className="mt-1 text-xs text-au-blue">{n.case_number}</p>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {role === "STUDENT" ? (
            <>
              {cases.length > 0 ? (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-200 bg-sky-50 px-5 py-4">
                  <p className="text-sm text-sky-900">
                    You have {cases.length} UFM case
                    {cases.length === 1 ? "" : "s"}. Submit a clarification if
                    you need to explain your side.
                  </p>
                  <Link
                    to="/app/clarification"
                    className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
                  >
                    Submit Clarification
                  </Link>
                </div>
              ) : null}
              <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="bg-au-navy px-5 py-3">
                  <h2 className="font-semibold text-white">
                    Important Guidelines
                  </h2>
                </div>
                <ul className="space-y-2 px-5 py-4 text-sm text-slate-700">
                  <li>Respond within 3 working days when notified.</li>
                  <li>Provide accurate information — statements are audited.</li>
                  <li>
                    Use Help & Support if you cannot see an expected case.
                  </li>
                </ul>
                <div className="border-t border-slate-100 px-5 py-3">
                  <Link
                    to="/app/help"
                    className="text-sm font-semibold text-au-blue"
                  >
                    Open Help & Support →
                  </Link>
                </div>
              </section>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
