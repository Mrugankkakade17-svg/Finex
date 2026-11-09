import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocalSession } from '../context/LocalSessionContext';
import { DomainOutcome } from '../context/localS2Capabilities';
import { LocalApplicationError } from '../services/localApplicationClient';
/** Route lifetime + private session work epoch. Abort-ignoring adapters cannot update a departed form. */
export function useLocalS2Tasks() {
  const session = useLocalSession();
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const mounted = useRef(true), active = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState<LocalApplicationError | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      active.current?.abort();
      active.current = null;
    };
  }, []);
  useEffect(() => {
    active.current?.abort();
    active.current = null;
    setBusy(false);
  }, [session.workEpoch]);
  useEffect(() => {
    if (error) {
      errorRef.current?.focus();
      errorRef.current?.scrollIntoView?.({ block: 'center', behavior: 'auto' });
    }
  }, [error]);
  const fail = useCallback((failure: unknown) => {
    if (mounted.current)
      setError(new LocalApplicationError(failure instanceof LocalApplicationError ? failure.code : 'API_UNAVAILABLE'));
  }, []);
  const run = useCallback(async <T>(request: (signal: AbortSignal) => Promise<DomainOutcome<T>>, confirmed: (data: T) => void): Promise<boolean> => {
    if (!mounted.current || active.current || sessionRef.current.busy)
      return false;
    const controller = new AbortController(), epoch = sessionRef.current.workEpoch;
    active.current = controller;
    const current = () => mounted.current && active.current === controller && !controller.signal.aborted && sessionRef.current.isCurrentWork(epoch);
    setBusy(true);
    setError(null);
    try {
      const outcome = await request(controller.signal);
      if (!current())
        return false;
      if (outcome.status === 'success') {
        confirmed(outcome.value);
        return true;
      }
      if (outcome.status === 'error')
        fail(outcome.error);
      return false;
    }
    catch (failure) {
      if (current())
        fail(failure);
      return false;
    }
    finally {
      if (active.current === controller) {
        active.current = null;
        if (mounted.current)
          setBusy(false);
      }
    }
  }, [fail]);
  return { run, fail, busy: busy || session.busy, error, errorRef, clearError: () => setError(null) };
}
