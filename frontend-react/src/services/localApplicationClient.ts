import { createLocalS2Client } from './localS2Client';
import { LocalApplicationError, LOCAL_SCOPE, LOCAL_CONTRACT_VERSION, LOCAL_PROFILE_VERSION, LOCAL_CONSENT_VERSION, validateLocalBaseOrigin, isKnownLocalErrorCode } from './localApplicationBoundary';
export { LocalApplicationError, LOCAL_SCOPE, LOCAL_CONTRACT_VERSION, LOCAL_PROFILE_VERSION, LOCAL_CONSENT_VERSION, validateLocalBaseOrigin } from './localApplicationBoundary';
/** Typed boundary for the persistent, synthetic local application, never the pilot. */

export type LocalAlias = 'learner-a' | 'learner-b';
export type LocalExperience = 'beginner' | 'intermediate' | 'advanced';
export interface LocalUser { id: string; alias: LocalAlias; }
export interface LocalIdentity {
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  user: LocalUser;
}
export interface LocalLogin extends LocalIdentity {
  access_token: string;
  token_type: 'Bearer';
  expires_at: string;
}
export interface LocalLogout {
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  signed_out: true;
}
export interface LocalDraftInput {
  display_name: string | null;
  experience_level: LocalExperience | null;
}
export interface LocalOnboardingState {
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  profile_schema_version: typeof LOCAL_PROFILE_VERSION;
  consent_version: typeof LOCAL_CONSENT_VERSION;
  consent: { accepted: boolean; version: typeof LOCAL_CONSENT_VERSION; recorded_at: string; } | null;
  draft: LocalDraftInput & { updated_at: string | null; };
  onboarding_completed: boolean;
  completed_at: string | null;
}
export interface LocalRequestOptions { signal?: AbortSignal; }
export interface LocalApplicationClient {
  /** Optional only for backwards-compatible S1 test adapters; never a runtime fixture fallback. */
  s2?: import('./localS2Client').LocalS2Api;
  login(alias: LocalAlias, options?: LocalRequestOptions): Promise<LocalLogin>;
  me(token: string, options?: LocalRequestOptions): Promise<LocalIdentity>;
  logout(token: string, options?: LocalRequestOptions): Promise<LocalLogout>;
  state(token: string, options?: LocalRequestOptions): Promise<LocalOnboardingState>;
  saveDraft(token: string, draft: LocalDraftInput, options?: LocalRequestOptions): Promise<LocalOnboardingState>;
  setConsent(token: string, accepted: boolean, options?: LocalRequestOptions): Promise<LocalOnboardingState>;
  complete(token: string, options?: LocalRequestOptions): Promise<LocalOnboardingState>;
}
export interface LocalClientConfiguration {
  baseOrigin?: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}


function invalidResponse(): never { throw new LocalApplicationError('RESPONSE_INVALID'); }
function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return invalidResponse();
  return value as Record<string, unknown>;
}
function text(value: unknown, maximum = 128): string {
  if (typeof value !== 'string' || !value || value.length > maximum) return invalidResponse();
  return value;
}
function utcTime(value: unknown): string {
  const timestamp = text(value, 40);
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|\+00:00)$/.exec(timestamp);
  const date = new Date(timestamp);
  if (!parts || !Number.isFinite(date.getTime()) ||
      date.getUTCFullYear() !== Number(parts[1]) || date.getUTCMonth() + 1 !== Number(parts[2]) ||
      date.getUTCDate() !== Number(parts[3]) || date.getUTCHours() !== Number(parts[4]) ||
      date.getUTCMinutes() !== Number(parts[5]) || date.getUTCSeconds() !== Number(parts[6])) {
    return invalidResponse();
  }
  return timestamp;
}
function nullableTime(value: unknown): string | null { return value === null ? null : utcTime(value); }
function scope(data: Record<string, unknown>): void {
  if (data.scope !== LOCAL_SCOPE || data.contract_version !== LOCAL_CONTRACT_VERSION) invalidResponse();
}
function user(value: unknown): LocalUser {
  const data = record(value);
  if (data.alias !== 'learner-a' && data.alias !== 'learner-b') return invalidResponse();
  return { id: text(data.id), alias: data.alias };
}
export function validateLocalIdentity(value: unknown): LocalIdentity {
  const data = record(value);
  scope(data);
  return { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION, user: user(data.user) };
}
export function validateLocalLogin(value: unknown): LocalLogin {
  const data = record(value);
  const identity = validateLocalIdentity(data);
  if (data.token_type !== 'Bearer' || typeof data.access_token !== 'string' ||
      !/^[A-Za-z0-9_-]{43}$/.test(data.access_token)) return invalidResponse();
  return { ...identity, access_token: data.access_token, token_type: 'Bearer', expires_at: utcTime(data.expires_at) };
}
export function hasCompletedOnboarding(value: LocalOnboardingState | null): boolean {
  return value !== null && value.scope === LOCAL_SCOPE && value.contract_version === LOCAL_CONTRACT_VERSION &&
    value.profile_schema_version === LOCAL_PROFILE_VERSION && value.consent_version === LOCAL_CONSENT_VERSION &&
    value.onboarding_completed === true && value.completed_at !== null &&
    value.consent?.accepted === true && value.consent.version === LOCAL_CONSENT_VERSION &&
    typeof value.draft.display_name === 'string' && value.draft.display_name.trim().length > 0 &&
    value.draft.experience_level !== null && value.draft.updated_at !== null;
}
export function validateLocalState(value: unknown): LocalOnboardingState {
  const data = record(value);
  scope(data);
  if (data.profile_schema_version !== LOCAL_PROFILE_VERSION || data.consent_version !== LOCAL_CONSENT_VERSION ||
      typeof data.onboarding_completed !== 'boolean') return invalidResponse();
  const draft = record(data.draft);
  if (draft.display_name !== null && (typeof draft.display_name !== 'string' ||
      Array.from(draft.display_name).length > 80 || draft.display_name !== draft.display_name.trim())) return invalidResponse();
  const experience = draft.experience_level;
  if (experience !== null && experience !== 'beginner' && experience !== 'intermediate' && experience !== 'advanced') {
    return invalidResponse();
  }
  let consent: LocalOnboardingState['consent'] = null;
  if (data.consent !== null) {
    const decision = record(data.consent);
    if (typeof decision.accepted !== 'boolean' || decision.version !== LOCAL_CONSENT_VERSION) return invalidResponse();
    consent = { accepted: decision.accepted, version: LOCAL_CONSENT_VERSION, recorded_at: utcTime(decision.recorded_at) };
  }
  const decoded: LocalOnboardingState = { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    profile_schema_version: LOCAL_PROFILE_VERSION, consent_version: LOCAL_CONSENT_VERSION, consent,
    draft: { display_name: draft.display_name as string | null, experience_level: experience,
      updated_at: nullableTime(draft.updated_at) },
    onboarding_completed: data.onboarding_completed, completed_at: nullableTime(data.completed_at) };
  if ((decoded.draft.display_name !== null || decoded.draft.experience_level !== null) &&
      decoded.draft.updated_at === null) return invalidResponse();
  if (decoded.onboarding_completed ? !hasCompletedOnboarding(decoded) : decoded.completed_at !== null) return invalidResponse();
  return decoded;
}
export function validateLocalSavedDraft(value: unknown, input: LocalDraftInput): LocalOnboardingState {
  const state = validateLocalState(value);
  const expectedLabel = input.display_name === null ? null : input.display_name.trim();
  if (state.draft.display_name !== expectedLabel || state.draft.experience_level !== input.experience_level ||
      state.draft.updated_at === null) return invalidResponse();
  return state;
}
export function validateLocalConsent(value: unknown, accepted: boolean): LocalOnboardingState {
  const state = validateLocalState(value);
  if (state.consent === null || state.consent.version !== LOCAL_CONSENT_VERSION || state.consent.accepted !== accepted) return invalidResponse();
  return state;
}
export function validateLocalCompletion(value: unknown): LocalOnboardingState {
  const state = validateLocalState(value);
  if (!hasCompletedOnboarding(state)) return invalidResponse();
  return state;
}
export function validateLocalLogout(value: unknown): LocalLogout {
  const data = record(value);
  scope(data);
  if (data.signed_out !== true) return invalidResponse();
  return { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION, signed_out: true };
}

export function createLocalApplicationClient(config: LocalClientConfiguration = {}): LocalApplicationClient {
  // This is evaluated before login can acquire a token, and remains immutable per client.
  const origin = validateLocalBaseOrigin(config.baseOrigin || process.env.REACT_APP_FINEX_API_BASE_URL || 'http://127.0.0.1:8000');
  const timeoutMs = config.timeoutMs ?? 8000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 50 || timeoutMs > 30000) {
    throw new LocalApplicationError('LOCAL_ORIGIN_INVALID');
  }
  const fetchImpl = config.fetchImpl;
  async function request<T>(path: string, method: 'GET' | 'POST' | 'PUT', decode: (data: unknown) => T,
    bearer: string | undefined, payload: Record<string, unknown> | undefined, options: LocalRequestOptions = {}): Promise<T> {
    if (options.signal?.aborted) throw new LocalApplicationError('REQUEST_CANCELLED');
    if (bearer !== undefined && !/^[A-Za-z0-9_-]{43}$/.test(bearer)) throw new LocalApplicationError('SESSION_INVALID');
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancel = (): void => undefined;
    const bounded = new Promise<never>((_resolve, reject) => {
      cancel = () => { controller.abort(); reject(new LocalApplicationError('REQUEST_CANCELLED')); };
      options.signal?.addEventListener('abort', cancel, { once: true });
      timer = setTimeout(() => { controller.abort(); reject(new LocalApplicationError('REQUEST_TIMEOUT')); }, timeoutMs);
    });
    async function perform(): Promise<T> {
      const sender = fetchImpl ?? (typeof globalThis.fetch === 'function' ? globalThis.fetch.bind(globalThis) : undefined);
      if (typeof sender !== 'function') throw new LocalApplicationError('API_UNAVAILABLE');
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (bearer !== undefined) headers.Authorization = 'Bearer ' + bearer;
      if (payload !== undefined) headers['Content-Type'] = 'application/json';
      const response = await sender(origin + path, { method, headers,
        body: payload === undefined ? undefined : JSON.stringify(payload), signal: controller.signal,
        credentials: 'omit', cache: 'no-store', redirect: 'error' });
      // A current HTTP401 ends the session even when a proxy/body cannot be decoded.
      if (response.status === 401) throw new LocalApplicationError('SESSION_INVALID');
      if (response.redirected === true) return invalidResponse();
      const envelope = record(await response.json());
      if (response.ok !== true) {
        const code = envelope.error_code;
        if (envelope.success !== false || typeof code !== 'string' || code === 'SESSION_INVALID') return invalidResponse();
        throw new LocalApplicationError(isKnownLocalErrorCode(code) ? code : 'API_UNAVAILABLE');
      }
      const metadata = record(envelope.meta);
      if (envelope.success !== true || typeof envelope.message !== 'string' ||
          metadata.apiVersion !== 'v1' || metadata.dataStatus !== 'CACHED' || metadata.dataAsOf !== null ||
          typeof metadata.correlationId !== 'string' || metadata.correlationId.length > 128 ||
          !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(metadata.correlationId)) return invalidResponse();
      return decode(envelope.data);
    }
    try {
      return await Promise.race([perform(), bounded]);
    } catch (failure) {
      if (failure instanceof LocalApplicationError) throw failure;
      throw new LocalApplicationError(controller.signal.aborted ? 'REQUEST_CANCELLED' : 'API_UNAVAILABLE');
    } finally {
      if (timer !== undefined) clearTimeout(timer);
      options.signal?.removeEventListener('abort', cancel);
    }
  }
  return {
    s2: createLocalS2Client({ ...config, baseOrigin: origin, timeoutMs }),
    login: (alias, options) => {
      if (alias !== 'learner-a' && alias !== 'learner-b') return Promise.reject(new LocalApplicationError('UNKNOWN_LOCAL_ALIAS'));
      return request('/api/v1/local-auth/mock-login', 'POST', (value) => {
        const login = validateLocalLogin(value);
        if (login.user.alias !== alias) return invalidResponse();
        return login;
      }, undefined, { alias }, options);
    },
    me: (bearer, options) => request('/api/v1/local-auth/me', 'GET', validateLocalIdentity, bearer, undefined, options),
    logout: (bearer, options) => request('/api/v1/local-auth/logout', 'POST', validateLocalLogout, bearer, undefined, options),
    state: (bearer, options) => request('/api/v1/local-onboarding/state', 'GET', validateLocalState, bearer, undefined, options),
    saveDraft: (bearer, draft, options) => {
      const requested = Object.freeze({ display_name: draft.display_name, experience_level: draft.experience_level });
      return request('/api/v1/local-onboarding/draft', 'PUT',
        (value) => validateLocalSavedDraft(value, requested), bearer,
        { profile_schema_version: LOCAL_PROFILE_VERSION, ...requested }, options);
    },
    setConsent: (bearer, accepted, options) => request('/api/v1/local-onboarding/consent', 'POST',
      (value) => validateLocalConsent(value, accepted), bearer,
      { consent_version: LOCAL_CONSENT_VERSION, consent_given: accepted }, options),
    complete: (bearer, options) => request('/api/v1/local-onboarding/complete', 'POST', validateLocalCompletion, bearer,
      { consent_version: LOCAL_CONSENT_VERSION, profile_schema_version: LOCAL_PROFILE_VERSION }, options),
  };
}
