/**
 * Static KPI / statistic card — C13-FIX information-only language.
 * Analytical resting appearance; never navigates.
 */
export default function KpiCard({
  title,
  value,
  hint,
  accent = "border-l-slate-400",
}) {
  return (
    <div
      className={`portal-kpi ${accent}`}
      data-affordance="static"
      role="group"
      aria-label={`${title}: ${value}`}
    >
      <p className="portal-kpi-label">{title}</p>
      <p className="portal-kpi-value">{value}</p>
      {hint ? <p className="portal-kpi-hint">{hint}</p> : null}
    </div>
  );
}
