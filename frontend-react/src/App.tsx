import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LocalSessionProvider } from './context/LocalSessionContext';
import { LocalApplicationShell } from './components/LocalApplicationShell';
import { LocalApplicationGuard } from './components/LocalApplicationGuard';
import { LocalApplicationClient } from './services/localApplicationClient';
import { LocalLoginPage } from './pages/LocalLoginPage';
import { LocalOnboardingPage } from './pages/LocalOnboardingPage';
import { LocalDashboardPage } from './pages/LocalDashboardPage';
import { PendingDeliveryPage } from './pages/PendingDeliveryPage';
import { ConsentPage } from './pages/ConsentPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { RiskPage } from './pages/RiskPage';
import { LocalRiskPage } from './pages/LocalRiskPage';
import { LocalPortfolioPage } from './pages/LocalPortfolioPage';
import { MarketPage } from './pages/MarketPage';
import { WatchlistPage } from './pages/WatchlistPage';
import { PaperTradingPage } from './pages/PaperTradingPage';
import { GoalsPage } from './pages/GoalsPage';
import { SpendingPage } from './pages/SpendingPage';
import { ChatPage } from './pages/ChatPage';
import { AlertsPage } from './pages/AlertsPage';
import { OpsPage } from './pages/OpsPage';
import { ReleasePage } from './pages/ReleasePage';

function App({ client }: { client?: LocalApplicationClient } = {}) {
  return <LocalSessionProvider client={client}>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LocalApplicationShell>
        <Routes>
          <Route path="/login" element={<LocalLoginPage />} />
          <Route path="/onboarding" element={<LocalApplicationGuard requireCompletion={false}><LocalOnboardingPage /></LocalApplicationGuard>} />
          <Route path="/consent" element={<Navigate to="/onboarding#consent" replace />} />
          <Route path="/dashboard" element={<LocalApplicationGuard><LocalDashboardPage /></LocalApplicationGuard>} />
          <Route path="/risk" element={<LocalApplicationGuard><LocalRiskPage /></LocalApplicationGuard>} />
          <Route path="/portfolio" element={<LocalApplicationGuard><LocalPortfolioPage /></LocalApplicationGuard>} />
          <Route path="/market" element={<LocalApplicationGuard><MarketPage /></LocalApplicationGuard>} />
          <Route path="/watchlist" element={<LocalApplicationGuard><WatchlistPage /></LocalApplicationGuard>} />
          <Route path="/paper-trading" element={<LocalApplicationGuard><PaperTradingPage /></LocalApplicationGuard>} />
          <Route path="/goals" element={<LocalApplicationGuard><GoalsPage /></LocalApplicationGuard>} />
          <Route path="/spending" element={<LocalApplicationGuard><SpendingPage /></LocalApplicationGuard>} />
          <Route path="/chat" element={<LocalApplicationGuard><ChatPage /></LocalApplicationGuard>} />
          <Route path="/alerts" element={<LocalApplicationGuard><AlertsPage /></LocalApplicationGuard>} />
          <Route path="/ops" element={<LocalApplicationGuard><OpsPage /></LocalApplicationGuard>} />
          <Route path="/release" element={<LocalApplicationGuard><ReleasePage /></LocalApplicationGuard>} />
          {/* Legacy adapters are compatibility-only and cannot authorize a full-app route. */}
          <Route path="/pilot/consent" element={<ConsentPage basePath="/pilot" />} />
          <Route path="/pilot/onboarding" element={<OnboardingPage basePath="/pilot" />} />
          <Route path="/pilot/risk" element={<RiskPage basePath="/pilot" />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </LocalApplicationShell>
    </BrowserRouter>
  </LocalSessionProvider>;
}
export default App;
