/**
 * Shared content panel with optional header actions.
 */
export default function SectionPanel({
  title,
  description,
  actions,
  children,
  className = "",
  bodyClassName = "",
}) {
  return (
    <section className={`portal-card overflow-hidden ${className}`.trim()}>
      {(title || actions) && (
        <div className="portal-panel-header">
          <div className="min-w-0">
            {title ? <h2 className="portal-section-title">{title}</h2> : null}
            {description ? (
              <p className="mt-0.5 text-xs text-slate-500">{description}</p>
            ) : null}
          </div>
          {actions ? (
            <div className="flex flex-wrap items-center gap-2">{actions}</div>
          ) : null}
        </div>
      )}
      <div className={bodyClassName || "portal-panel-body"}>{children}</div>
    </section>
  );
}
