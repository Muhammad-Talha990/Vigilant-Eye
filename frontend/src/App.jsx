import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import { DenyAdministrator, RequireAdministrator, RequireRoles } from "./components/RoleGates";
import { useAuth } from "./context/AuthContext";
import { DEMO_HELPERS_ENABLED } from "./config/demoMode";
import { homePathForRole } from "./config/roleHome";
import {
  CASE_CREATE_ROLES,
  DETECTION_ROLES,
  EVIDENCE_VIEW_ROLES,
  MASTER_DATA_VIEW_ROLES,
  MONITOR_ROLES,
  OPERATIONAL_AUDIT_ROLES,
  REPORTS_ROLES,
  RESULT_CONTROL_ROLES,
  STUDENT_DIRECTORY_VIEW_ROLES,
} from "./config/roleAccess";
import { fetchAuthConfig } from "./services/api";
import NotFoundPage from "./components/NotFoundPage";
import ProfilePage from "./pages/ProfilePage";
import AdminAuditPage from "./pages/AdminAuditPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminImportPage from "./pages/AdminImportPage";
import AdminProfilePage from "./pages/AdminProfilePage";
import AdminRolesPage from "./pages/AdminRolesPage";
import AdminStudentsPage from "./pages/AdminStudentsPage";
import AdminSystemPage from "./pages/AdminSystemPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import DashboardHome from "./pages/DashboardHome";
import DetectionsPage from "./pages/DetectionsPage";
import CaseDetailPage from "./pages/CaseDetailPage";
import CasesPage from "./pages/CasesPage";
import CreateCasePage from "./pages/CreateCasePage";
import AuditTrailPage from "./pages/AuditTrailPage";
import ClarificationPage from "./pages/ClarificationPage";
import EvidencePage from "./pages/EvidencePage";
import HelpPage from "./pages/HelpPage";
import Login from "./pages/Login";
import MasterDataPage from "./pages/MasterDataPage";
import MonitoringPage from "./pages/MonitoringPage";
import DemoMonitoringPage from "./pages/DemoMonitoringPage";
import NotificationsPage from "./pages/NotificationsPage";
import ReportsPage from "./pages/ReportsPage";
import ResultControlsPage from "./pages/ResultControlsPage";
import StudentsPage from "./pages/StudentsPage";
// Operational /app/users removed (C11-B) — staff provisioning is Administrator-only.

function DemoMonitoringGate() {
  const [allowed, setAllowed] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!DEMO_HELPERS_ENABLED) {
      setAllowed(false);
      return undefined;
    }
    fetchAuthConfig()
      .then((cfg) => {
        if (!cancelled) setAllowed(Boolean(cfg?.demo_helpers_enabled));
      })
      .catch(() => {
        if (!cancelled) setAllowed(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (allowed === null) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-600 shadow-sm">
        Checking demo access…
      </div>
    );
  }
  if (!allowed) {
    return <Navigate to="/app/monitoring" replace />;
  }
  return <DemoMonitoringPage />;
}

function RoleHomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={homePathForRole(user?.role)} replace />;
}

function Operational({ children }) {
  return <DenyAdministrator>{children}</DenyAdministrator>;
}

function AdminOnly({ children }) {
  return <RequireAdministrator>{children}</RequireAdministrator>;
}

function OpsRoles({ roles, children }) {
  return (
    <Operational>
      <RequireRoles roles={roles}>{children}</RequireRoles>
    </Operational>
  );
}

export default function App() {
  const { isAuthenticated, loading, user } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 text-slate-600">
        Loading session…
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <Navigate
            to={
              isAuthenticated
                ? homePathForRole(user?.role)
                : "/login"
            }
            replace
          />
        }
      />
      <Route path="/login" element={<Login />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<RoleHomeRedirect />} />
        <Route
          path="dashboard"
          element={
            user?.role === "ADMINISTRATOR" ? (
              <Navigate to="/app/admin/dashboard" replace />
            ) : (
              <DashboardHome />
            )
          }
        />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route
          path="cases"
          element={
            <Operational>
              <CasesPage />
            </Operational>
          }
        />
        <Route
          path="cases/new"
          element={
            <OpsRoles roles={CASE_CREATE_ROLES}>
              <CreateCasePage />
            </OpsRoles>
          }
        />
        <Route
          path="cases/:caseId"
          element={
            <Operational>
              <CaseDetailPage />
            </Operational>
          }
        />
        <Route
          path="detections"
          element={
            <OpsRoles roles={DETECTION_ROLES}>
              <DetectionsPage />
            </OpsRoles>
          }
        />
        <Route
          path="evidence"
          element={
            <OpsRoles roles={EVIDENCE_VIEW_ROLES}>
              <EvidencePage />
            </OpsRoles>
          }
        />
        <Route
          path="students"
          element={
            <OpsRoles roles={STUDENT_DIRECTORY_VIEW_ROLES}>
              <StudentsPage />
            </OpsRoles>
          }
        />
        <Route
          path="users"
          element={
            <Operational>
              <Navigate to="/app/dashboard" replace />
            </Operational>
          }
        />
        <Route
          path="admin/dashboard"
          element={
            <AdminOnly>
              <AdminDashboardPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/users"
          element={
            <AdminOnly>
              <AdminUsersPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/import"
          element={
            <AdminOnly>
              <AdminImportPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/roles"
          element={
            <AdminOnly>
              <AdminRolesPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/audit"
          element={
            <AdminOnly>
              <AdminAuditPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/students"
          element={
            <AdminOnly>
              <AdminStudentsPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/system"
          element={
            <AdminOnly>
              <AdminSystemPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/profile"
          element={
            <AdminOnly>
              <AdminProfilePage />
            </AdminOnly>
          }
        />
        <Route
          path="master-data"
          element={
            <OpsRoles roles={MASTER_DATA_VIEW_ROLES}>
              <MasterDataPage />
            </OpsRoles>
          }
        />
        <Route
          path="result-controls"
          element={
            <OpsRoles roles={RESULT_CONTROL_ROLES}>
              <ResultControlsPage />
            </OpsRoles>
          }
        />
        <Route
          path="audit"
          element={
            <OpsRoles roles={OPERATIONAL_AUDIT_ROLES}>
              <AuditTrailPage />
            </OpsRoles>
          }
        />
        <Route
          path="monitoring"
          element={
            <OpsRoles roles={MONITOR_ROLES}>
              <MonitoringPage />
            </OpsRoles>
          }
        />
        <Route
          path="monitoring/demo"
          element={
            <OpsRoles roles={MONITOR_ROLES}>
              <DemoMonitoringGate />
            </OpsRoles>
          }
        />
        <Route
          path="reports"
          element={
            <OpsRoles roles={REPORTS_ROLES}>
              <ReportsPage />
            </OpsRoles>
          }
        />
        <Route
          path="clarification"
          element={
            <OpsRoles roles={["STUDENT"]}>
              <ClarificationPage />
            </OpsRoles>
          }
        />
        <Route path="help" element={<HelpPage />} />
        <Route
          path="profile"
          element={
            user?.role === "ADMINISTRATOR" ? (
              <Navigate to="/app/admin/profile" replace />
            ) : (
              <ProfilePage />
            )
          }
        />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
