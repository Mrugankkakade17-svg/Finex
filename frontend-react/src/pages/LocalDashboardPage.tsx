import React from 'react';
import { Link } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { useAuth } from '../context/AuthContext';
import { Target, PieChart, Bot, TrendingUp, CreditCard, Bell } from 'lucide-react';

export function LocalDashboardPage() {
  const { onboarding: state, user: sessionUser } = useLocalSession();
  const { user: authUser, isAuthenticated } = useAuth();

  const displayName =
    state?.draft.display_name?.trim() ||
    (isAuthenticated && authUser?.displayName ? authUser.displayName : null) ||
    sessionUser?.alias ||
    'Investor';

  const experienceLevel = state?.draft.experience_level || 'intermediate';
  const consentVersion = state?.consent?.version || 'v1.0';
  const recordedAt = state?.consent?.recorded_at || 'Active session';
  const completedAt = state?.completed_at || 'Confirmed';

  return (
    <section className="local-card">
      <p className="local-eyebrow">YOUR PERSONAL FINANCIAL RHYTHM</p>
      <h1 tabIndex={-1}>Welcome back, {displayName}</h1>
      <p className="local-lede">
        Your space is ready. Review your profile, build your savings goals, track your manual
        portfolios, and explore grounded educational insights at your own pace.
      </p>

      <div className="local-summary-grid" style={{ marginBottom: '24px' }}>
        <section className="local-notice">
          <h2>Saved profile</h2>
          <p style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-text)' }}>
            {displayName}
          </p>
          <p className="local-help">Self-declared experience: {experienceLevel}</p>
        </section>

        <section className="local-notice">
          <h2>Educational notice</h2>
          <p style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-accent-violet)' }}>
            {consentVersion}
          </p>
          <p className="local-help">Accepted: {recordedAt}</p>
        </section>

        <section className="local-notice">
          <h2>Confirmed onboarding</h2>
          <p style={{ fontWeight: 700, fontSize: '1.1rem', color: '#16654E' }}>
            Active &amp; Verified
          </p>
          <p className="local-help">{completedAt}</p>
        </section>
      </div>

      <div className="local-actions">
        <Link className="btn-primary" to="/goals">
          Build your money rhythm ↗
        </Link>
        <Link className="btn-secondary" to="/onboarding">
          Review profile and consent
        </Link>
      </div>

      {/* Quick Orbit Modules Grid */}
      <section className="local-delivery">
        <h2>Explore your money orbit</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '16px',
            marginTop: '16px',
          }}
        >
          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Target size={20} color="var(--color-accent-coral)" />
              <h2 style={{ margin: 0 }}>Goal Planning</h2>
            </div>
            <p>Plan milestones like a weekend away or emergency fund with clear projections.</p>
            <Link className="btn-secondary" to="/goals">
              Open Goals
            </Link>
          </div>

          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <PieChart size={20} color="var(--color-accent-violet)" />
              <h2 style={{ margin: 0 }}>Portfolios &amp; Risk</h2>
            </div>
            <p>Understand your risk appetite and manage your manual practice holdings.</p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Link className="btn-secondary" to="/risk">
                Risk Profile
              </Link>
              <Link className="btn-secondary" to="/portfolio">
                Portfolios
              </Link>
            </div>
          </div>

          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <TrendingUp size={20} color="#16654E" />
              <h2 style={{ margin: 0 }}>Market &amp; Paper Trading</h2>
            </div>
            <p>Search market quotes, curate your watchlist, and practice simulated orders.</p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Link className="btn-secondary" to="/market">
                Market
              </Link>
              <Link className="btn-secondary" to="/paper-trading">
                Paper Trade
              </Link>
            </div>
          </div>

          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <CreditCard size={20} color="var(--color-accent-coral)" />
              <h2 style={{ margin: 0 }}>Spending &amp; Alerts</h2>
            </div>
            <p>Spend with intention using category insights and smart threshold notifications.</p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Link className="btn-secondary" to="/spending">
                Spending
              </Link>
              <Link className="btn-secondary" to="/alerts">
                Alerts
              </Link>
            </div>
          </div>

          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Bot size={20} color="var(--color-accent-violet)" />
              <h2 style={{ margin: 0 }}>Grounded AI Assistant</h2>
            </div>
            <p>Ask citation-backed questions about diversification, risk, and financial concepts.</p>
            <Link className="btn-secondary" to="/chat">
              Ask FinEx AI
            </Link>
          </div>

          <div className="local-persona-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Bell size={20} color="#16654E" />
              <h2 style={{ margin: 0 }}>Watchlist &amp; Insights</h2>
            </div>
            <p>Keep track of the companies and instruments that matter to your learning journey.</p>
            <Link className="btn-secondary" to="/watchlist">
              View Watchlist
            </Link>
          </div>
        </div>
      </section>
    </section>
  );
}
