import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { ErrorBoundary } from "./components/shared/ErrorBoundary";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AuthProvider } from "./contexts/AuthContext";
import { Loader2 } from "lucide-react";
import "./styles.css";
import "./design-system.css";

// Lazy load page components for code splitting
const DashboardPage = lazy(() => import("./pages/DashboardPage").then(m => ({ default: m.DashboardPage })));
const JobsHistoryPage = lazy(() => import("./pages/JobsHistoryPage").then(m => ({ default: m.JobsHistoryPage })));
const CreateBatchPage = lazy(() => import("./pages/CreateBatchPage").then(m => ({ default: m.CreateBatchPage })));
const JobStatusPage = lazy(() => import("./pages/JobStatusPage").then(m => ({ default: m.JobStatusPage })));
const ReviewBatchPage = lazy(() => import("./pages/ReviewBatchPage").then(m => ({ default: m.ReviewBatchPage })));
const QuestionBrowserPage = lazy(() => import("./pages/QuestionBrowserPage").then(m => ({ default: m.QuestionBrowserPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(m => ({ default: m.SettingsPage })));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage").then(m => ({ default: m.ReviewQueuePage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then(m => ({ default: m.LoginPage })));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const UserManagementPage = lazy(() => import("./pages/UserManagementPage").then(m => ({ default: m.UserManagementPage })));

// Loading fallback component
function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      gap: 'var(--space-3)',
      color: 'var(--gray-500)',
    }}>
      <Loader2 className="animate-spin" size={24} />
      <span>Loading...</span>
    </div>
  );
}

export default function App() {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const apiKey = import.meta.env.VITE_QBANK_API_KEY ?? "";

  return (
    <ErrorBoundary>
      <AuthProvider>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes within AppLayout */}
            <Route element={<AppLayout />}>
              {/* Dashboard / Home */}
              <Route path="/" element={<DashboardPage apiBaseUrl={baseUrl} apiKey={apiKey} />} />

              {/* Job History */}
              <Route path="/jobs" element={<JobsHistoryPage apiBaseUrl={baseUrl} apiKey={apiKey} />} />

              {/* Create New Batch — Creator & Admin only */}
              <Route path="/create" element={
                <ProtectedRoute allowedRoles={['creator', 'admin']}>
                  <CreateBatchPage apiBaseUrl={baseUrl} apiKey={apiKey} />
                </ProtectedRoute>
              } />

              {/* Question Library */}
              <Route path="/library" element={<QuestionBrowserPage apiBaseUrl={baseUrl} apiKey={apiKey} />} />

              {/* Specific Job Status (Live View) */}
              <Route path="/job/:jobId" element={<JobStatusPage apiBaseUrl={baseUrl} apiKey={apiKey} />} />

              {/* Review Mode — Reviewer & Admin only */}
              <Route path="/job/:jobId/review" element={
                <ProtectedRoute allowedRoles={['creator', 'reviewer', 'admin']}>
                  <ReviewBatchPage apiBaseUrl={baseUrl} apiKey={apiKey} />
                </ProtectedRoute>
              } />

              {/* Review Queue — Reviewer & Admin only */}
              <Route path="/queue" element={
                <ProtectedRoute allowedRoles={['creator', 'reviewer', 'admin']}>
                  <ReviewQueuePage apiBaseUrl={baseUrl} apiKey={apiKey} />
                </ProtectedRoute>
              } />

              {/* Settings */}
              <Route path="/settings" element={<SettingsPage apiBaseUrl={baseUrl} apiKey={apiKey} />} />

              {/* Analytics — Admin only */}
              <Route path="/analytics" element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AnalyticsPage />
                </ProtectedRoute>
              } />

              {/* User Management — Admin only */}
              <Route path="/users" element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <UserManagementPage apiBaseUrl={baseUrl} apiKey={apiKey} />
                </ProtectedRoute>
              } />

              {/* Redirect unknown routes to dashboard */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </AuthProvider>
    </ErrorBoundary>
  );
}
