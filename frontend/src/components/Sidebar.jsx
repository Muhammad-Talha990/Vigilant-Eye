import { NavLink } from "react-router-dom";
import { ROLE_LABELS, getNavForRole } from "../config/navByRole";
import { useAuth } from "../context/AuthContext";

function linkClass({ isActive }) {
  return [
    "flex items-center justify-between rounded-lg px-3 py-2 text-sm transition",
    isActive
      ? "bg-au-navy font-semibold text-white"
      : "text-slate-700 hover:bg-slate-200/80",
  ].join(" ");
}

export default function Sidebar({ open, badges = {}, onNavigate }) {
  const { user } = useAuth();
  const role = user?.role || "INVIGILATOR";
  const items = getNavForRole(role);
  const now = new Date();

  return (
    <>
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          aria-label="Close sidebar"
          onClick={onNavigate}
        />
      ) : null}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-[#eef1f6] pt-14 transition-transform lg:static lg:translate-x-0 lg:pt-0",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="border-b border-slate-200 px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Signed in as
          </p>
          <div className="mt-1 rounded-lg border border-slate-300 bg-white px-3 py-2">
            <p className="text-sm font-semibold text-au-navy">
              {user?.name || "User"}
            </p>
            <p className="text-xs text-slate-500">
              {ROLE_LABELS[role] || role}
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {items.map((item) => (
            <NavLink
              key={`${item.to}-${item.label}`}
              to={item.to}
              end={item.to === "/app/dashboard"}
              className={linkClass}
              onClick={onNavigate}
            >
              <span>{item.label}</span>
              {item.badgeKey && badges[item.badgeKey] > 0 ? (
                <span className="rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                  {badges[item.badgeKey]}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-3 text-xs text-slate-500">
          <div className="rounded-lg bg-white px-3 py-2 shadow-sm">
            <p className="font-medium text-slate-700">System Time</p>
            <p>
              {now.toLocaleDateString()} · {now.toLocaleTimeString()}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}
