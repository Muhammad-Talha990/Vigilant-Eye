/**
 * Select existing record vs manual entry for UFM filing sections.
 */
export default function FormModeToggle({
  name,
  value,
  onChange,
  selectLabel = "Select existing",
  manualLabel = "Enter manually",
  disabled = false,
}) {
  const base =
    "flex-1 rounded-lg border px-3 py-2 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-au-blue";
  const active = "border-au-navy bg-au-navy text-white";
  const idle =
    "border-slate-300 bg-white text-slate-700 hover:border-slate-400";

  return (
    <div
      className="flex flex-col gap-2 sm:flex-row"
      role="radiogroup"
      aria-label={name}
    >
      <button
        type="button"
        role="radio"
        aria-checked={value === "select"}
        disabled={disabled}
        className={`${base} ${value === "select" ? active : idle}`}
        onClick={() => onChange("select")}
      >
        {selectLabel}
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={value === "manual"}
        disabled={disabled}
        className={`${base} ${value === "manual" ? active : idle}`}
        onClick={() => onChange("manual")}
      >
        {manualLabel}
      </button>
    </div>
  );
}
