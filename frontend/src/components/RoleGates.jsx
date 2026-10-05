import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homePathForRole } from "../config/roleHome";
import { roleIn } from "../config/roleAccess";
import LoadingState from "./LoadingState";

/** Only ADMINISTRATOR may view children. */
export function RequireAdministrator({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <LoadingState label="Checking authorization…" />;
  }
  if (user?.role !== "ADMINISTRATOR") {
    return <Navigate to={homePathForRole(user?.role)} replace />;
  }
  return children;
}

/** Block ADMINISTRATOR from operational UFM routes. */
export function DenyAdministrator({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <LoadingState label="Checking authorization…" />;
  }
  if (user?.role === "ADMINISTRATOR") {
    return <Navigate to="/app/admin/dashboard" replace />;
  }
  return children;
}

/**
 * Require one of the listed roles. Administrator is never matched here —
 * wrap with DenyAdministrator for operational pages.
 */
export function RequireRoles({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <LoadingState label="Checking authorization…" />;
  }
  if (!roleIn(user?.role, roles || [])) {
    return <Navigate to={homePathForRole(user?.role)} replace />;
  }
  return children;
}
