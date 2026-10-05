/**
 * Lightweight professional loading panel for data-driven pages.
 * Accepts `title` or legacy `label` prop.
 */
export default function LoadingState({
  title,
  label,
  detail,
  compact = false,
}) {
  const heading = title || label || "Loading…";
  return (
    <div
      role="status"
      aria-live="polite"
      className={
        compact
          ? "flex flex-col items-center gap-3 px-6 py-10 text-center"
          : "portal-card flex flex-col items-center gap-3 px-6 py-12 text-center"
      }
    >
      <span className="portal-spinner" aria-hidden />
      <div>
        <p className="font-medium text-au-navy">{heading}</p>
        {detail ? (
          <p className="mt-1 text-sm text-slate-500">{detail}</p>
        ) : null}
      </div>
    </div>
  );
}
