import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createLocalApplicationClient, hasCompletedOnboarding, LocalRequestOptions, LocalAlias, LocalApplicationClient, LocalApplicationError, LocalDraftInput, LocalOnboardingState, LocalUser, validateLocalIdentity, validateLocalLogin, validateLocalLogout, validateLocalState, validateLocalSavedDraft, validateLocalConsent, validateLocalCompletion, } from '../services/localApplicationClient';
import { DomainOutcome, LocalS2Capabilities } from './localS2Capabilities';
import { checkedS2, confirmedHolding, confirmedPortfolio, LocalS2Api, metricsMeta, nullMeta, portfolioRequest, riskMeta, updatedMeta } from '../services/localS2Client';
import { cursorS2, decodeCatalog, decodeHolding, decodeHoldingDeletion, decodeHoldingList, decodeMetrics, decodePortfolio, decodePortfolioDeletion, decodePortfolioList, decodeQuestionnaire, decodeRiskDraft, decodeRiskHistory, decodeSavedRisk, HoldingInput, HoldingUpdate, invalidS2, LocalS2Response, PortfolioInput, RiskInput, riskInput, sameRiskInput, uuidS2 } from '../services/localS2Models';
export type LocalOperation = 'login' | 'refresh' | 'logout' | 'save' | 'consent' | 'complete' | null;
export interface LocalSession {
  user: LocalUser | null;
  onboarding: LocalOnboardingState | null;
  error: LocalApplicationError | null;
  errorOperation: LocalOperation;
  busy: boolean;
  operation: LocalOperation;
  sessionEpoch: number;
  domain: LocalS2Capabilities;
  workEpoch: number;
  isCurrentWork(epoch: number): boolean;
  login(alias: LocalAlias): Promise<boolean>;
  refresh(): Promise<boolean>;
  logout(): Promise<boolean>;
  saveDraft(input: LocalDraftInput): Promise<boolean>;
  setConsent(accepted: boolean): Promise<boolean>;
  complete(): Promise<boolean>;
  isCurrentSession(epoch: number): boolean;
}
const Context = createContext<LocalSession | null>(null);
type Snapshot = Pick<LocalSession, 'user' | 'onboarding' | 'error' | 'errorOperation' | 'busy' | 'operation' | 'sessionEpoch' | 'workEpoch'>;
interface Job {
  generation: number;
  controller: AbortController;
  operation: Exclude<LocalOperation, null>;
}
function safeFailure(failure: unknown): LocalApplicationError {
  // Never display an arbitrary exception/body, even from a substituted adapter.
  return new LocalApplicationError(failure instanceof LocalApplicationError ? failure.code : 'API_UNAVAILABLE');
}
export function LocalSessionProvider({ children, client: suppliedClient }: {
  children: React.ReactNode;
  client?: LocalApplicationClient;
}) {
  const configuration = useMemo(() => {
    try {
      return { client: suppliedClient || createLocalApplicationClient(), error: null };
    }
    catch (failure) {
      return { client: null, error: safeFailure(failure) };
    }
  }, [suppliedClient]);
  const { client } = configuration;
  const [snapshot, setSnapshot] = useState<Snapshot>({ user: null, onboarding: null,
    error: configuration.error, errorOperation: null, busy: false, operation: null, sessionEpoch: 0, workEpoch: 0 });
  const snapshotRef = useRef(snapshot);
  const token = useRef<string | null>(null);
  const expiry = useRef<number | null>(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const controllers = useRef(new Set<AbortController>());
  const activeJob = useRef<Job | null>(null);
  const publish = useCallback((change: Partial<Snapshot>) => {
    if (!mounted.current)
      return;
    snapshotRef.current = { ...snapshotRef.current, ...change };
    setSnapshot(snapshotRef.current);
  }, []);
  const invalidateWork = useCallback(() => {
    generation.current += 1;
    controllers.current.forEach((controller) => controller.abort());
    controllers.current.clear();
    activeJob.current = null;
    publish({ workEpoch: generation.current });
  }, [publish]);
  const endSession = useCallback((error: LocalApplicationError | null = null) => {
    invalidateWork();
    token.current = null;
    expiry.current = null;
    publish({ user: null, onboarding: null, busy: false, operation: null, error, errorOperation: null,
      sessionEpoch: snapshotRef.current.sessionEpoch + 1 });
  }, [invalidateWork, publish]);
  useEffect(() => {
    mounted.current = true;
    endSession(configuration.error);
    return () => {
      mounted.current = false;
      invalidateWork();
      token.current = null;
      expiry.current = null;
    };
  }, [configuration, endSession, invalidateWork]);
  useEffect(() => {
    if (snapshot.user === null || expiry.current === null)
      return;
    const credential = token.current;
    const delay = Math.max(0, expiry.current - Date.now());
    const timer = setTimeout(() => {
      if (credential !== null && token.current === credential)
        endSession(new LocalApplicationError('SESSION_INVALID'));
    }, delay);
    return () => clearTimeout(timer);
  }, [snapshot.user, snapshot.sessionEpoch, endSession]);
  const current = useCallback((job: Job) => mounted.current && generation.current === job.generation &&
    !job.controller.signal.aborted, []);
  const start = useCallback((operation: Exclude<LocalOperation, null>): Job => {
    const job = { generation: generation.current, controller: new AbortController(), operation };
    controllers.current.add(job.controller);
    activeJob.current = job;
    publish({ busy: true, operation, error: null, errorOperation: null });
    return job;
  }, [publish]);
  const finish = useCallback((job: Job) => {
    controllers.current.delete(job.controller);
    if (!current(job) || activeJob.current !== job)
      return;
    activeJob.current = null;
    publish({ busy: false, operation: null });
  }, [current, publish]);
  const fail = useCallback((job: Job, failure: unknown): boolean => {
    if (!current(job))
      return false;
    const error = safeFailure(failure);
    if (error.code === 'SESSION_INVALID')
      endSession(error);
    else {
      const state = snapshotRef.current.onboarding;
      publish({ error, errorOperation: job.operation, ...(error.code === 'ONBOARDING_REQUIRED' && state !== null
          ? { onboarding: { ...state, onboarding_completed: false, completed_at: null } } : {}) });
    }
    return false;
  }, [current, endSession, publish]);
  const login = useCallback(async (alias: LocalAlias): Promise<boolean> => {
    if (client === null) {
      publish({ error: configuration.error });
      return false;
    }
    // A new identity attempt always invalidates work, including late 401 responses.
    invalidateWork();
    token.current = null;
    expiry.current = null;
    publish({ user: null, onboarding: null, sessionEpoch: snapshotRef.current.sessionEpoch + 1 });
    const job = start('login');
    try {
      const result = validateLocalLogin(await client.login(alias, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      if (result.user.alias !== alias)
        throw new LocalApplicationError('RESPONSE_INVALID');
      if (Date.parse(result.expires_at) <= Date.now())
        throw new LocalApplicationError('SESSION_INVALID');
      const identity = validateLocalIdentity(await client.me(result.access_token, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      if (identity.user.id !== result.user.id || identity.user.alias !== result.user.alias) {
        throw new LocalApplicationError('RESPONSE_INVALID');
      }
      token.current = result.access_token;
      expiry.current = Date.parse(result.expires_at);
      publish({ user: identity.user });
      const state = validateLocalState(await client.state(result.access_token, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      publish({ onboarding: state });
      return true;
    }
    catch (failure) {
      return fail(job, failure);
    }
    finally {
      finish(job);
    }
  }, [client, configuration.error, current, fail, finish, invalidateWork, publish, start]);
  const refresh = useCallback(async (): Promise<boolean> => {
    const credential = token.current;
    const owner = snapshotRef.current.user;
    if (client === null || credential === null || owner === null || activeJob.current !== null)
      return false;
    const job = start('refresh');
    try {
      const identity = validateLocalIdentity(await client.me(credential, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      if (identity.user.id !== owner.id || identity.user.alias !== owner.alias) {
        endSession(new LocalApplicationError('RESPONSE_INVALID'));
        return false;
      }
      const state = validateLocalState(await client.state(credential, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      publish({ onboarding: state });
      return true;
    }
    catch (failure) {
      return fail(job, failure);
    }
    finally {
      finish(job);
    }
  }, [client, current, endSession, fail, finish, publish, start]);
  const logout = useCallback(async (): Promise<boolean> => {
    const credential = token.current;
    if (client === null || credential === null)
      return false;
    // Cancel older work now; retain the same rendered owner/input until revocation is confirmed.
    invalidateWork();
    const job = start('logout');
    try {
      validateLocalLogout(await client.logout(credential, { signal: job.controller.signal }));
      if (!current(job))
        return false;
      endSession();
      return true;
    }
    catch (failure) {
      if (!current(job))
        return false;
      const error = safeFailure(failure);
      if (error.code === 'SESSION_INVALID') {
        endSession(error);
        return true;
      }
      return fail(job, error);
    }
    finally {
      finish(job);
    }
  }, [client, current, endSession, fail, finish, invalidateWork, start]);
  const mutate = useCallback(async (operation: 'save' | 'consent' | 'complete', request: (adapter: LocalApplicationClient, credential: string, signal: AbortSignal) => Promise<LocalOnboardingState>) => {
    const credential = token.current;
    if (client === null || credential === null || snapshotRef.current.user === null || activeJob.current !== null)
      return false;
    const job = start(operation);
    try {
      const state = validateLocalState(await request(client, credential, job.controller.signal));
      if (!current(job))
        return false;
      publish({ onboarding: state });
      return true;
    }
    catch (failure) {
      return fail(job, failure);
    }
    finally {
      finish(job);
    }
  }, [client, current, fail, finish, publish, start]);
  const saveDraft = useCallback((input: LocalDraftInput) => {
    const requested = Object.freeze({ display_name: input.display_name, experience_level: input.experience_level });
    return mutate('save', async (adapter, credential, signal) => validateLocalSavedDraft(await adapter.saveDraft(credential, requested, { signal }), requested));
  }, [mutate]);
  const setConsent = useCallback((accepted: boolean) => mutate('consent', async (adapter, credential, signal) => validateLocalConsent(await adapter.setConsent(credential, accepted, { signal }), accepted)), [mutate]);
  const complete = useCallback(() => mutate('complete', async (adapter, credential, signal) => validateLocalCompletion(await adapter.complete(credential, { signal }))), [mutate]);
  const isCurrentSession = useCallback((epoch: number) => mounted.current && token.current !== null &&
    snapshotRef.current.user !== null && snapshotRef.current.sessionEpoch === epoch &&
    snapshotRef.current.operation !== 'logout', []);
  const isCurrentWork = useCallback((epoch: number) => mounted.current && generation.current === epoch && token.current !== null &&
    snapshotRef.current.user !== null && snapshotRef.current.operation !== 'logout', []);
  const domainRequest = useCallback(async <T,>(options: LocalRequestOptions | undefined, request: (api: LocalS2Api, credential: string, signal: AbortSignal) => Promise<LocalS2Response<T>>, validate: (value: unknown) => LocalS2Response<T>): Promise<DomainOutcome<LocalS2Response<T>>> => {
    const credential = token.current, owner = snapshotRef.current.user;
    if (!mounted.current || options?.signal?.aborted || activeJob.current !== null || credential === null || owner === null)
      return { status: 'cancelled' };
    if (!hasCompletedOnboarding(snapshotRef.current.onboarding))
      return { status: 'error', error: new LocalApplicationError('ONBOARDING_REQUIRED') };
    const adapter = client?.s2;
    if (!adapter)
      return { status: 'error', error: new LocalApplicationError('S2_UNAVAILABLE') };
    const captured = generation.current, controller = new AbortController();
    controllers.current.add(controller);
    const currentOwner = () => mounted.current && captured === generation.current && token.current === credential && snapshotRef.current.user?.id === owner.id;
    const valid = () => currentOwner() && !controller.signal.aborted;
    const pageAbort = () => controller.abort();
    options?.signal?.addEventListener('abort', pageAbort, { once: true });
    let timer: ReturnType<typeof setTimeout> | undefined, cancel = (): void => undefined;
    let timedOut = false;
    const cancelled = new Promise<never>((_yes, no) => {
      cancel = () => no(new LocalApplicationError('REQUEST_CANCELLED'));
      controller.signal.addEventListener('abort', cancel, { once: true });
      timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, 30000);
    });
    try {
      const response = await Promise.race([request(adapter, credential, controller.signal), cancelled]);
      if (!valid()) {
        if (timedOut && currentOwner() && !options?.signal?.aborted)
          return { status: 'error', error: new LocalApplicationError('REQUEST_TIMEOUT') };
        return { status: 'cancelled' };
      }
      return { status: 'success', value: validate(response) };
    }
    catch (failure) {
      if (!valid()) {
        if (timedOut && currentOwner() && !options?.signal?.aborted)
          return { status: 'error', error: new LocalApplicationError('REQUEST_TIMEOUT') };
        return { status: 'cancelled' };
      }
      const error = safeFailure(failure);
      if (error.code === 'REQUEST_CANCELLED')
        return { status: 'cancelled' };
      if (error.code === 'SESSION_INVALID')
        endSession(error);
      else if (error.code === 'ONBOARDING_REQUIRED') {
        invalidateWork();
        const state = snapshotRef.current.onboarding;
        publish({ onboarding: state === null ? null : { ...state, onboarding_completed: false, completed_at: null }, error, errorOperation: null });
      }
      return { status: 'error', error };
    }
    finally {
      if (timer !== undefined)
        clearTimeout(timer);
      controllers.current.delete(controller);
      options?.signal?.removeEventListener('abort', pageAbort);
      controller.signal.removeEventListener('abort', cancel);
    }
  }, [client, endSession, invalidateWork, publish]);
  const domain = useMemo<LocalS2Capabilities>(() => {
    const response = <T,>(decode: (v: unknown) => T, meta: (data: T) => {
      status: 'CACHED' | 'UNAVAILABLE';
      asOf: string | null;
    }) => (v: unknown) => checkedS2(v, decode, meta);
    const owned = <T extends {
      portfolio_id: string;
    }>(decode: (v: unknown) => T, id: string) => (v: unknown) => {
      const d = decode(v);
      if (d.portfolio_id !== id)
        return invalidS2();
      return d;
    };
    const frozenHolding = <T extends HoldingUpdate>(input: T): T => Object.freeze({ ...input });
    const frozenPortfolio = (input: PortfolioInput) => Object.freeze(portfolioRequest(input));
    const frozenRisk = (input: RiskInput, complete = false): RiskInput => {
      const copied = riskInput(input, complete);
      copied.answers.forEach((answer) => Object.freeze(answer));
      Object.freeze(copied.answers);
      return Object.freeze(copied);
    };
    return {
      questionnaire: (o) => domainRequest(o, (a, t, s) => a.questionnaire(t, { signal: s }), response(decodeQuestionnaire, nullMeta)),
      riskDraft: (o) => domainRequest(o, (a, t, s) => a.riskDraft(t, { signal: s }), response(decodeRiskDraft, updatedMeta)),
      saveRiskDraft: (input, o) => {
        const frozen = frozenRisk(input);
        return domainRequest(o, (a, t, s) => a.saveRiskDraft(t, frozen, { signal: s }), response((v) => {
          const d = decodeRiskDraft(v);
          if (!sameRiskInput(d, frozen) || d.updated_at === null)
            return invalidS2();
          return d;
        }, updatedMeta));
      },
      submitRisk: (input, o) => {
        const frozen = Object.freeze({ ...frozenRisk({ questionnaire_id: input.questionnaire_id, questionnaire_version: input.questionnaire_version, answers: input.answers }, true), idempotency_key: uuidS2(input.idempotency_key) });
        return domainRequest(o, (a, t, s) => a.submitRisk(t, frozen, { signal: s }), response((v) => {
          const d = decodeSavedRisk(v);
          if (!sameRiskInput(d.input, frozen))
            return invalidS2();
          return d;
        }, riskMeta));
      },
      riskHistory: (before, o) => {
        cursorS2(before);
        return domainRequest(o, (a, t, s) => a.riskHistory(t, before, { signal: s }), response(decodeRiskHistory, nullMeta));
      },
      riskDetail: (id, o) => {
        uuidS2(id);
        return domainRequest(o, (a, t, s) => a.riskDetail(t, id, { signal: s }), response((v) => {
          const d = decodeSavedRisk(v);
          if (d.assessment_id !== id)
            return invalidS2();
          return d;
        }, riskMeta));
      },
      catalog: (o) => domainRequest(o, (a, t, s) => a.catalog(t, { signal: s }), response(decodeCatalog, nullMeta)),
      portfolios: (o) => domainRequest(o, (a, t, s) => a.portfolios(t, { signal: s }), response(decodePortfolioList, nullMeta)),
      portfolio: (id, o) => {
        uuidS2(id);
        return domainRequest(o, (a, t, s) => a.portfolio(t, id, { signal: s }), response(owned(decodePortfolio, id), updatedMeta));
      },
      createPortfolio: (input, o) => {
        const frozen = frozenPortfolio(input);
        return domainRequest(o, (a, t, s) => a.createPortfolio(t, frozen, { signal: s }), response((v) => confirmedPortfolio(v, frozen), updatedMeta));
      },
      updatePortfolio: (id, input, o) => {
        uuidS2(id);
        const frozen = frozenPortfolio(input);
        return domainRequest(o, (a, t, s) => a.updatePortfolio(t, id, frozen, { signal: s }), response((v) => confirmedPortfolio(v, frozen, id), updatedMeta));
      },
      deletePortfolio: (id, o) => {
        uuidS2(id);
        return domainRequest(o, (a, t, s) => a.deletePortfolio(t, id, { signal: s }), response(owned(decodePortfolioDeletion, id), nullMeta));
      },
      holdings: (id, o) => {
        uuidS2(id);
        return domainRequest(o, (a, t, s) => a.holdings(t, id, { signal: s }), response(owned(decodeHoldingList, id), nullMeta));
      },
      holding: (id, h, o) => {
        uuidS2(id);
        uuidS2(h);
        return domainRequest(o, (a, t, s) => a.holding(t, id, h, { signal: s }), response((v) => {
          const d = owned(decodeHolding, id)(v);
          if (d.holding_id !== h)
            return invalidS2();
          return d;
        }, updatedMeta));
      },
      createHolding: (id, input: HoldingInput, o) => {
        uuidS2(id);
        const frozen = frozenHolding(input);
        return domainRequest(o, (a, t, s) => a.createHolding(t, id, frozen, { signal: s }), response((v) => confirmedHolding(v, frozen, id, undefined, frozen.instrument_id), updatedMeta));
      },
      updateHolding: (id, h, input, o) => {
        uuidS2(id);
        uuidS2(h);
        const frozen = frozenHolding(input);
        return domainRequest(o, (a, t, s) => a.updateHolding(t, id, h, frozen, { signal: s }), response((v) => confirmedHolding(v, frozen, id, h), updatedMeta));
      },
      deleteHolding: (id, h, o) => {
        uuidS2(id);
        uuidS2(h);
        return domainRequest(o, (a, t, s) => a.deleteHolding(t, id, h, { signal: s }), response((v) => {
          const d = owned(decodeHoldingDeletion, id)(v);
          if (d.holding_id !== h)
            return invalidS2();
          return d;
        }, nullMeta));
      },
      metrics: (id, o) => {
        uuidS2(id);
        return domainRequest(o, (a, t, s) => a.metrics(t, id, { signal: s }), response(owned(decodeMetrics, id), metricsMeta));
      },
    };
  }, [domainRequest]);
  return <Context.Provider value={{ ...snapshot, login, refresh, logout, saveDraft, setConsent, complete, isCurrentSession, isCurrentWork, domain }}>
 {children}
</Context.Provider>;
}
export function useLocalSession(): LocalSession {
  const value = useContext(Context);
  if (value === null)
    throw new Error('Local session provider is required.');
  return value;
}
