import React, { useEffect, useRef, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { hasCompletedOnboarding } from '../services/localApplicationClient';
/** A route entry earns its gate from a fresh server check, never browser storage. */
export function LocalApplicationGuard({ children, requireCompletion = true }: {
  children: React.ReactNode;
  requireCompletion?: boolean;
}) {
  const session = useLocalSession();
  const location = useLocation();
  const [retry, setRetry] = useState(0);
  const [check, setCheck] = useState<{
    key: string;
    passed: boolean;
  }>({ key: '', passed: false });
  const key = `${session.sessionEpoch}:${location.key}:${retry}`;
  const currentKey = useRef(key);
  currentKey.current = key;
  const requestedKey = useRef('');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const { user, busy, refresh } = session;
  useEffect(() => {
    if (user === null || busy || requestedKey.current === key)
      return;
    requestedKey.current = key;
    void refresh().then((passed) => {
      if (mounted.current && currentKey.current === key)
        setCheck({ key, passed });
    });
  }, [user, busy, refresh, key]);
  if (user === null)
    return <Navigate to="/login" replace/>;
  if (check.key !== key)
    return <section className="local-card" aria-busy="true">
  <h1 tabIndex={-1}>Checking your local session</h1>
  <p role="status">Confirming your current profile and consent on the backend…</p>
 </section>;
  if (!check.passed || session.onboarding === null)
    return <section className="local-card">
  <h1 tabIndex={-1}>Server check needed</h1>
  <p role="alert" className="local-error">{session.error?.message || 'Your current server state could not be confirmed. Please retry.'}</p>
  <button className="btn-primary" disabled={busy} onClick={() => setRetry((value) => value + 1)}>Retry server check</button>
 </section>;
  if (requireCompletion && !hasCompletedOnboarding(session.onboarding))
    return <Navigate to="/onboarding" replace/>;
  // Keep current-owner form controllers mounted while a check/sign-out is uncertain,
  // but hidden content is neither accessible nor keyboard-interactive. The mount key
  // is independent of work cancellation, so failed logout retains input while a
  // confirmed logout/re-login resets it even if React coalesces all owner updates.
  const ownerMountKey = `${session.sessionEpoch}:${user.id}:${user.alias}`;
  return <>
  {busy && <section className="local-card" aria-busy="true">
   <p role="status">Checking your local session / confirming sign-out…</p>
  </section>}
  <div key={ownerMountKey} hidden={busy}>{children}</div>
 </>;
}
