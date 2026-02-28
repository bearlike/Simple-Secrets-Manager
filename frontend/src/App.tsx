import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, ProtectedRoute } from './lib/auth';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { SecretsPage } from './pages/SecretsPage';
import { ConfigSettingsPage } from './pages/ConfigSettingsPage';
import { TokensPage } from './pages/TokensPage';
import { AuditPage } from './pages/AuditPage';
import { CompareBySecretPage } from './pages/CompareBySecretPage';
import { AccountPage } from './pages/AccountPage';
import { TeamPage } from './pages/TeamPage';
import { GroupsPage } from './pages/GroupsPage';
import { notifyApiError } from './lib/api/errorToast';
const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      notifyApiError(error, 'Request failed');
    }
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      notifyApiError(error, 'Request failed');
    }
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000
    }
  }
});
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
              <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }>

              <Route path="/projects" element={<ProjectsPage />} />
              <Route
                path="/projects/:projectSlug/configs/:configSlug"
                element={<SecretsPage />} />

              <Route
                path="/projects/:projectSlug/settings"
                element={<ConfigSettingsPage />} />

              <Route
                path="/projects/:projectSlug/compare/secret"
                element={<CompareBySecretPage />} />

              <Route path="/tokens" element={<TokensPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/account" element={<AccountPage />} />
              <Route path="/team" element={<TeamPage />} />
              <Route path="/groups" element={<GroupsPage />} />
              <Route path="/" element={<Navigate to="/projects" replace />} />
              <Route path="*" element={<Navigate to="/projects" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="bottom-right" />
      </AuthProvider>
    </QueryClientProvider>);

}
