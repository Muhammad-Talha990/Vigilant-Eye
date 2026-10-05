/**
 * Non-error informational / success banners for forms and actions.
 */
export default function FeedbackBanner({
  tone = "info",
  title,
  message,
  onDismiss,
}) {
  const styles = {
    info: "border-sky-200 bg-sky-50 text-sky-950",
    success: "border-emerald-200 bg-emerald-50 text-emerald-950",
    warning: "border-amber-200 bg-amber-50 text-amber-950",
  };
  const cls = styles[tone] || styles.info;

  return (
    <div
      role={tone === "warning" ? "alert" : "status"}
      className={`rounded-xl border px-4 py-3 text-sm ${cls}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          {title ? <p className="font-semibold">{title}</p> : null}
          {message ? (
            <p className={title ? "mt-1" : ""}>{message}</p>
          ) : null}
        </div>
        {typeof onDismiss === "function" ? (
          <button
            type="button"
            className="shrink-0 text-xs font-semibold underline"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
