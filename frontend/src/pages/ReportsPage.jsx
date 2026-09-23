import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DonutChart from "../components/DonutChart";
import KpiCard from "../components/KpiCard";
import { countByField } from "../config/dashboardByRole";
import { downloadCasesCsv, fetchCases, fetchDetections } from "../services/api";

export default function ReportsPage() {
  const [cases, setCases] = useState([]);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [c, d] = await Promise.all([
          fetchCases().catch(() => []),
          fetchDetections(true).catch(() => []),
        ]);
        if (cancelled) return;
        setCases(Array.isArray(c) ? c : []);
        setDetections(Array.isArray(d) ? d : []);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load reports");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const statusSegments = useMemo(() => countByField(cases, "status"), [cases]);
  const violationSegments = useMemo(
    () => countByField(cases, "violation_type"),
    [cases]
  );
  const closed = cases.filter(
    (c) => c.status === "APPROVED" || c.status === "REJECTED"
  ).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Home / Reports</p>
          <h1 className="text-2xl font-semibold text-au-navy">Reports</h1>
          <p className="mt-1 text-sm text-slate-600">
            Live summaries from cases and detections. Download a CSV of cases for
            reporting packages; formal PDF output can be added later if required.
          </p>
        </div>
        <button
          type="button"
          onClick={async () => {
            try {
              await downloadCasesCsv();
            } catch (err) {
              setError(err.message || "CSV export failed");
            }
          }}
          className="rounded-lg bg-au-navy px-4 py-2 text-sm font-semibold text-white"
        >
          Export cases CSV
        </button>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-slate-500">Loading report data...</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
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
            <KpiCard
              title="Confirmed Detections"
              value={String(detections.length).padStart(2, "0")}
              hint="AI alerts saved to DB"
              accent="border-l-orange-500"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <DonutChart title="Cases by Status" segments={statusSegments} />
            <DonutChart
              title="Violation Distribution"
              segments={violationSegments}
            />
          </div>

          <p className="text-sm text-slate-500">
            Drill into{" "}
            <Link to="/app/cases" className="font-semibold text-au-blue">
              Cases
            </Link>{" "}
            or{" "}
            <Link to="/app/audit" className="font-semibold text-au-blue">
              Audit Trail
            </Link>{" "}
            for detail.
          </p>
        </>
      )}
    </div>
  );
}
