import { ConsentPage } from './pages/ConsentPage';
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppShell } from './components/AppShell';
import { LoginPage } from './pages/LoginPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { DashboardPage } from './pages/DashboardPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { ChatPage } from './pages/ChatPage';
import { PaperTradingPage } from './pages/PaperTradingPage';
import { AlertsPage } from './pages/AlertsPage';
import { GoalsPage } from './pages/GoalsPage';
import { SpendingPage } from './pages/SpendingPage';
import { MarketPage } from './pages/MarketPage';
import { WatchlistPage } from './pages/WatchlistPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppShell>
          <Routes>
            {/* Public Auth Route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected Application Routes */}
            <Route
              path="/consent"
              element={
                <ProtectedRoute>
                  <ConsentPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/onboarding"
              element={
                <ProtectedRoute>
                  <OnboardingPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolio"
              element={
                <ProtectedRoute>
                  <PortfolioPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/market"
              element={
                <ProtectedRoute>
                  <MarketPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/watchlist"
              element={
                <ProtectedRoute>
                  <WatchlistPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/paper-trading"
              element={
                <ProtectedRoute>
                  <PaperTradingPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/alerts"
              element={
                <ProtectedRoute>
                  <AlertsPage />
                </ProtectedRoute>
              }
            />
            <Route

              path="/goals"
              element={
                <ProtectedRoute>
                  <GoalsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/spending"
              element={
                <ProtectedRoute>
                  <SpendingPage />
                </ProtectedRoute>
              }
            />

            {/* Fallback & Root Redirect */}
            <Route path="/" element={<Navigate to="/onboarding" replace />} />
            <Route path="*" element={<Navigate to="/onboarding" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;