/**
 * Constrains page content width and vertical rhythm for institutional layouts.
 */
export default function PageShell({ children, className = "", narrow = false }) {
  return (
    <div
      className={[
        "mx-auto w-full space-y-6",
        narrow ? "max-w-3xl" : "max-w-7xl",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}
