import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ActionNavCard from "../components/ActionNavCard";
import CaseQueueTable from "../components/CaseQueueTable";
import DonutChart from "../components/DonutChart";
import ErrorBanner from "../components/ErrorBanner";
import KpiCard from "../components/KpiCard";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import PageShell from "../components/PageShell";
import SectionPanel from "../components/SectionPanel";
import StatusBadge from "../components/StatusBadge";
import {
  ACTION_TONES,
  buildRoleKpis,
  casesForRoleQueue,
  dashboardIntro,
  queueMetaForRole,
  quickActionsForRole,
  statusChartSegments,
  violationChartSegments,
} from "../config/dashboardByRole";
import { formatViolationLabel } from "../config/casePresentation";
import { apiDateTimeMs, formatDateTime } from "../config/dateTime";
import { destinationForNotification } from "../config/notificationPresentation";
import { dashboardTitle } from "../config/navByRole";
import {
  DETECTION_ROLES,
  MONITOR_ROLES,
  roleIn,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import {
  fetchAdminUserStats,
  fetchCameras,
  fetchCases,
  fetchDetections,
  fetchNotifications,
  fetchResultControls,
  markNotificationRead,
} from "../services/api";

function formatWhen(iso) {
  if (!iso) return "—";
  return formatDateTime(iso) || "—";
}

function actionHintFor(action, isPrimary) {
  if (!action?.label) return "Open →";
  const label = action.label.toLowerCase();
  if (
    label.includes("create ufm") ||
    label.includes("report ufm") ||
    (label.includes("incident") && action.to === "/app/cases/new")
  )
    return "Report a new UFM incident →";
  if (label.includes("pending") || label.includes("cases for review"))
    return "Review pending cases →";
  if (label.includes("final")) return "Open final review →";
  if (label.includes("department queue") || label.includes("processing"))
    return "Process department cases →";
  if (label.includes("dec review") || label.includes("received"))
    return "Review DEC queue →";
  if (label.includes("queue") || label.includes("review"))
    return "Open review queue →";
  if (label.includes("all ufm") || label === "all cases" || label.includes("my cases"))
    return "View all cases →";
  if (label.includes("case") && !label.includes("pending") && !label.includes("create"))
    return "View cases →";
  if (label.includes("evidence")) return "Review evidence →";
  if (label.includes("reports")) return "Open reports →";
  if (label.includes("audit")) return "View audit history →";
  if (label.includes("result")) return "Manage result holds →";
  if (label.includes("detection")) return "View detections →";
  if (label.includes("monitor")) return "Open live monitoring →";
  if (label.includes("clarification")) return "Submit required actions →";
  if (label.includes("notification")) return "Open inbox →";
  if (label.includes("help")) return "Open help →";
  if (isPrimary) return "Go to primary task →";
  return "Open →";
}

function PrimaryActions({ role, actions }) {
  if (!actions?.length) return null;
  const primary =
    role === "INVIGILATOR"
      ? actions.find((a) => a.to === "/app/cases/new")
      : role === "HOD"
        ? actions.find((a) => a.to.includes("scope=active"))
        : role === "DEC"
          ? actions.find((a) => a.to.includes("DEC_REVIEW"))
          : role === "EXAM_DEPARTMENT"
            ? actions.find((a) => a.to.includes("EXAM_DEPARTMENT"))
            : role === "UFM_COMMITTEE"
              ? actions.find((a) => a.to.includes("UFM_COMMITTEE"))
              : role === "STUDENT"
                ? actions.find((a) => a.to === "/app/clarification")
                : actions[0];

  const rest = actions.filter((a) => a !== primary);

  return (
    <section aria-label="Primary actions">
      <div className="portal-action-strip">
        <p className="portal-action-strip-label">Actions</p>
        {primary ? (
          <ActionNavCard
            to={primary.to}
            label={primary.label}
            hint={actionHintFor(primary, true)}
            primary
          />
        ) : null}
        {rest.slice(0, 4).map((a) => (
          <ActionNavCard
            key={`${a.to}-${a.label}`}
            to={a.to}
            label={a.label}
            hint={actionHintFor(a, false)}
          />
        ))}
      </div>
    </section>
  );
}

export default function DashboardHome() {
  const { user } = useAuth();
  const role = user?.role || "INVIGILATOR";
  const isStudent = role === "STUDENT";
  const canMonitor = roleIn(role, MONITOR_ROLES);
  const canDetect = roleIn(role, DETECTION_ROLES);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cases, setCases] = useState([]);
  const [detections, setDetections] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [unread, setUnread] = useState([]);
  const [resultControls, setResultControls] = useState([]);
  const [adminStats, setAdminStats] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        if (role === "ADMINISTRATOR") {
          const [stats, unreadData] = await Promise.all([
            fetchAdminUserStats(),
            fetchNotifications(true).catch(() => []),
          ]);
          if (cancelled) return;
          setAdminStats(stats || null);
          setCases([]);
          setDetections([]);
          setCameras([]);
          setUnread(Array.isArray(unreadData) ? unreadData : []);
          setResultControls([]);
          return;
        }

        const needResults =
          role === "EXAM_DEPARTMENT" || role === "UFM_COMMITTEE";

        const [caseData, detectionData, cameraData, unreadData, resultData] =
          await Promise.all([
            fetchCases({ scope: "dashboard" }),
            canDetect
              ? fetchDetections(true).catch(() => [])
              : Promise.resolve([]),
            canMonitor ? fetchCameras().catch(() => []) : Promise.resolve([]),
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
      } catch {
        if (!cancelled) {
          setError("Unable to load dashboard data. Please try again.");
          setCases([]);
          setDetections([]);
          setCameras([]);
          setUnread([]);
          setResultControls([]);
          setAdminStats(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [role, canDetect, canMonitor]);

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
        adminStats,
      }),
    [role, cases, detections, cameras, unread, resultControls, user?.id, adminStats]
  );

  const queueMeta = useMemo(() => queueMetaForRole(role), [role]);

  const queueCases = useMemo(
    () => casesForRoleQueue(cases, role, user?.id).slice(0, 8),
    [cases, role, user?.id]
  );

  const statusSegments = useMemo(() => statusChartSegments(cases), [cases]);
  const violationSegments = useMemo(
    () => violationChartSegments(cases),
    [cases]
  );

  const casesById = useMemo(() => {
    const map = {};
    for (const c of cases) map[c.id] = c;
    return map;
  }, [cases]);

  const recentDetections = detections.slice(0, 6);
  const actions = quickActionsForRole(role);
  const showHolds =
    role === "EXAM_DEPARTMENT" || role === "UFM_COMMITTEE";
  const showCharts =
    !isStudent &&
    role !== "ADMINISTRATOR" &&
    (role === "EXAM_DEPARTMENT" ||
      role === "UFM_COMMITTEE" ||
      role === "HOD" ||
      role === "DEC");
  const showCaseQueue = role !== "ADMINISTRATOR";
  const showSecondaryQueues =
    role === "DEC" ||
    role === "EXAM_DEPARTMENT" ||
    role === "HOD" ||
    role === "UFM_COMMITTEE";

  const activeHolds = resultControls.filter((r) => r.result_status === "HELD");
  const releasedHolds = resultControls.filter(
    (r) => r.result_status === "RELEASED"
  );

  return (
    <PageShell>
      <PageHeader
        breadcrumb="Home / Dashboard"
        title={dashboardTitle(role)}
        description={dashboardIntro(role)}
        actions={
          <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 tabular-nums">
            {new Date().toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </div>
        }
      />

      {error ? (
        <ErrorBanner
          title="Unable to load dashboard data."
          message={error}
          onRetry={() => window.location.reload()}
        />
      ) : null}

      {loading ? <LoadingState label="Loading dashboard…" /> : null}

      {!loading && !error ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {kpiCards.map((card) => (
              <KpiCard key={card.title} {...card} />
            ))}
          </div>

          <PrimaryActions role={role} actions={actions} />

          {isStudent && queueCases.length > 0 ? (
            <div className="portal-callout flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm">
                <strong>{queueCases.length}</strong> open UFM case
                {queueCases.length === 1 ? "" : "s"} require attention.
                Clarification may be submitted where applicable.
              </p>
              <Link to="/app/clarification" className="btn-primary btn-sm">
                Clarification / Required Actions
              </Link>
            </div>
          ) : null}

          {role === "ADMINISTRATOR" && adminStats ? (
            <SectionPanel
              title="Role breakdown"
              description="Authorized portal accounts by role. Google identity alone never grants access."
            >
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(adminStats.by_role || {}).map(([r, n]) => (
                  <div
                    key={r}
                    className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      {r.replaceAll("_", " ")}
                    </p>
                    <p className="text-xl font-semibold tabular-nums text-au-navy">
                      {n}
                    </p>
                  </div>
                ))}
              </div>
            </SectionPanel>
          ) : null}

          {canMonitor || canDetect ? (
            <div
              className={[
                "grid gap-4",
                canMonitor && canDetect ? "xl:grid-cols-3" : "",
              ].join(" ")}
            >
              {canMonitor ? (
                <SectionPanel
                  className={canDetect ? "xl:col-span-2" : ""}
                  title="Examination monitoring"
                  description="Registered cameras available for live monitoring."
                  actions={
                    <Link to="/app/monitoring" className="btn-ghost btn-sm">
                      Open Live Monitoring
                    </Link>
                  }
                >
                  {cameras.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      No cameras are registered yet.
                      {role === "INVIGILATOR" ? (
                        <> Contact an administrator to register cameras.</>
                      ) : null}
                    </p>
                  ) : (
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {cameras.slice(0, 6).map((cam) => (
                        <Link
                          key={cam.id}
                          to="/app/monitoring"
                          className="portal-media-nav"
                          data-affordance="interactive"
                          aria-label={`Go live on ${cam.name || cam.camera_id}`}
                        >
                          <div className="flex h-24 flex-col items-center justify-center gap-1 px-3 text-center text-slate-400">
                            <span className="text-xs font-medium text-slate-300">
                              {cam.name}
                            </span>
                            <span className="text-[10px] font-semibold text-sky-300">
                              Go live →
                            </span>
                          </div>
                          <div className="flex items-center justify-between bg-white px-3 py-2 text-sm">
                            <div className="min-w-0">
                              <p className="truncate font-medium text-au-navy">
                                {cam.camera_id}
                              </p>
                            </div>
                            <span
                              className={[
                                "shrink-0 rounded px-2 py-0.5 text-[10px] font-bold text-white",
                                cam.is_active ? "bg-emerald-600" : "bg-rose-500",
                              ].join(" ")}
                            >
                              {cam.is_active ? "READY" : "OFF"}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </SectionPanel>
              ) : null}

              {canDetect ? (
                <SectionPanel
                  title="Recent detections"
                  actions={
                    <Link to="/app/detections" className="btn-ghost btn-sm">
                      View all
                    </Link>
                  }
                >
                  {recentDetections.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      No confirmed detections yet. Use Live Monitoring to capture
                      incidents.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {recentDetections.map((d) => (
                        <li
                          key={d.id}
                          className="portal-info-row"
                          data-affordance="static"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm font-semibold text-au-navy">
                              {formatViolationLabel(d.detection_type)}
                            </p>
                            {!d.is_seen ? (
                              <span className="rounded bg-rose-500 px-1.5 text-[10px] font-bold text-white">
                                NEW
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            Confidence{" "}
                            {(Number(d.confidence || 0) * 100).toFixed(0)}% ·{" "}
                            {formatWhen(d.timestamp)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionPanel>
              ) : null}
            </div>
          ) : null}

          {showCaseQueue ? (
            <div
              className={["grid gap-4", showHolds ? "xl:grid-cols-2" : ""].join(
                " "
              )}
            >
              <CaseQueueTable
                title={queueMeta.title}
                cases={queueCases}
                emptyLabel={queueMeta.empty}
                actionLabel={queueMeta.action}
                viewAllTo={queueMeta.viewAll}
              />

              {showHolds ? (
                <SectionPanel
                  title="Result holds"
                  description={`${activeHolds.length} on hold · ${releasedHolds.length} released — student result restrictions linked to Approved UFM cases`}
                  actions={
                    <Link
                      to="/app/result-controls"
                      className="btn-ghost btn-sm"
                    >
                      Open Result Controls →
                    </Link>
                  }
                  bodyClassName="p-0"
                >
                  {activeHolds.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-slate-500">
                      No students currently have an active result hold.
                    </p>
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {activeHolds.slice(0, 8).map((r) => {
                        const linked = casesById[r.case_id];
                        const name =
                          r.student_name ||
                          linked?.student_name ||
                          `Student #${r.student_id}`;
                        const roll =
                          r.student_roll || linked?.student_roll || null;
                        const caseNo =
                          r.case_number ||
                          linked?.case_number ||
                          `Case #${r.case_id}`;
                        return (
                          <li key={r.id} className="px-5 py-3 text-sm">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="min-w-0">
                                <p className="font-semibold text-au-navy">
                                  {name}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {roll ? `Roll ${roll} · ` : ""}
                                  <Link
                                    to={`/app/cases/${r.case_id}`}
                                    className="text-au-blue hover:underline"
                                  >
                                    {caseNo}
                                  </Link>
                                </p>
                              </div>
                              <StatusBadge status={r.result_status} />
                            </div>
                            {r.reason ? (
                              <p className="mt-1 line-clamp-2 text-slate-600">
                                {r.reason}
                              </p>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </SectionPanel>
              ) : null}
            </div>
          ) : null}

          {showCharts ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <DonutChart
                title="UFM cases by status"
                segments={statusSegments}
                emptyLabel="No UFM cases yet — status distribution will appear here."
              />
              <DonutChart
                title="Violation type distribution"
                segments={violationSegments}
                emptyLabel="No violation data yet."
              />
            </div>
          ) : null}

          {showSecondaryQueues ? (
            role === "HOD" || role === "DEC" ? (
              role === "HOD" ? (
                <CaseQueueTable
                  title="Recent UFM cases"
                  cases={[...cases]
                    .sort(
                      (a, b) =>
                        (apiDateTimeMs(b.created_at) || 0) -
                        (apiDateTimeMs(a.created_at) || 0)
                    )
                    .slice(0, 6)}
                  emptyLabel="No recent UFM activity."
                  actionLabel="Open"
                  viewAllTo="/app/cases"
                />
              ) : (
                <CaseQueueTable
                  title="Closed / decided"
                  cases={cases
                    .filter(
                      (c) =>
                        c.status === "APPROVED" || c.status === "REJECTED"
                    )
                    .slice(0, 6)}
                  emptyLabel="No final decisions yet."
                  actionLabel="Open"
                  viewAllTo="/app/cases"
                />
              )
            ) : (
              <div className="grid gap-4 xl:grid-cols-2">
                {role === "EXAM_DEPARTMENT" ? (
                  <>
                    <CaseQueueTable
                      title="At UFM Committee"
                      cases={cases
                        .filter((c) => c.status === "UFM_COMMITTEE_REVIEW")
                        .slice(0, 6)}
                      emptyLabel="Nothing forwarded to committee yet."
                      actionLabel="Open"
                      viewAllTo="/app/cases?status=UFM_COMMITTEE_REVIEW"
                    />
                    <CaseQueueTable
                      title="Closed / decided"
                      cases={cases
                        .filter(
                          (c) =>
                            c.status === "APPROVED" || c.status === "REJECTED"
                        )
                        .slice(0, 6)}
                      emptyLabel="No final decisions yet."
                      actionLabel="Open"
                    />
                  </>
                ) : null}
                {role === "UFM_COMMITTEE" ? (
                  <>
                    <CaseQueueTable
                      title="Approved decisions"
                      cases={cases
                        .filter((c) => c.status === "APPROVED")
                        .slice(0, 6)}
                      emptyLabel="No approved decisions yet."
                      actionLabel="Open"
                      viewAllTo="/app/cases?status=APPROVED"
                    />
                    <CaseQueueTable
                      title="Rejected cases"
                      cases={cases
                        .filter((c) => c.status === "REJECTED")
                        .slice(0, 6)}
                      emptyLabel="No rejected decisions yet."
                      actionLabel="Open"
                    />
                  </>
                ) : null}
              </div>
            )
          ) : null}

          {unread.length > 0 ? (
            <SectionPanel
              title="Unread notifications"
              actions={
                <Link to="/app/notifications" className="btn-ghost btn-sm">
                  Open inbox
                </Link>
              }
              bodyClassName="p-0"
            >
              <ul className="divide-y divide-slate-100">
                {unread.slice(0, 5).map((n) => {
                  const dest =
                    destinationForNotification(n, role) || "/app/notifications";
                  return (
                    <li key={n.id}>
                      <Link
                        to={dest}
                        onClick={() => {
                          if (!n.is_read) {
                            markNotificationRead(n.id).catch(() => {});
                          }
                        }}
                        className="portal-option flex items-start justify-between gap-3 px-5 py-3 text-sm hover:bg-sky-200 focus-visible:bg-sky-200"
                        data-affordance="interactive"
                      >
                        <span className="min-w-0">
                          <p className="font-medium text-au-navy">{n.title}</p>
                          <p className="line-clamp-2 text-slate-600">
                            {n.message}
                          </p>
                          {n.case_number ? (
                            <p className="mt-1 text-xs text-au-blue">
                              {n.case_number}
                            </p>
                          ) : null}
                        </span>
                        <span
                          className="shrink-0 text-au-blue"
                          aria-hidden="true"
                        >
                          →
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </SectionPanel>
          ) : (
            <div className="rounded-md border border-dashed border-slate-200 bg-white/60 px-4 py-4 text-sm text-slate-500">
              No unread notifications.
            </div>
          )}

          {isStudent ? (
            <SectionPanel title="Student guidelines">
              <ul className="space-y-2 text-sm text-slate-700">
                <li>Respond promptly when notified about a UFM case.</li>
                <li>
                  Provide accurate information — clarifications become part of
                  the case record.
                </li>
                <li>
                  Refer to Help and Guidance if a listed case is not visible.
                </li>
              </ul>
              <div className="mt-4">
                <Link to="/app/help" className="btn-secondary btn-sm">
                  Open Help and Guidance
                </Link>
              </div>
            </SectionPanel>
          ) : null}

          {/* Secondary shortcuts for remaining actions beyond primary strip */}
          {actions.length > 5 ? (
            <SectionPanel
              title="Additional pages"
              description="Further portal pages available for this role."
            >
              <div className="flex flex-wrap gap-2">
                {actions.slice(5).map((a) => (
                  <Link
                    key={`${a.to}-${a.label}`}
                    to={a.to}
                    className={`rounded-md border px-3 py-1.5 text-sm font-medium ${ACTION_TONES[a.tone] || ACTION_TONES.slate}`}
                  >
                    {a.label}
                  </Link>
                ))}
              </div>
            </SectionPanel>
          ) : null}
        </>
      ) : null}
    </PageShell>
  );
}
