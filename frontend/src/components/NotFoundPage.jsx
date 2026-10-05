import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homePathForRole } from "../config/roleHome";
import PageShell from "./PageShell";

export default function NotFoundPage() {
  const { isAuthenticated, user } = useAuth();
  const home = isAuthenticated ? homePathForRole(user?.role) : "/login";

  return (
    <div className="flex min-h-dvh items-center justify-center bg-au-surface p-6">
      <PageShell narrow className="text-center">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Error 404
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-au-navy">
          Page not found
        </h1>
        <p className="mt-3 text-sm text-slate-600">
          The address you opened is not part of the VigilantEye portal, or you
          do not have a route for this path.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to={home} className="btn-primary">
            {isAuthenticated ? "Go to dashboard" : "Sign in"}
          </Link>
        </div>
      </PageShell>
    </div>
  );
}
