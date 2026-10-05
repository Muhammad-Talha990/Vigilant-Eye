import { useCallback, useEffect, useId, useRef, useState } from "react";

/**
 * Accessible searchable combobox for institutional records (students, exams, staff).
 */
export default function PortalSearchSelect({
  label,
  required = false,
  placeholder = "Search…",
  value,
  selectedItem,
  onSelect,
  onClear,
  searchFn,
  getOptionKey = (item) => String(item.id),
  formatOptionLabel,
  renderOption,
  disabled = false,
  error = "",
  hint = "",
  minSearchLength = 1,
  emptyMessage = "No results found.",
  loadingMessage = "Searching…",
  errorMessage = "Unable to load results. Try again.",
  id: idProp,
}) {
  const autoId = useId();
  const inputId = idProp || `portal-search-${autoId}`;
  const listId = `${inputId}-listbox`;
  const errorId = error ? `${inputId}-error` : undefined;

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [options, setOptions] = useState([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const debounceRef = useRef(null);
  const wrapRef = useRef(null);

  const displayValue =
    selectedItem && formatOptionLabel
      ? formatOptionLabel(selectedItem)
      : selectedItem
        ? String(selectedItem)
        : "";

  const runSearch = useCallback(
    async (term) => {
      const q = term.trim();
      if (minSearchLength > 0 && q.length < minSearchLength) {
        setOptions([]);
        setLoadError("");
        setLoading(false);
        return;
      }
      setLoading(true);
      setLoadError("");
      try {
        const rows = await searchFn(q);
        setOptions(Array.isArray(rows) ? rows : []);
      } catch {
        setOptions([]);
        setLoadError(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [searchFn, minSearchLength, errorMessage]
  );

  useEffect(() => {
    if (!open) return undefined;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runSearch(query);
    }, 280);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, open, runSearch]);

  useEffect(() => {
    function onDocClick(e) {
      if (!wrapRef.current?.contains(e.target)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function pick(item) {
    onSelect?.(item);
    setQuery("");
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(e) {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      // Keep Enter inside the combobox from submitting the parent form.
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, options.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0 && options[activeIndex]) {
        pick(options[activeIndex]);
      }
    }
  }

  return (
    <div ref={wrapRef} className="relative min-w-0">
      <label htmlFor={inputId} className="block">
        <span className="portal-label">
          {label}
          {required ? <span className="text-red-600"> *</span> : null}
        </span>
        <div className="mt-1 flex gap-2">
          <input
            id={inputId}
            type="search"
            autoComplete="off"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-invalid={Boolean(error)}
            aria-describedby={[errorId, hint ? `${inputId}-hint` : null]
              .filter(Boolean)
              .join(" ") || undefined}
            disabled={disabled}
            placeholder={placeholder}
            className="portal-input min-w-0 flex-1"
            value={open ? query : displayValue || query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
              if (value && onClear) onClear();
            }}
            onFocus={() => {
              setOpen(true);
              if (!query && displayValue) setQuery("");
            }}
            onKeyDown={handleKeyDown}
          />
          {value && onClear ? (
            <button
              type="button"
              className="btn-secondary shrink-0 px-3"
              disabled={disabled}
              onClick={() => {
                onClear();
                setQuery("");
                setOptions([]);
              }}
            >
              Clear
            </button>
          ) : null}
        </div>
      </label>
      {hint ? (
        <p id={`${inputId}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : null}

      {open && !disabled ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {loading ? (
            <li className="px-3 py-2 text-sm text-slate-600">{loadingMessage}</li>
          ) : loadError ? (
            <li className="px-3 py-2 text-sm text-red-700" role="alert">
              {loadError}
            </li>
          ) : minSearchLength > 0 && query.trim().length < minSearchLength ? (
            <li className="px-3 py-2 text-sm text-slate-500">
              Type at least {minSearchLength} character
              {minSearchLength === 1 ? "" : "s"} to search.
            </li>
          ) : options.length === 0 ? (
            <li className="px-3 py-2 text-sm text-slate-600">{emptyMessage}</li>
          ) : (
            options.map((item, idx) => {
              const key = getOptionKey(item);
              const active = idx === activeIndex;
              return (
                <li key={key} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={`portal-option w-full px-3 py-2 text-left text-sm hover:bg-sky-200 focus-visible:bg-sky-200 focus-visible:outline-none ${
                      active ? "bg-sky-100" : ""
                    }`}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => pick(item)}
                  >
                    {renderOption ? renderOption(item) : formatOptionLabel?.(item)}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
