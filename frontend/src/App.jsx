import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
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
import UsersPage from "./pages/UsersPage";

export default function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-au-surface text-au-navy">
        Loading...
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/"
        element={<Navigate to={isAuthenticated ? "/app/dashboard" : "/login"} replace />}
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
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<DashboardHome />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="cases/new" element={<CreateCasePage />} />
        <Route path="cases/:caseId" element={<CaseDetailPage />} />
        <Route path="detections" element={<DetectionsPage />} />
        <Route path="evidence" element={<EvidencePage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="master-data" element={<MasterDataPage />} />
        <Route path="result-controls" element={<ResultControlsPage />} />
        <Route path="audit" element={<AuditTrailPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="monitoring/demo" element={<DemoMonitoringPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="clarification" element={<ClarificationPage />} />
        <Route path="help" element={<HelpPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
