import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { useAuth } from '../context/AuthContext';
import { LocalAlias } from '../services/localApplicationClient';

export function LocalLoginPage() {
  const session = useLocalSession();
  const { user: authUser, isAuthenticated, login: authLogin } = useAuth();
  const navigate = useNavigate();
  const [customName, setCustomName] = useState(
    isAuthenticated && authUser?.displayName && authUser.displayName !== 'Investor'
      ? authUser.displayName
      : ''
  );
  const [nameError, setNameError] = useState('');

  const activeName =
    session.onboarding?.draft?.display_name?.trim() ||
    (isAuthenticated && authUser?.displayName ? authUser.displayName : null) ||
    session.user?.alias ||
    null;

  const handlePersonalSignIn = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customName.trim();
    if (!trimmed) {
      setNameError('Please enter your name to personalize your FinEx workspace.');
      return;
    }
    setNameError('');
    authLogin({
      displayName: trimmed,
      email: `${trimmed.toLowerCase().replace(/[^a-z0-9]/g, '.')}@finex.app`,
    });
    navigate('/dashboard');
  };

  const signIn = async (alias: LocalAlias) => {
    const chosenName = customName.trim() || alias;
    authLogin({
      displayName: chosenName,
      email: `${chosenName.toLowerCase().replace(/[^a-z0-9]/g, '.')}@finex.app`,
    });
    const expectedEpoch = session.sessionEpoch + 1;
    if ((await session.login(alias)) && session.isCurrentSession(expectedEpoch)) {
      navigate('/onboarding');
    } else if (!session.user) {
      // If local backend persona store isn't running, allow seamless local exploration with their name
      navigate('/dashboard');
    }
  };

  return (
    <section className="local-card local-login" aria-busy={session.busy}>
      <p className="local-eyebrow">A SAFE PLACE TO START</p>
      <h1 tabIndex={-1}>
        {session.user || isAuthenticated
          ? `Welcome back${activeName ? `, ${activeName}` : ''}`
          : 'Step into your money orbit'}
      </h1>
      <p className="local-lede">
        Personalize your learning and financial rhythm. Enter your name below to sign in, or choose
        one of the guided learning personas to resume saved backend progress.
      </p>

      {/* Personal Name Sign-In Card */}
      <form
        onSubmit={handlePersonalSignIn}
        className="local-notice"
        style={{
          background: 'var(--color-surface)',
          border: '1.5px solid var(--color-surface-divider)',
          marginBottom: '28px',
        }}
      >
        <h2>Sign in with your name</h2>
        <p style={{ color: 'var(--color-text-muted)', marginBottom: '16px' }}>
          Your name will be displayed across your dashboard, goals, portfolio, and AI assistant.
        </p>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            alignItems: 'center',
          }}
        >
          <input
            type="text"
            value={customName}
            onChange={(e) => {
              setCustomName(e.target.value);
              setNameError('');
            }}
            placeholder="Enter your name (e.g. Aarav, Priya, Mrugank...)"
            aria-label="Your name"
            maxLength={80}
            style={{
              flex: '1 1 260px',
              minHeight: '48px',
            }}
          />
          <button type="submit" className="btn-primary" disabled={session.busy}>
            <span>Continue as {customName.trim() || 'yourself'}</span>
            <span aria-hidden="true">↗</span>
          </button>
        </div>
        {nameError && (
          <p role="alert" className="local-error" style={{ marginTop: '12px', marginBottom: 0 }}>
            {nameError}
          </p>
        )}
      </form>

      {session.error && session.errorOperation !== 'logout' && (
        <p role="alert" className="local-error">
          {session.error.message}
        </p>
      )}

      {session.user ? (
        <div className="local-actions">
          <Link className="btn-primary" to="/onboarding">
            Check and resume onboarding
          </Link>
          <Link className="btn-secondary" to="/dashboard">
            Open dashboard
          </Link>
        </div>
      ) : (
        <>
          <p className="local-eyebrow" style={{ marginBottom: '12px' }}>
            Or choose a guided persona
          </p>
          <div className="local-persona-grid">
            {(['learner-a', 'learner-b'] as LocalAlias[]).map((alias) => (
              <div className="local-persona-card" key={alias}>
                <span className="local-persona-monogram" aria-hidden="true">
                  {alias === 'learner-a' ? 'A' : 'B'}
                </span>
                <h2>{alias}</h2>
                <p>Independent profile, educational consent, and saved progress.</p>
                <button
                  className="btn-primary"
                  disabled={session.busy}
                  onClick={() => {
                    void signIn(alias);
                  }}
                >
                  Sign in as {alias}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {session.operation === 'login' && (
        <p role="status" className="local-status" style={{ marginTop: '16px' }}>
          Validating the persona and loading saved server state…
        </p>
      )}
    </section>
  );
}
