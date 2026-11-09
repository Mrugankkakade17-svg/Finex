import { LocalApplicationError, validateLocalBaseOrigin } from './localApplicationBoundary';
import type { LocalClientConfiguration, LocalRequestOptions } from './localApplicationClient';
import { Catalog, Holding, HoldingDeletion, HoldingInput, HoldingList, HoldingUpdate, LocalQuestionnaire, LocalRiskDraft, LocalS2Metadata, LocalS2Response, Portfolio, PortfolioDeletion, PortfolioInput, PortfolioList, PortfolioMetrics, RiskHistory, RiskInput, RiskSubmission, SavedRisk, cursorS2, decodeCatalog, decodeHolding, decodeHoldingDeletion, decodeHoldingList, decodeMetrics, decodePortfolio, decodePortfolioDeletion, decodePortfolioList, decodeQuestionnaire, decodeRiskDraft, decodeRiskHistory, decodeSavedRisk, exactS2, FIXTURE_AS_OF, invalidS2, objectS2, riskInput, sameDecimal, sameRiskInput, textS2, utcInstant, utcS2, utf8Length, uuidS2 } from './localS2Models';
/** Internal wire adapter. Only the session provider supplies a credential; never expose this on context. */
export interface LocalS2Api {
  questionnaire(token: string, options?: LocalRequestOptions): Promise<LocalS2Response<LocalQuestionnaire>>;
  riskDraft(token: string, options?: LocalRequestOptions): Promise<LocalS2Response<LocalRiskDraft>>;
  saveRiskDraft(token: string, input: RiskInput, options?: LocalRequestOptions): Promise<LocalS2Response<LocalRiskDraft>>;
  submitRisk(token: string, input: RiskSubmission, options?: LocalRequestOptions): Promise<LocalS2Response<SavedRisk>>;
  riskHistory(token: string, before: string | null, options?: LocalRequestOptions): Promise<LocalS2Response<RiskHistory>>;
  riskDetail(token: string, id: string, options?: LocalRequestOptions): Promise<LocalS2Response<SavedRisk>>;
  catalog(token: string, options?: LocalRequestOptions): Promise<LocalS2Response<Catalog>>;
  portfolios(token: string, options?: LocalRequestOptions): Promise<LocalS2Response<PortfolioList>>;
  portfolio(token: string, id: string, options?: LocalRequestOptions): Promise<LocalS2Response<Portfolio>>;
  createPortfolio(token: string, input: PortfolioInput, options?: LocalRequestOptions): Promise<LocalS2Response<Portfolio>>;
  updatePortfolio(token: string, id: string, input: PortfolioInput, options?: LocalRequestOptions): Promise<LocalS2Response<Portfolio>>;
  deletePortfolio(token: string, id: string, options?: LocalRequestOptions): Promise<LocalS2Response<PortfolioDeletion>>;
  holdings(token: string, id: string, options?: LocalRequestOptions): Promise<LocalS2Response<HoldingList>>;
  holding(token: string, id: string, holdingId: string, options?: LocalRequestOptions): Promise<LocalS2Response<Holding>>;
  createHolding(token: string, id: string, input: HoldingInput, options?: LocalRequestOptions): Promise<LocalS2Response<Holding>>;
  updateHolding(token: string, id: string, holdingId: string, input: HoldingUpdate, options?: LocalRequestOptions): Promise<LocalS2Response<Holding>>;
  deleteHolding(token: string, id: string, holdingId: string, options?: LocalRequestOptions): Promise<LocalS2Response<HoldingDeletion>>;
  metrics(token: string, id: string, options?: LocalRequestOptions): Promise<LocalS2Response<PortfolioMetrics>>;
}
type ExpectedMeta<T> = (data: T) => {
  status: 'CACHED' | 'UNAVAILABLE';
  asOf: string | null;
};
export const nullMeta = () => ({ status: 'CACHED' as const, asOf: null });
export const updatedMeta = (data: {
  updated_at: string | null;
}) => ({ status: 'CACHED' as const, asOf: data.updated_at });
export const riskMeta = (data: SavedRisk) => ({ status: 'CACHED' as const, asOf: data.created_at });
export const metricsMeta = (data: PortfolioMetrics) => ({ status: data.valuation_status === 'INCOMPLETE' || data.valuation_status === 'UNAVAILABLE' ? 'UNAVAILABLE' as const : 'CACHED' as const,
  asOf: data.valuation_status === 'COMPLETE' ? FIXTURE_AS_OF : null });
export function checkedS2<T>(value: unknown, decode: (value: unknown) => T, expected: ExpectedMeta<T>): LocalS2Response<T> {
  const r = exactS2(value, ['data', 'meta']);
  const data = decode(r.data);
  const m = exactS2(r.meta, ['apiVersion', 'dataStatus', 'dataAsOf', 'correlationId']);
  const binding = expected(data);
  if (m.apiVersion !== 'v1' || m.dataStatus !== binding.status || (binding.asOf === null ? m.dataAsOf !== null :
    m.dataAsOf === null || utcInstant(utcS2(m.dataAsOf)) !== utcInstant(binding.asOf)))
    return invalidS2();
  const correlation = textS2(m.correlationId, 128);
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(correlation))
    return invalidS2();
  const meta: LocalS2Metadata = { apiVersion: 'v1', dataStatus: binding.status, dataAsOf: binding.asOf === null ? null : utcS2(m.dataAsOf), correlationId: correlation };
  return { data, meta };
}
export function portfolioRequest(input: PortfolioInput): PortfolioInput {
  const d = exactS2(input, ['portfolio_version', 'name', 'description', 'currency']);
  const name = textS2(d.name, 10000).trim(), description = d.description === null ? null : textS2(d.description, 10000, true).trim();
  if (d.portfolio_version !== 'portfolio.v1' || d.currency !== 'USD' || !name || Array.from(name).length > 100 || (description !== null && Array.from(description).length > 500))
    throw new LocalApplicationError('VALIDATION_ERROR');
  return { portfolio_version: 'portfolio.v1', name, description, currency: 'USD' };
}
export function confirmedPortfolio(value: unknown, input: PortfolioInput, id?: string): Portfolio {
  const d = decodePortfolio(value);
  if ((id !== undefined && d.portfolio_id !== id) || d.name !== input.name.trim() || d.description !== (input.description === null ? null : input.description.trim()) || d.currency !== input.currency)
    return invalidS2();
  return d;
}
export function confirmedHolding(value: unknown, input: HoldingUpdate, id: string, holdingId?: string, instrumentId?: string): Holding {
  const d = decodeHolding(value);
  if (d.portfolio_id !== id || (holdingId !== undefined && d.holding_id !== holdingId) || (instrumentId !== undefined && d.instrument_id !== instrumentId) ||
    !sameDecimal(d.quantity, input.quantity, 6) || !sameDecimal(d.average_cost, input.average_cost, 4) || d.currency !== input.currency)
    return invalidS2();
  return d;
}
export function createLocalS2Client(config: LocalClientConfiguration = {}): LocalS2Api {
  const origin = validateLocalBaseOrigin(config.baseOrigin || process.env.REACT_APP_FINEX_API_BASE_URL || 'http://127.0.0.1:8000');
  const timeout = config.timeoutMs ?? 8000;
  if (!Number.isInteger(timeout) || timeout < 50 || timeout > 30000)
    throw new LocalApplicationError('LOCAL_ORIGIN_INVALID');
  async function bodyText(response: Response, controller: AbortController): Promise<string> {
    // A streaming response is bounded during consumption, not only after JSON parsing.
    if (response.body?.getReader && typeof TextDecoder === 'function') {
      const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', { fatal: true });
      let bytes = 0, result = '';
      let cancelled = false;
      const cancelBody = () => {
        if (cancelled)
          return;
        cancelled = true;
        try {
          void Promise.resolve(reader.cancel()).catch(() => undefined);
        }
        catch { /* cleanup cannot replace the safe failure */
        }
      };
      controller.signal.addEventListener('abort', cancelBody, { once: true });
      if (controller.signal.aborted)
        cancelBody();
      try {
        while (true) {
          const chunk = await reader.read();
          if (chunk.done)
            break;
          bytes += chunk.value.byteLength;
          if (bytes > 524288)
            return invalidS2();
          result += decoder.decode(chunk.value, { stream: true });
        }
        return result + decoder.decode();
      }
      catch (error) {
        controller.abort();
        cancelBody();
        throw error;
      }
      finally {
        controller.signal.removeEventListener('abort', cancelBody);
        try {
          reader.releaseLock();
        }
        catch { /* a hostile reader cannot replace the result */
        }
      }
    }
    const result = await response.text();
    if (utf8Length(result) > 524288)
      return invalidS2();
    return result;
  }
  async function request<T>(path: string, method: 'GET' | 'POST' | 'PUT' | 'DELETE', token: string, decode: (v: unknown) => T, expected: ExpectedMeta<T>, payload: object | undefined, options: LocalRequestOptions = {}, status = 200): Promise<LocalS2Response<T>> {
    if (options.signal?.aborted)
      throw new LocalApplicationError('REQUEST_CANCELLED');
    if (!/^[A-Za-z0-9_-]{43}$/.test(token))
      throw new LocalApplicationError('SESSION_INVALID');
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancel = (): void => undefined;
    const bounded = new Promise<never>((_yes, no) => {
      cancel = () => {
        controller.abort();
        no(new LocalApplicationError('REQUEST_CANCELLED'));
      };
      options.signal?.addEventListener('abort', cancel, { once: true });
      timer = setTimeout(() => {
        controller.abort();
        no(new LocalApplicationError('REQUEST_TIMEOUT'));
      }, timeout);
    });
    async function perform() {
      const sender = config.fetchImpl ?? (typeof globalThis.fetch === 'function' ? globalThis.fetch.bind(globalThis) : undefined);
      if (typeof sender !== 'function')
        throw new LocalApplicationError('API_UNAVAILABLE');
      const headers: Record<string, string> = { Accept: 'application/json', Authorization: 'Bearer ' + token };
      if (payload !== undefined)
        headers['Content-Type'] = 'application/json';
      const response = await sender(origin + path, { method, headers, body: payload === undefined ? undefined : JSON.stringify(payload), signal: controller.signal,
        credentials: 'omit', cache: 'no-store', redirect: 'error' });
      if (response.status === 401)
        throw new LocalApplicationError('SESSION_INVALID');
      if (response.redirected || !/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') || ''))
        return invalidS2();
      let parsed: unknown;
      try {
        parsed = JSON.parse(await bodyText(response, controller));
      }
      catch (error) {
        if (error instanceof LocalApplicationError)
          throw error;
        return invalidS2();
      }
      if (!response.ok) {
        const e = exactS2(parsed, ['success', 'message', 'detail', 'error_code', 'error']);
        const inner = exactS2(e.error, ['code', 'message', 'fieldErrors', 'correlationId']);
        const message = textS2(e.message);
        const correlation = textS2(inner.correlationId, 128);
        if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(correlation) || !Array.isArray(inner.fieldErrors) || inner.fieldErrors.length > 64)
          return invalidS2();
        for (const value of inner.fieldErrors) {
          const field = exactS2(value, ['field', 'code']);
          textS2(field.field, 128);
          textS2(field.code, 128);
        }
        if (e.success !== false || e.detail !== message || inner.message !== message || e.error_code !== inner.code || typeof e.error_code !== 'string' || e.error_code === 'SESSION_INVALID')
          return invalidS2();
        const allowed: Record<string, number> = { LOCAL_APPLICATION_ONLY: 403, ONBOARDING_REQUIRED: 409, IDEMPOTENCY_CONFLICT: 409,
          RISK_ASSESSMENT_NOT_FOUND: 404, LOCAL_PORTFOLIO_NOT_FOUND: 404, LOCAL_HOLDING_NOT_FOUND: 404, HOLDING_ALREADY_EXISTS: 409, PORTFOLIO_LIMIT_REACHED: 409, HOLDING_LIMIT_REACHED: 409,
          VALIDATION_ERROR: 422, UNSUPPORTED_INSTRUMENT: 422, LOCAL_STORE_UNAVAILABLE: 503, RISK_ASSESSMENT_UNAVAILABLE: 503, LOCAL_CATALOG_UNAVAILABLE: 503, LOCAL_QUOTE_UNAVAILABLE: 503,
          MALFORMED_ANSWER: 400, UNSUPPORTED_QUESTIONNAIRE_VERSION: 400, DUPLICATE_QUESTION_ANSWER: 400, UNKNOWN_QUESTION_ID: 400, MISSING_REQUIRED_QUESTION: 400, INVALID_ANSWER_CODE: 400, ANSWER_NOT_PERMITTED_FOR_QUESTION: 400 };
        const common = ['LOCAL_APPLICATION_ONLY', 'ONBOARDING_REQUIRED', 'LOCAL_STORE_UNAVAILABLE', 'VALIDATION_ERROR'];
        const operations = [...common];
        if (path.startsWith('/api/v1/local-risk/')) {
          operations.push('RISK_ASSESSMENT_UNAVAILABLE');
          if (method === 'PUT' || method === 'POST')
            operations.push('MALFORMED_ANSWER', 'UNSUPPORTED_QUESTIONNAIRE_VERSION', 'DUPLICATE_QUESTION_ANSWER', 'UNKNOWN_QUESTION_ID', 'INVALID_ANSWER_CODE', 'ANSWER_NOT_PERMITTED_FOR_QUESTION');
          if (path === '/api/v1/local-risk/assessments' && method === 'POST')
            operations.push('IDEMPOTENCY_CONFLICT', 'MISSING_REQUIRED_QUESTION');
          if (/^\/api\/v1\/local-risk\/assessments\/[0-9a-f-]{36}$/.test(path))
            operations.push('RISK_ASSESSMENT_NOT_FOUND');
        }
        else {
          if (path === '/api/v1/local-portfolios/instruments' || path.endsWith('/metrics') || /\/holdings(?:\/|$)/.test(path))
            operations.push('LOCAL_CATALOG_UNAVAILABLE');
          if (path.endsWith('/metrics'))
            operations.push('LOCAL_QUOTE_UNAVAILABLE');
          if (/^\/api\/v1\/local-portfolios\/[0-9a-f-]{36}(?:\/|$)/.test(path))
            operations.push('LOCAL_PORTFOLIO_NOT_FOUND');
          if (/\/holdings\/[0-9a-f-]{36}$/.test(path))
            operations.push('LOCAL_HOLDING_NOT_FOUND');
          if (method === 'POST' && path.endsWith('/holdings'))
            operations.push('UNSUPPORTED_INSTRUMENT', 'HOLDING_ALREADY_EXISTS', 'HOLDING_LIMIT_REACHED');
          if (method === 'POST' && path === '/api/v1/local-portfolios')
            operations.push('PORTFOLIO_LIMIT_REACHED');
        }
        if (!operations.includes(e.error_code) || response.status !== allowed[e.error_code])
          return invalidS2();
        throw new LocalApplicationError(e.error_code);
      }
      if (response.status !== status)
        return invalidS2();
      const envelope = exactS2(parsed, ['success', 'message', 'data', 'meta']);
      if (envelope.success !== true)
        return invalidS2();
      textS2(envelope.message);
      return checkedS2({ data: envelope.data, meta: envelope.meta }, decode, expected);
    }
    try {
      return await Promise.race([perform(), bounded]);
    }
    catch (failure) {
      if (failure instanceof LocalApplicationError)
        throw failure;
      throw new LocalApplicationError('API_UNAVAILABLE');
    }
    finally {
      if (timer !== undefined)
        clearTimeout(timer);
      options.signal?.removeEventListener('abort', cancel);
      controller.abort();
    }
  }
  const riskPath = '/api/v1/local-risk', portfoliosPath = '/api/v1/local-portfolios';
  const owned = <T extends {
    portfolio_id: string;
  }>(decoder: (v: unknown) => T, id: string) => (v: unknown) => {
    const d = decoder(v);
    if (d.portfolio_id !== id)
      return invalidS2();
    return d;
  };
  function holdingPayload(input: HoldingUpdate | HoldingInput, create: boolean) {
    exactS2(input, ['holding_version', 'quantity', 'average_cost', 'currency', ...(create ? ['instrument_id'] : [])]);
    if (input.holding_version !== 'holding.v1' || input.currency !== 'USD' || !/^SYN:[A-Z][A-Z0-9_]{0,31}$/.test(create ? (input as HoldingInput).instrument_id : 'SYN:AAPL'))
      throw new LocalApplicationError('VALIDATION_ERROR');
    // Canonical precision is required on the wire, including valid trailing zeros.
    const q = textS2(input.quantity, 32), c = textS2(input.average_cost, 32);
    if (!/^\d+\.\d{6}$/.test(q) || !/^\d+\.\d{4}$/.test(c) || !sameDecimal(q, q, 6) || !sameDecimal(c, c, 4) || q === '0.000000')
      throw new LocalApplicationError('VALIDATION_ERROR');
    return Object.freeze({ ...input });
  }
  return {
    questionnaire: (t, o) => request(riskPath + '/questionnaire', 'GET', t, decodeQuestionnaire, nullMeta, undefined, o),
    riskDraft: (t, o) => request(riskPath + '/draft', 'GET', t, decodeRiskDraft, updatedMeta, undefined, o),
    saveRiskDraft: async (t, input, o) => {
      const frozen = riskInput(input);
      return request(riskPath + '/draft', 'PUT', t, (v) => {
        const d = decodeRiskDraft(v);
        if (!sameRiskInput(d, frozen) || d.updated_at === null)
          return invalidS2();
        return d;
      }, updatedMeta, frozen, o);
    },
    submitRisk: async (t, input, o) => {
      exactS2(input, ['questionnaire_id', 'questionnaire_version', 'answers', 'idempotency_key']);
      const frozen = riskInput({ questionnaire_id: input.questionnaire_id, questionnaire_version: input.questionnaire_version, answers: input.answers }, true);
      const key = uuidS2(input.idempotency_key);
      return request(riskPath + '/assessments', 'POST', t, (v) => {
        const d = decodeSavedRisk(v);
        if (!sameRiskInput(d.input, frozen))
          return invalidS2();
        return d;
      }, riskMeta, { ...frozen, idempotency_key: key }, o);
    },
    riskHistory: async (t, before, o) => request(riskPath + '/assessments?limit=2' + (cursorS2(before) === null ? '' : '&before=' + before), 'GET', t, decodeRiskHistory, nullMeta, undefined, o),
    riskDetail: async (t, id, o) => request(riskPath + '/assessments/' + uuidS2(id), 'GET', t, (v) => {
      const d = decodeSavedRisk(v);
      if (d.assessment_id !== id)
        return invalidS2();
      return d;
    }, riskMeta, undefined, o),
    catalog: (t, o) => request(portfoliosPath + '/instruments', 'GET', t, decodeCatalog, nullMeta, undefined, o),
    portfolios: (t, o) => request(portfoliosPath, 'GET', t, decodePortfolioList, nullMeta, undefined, o),
    portfolio: async (t, id, o) => request(portfoliosPath + '/' + uuidS2(id), 'GET', t, owned(decodePortfolio, id), updatedMeta, undefined, o),
    createPortfolio: async (t, input, o) => {
      const frozen = portfolioRequest(input);
      return request(portfoliosPath, 'POST', t, (v) => confirmedPortfolio(v, frozen), updatedMeta, frozen, o, 201);
    },
    updatePortfolio: async (t, id, input, o) => {
      uuidS2(id);
      const frozen = portfolioRequest(input);
      return request(portfoliosPath + '/' + id, 'PUT', t, (v) => confirmedPortfolio(v, frozen, id), updatedMeta, frozen, o);
    },
    deletePortfolio: async (t, id, o) => request(portfoliosPath + '/' + uuidS2(id), 'DELETE', t, owned(decodePortfolioDeletion, id), nullMeta, undefined, o),
    holdings: async (t, id, o) => request(portfoliosPath + '/' + uuidS2(id) + '/holdings', 'GET', t, owned(decodeHoldingList, id), nullMeta, undefined, o),
    holding: async (t, id, h, o) => request(portfoliosPath + '/' + uuidS2(id) + '/holdings/' + uuidS2(h), 'GET', t, (v) => {
      const d = owned(decodeHolding, id)(v);
      if (d.holding_id !== h)
        return invalidS2();
      return d;
    }, updatedMeta, undefined, o),
    createHolding: async (t, id, input, o) => {
      uuidS2(id);
      const frozen = holdingPayload(input, true) as HoldingInput;
      return request(portfoliosPath + '/' + id + '/holdings', 'POST', t, (v) => confirmedHolding(v, frozen, id, undefined, frozen.instrument_id), updatedMeta, frozen, o, 201);
    },
    updateHolding: async (t, id, h, input, o) => {
      uuidS2(id);
      uuidS2(h);
      const frozen = holdingPayload(input, false);
      return request(portfoliosPath + '/' + id + '/holdings/' + h, 'PUT', t, (v) => confirmedHolding(v, frozen, id, h), updatedMeta, frozen, o);
    },
    deleteHolding: async (t, id, h, o) => request(portfoliosPath + '/' + uuidS2(id) + '/holdings/' + uuidS2(h), 'DELETE', t, (v) => {
      const d = owned(decodeHoldingDeletion, id)(v);
      if (d.holding_id !== h)
        return invalidS2();
      return d;
    }, nullMeta, undefined, o),
    metrics: async (t, id, o) => request(portfoliosPath + '/' + uuidS2(id) + '/metrics', 'GET', t, owned(decodeMetrics, id), metricsMeta, undefined, o),
  };
}
