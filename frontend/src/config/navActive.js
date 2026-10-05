/**
 * Query-aware sidebar active matching (C13-ACTIVE-STATE-FIX).
 *
 * NavLink pathname matching alone is insufficient when siblings share
 * `/app/cases` but differ by `?status=…`.
 */

const EXACT_PATHS = new Set([
  "/app/dashboard",
  "/app/admin/dashboard",
  "/app/cases",
  "/app/cases/new",
]);

function splitTo(to) {
  const raw = typeof to === "string" ? to : "";
  const q = raw.indexOf("?");
  if (q < 0) return { pathname: raw, params: new URLSearchParams() };
  return {
    pathname: raw.slice(0, q),
    params: new URLSearchParams(raw.slice(q + 1)),
  };
}

/**
 * @param {{ pathname: string, search?: string }} location
 * @param {string} to sidebar item `to` (may include query string)
 * @returns {boolean}
 */
export function isSidebarNavActive(location, to) {
  if (!location?.pathname || typeof to !== "string" || !to) return false;

  const currentPath = location.pathname;
  const currentParams = new URLSearchParams(location.search || "");
  const { pathname: toPath, params: toParams } = splitTo(to);
  const toKeys = [...toParams.keys()];

  // Filtered siblings (e.g. /app/cases?status=PENDING): require exact path + all params.
  if (toKeys.length > 0) {
    if (currentPath !== toPath) return false;
    for (const key of toKeys) {
      if (currentParams.get(key) !== toParams.get(key)) return false;
    }
    return true;
  }

  // Unfiltered /app/cases ("All UFM Cases" / "My Cases"):
  // active only on the bare list — not when a status or scope filter is present.
  if (toPath === "/app/cases") {
    if (currentPath !== "/app/cases") return false;
    const status = currentParams.get("status");
    const scope = currentParams.get("scope");
    return (
      (status == null || status === "") && (scope == null || scope === "")
    );
  }

  // Exact path match for other leaf destinations.
  if (currentPath === toPath) {
    return true;
  }

  // Nested routes: allow prefix match except for exact-only leaves.
  if (EXACT_PATHS.has(toPath)) {
    return false;
  }
  if (currentPath.startsWith(`${toPath}/`)) {
    return true;
  }

  return false;
}
