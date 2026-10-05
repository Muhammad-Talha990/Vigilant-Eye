import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DonutChart from "../components/DonutChart";
import ErrorBanner from "../components/ErrorBanner";
import KpiCard from "../components/KpiCard";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { countByField } from "../config/dashboardByRole";
import {
  departmentWiseStats,
  semesterWiseStats,
} from "../config/reportStats";
import {
  DETECTION_ROLES,
  OPERATIONAL_AUDIT_ROLES,
  roleIn,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import { downloadCasesCsv, fetchCases, fetchDetections } from "../services/api";

function StatsTable({ title, rows, labelHeader, emptyLabel }) {
  return (
    <section className="portal-card p-4">
      <h2 className="portal-section-title">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{emptyLabel}</p>
      ) : (
        <div className="mt-4 portal-table-wrap">
          <table className="portal-table min-w-0">
            <thead>
              <tr>
                <th>{labelHeader}</th>
                <th className="text-right">UFM cases</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label}>
                  <td className="max-w-[14rem] truncate text-slate-800 sm:max-w-none">
                    {row.label}
                  </td>
                  <td className="text-right font-semibold tabular-nums text-au-navy">
                    {row.count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function ReportsPage() {
  const { user } = useAuth();
  const canDetect = roleIn(user?.role, DETECTION_ROLES);
  const canAudit = roleIn(user?.role, OPERATIONAL_AUDIT_ROLES);
  const [cases, setCases] = useState([]);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        // C27: detections are Invigilator-only after C26-FIX. Do not authorize
        // Reports via DETECTION_ROLES — only enrich the page when permitted.
        const casePromise = fetchCases({ scope: "all" });
        const detectionPromise = canDetect
          ? fetchDetections(true)
          : Promise.resolve([]);
        const results = await Promise.allSettled([
          casePromise,
          detectionPromise,
        ]);
        if (cancelled) return;
        if (results[0].status === "fulfilled" && Array.isArray(results[0].value)) {
          setCases(results[0].value);
        } else {
          setCases([]);
          setError(
            results[0].status === "rejected"
              ? results[0].reason?.message || "Failed to load cases"
              : "Cases response invalid"
          );
          setDetections([]);
          return;
        }
        if (results[1].status === "fulfilled" && Array.isArray(results[1].value)) {
          setDetections(results[1].value);
        } else {
          setDetections([]);
          // Detection enrichment is optional for non-monitor report roles.
          if (canDetect) {
            setError(
              results[1].status === "rejected"
                ? results[1].reason?.message || "Failed to load detections"
                : "Detections response invalid"
            );
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load reports");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canDetect]);

  const statusSegments = useMemo(() => countByField(cases, "status"), [cases]);
  const violationSegments = useMemo(
    () => countByField(cases, "violation_type"),
    [cases]
  );
  const departmentRows = useMemo(() => departmentWiseStats(cases), [cases]);
  const semesterRows = useMemo(() => semesterWiseStats(cases), [cases]);
  const closed = cases.filter(
    (c) => c.status === "APPROVED" || c.status === "REJECTED"
  ).length;

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb="Home / Reports"
        title="Reports and Analytics"
        description={
          canDetect
            ? "Operational reports and examination integrity statistics, including detection summaries."
            : "Operational reports and examination integrity statistics."
        }
        actions={
          <button
            type="button"
            onClick={async () => {
              try {
                setError("");
                await downloadCasesCsv();
              } catch (err) {
                let message = err.message || "CSV export failed";
                try {
                  const parsed = JSON.parse(message);
                  if (parsed?.detail) message = parsed.detail;
                } catch {
                  /* keep raw message */
                }
                setError(message);
              }
            }}
            className="btn-primary"
          >
            Export cases CSV
          </button>
        }
      />

      {error ? (
        <ErrorBanner title="Unable to complete report request." message={error} />
      ) : null}

      {loading ? (
        <LoadingState
          title="Loading report data…"
          detail={
            canDetect
              ? "Retrieving cases and detections for summary charts."
              : "Retrieving cases for summary charts."
          }
        />
      ) : (
        <>
          {!error &&
          cases.length === 0 &&
          (!canDetect || detections.length === 0) ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-600">
              No case records yet. Reports will populate when institutional
              activity is recorded.
            </p>
          ) : null}
          <div
            className={[
              "grid gap-4",
              canDetect ? "sm:grid-cols-3" : "sm:grid-cols-2",
            ].join(" ")}
          >
            <KpiCard
              title="Total Cases"
              value={String(cases.length).padStart(2, "0")}
              hint="All statuses"
              accent="border-l-sky-500"
            />
            <KpiCard
              title="Closed Cases"
              value={String(closed).padStart(2, "0")}
              hint="Approved + rejected"
              accent="border-l-emerald-500"
            />
            {canDetect ? (
              <KpiCard
                title="Confirmed Detections"
                value={String(detections.length).padStart(2, "0")}
                hint="AI alerts saved to DB"
                accent="border-l-orange-500"
              />
            ) : null}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <DonutChart title="Cases by Status" segments={statusSegments} />
            <DonutChart
              title="Violation Distribution"
              segments={violationSegments}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <StatsTable
              title="Department-wise UFM Statistics"
              labelHeader="Department"
              rows={departmentRows}
              emptyLabel="No UFM cases available for department statistics."
            />
            <StatsTable
              title="Semester-wise UFM Statistics"
              labelHeader="Semester"
              rows={semesterRows}
              emptyLabel="No UFM cases available for semester statistics."
            />
          </div>

          <p className="text-sm text-slate-500">
            Drill into{" "}
            <Link to="/app/cases" className="font-semibold text-au-blue">
              Cases
            </Link>
            {canAudit ? (
              <>
                {" "}
                or{" "}
                <Link to="/app/audit" className="font-semibold text-au-blue">
                  Audit Trail
                </Link>
              </>
            ) : null}{" "}
            for detail.
          </p>
        </>
      )}
    </div>
  );
}
