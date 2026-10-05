/**
 * Consistent API error banner with optional retry.
 */
export default function ErrorBanner({
  title = "Unable to load data.",
  message,
  onRetry,
  retryLabel = "Try again",
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <p className="font-semibold">{title}</p>
      {message ? <p className="mt-1">{message}</p> : null}
      {typeof onRetry === "function" ? (
        <button
          type="button"
          onClick={onRetry}
          className="btn-secondary mt-3 border-red-200 bg-white text-red-800 hover:bg-red-50"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
