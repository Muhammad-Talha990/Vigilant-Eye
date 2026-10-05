import { openEvidenceFile, downloadEvidenceFile } from "../services/api";

/**
 * Shared Open / Download controls for evidence rows.
 * Uses existing API helpers; does not change file-serving behavior.
 */
export default function EvidenceFileActions({
  evidenceId,
  onError,
  onPreview,
  showPreview = false,
  className = "",
}) {
  return (
    <div className={`flex flex-wrap items-center gap-3 ${className}`}>
      {showPreview && typeof onPreview === "function" ? (
        <button
          type="button"
          className="text-xs font-semibold text-au-navy hover:underline"
          aria-label={`Preview evidence ${evidenceId}`}
          onClick={() => onPreview(evidenceId)}
        >
          Preview
        </button>
      ) : null}
      <button
        type="button"
        className="text-xs font-semibold text-au-blue hover:underline"
        aria-label={`Open evidence ${evidenceId}`}
        onClick={async () => {
          try {
            await openEvidenceFile(evidenceId);
          } catch (err) {
            onError?.(err?.message || "Could not open evidence file.");
          }
        }}
      >
        Open
      </button>
      <button
        type="button"
        className="text-xs font-semibold text-slate-700 hover:underline"
        aria-label={`Download evidence ${evidenceId}`}
        onClick={async () => {
          try {
            await downloadEvidenceFile(evidenceId);
          } catch (err) {
            onError?.(err?.message || "Could not download evidence file.");
          }
        }}
      >
        Download
      </button>
    </div>
  );
}
