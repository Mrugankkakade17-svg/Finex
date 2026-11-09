import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { LocalAlias } from '../services/localApplicationClient';

export function LocalLoginPage() {
  const session = useLocalSession();
  const navigate = useNavigate();
  const signIn = async (alias: LocalAlias) => {
    const expectedEpoch = session.sessionEpoch + 1;
    if (await session.login(alias) && session.isCurrentSession(expectedEpoch)) navigate('/onboarding');
  };
  return <section className="local-card local-login" aria-busy={session.busy}>
    <p className="local-eyebrow">A safe place to start</p>
    <h1 tabIndex={-1}>{session.user ? 'Resume your local journey' : 'Choose a local persona'}</h1>
    <p className="local-lede">This is an explicitly enabled local educational application, not real Google sign-in.
      Use only the two synthetic personas. Do not enter a real email, password or legal name.</p>
    <div className="local-notice">
      <h2>How local sign-in works</h2>
      <p>Your short-lived session stays in memory only. Reloading signs you out; choosing the same persona again
        resumes its saved profile and consent from the native backend.</p>
      <p>Anyone trusted to use this local machine can select either persona. Do not expose this application publicly.</p>
    </div>
    {session.error && session.errorOperation !== 'logout' && <p role="alert" className="local-error">{session.error.message}</p>}
    {session.user ? <div className="local-actions">
      <Link className="btn-primary" to="/onboarding">Check and resume onboarding</Link>
      <p className="local-help">A session is known, but only a fresh server check grants feature access.</p>
    </div> : <div className="local-persona-grid">
      {(['learner-a', 'learner-b'] as LocalAlias[]).map((alias) => <div className="local-persona-card" key={alias}>
        <span className="local-persona-monogram" aria-hidden="true">{alias === 'learner-a' ? 'A' : 'B'}</span>
        <h2>{alias}</h2>
        <p>Independent synthetic profile, consent and saved progress.</p>
        <button className="btn-primary" disabled={session.busy} onClick={() => { void signIn(alias); }}>Sign in as {alias}</button>
      </div>)}
    </div>}
    {session.operation === 'login' && <p role="status">Validating the persona and loading saved server state…</p>}
    <p className="local-help">If the backend is stopped or the local application is disabled, a safe error is shown. There is no fixture fallback.</p>
  </section>;
}
