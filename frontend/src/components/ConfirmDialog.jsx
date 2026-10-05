/**
 * Accessible confirmation dialog for consequential actions.
 * Focus moves into the dialog on open, Tab cycles inside, Esc cancels.
 */
import { useEffect, useId, useRef } from "react";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "danger",
  busy = false,
  onConfirm,
  onCancel,
}) {
  const panelRef = useRef(null);
  const cancelRef = useRef(null);
  const previouslyFocused = useRef(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocused.current = document.activeElement;
    const focusTimer = window.setTimeout(() => {
      cancelRef.current?.focus();
    }, 0);

    function onKeyDown(event) {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onCancel?.();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      const list = Array.from(focusable).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", onKeyDown);
      const prev = previouslyFocused.current;
      if (prev && typeof prev.focus === "function") {
        prev.focus();
      }
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  const confirmClass =
    tone === "danger"
      ? "btn-danger"
      : tone === "success"
        ? "btn-success"
        : "btn-primary";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center"
      role="presentation"
      onClick={busy ? undefined : onCancel}
    >
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={message ? descId : undefined}
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="text-lg font-semibold text-au-navy">
          {title}
        </h2>
        {message ? (
          <p id={descId} className="mt-2 text-sm text-slate-600">
            {message}
          </p>
        ) : null}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (!busy) onCancel?.();
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={confirmClass}
            disabled={busy}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (!busy) onConfirm?.();
            }}
          >
            {busy ? "Please wait…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
