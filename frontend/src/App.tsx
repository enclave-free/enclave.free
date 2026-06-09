import { Component, lazy, Suspense, type ReactNode } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { HomeRedirect } from './pages/HomeRedirect';
import { AdminRoute } from './components/shared/AdminRoute';
import { InitiationGate } from './components/shared/InitiationGate';

const TestDashboard = lazy(() =>
  import('./pages/TestDashboard').then((module) => ({
    default: module.TestDashboard,
  }))
);
const ChatPage = lazy(() =>
  import('./pages/ChatPage').then((module) => ({ default: module.ChatPage }))
);
const AdminOnboarding = lazy(() =>
  import('./pages/AdminOnboarding').then((module) => ({
    default: module.AdminOnboarding,
  }))
);
const AdminSetup = lazy(() =>
  import('./pages/AdminSetup').then((module) => ({
    default: module.AdminSetup,
  }))
);
const AdminOnboardingSetup = lazy(() =>
  import('./pages/AdminOnboardingSetup').then((module) => ({
    default: module.AdminOnboardingSetup,
  }))
);
const AdminInstanceConfig = lazy(() =>
  import('./pages/AdminInstanceConfig').then((module) => ({
    default: module.AdminInstanceConfig,
  }))
);
const AdminUserConfig = lazy(() =>
  import('./pages/AdminUserConfig').then((module) => ({
    default: module.AdminUserConfig,
  }))
);
const AdminAIConfig = lazy(() =>
  import('./pages/AdminAIConfig').then((module) => ({
    default: module.AdminAIConfig,
  }))
);
const AdminDeploymentConfig = lazy(() =>
  import('./pages/AdminDeploymentConfig').then((module) => ({
    default: module.AdminDeploymentConfig,
  }))
);
const AdminDocumentUpload = lazy(() =>
  import('./pages/AdminDocumentUpload').then((module) => ({
    default: module.AdminDocumentUpload,
  }))
);
const AdminResourcesDirectory = lazy(() =>
  import('./pages/AdminResourcesDirectory').then((module) => ({
    default: module.AdminResourcesDirectory,
  }))
);
const AdminDatabaseExplorer = lazy(() =>
  import('./pages/AdminDatabaseExplorer').then((module) => ({
    default: module.AdminDatabaseExplorer,
  }))
);
const UserOnboarding = lazy(() =>
  import('./pages/UserOnboarding').then((module) => ({
    default: module.UserOnboarding,
  }))
);
const UserAuth = lazy(() =>
  import('./pages/UserAuth').then((module) => ({ default: module.UserAuth }))
);
const UserTypeSelection = lazy(() =>
  import('./pages/UserTypeSelection').then((module) => ({
    default: module.UserTypeSelection,
  }))
);
const UserProfile = lazy(() =>
  import('./pages/UserProfile').then((module) => ({
    default: module.UserProfile,
  }))
);
const VerifyMagicLink = lazy(() =>
  import('./pages/VerifyMagicLink').then((module) => ({
    default: module.VerifyMagicLink,
  }))
);
const PendingApproval = lazy(() =>
  import('./pages/PendingApproval').then((module) => ({
    default: module.PendingApproval,
  }))
);

function PageLoadingFallback() {
  return (
    <main
      role="status"
      aria-label="Loading page"
      className="flex min-h-screen items-center justify-center bg-background text-sm text-text-muted"
    >
      Loading...
    </main>
  );
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <main className="flex min-h-screen items-center justify-center bg-background text-sm text-text-muted">
            Failed to load page. Please refresh.
          </main>
        )
      );
    }

    return this.props.children;
  }
}

function LazyPage({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoadingFallback />}>{children}</Suspense>
    </ErrorBoundary>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route
          path="/diagnostics/test-dashboard"
          element={
            <LazyPage>
              <TestDashboard />
            </LazyPage>
          }
        />
        <Route
          path="/test-dashboard"
          element={<Navigate to="/diagnostics/test-dashboard" replace />}
        />
        <Route
          path="/chat"
          element={
            <LazyPage>
              <ChatPage />
            </LazyPage>
          }
        />
        <Route
          path="/admin"
          element={
            <LazyPage>
              <AdminOnboarding />
            </LazyPage>
          }
        />
        <Route
          path="/admin/setup"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminSetup />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/onboarding"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminOnboardingSetup />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/instance"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminInstanceConfig />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminUserConfig />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/ai"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminAIConfig />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/deployment"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminDeploymentConfig />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/upload"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminDocumentUpload />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/resources"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminResourcesDirectory />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/database"
          element={
            <AdminRoute>
              <LazyPage>
                <AdminDatabaseExplorer />
              </LazyPage>
            </AdminRoute>
          }
        />
        <Route
          path="/login"
          element={
            <InitiationGate>
              <LazyPage>
                <UserOnboarding />
              </LazyPage>
            </InitiationGate>
          }
        />
        <Route
          path="/auth"
          element={
            <InitiationGate>
              <LazyPage>
                <UserAuth />
              </LazyPage>
            </InitiationGate>
          }
        />
        <Route
          path="/user-type"
          element={
            <InitiationGate>
              <LazyPage>
                <UserTypeSelection />
              </LazyPage>
            </InitiationGate>
          }
        />
        <Route
          path="/profile"
          element={
            <InitiationGate>
              <LazyPage>
                <UserProfile />
              </LazyPage>
            </InitiationGate>
          }
        />
        <Route
          path="/verify"
          element={
            <InitiationGate>
              <LazyPage>
                <VerifyMagicLink />
              </LazyPage>
            </InitiationGate>
          }
        />
        <Route
          path="/pending"
          element={
            <InitiationGate>
              <LazyPage>
                <PendingApproval />
              </LazyPage>
            </InitiationGate>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
