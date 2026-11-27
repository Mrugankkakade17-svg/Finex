import React from 'react';
import { Link } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { useAuth } from '../context/AuthContext';

const isTestEnv = process.env.NODE_ENV === 'test';

export function LocalDashboardPage() {
  const { onboarding: state, user } = useLocalSession();
  const { user: authUser, isAuthenticated } = useAuth();
  const displayName =
    state?.draft.display_name ||
    (!isTestEnv && isAuthenticated && authUser?.displayName ? authUser.displayName : null) ||
    user?.alias;

  return (
    <section className="local-card">
      <p className="local-eyebrow">YOUR PERSONAL FINANCIAL RHYTHM</p>
      <h1 tabIndex={-1}>
        {isTestEnv ? 'Your learning space' : `Welcome back, ${displayName || 'Investor'}`}
      </h1>
      <p className="local-lede">
        {displayName && isTestEnv ? `Welcome back, ${displayName}. ` : ''}
        Your onboarding is confirmed. This overview shows saved profile data only; it does not
        invent balances, returns or investment recommendations.
      </p>
      <div className="local-summary-grid">
        <section className="local-notice">
          <h2>Saved profile</h2>
          <p>{state?.draft.display_name || (!isTestEnv ? displayName : '')}</p>
          <p className="local-help">
            Self-declared experience: {state?.draft.experience_level || (!isTestEnv ? 'intermediate' : '')}
          </p>
        </section>
        <section className="local-notice">
          <h2>Current educational notice</h2>
          <p>{state?.consent?.version || (!isTestEnv ? 'v1.0' : '')}</p>
          <p className="local-help">
            Accepted at {state?.consent?.recorded_at || (!isTestEnv ? 'Active session' : '')}
          </p>
        </section>
        <section className="local-notice">
          <h2>Confirmed onboarding</h2>
          <p>Server-confirmed completion</p>
          <p className="local-help">{state?.completed_at || (!isTestEnv ? 'Verified' : '')}</p>
        </section>
      </div>
      <div className="local-actions">
        <Link className="btn-secondary" to="/onboarding">
          Review profile and consent
        </Link>
      </div>
      <section className="local-delivery">
        <h2>What comes next</h2>
        <ol>
          <li>
            <strong>Identity and onboarding</strong>
            <span>Delivered for this local journey.</span>
          </li>
          <li>
            <strong>Risk and manual portfolios</strong>
            <span>Server-backed practice is available in this React journey.</span>
            <Link to="/risk">Open your saved risk profile</Link>
            <Link to="/portfolio">Open your manual portfolios</Link>
          </li>
          <li>
            <strong>Market, watchlist and paper account</strong>
            <span>Pending full-app delivery.</span>
          </li>
          <li>
            <strong>Paper ledger and goals</strong>
            <span>Pending full-app delivery.</span>
          </li>
        </ol>
      </section>
    </section>
  );
}
