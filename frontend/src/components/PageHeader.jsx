/**
 * Consistent page header: breadcrumb, title, description, optional actions.
 */
export default function PageHeader({
  breadcrumb = "Home",
  title,
  description,
  actions,
  children,
}) {
  return (
    <header className="flex flex-col gap-3 border-b border-slate-200/80 pb-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 flex-1">
        {breadcrumb ? (
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {breadcrumb}
          </p>
        ) : null}
        <h1 className="mt-0.5 text-xl font-semibold tracking-tight text-au-navy sm:text-2xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">
            {description}
          </p>
        ) : null}
        {children}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  );
}
