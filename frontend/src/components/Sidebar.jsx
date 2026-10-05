import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { isSidebarNavActive } from "../config/navActive";
import { ROLE_LABELS, getNavForRole } from "../config/navByRole";
import { useAuth } from "../context/AuthContext";

function linkClass(active) {
  return [
    "portal-option flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none",
    active
      ? "bg-au-navy font-semibold text-white shadow-sm"
      : "text-slate-700 hover:bg-sky-200 hover:text-au-navy",
  ].join(" ");
}

export default function Sidebar({ open, badges = {}, onNavigate }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const role = typeof user?.role === "string" ? user.role.trim().toUpperCase() : "";
  const sections = getNavForRole(role);
  const now = new Date();
  const roleUnresolved = Boolean(user) && !role;
  const unsupportedRole = Boolean(role) && sections.length === 0;
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(min-width: 1024px)").matches
      : true
  );

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const onChange = () => setIsDesktop(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // Off-canvas mobile drawer must not remain keyboard-focusable when closed.
  const drawerHidden = !isDesktop && !open;

  return (
    <>
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          aria-label="Close sidebar"
          onClick={onNavigate}
        />
      ) : null}

      <aside
        id="portal-sidebar"
        data-portal-chrome
        className={[
          "sidebar fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-[#e8ecf2] pt-14 transition-transform duration-200",
          "lg:static lg:inset-auto lg:h-full lg:min-h-0 lg:shrink-0 lg:translate-x-0 lg:pt-0",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        aria-label="Main navigation"
        aria-hidden={drawerHidden ? true : undefined}
        inert={drawerHidden ? true : undefined}
      >
        <div className="shrink-0 border-b border-slate-200/80 px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Signed in as
          </p>
          <div className="mt-1.5 rounded-md border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
            <p
              className="truncate text-sm font-semibold text-au-navy"
              title={user?.name || ""}
            >
              {user?.name || "User"}
            </p>
            <p
              className="mt-0.5 truncate text-xs text-slate-500"
              title={user?.email || ""}
            >
              {user?.email || "—"}
            </p>
            <p className="mt-2">
              <span className="portal-badge-role">
                {ROLE_LABELS[role] || role || (loading ? "…" : "—")}
              </span>
            </p>
          </div>
        </div>

        <nav className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-3 py-4">
          {loading && !user ? (
            <p className="px-3 text-sm text-slate-500">Resolving session…</p>
          ) : null}
          {roleUnresolved || unsupportedRole ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Access denied: unrecognized portal role
              {role ? ` (${role})` : ""}. Contact an administrator.
            </div>
          ) : null}
          {sections.map((group) => (
            <div key={group.section}>
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                {group.section}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = isSidebarNavActive(location, item.to);
                  return (
                    <Link
                      key={`${item.to}-${item.label}`}
                      to={item.to}
                      className={linkClass(active)}
                      aria-current={active ? "page" : undefined}
                      onClick={onNavigate}
                      data-nav-to={item.to}
                      data-nav-active={active ? "true" : "false"}
                    >
                      <span>{item.label}</span>
                      {item.badgeKey && badges[item.badgeKey] > 0 ? (
                        <span className="min-w-[1.25rem] rounded-full bg-rose-500 px-1.5 text-center text-[10px] font-bold leading-5 text-white">
                          {badges[item.badgeKey] > 99
                            ? "99+"
                            : badges[item.badgeKey]}
                        </span>
                      ) : null}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-slate-200/80 p-3 text-xs text-slate-500">
          <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
            <p className="font-medium text-slate-700">System time</p>
            <p className="mt-0.5 tabular-nums">
              {now.toLocaleDateString()} · {now.toLocaleTimeString()}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}
