import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Header({
  unreadCount = 0,
  onToggleSidebar,
  sidebarOpen = false,
}) {
  const { user, logout } = useAuth();

  return (
    <header
      data-portal-chrome
      className="app-chrome z-30 flex h-14 shrink-0 items-center justify-between border-b border-au-navy-deep bg-au-navy px-4 text-white"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="rounded-md p-2 hover:bg-white/10 lg:hidden"
          aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          aria-expanded={sidebarOpen}
          aria-controls="portal-sidebar"
        >
          <span className="block h-0.5 w-5 bg-white" />
          <span className="mt-1 block h-0.5 w-5 bg-white" />
          <span className="mt-1 block h-0.5 w-5 bg-white" />
        </button>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white/15 text-xs font-bold tracking-wide">
            AU
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-300">
              Air University
            </p>
            <p className="text-sm font-semibold leading-tight">
              VigilantEye · UFM Portal
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        <Link
          to="/app/notifications"
          className="relative rounded-full p-2 hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
          aria-label={
            unreadCount > 0
              ? `Notifications, ${unreadCount} unread`
              : "Notifications"
          }
          title="Notifications"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-5 w-5 fill-none stroke-current stroke-2"
            aria-hidden
          >
            <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
            <path d="M9 17a3 3 0 0 0 6 0" />
          </svg>
          {unreadCount > 0 ? (
            <span
              className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-red-500 px-1 text-center text-[10px] font-bold leading-4"
              aria-hidden
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          ) : null}
        </Link>

        <div className="hidden max-w-[14rem] text-right sm:block">
          <p className="truncate text-sm font-medium leading-tight" title={user?.name || ""}>
            {user?.name}
          </p>
          <p className="truncate text-xs text-slate-300" title={user?.email || ""}>
            <span className="mr-1 inline-flex rounded bg-white/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide">
              {(user?.role || "").replaceAll("_", " ") || "—"}
            </span>
          </p>
        </div>

        <button
          type="button"
          onClick={logout}
          className="rounded-lg border border-white/20 px-3 py-1.5 text-xs font-semibold hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
