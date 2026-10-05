import { formatDateTime } from "../config/dateTime";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import {
  formatAuditActionLabel,
  formatEntityTypeLabel,
  formatRoleLabel,
} from "../config/casePresentation";
import {
  OPERATIONAL_AUDIT_ROLES,
} from "../config/roleAccess";
import { useAuth } from "../context/AuthContext";
import { downloadAuditLogsCsv, fetchAuditLogs } from "../services/api";

const CAN_VIEW = new Set(OPERATIONAL_AUDIT_ROLES);

export default function AuditTrailPage() {
  const { user } = useAuth();
  const canView = CAN_VIEW.has(user?.role);

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [entityFilter, setEntityFilter] = useState("");
  const [query, setQuery] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!canView) {
      setLoading(false);
      setError("Your role cannot view the audit trail.");
      return undefined;
    }
    (async () => {
      setLoading(true);
      setError("");
      try {
        const data = await fetchAuditLogs();
        if (!cancelled) setItems(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) {
          setError("Unable to load audit trail. Please try again.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canView]);

  const actions = useMemo(() => {
    const set = new Set(items.map((i) => i.action).filter(Boolean));
    return [...set].sort();
  }, [items]);

  const entityTypes = useMemo(() => {
    const set = new Set(items.map((i) => i.entity_type).filter(Boolean));
    return [...set].sort();
  }, [items]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((row) => {
      if (actionFilter && row.action !== actionFilter) return false;
      if (entityFilter && row.entity_type !== entityFilter) return false;
      if (!q) return true;
      const hay = [
        row.action,
        row.entity_type,
        row.description,
        String(row.user_id ?? ""),
        String(row.entity_id ?? ""),
        row.user_role,
        formatRoleLabel(row.user_role),
        formatAuditActionLabel(row.action),
        formatEntityTypeLabel(row.entity_type),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, actionFilter, entityFilter, query]);

  function entityCell(row) {
    const label = formatEntityTypeLabel(row.entity_type);
    if (row.entity_id == null) return label;
    if (row.entity_type === "ufm_case") {
      return (
        <span>
          {label}{" "}
          <Link
            to={`/app/cases/${row.entity_id}`}
            className="font-medium text-au-blue hover:underline"
          >
            #{row.entity_id}
          </Link>
        </span>
      );
    }
    return (
      <span>
        {label} <span className="text-slate-500">#{row.entity_id}</span>
      </span>
    );
  }

  async function onExportCsv() {
    setExporting(true);
    setError("");
    try {
      await downloadAuditLogsCsv({
        action: actionFilter,
        entity_type: entityFilter,
        q: query,
      });
    } catch (err) {
      setError(err.message || "Unable to export audit CSV.");
    } finally {
      setExporting(false);
    }
  }

  if (!canView && !loading) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">Audit trail is not available</p>
        <p className="mt-1">
          This administrative log is limited to HOD, DEC, Exam Department, and
          UFM Committee roles.
        </p>
        <Link
          to="/app/dashboard"
          className="mt-3 inline-flex text-sm font-semibold text-au-blue"
        >
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumb="Home / Audit Trail"
        title="Audit Trail"
        description="Recorded system activity, workflow actions, and case history."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <p className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              {filtered.length} of {items.length} events
            </p>
            <button
              type="button"
              disabled={exporting || loading}
              onClick={onExportCsv}
              className="btn-primary"
            >
              {exporting ? "Exporting…" : "Export CSV"}
            </button>
          </div>
        }
      />

      {error ? (
        <ErrorBanner
          title="Unable to load audit trail."
          message={error}
          onRetry={() => {
            setLoading(true);
            setError("");
            fetchAuditLogs()
              .then((data) => setItems(Array.isArray(data) ? data : []))
              .catch(() =>
                setError("Unable to load audit trail. Please try again.")
              )
              .finally(() => setLoading(false));
          }}
        />
      ) : null}

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="audit-search">
          Search audit trail
        </label>
        <input
          id="audit-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search action, entity, description, ids…"
          className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          aria-label="Filter by action"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {formatAuditActionLabel(a)}
            </option>
          ))}
        </select>
        <select
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          aria-label="Filter by entity"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All entities</option>
          {entityTypes.map((t) => (
            <option key={t} value={t}>
              {formatEntityTypeLabel(t)}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <LoadingState
            compact
            title="Loading audit trail…"
            detail="Retrieving historical administrative events."
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No audit events to show"
            detail={
              items.length === 0
                ? "No audit records are available for this role yet."
                : "No audit events match the current filters."
            }
            actions={
              actionFilter || entityFilter || query ? (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setActionFilter("");
                    setEntityFilter("");
                    setQuery("");
                  }}
                >
                  Clear filters
                </button>
              ) : null
            }
          />
        ) : (
          <>
            <div className="portal-data-cards">
              {filtered.map((row) => (
                <div key={row.id} className="portal-case-card" data-affordance="static">
                  <div className="flex items-start justify-between gap-2">
                    <p className="portal-case-card-title">
                      {formatAuditActionLabel(row.action)}
                    </p>
                    <span className="text-xs text-slate-500">
                      {row.timestamp
                        ? formatDateTime(row.timestamp)
                        : "—"}
                    </span>
                  </div>
                  <p className="portal-case-card-meta">
                    {formatRoleLabel(row.user_role)} · {entityCell(row)}
                  </p>
                  {row.entity_type === "ufm_case" && row.entity_id != null ? (
                    <p className="portal-case-card-meta">
                      <Link
                        to={`/app/cases/${row.entity_id}`}
                        className="font-medium text-au-blue hover:underline"
                      >
                        Case #{row.entity_id}
                      </Link>
                    </p>
                  ) : null}
                  <details className="mt-2 text-sm text-slate-700">
                    <summary className="cursor-pointer font-medium text-au-navy">
                      Details
                    </summary>
                    <p className="mt-1 whitespace-pre-wrap break-words">
                      {row.description || "—"}
                    </p>
                  </details>
                </div>
              ))}
            </div>

            <div className="portal-table-wrap portal-table-desktop">
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th className="col-hide-sm">User</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th className="col-hide-md">Case</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.id}>
                      <td className="text-xs text-slate-500">
                        {row.timestamp
                          ? formatDateTime(row.timestamp)
                          : "—"}
                      </td>
                      <td className="col-hide-sm text-slate-700">
                        {formatRoleLabel(row.user_role)}
                      </td>
                      <td>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-au-navy">
                          {formatAuditActionLabel(row.action)}
                        </span>
                      </td>
                      <td className="cell-wrap text-slate-700">{entityCell(row)}</td>
                      <td className="col-hide-md">
                        {row.entity_type === "ufm_case" &&
                        row.entity_id != null ? (
                          <Link
                            to={`/app/cases/${row.entity_id}`}
                            className="font-medium text-au-blue hover:underline"
                          >
                            Case #{row.entity_id}
                          </Link>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="text-slate-700">
                        <details>
                          <summary className="cursor-pointer text-xs font-medium text-au-blue">
                            <span className="line-clamp-2 inline text-slate-700">
                              {row.description
                                ? row.description.length > 80
                                  ? `${row.description.slice(0, 80)}…`
                                  : row.description
                                : "—"}
                            </span>
                          </summary>
                          <p className="mt-1 whitespace-pre-wrap break-words text-sm">
                            {row.description || "—"}
                          </p>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
