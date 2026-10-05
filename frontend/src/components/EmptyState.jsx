/**
 * Consistent empty-state panel for tables and lists.
 */
export default function EmptyState({ title, detail, actions, icon }) {
  return (
    <div className="space-y-3 px-6 py-12 text-center">
      {icon ? (
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
          {icon}
        </div>
      ) : (
        <div
          className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400"
          aria-hidden
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-1.5">
            <path d="M4 6h16M4 12h10M4 18h16" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </div>
      )}
      <p className="text-base font-semibold text-au-navy">{title}</p>
      {detail ? (
        <p className="mx-auto max-w-md text-sm leading-relaxed text-slate-600">
          {detail}
        </p>
      ) : null}
      {actions ? (
        <div className="flex flex-wrap justify-center gap-2 pt-1">{actions}</div>
      ) : null}
    </div>
  );
}
