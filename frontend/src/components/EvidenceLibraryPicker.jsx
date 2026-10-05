import { formatDateTime } from "../config/dateTime";
import { useEffect, useState } from "react";
import {
  fetchEvidenceLibrary,
  loadEvidenceObjectUrl,
} from "../services/api";

function fileNameFromPath(filePath) {
  if (!filePath) return "";
  const parts = String(filePath).split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}

/**
 * Modal to search and attach existing Evidence Library records (orphan rows).
 */
export default function EvidenceLibraryPicker({
  open,
  onClose,
  selectedIds,
  onApply,
}) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState([]);
  const [previews, setPreviews] = useState({});
  const [draftIds, setDraftIds] = useState(selectedIds);

  useEffect(() => {
    if (open) setDraftIds(selectedIds);
  }, [open, selectedIds]);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const list = await fetchEvidenceLibrary(query.trim() || null);
        if (cancelled) return;
        setRows(Array.isArray(list) ? list : []);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load evidence.");
          setRows([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, query]);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    const urls = [];
    (async () => {
      const next = {};
      for (const ev of rows.slice(0, 12)) {
        if (draftIds.includes(ev.id)) continue;
        try {
          const { url, mime } = await loadEvidenceObjectUrl(ev.id, {
            preview: true,
          });
          if (cancelled) {
            URL.revokeObjectURL(url);
            continue;
          }
          urls.push(url);
          next[ev.id] = { url, mime };
        } catch {
          /* metadata only */
        }
      }
      if (!cancelled) setPreviews(next);
    })();
    return () => {
      cancelled = true;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [open, rows, draftIds]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setRows([]);
      setPreviews((prev) => {
        Object.values(prev).forEach((p) => {
          if (p?.url) URL.revokeObjectURL(p.url);
        });
        return {};
      });
    }
  }, [open]);

  if (!open) return null;

  const selectedSet = new Set(draftIds);

  function toggle(id) {
    if (selectedSet.has(id)) {
      setDraftIds(draftIds.filter((x) => x !== id));
    } else {
      setDraftIds([...draftIds, id]);
    }
  }

  function handleDone() {
    const idSet = new Set(draftIds);
    const picked = rows.filter((r) => idSet.has(r.id));
    const missing = draftIds.filter(
      (id) => !picked.some((r) => r.id === id)
    );
    const fromPrev = missing.map((id) => ({ id }));
    onApply?.([...picked, ...fromPrev]);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-3 sm:items-center sm:p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-library-title"
        className="flex max-h-[min(90vh,40rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b border-slate-100 px-4 py-3 sm:px-5">
          <h2
            id="evidence-library-title"
            className="text-lg font-semibold text-au-navy"
          >
            Attach from Evidence Library
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Select existing evidence records. Files are referenced — not
            duplicated.
          </p>
          <label className="mt-3 block">
            <span className="sr-only">Search evidence</span>
            <input
              type="search"
              className="portal-input w-full"
              placeholder="Search by ID, type, or file name…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-5">
          {loading ? (
            <p className="text-sm text-slate-600">Searching evidence…</p>
          ) : error ? (
            <p className="text-sm text-red-700" role="alert">
              {error}
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-slate-600">No evidence found.</p>
          ) : (
            <ul className="divide-y divide-slate-100 border border-slate-200">
              {rows.map((ev) => {
                const checked = selectedSet.has(ev.id);
                const preview = previews[ev.id];
                const isImage = preview?.mime?.startsWith("image/");
                return (
                  <li key={ev.id}>
                    <label className="portal-option flex cursor-pointer gap-3 px-3 py-2 hover:bg-sky-200">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 shrink-0 accent-au-blue"
                        checked={checked}
                        onChange={() => toggle(ev.id)}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-au-navy">
                          #{ev.id} · {ev.evidence_type}
                        </p>
                        <p className="truncate text-xs text-slate-600">
                          {fileNameFromPath(ev.file_path)}
                          {ev.detection_id
                            ? ` · detection #${ev.detection_id}`
                            : ""}
                          {ev.timestamp
                            ? ` · ${formatDateTime(ev.timestamp)}`
                            : ""}
                        </p>
                        {isImage ? (
                          <img
                            src={preview.url}
                            alt=""
                            className="mt-2 max-h-24 rounded border border-slate-200 object-contain"
                          />
                        ) : null}
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-4 py-3 sm:px-5">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={handleDone}>
            Attach selected
          </button>
        </footer>
      </div>
    </div>
  );
}
