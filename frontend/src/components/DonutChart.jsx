/** Simple CSS donut + legend — no chart library. */

export default function DonutChart({ title, segments, emptyLabel = "No data" }) {
  const total = segments.reduce((sum, s) => sum + s.count, 0);

  let cumulative = 0;
  const stops = segments
    .map((s) => {
      const start = total ? (cumulative / total) * 100 : 0;
      cumulative += s.count;
      const end = total ? (cumulative / total) * 100 : 0;
      return `${s.color} ${start}% ${end}%`;
    })
    .join(", ");

  return (
    <section className="portal-card p-4">
      <h2 className="portal-section-title">{title}</h2>
      {total === 0 ? (
        <p className="mt-6 text-sm text-slate-500">{emptyLabel}</p>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-6">
          <div
            className="relative h-36 w-36 shrink-0 rounded-full"
            style={{
              background: `conic-gradient(${stops})`,
            }}
            aria-hidden
          >
            <div className="absolute inset-4 flex flex-col items-center justify-center rounded-full bg-white">
              <span className="text-2xl font-semibold text-au-navy">{total}</span>
              <span className="text-[10px] uppercase tracking-wide text-slate-400">
                total
              </span>
            </div>
          </div>
          <ul className="min-w-[10rem] flex-1 space-y-2 text-sm">
            {segments.map((s) => (
              <li key={s.label} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-slate-700">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: s.color }}
                  />
                  {s.label.replaceAll("_", " ")}
                </span>
                <span className="font-medium text-au-navy">
                  {s.count}{" "}
                  <span className="text-xs font-normal text-slate-400">
                    ({((s.count / total) * 100).toFixed(0)}%)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
