import { randomBytes } from 'crypto';
import { createLocalS2Client } from './localS2Client';
import { createLocalApplicationClient } from './localApplicationClient';
import { catalogFixture, draftFixture, emptyMetrics, inputFixture, portfolioFixture, portfolioId, questionnaireFixture, savedFixture, s2Scope, s2Time } from '../testHelpers/localS2';
import { deferred } from '../testHelpers/localApplication';
import { TextDecoder as NodeTextDecoder } from 'util';
const credential = () => randomBytes(32).toString('base64url');
function response(data: unknown, asOf: string | null = null, status = 200, dataStatus = 'CACHED'): Response {
  return { ok: status >= 200 && status < 300, status, redirected: false,
    headers: { get: () => 'application/json' }, text: async () => JSON.stringify({ success: true, message: 'Confirmed', data,
      meta: { apiVersion: 'v1', dataStatus, dataAsOf: asOf, correlationId: 's2-test' } }) } as unknown as Response;
}
test('S2 uses real typed server questionnaire, credentials omit, no-store and no redirects', async () => {
  const token = credential();
  const fetchMock = jest.fn().mockResolvedValue(response(questionnaireFixture()));
  expect((await createLocalS2Client({ baseOrigin: 'http://127.0.0.1:8082', fetchImpl: fetchMock }).questionnaire(token)).data.questions).toHaveLength(10);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url === 'http://127.0.0.1:8082/api/v1/local-risk/questionnaire' && init.headers.Authorization === 'Bearer ' + token).toBe(true);
  expect(init).toMatchObject({ method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error' });
});
test.each([
  [questionnaireFixture, null, 'questionnaire'], [draftFixture, null, 'riskDraft'],
  [catalogFixture, null, 'catalog'], [(): unknown => ({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [], count: 0 }), null, 'portfolios'],
  [emptyMetrics, null, 'metrics'],
] as const)('public S2 read validates server DTO and operation-specific as-of', async (fixture, asOf, method) => {
  const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(response(fixture(), asOf)) });
  expect(await (method === 'metrics' ? client.metrics(credential(), portfolioId) : client[method](credential()))).toHaveProperty('data.scope', s2Scope.scope);
});
test('risk retries freeze caller input and accept an original equivalent answer order', async () => {
  const gate = deferred<Response>();
  const fetchMock = jest.fn().mockReturnValue(gate.promise);
  const client = createLocalS2Client({ fetchImpl: fetchMock });
  const input = { ...inputFixture(), idempotency_key: portfolioId };
  input.answers.reverse();
  const pending = client.submitRisk(credential(), input);
  input.answers[0].answer_code = 'C5_A';
  input.answers.length = 0;
  gate.resolve(response(savedFixture(), s2Time));
  const saved = await pending;
  expect(saved.data.input.answers).toEqual(inputFixture().answers);
  let matches = false;
  try {
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body);
    matches = payload.answers.length === 10 && payload.answers[0].answer_code === 'C5_C' && payload.idempotency_key === portfolioId;
  }
  catch { /* only boolean diagnostics */
  }
  expect(matches).toBe(true);
});
test('save cannot be claimed from a well-formed but contradictory draft/result/portfolio', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(draftFixture()));
  const client = createLocalS2Client({ fetchImpl: fetchMock });
  await expect(client.saveRiskDraft(credential(), inputFixture())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  fetchMock.mockResolvedValue(response({ ...savedFixture(), input: { ...inputFixture(), answers: inputFixture().answers.map((a) => ({ ...a, answer_code: a.question_id + '_A' })) } }, s2Time));
  await expect(client.submitRisk(credential(), { ...inputFixture(), idempotency_key: portfolioId })).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  fetchMock.mockResolvedValue(response(portfolioFixture(), s2Time, 201));
  await expect(client.createPortfolio(credential(), { portfolio_version: 'portfolio.v1', name: 'Different', description: null, currency: 'USD' })).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test.each(['http://127.0.0.1:8000', 'http://127.0.0.1:8082'])('history fixes limit two and preserves a bounded cursor at %s without numeric conversion', async (baseOrigin) => {
  const fetchMock = jest.fn().mockResolvedValue(response({ ...s2Scope, items: [], next_cursor: null }));
  const client = createLocalS2Client({ baseOrigin, fetchImpl: fetchMock });
  await client.riskHistory(credential(), '9223372036854775807');
  expect(fetchMock.mock.calls[0][0] === baseOrigin + '/api/v1/local-risk/assessments?limit=2&before=9223372036854775807').toBe(true);
});
test('non-null S2 persisted metadata never loosens the unchanged S1 null metadata contract', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(portfolioFixture(), s2Time));
  expect((await createLocalS2Client({ fetchImpl: fetchMock }).portfolio(credential(), portfolioId)).meta.dataAsOf).toBe(s2Time);
  const old = createLocalApplicationClient({ fetchImpl: jest.fn().mockResolvedValue({ ...response({}), json: async () => ({ success: true, message: 'x', data: {}, meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: s2Time, correlationId: 'test' } }) }) });
  await expect(old.state(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('HTTP401 expires before reading a stalled body, while a non401 SESSION_INVALID is incompatible', async () => {
  const read = jest.fn().mockImplementation(() => new Promise(() => undefined));
  const fetchMock = jest.fn().mockResolvedValue({ status: 401, text: read });
  const client = createLocalS2Client({ fetchImpl: fetchMock });
  await expect(client.questionnaire(credential())).rejects.toMatchObject({ code: 'SESSION_INVALID' });
  expect(read).not.toHaveBeenCalled();
  fetchMock.mockResolvedValue({ status: 503, ok: false, headers: { get: () => 'application/json' }, text: async () => JSON.stringify({ success: false, message: 'safe', detail: 'safe', error_code: 'SESSION_INVALID', error: { code: 'SESSION_INVALID', message: 'safe', correlationId: 'x', fieldErrors: [] } }) });
  await expect(client.questionnaire(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
function errorResponse(code: string, status: number, fields: unknown = []): Response {
  return { status, ok: false, headers: { get: () => 'application/json' }, text: async () => JSON.stringify({ success: false, message: 'Safe diagnostic from API serializer', detail: 'Safe diagnostic from API serializer', error_code: code,
      error: { code, message: 'Safe diagnostic from API serializer', correlationId: 's2-wire-error', fieldErrors: fields } }) } as unknown as Response;
}
test.each([{ fields: [] }, { fields: [{ field: 'quantity', code: 'INVALID_FIELD' }] }])('actual API fieldErrors list shape decodes safe stable errors without reflecting body text', async ({ fields }) => {
  const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(errorResponse('ONBOARDING_REQUIRED', 409, fields)) });
  await expect(client.questionnaire(credential())).rejects.toMatchObject({ code: 'ONBOARDING_REQUIRED' });
});
test.each([['HOLDING_ALREADY_EXISTS', 409], ['IDEMPOTENCY_CONFLICT', 409], ['UNEXPECTED_CODE', 503]])('a risk GET rejects unrelated/unknown error %s', async (code, status) => {
  const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(errorResponse(code, status)) });
  await expect(client.questionnaire(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('a catalogue GET rejects a risk-only error and malformed list field errors', async () => {
  const fetchMock = jest.fn().mockResolvedValue(errorResponse('IDEMPOTENCY_CONFLICT', 409));
  const client = createLocalS2Client({ fetchImpl: fetchMock });
  await expect(client.catalog(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  fetchMock.mockResolvedValue(errorResponse('ONBOARDING_REQUIRED', 409, {}));
  await expect(client.catalog(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('a partial draft PUT rejects submission-only missing-question error authority', async () => {
  const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(errorResponse('MISSING_REQUIRED_QUESTION', 400)) });
  await expect(client.saveRiskDraft(credential(), { ...inputFixture(), answers: [] })).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test.each(['list', 'detail', 'create', 'update', 'delete'] as const)(
  'portfolio-only %s rejects catalogue-error authority from an unrelated operation', async (operation) => {
    const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(errorResponse('LOCAL_CATALOG_UNAVAILABLE', 503)) });
    const token = credential();
    const input = { portfolio_version: 'portfolio.v1' as const, name: 'Synthetic label', description: null, currency: 'USD' as const };
    const pending = operation === 'list' ? client.portfolios(token) : operation === 'detail' ? client.portfolio(token, portfolioId) :
      operation === 'create' ? client.createPortfolio(token, input) : operation === 'update' ? client.updatePortfolio(token, portfolioId, input) :
      client.deletePortfolio(token, portfolioId);
    await expect(pending).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  },
);
test.each(['catalog', 'holdings', 'metrics'] as const)(
  'the %s operation still accepts the safe catalogue-port failure it can actually produce', async (operation) => {
    const client = createLocalS2Client({ fetchImpl: jest.fn().mockResolvedValue(errorResponse('LOCAL_CATALOG_UNAVAILABLE', 503)) });
    const token = credential();
    const pending = operation === 'catalog' ? client.catalog(token) : client[operation](token, portfolioId);
    await expect(pending).rejects.toMatchObject({ code: 'LOCAL_CATALOG_UNAVAILABLE' });
  },
);
test('unsafe origins and IDs reject before sending a credential', async () => {
  const fetchMock = jest.fn();
  expect(() => createLocalS2Client({ baseOrigin: 'https://example.com', fetchImpl: fetchMock })).toThrow();
  const client = createLocalS2Client({ fetchImpl: fetchMock });
  await expect(client.portfolio(credential(), '../me')).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  expect(fetchMock).not.toHaveBeenCalled();
});
test('body timeout is bounded and aborts without automatically replaying a mutation', async () => {
  const fetchMock = jest.fn().mockResolvedValue({ status: 200, ok: true, headers: { get: () => 'application/json' }, text: async () => new Promise(() => undefined) });
  const client = createLocalS2Client({ timeoutMs: 50, fetchImpl: fetchMock });
  await expect(client.saveRiskDraft(credential(), inputFixture())).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
  expect(fetchMock.mock.calls.length).toBe(1);
  expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
});
function streamedResponse(reader: {
  read: jest.Mock;
  cancel: jest.Mock;
  releaseLock: jest.Mock;
}): Response {
  return { status: 200, ok: true, redirected: false, headers: { get: () => 'application/json' }, body: { getReader: () => reader } } as unknown as Response;
}
test('oversized streaming bytes fail before timeout even if cancel never settles', async () => {
  const previous = globalThis.TextDecoder;
  Object.defineProperty(globalThis, 'TextDecoder', { configurable: true, value: NodeTextDecoder });
  try {
    const reader = { read: jest.fn().mockResolvedValue({ done: false, value: new Uint8Array(524289) }), cancel: jest.fn().mockReturnValue(new Promise(() => undefined)), releaseLock: jest.fn() };
    const fetchMock = jest.fn().mockResolvedValue(streamedResponse(reader));
    const client = createLocalS2Client({ timeoutMs: 50, fetchImpl: fetchMock });
    await expect(client.questionnaire(credential())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
    expect(reader.read).toHaveBeenCalledTimes(1);
    expect(reader.cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
  }
  finally {
    Object.defineProperty(globalThis, 'TextDecoder', { configurable: true, value: previous });
  }
});
test('a stalled streaming body timeout cancels the reader and mutation is never replayed', async () => {
  const previous = globalThis.TextDecoder;
  Object.defineProperty(globalThis, 'TextDecoder', { configurable: true, value: NodeTextDecoder });
  try {
    const reader = { read: jest.fn().mockReturnValue(new Promise(() => undefined)), cancel: jest.fn().mockReturnValue(new Promise(() => undefined)), releaseLock: jest.fn() };
    const fetchMock = jest.fn().mockResolvedValue(streamedResponse(reader));
    await expect(createLocalS2Client({ timeoutMs: 50, fetchImpl: fetchMock }).saveRiskDraft(credential(), inputFixture())).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
    expect(reader.cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.length).toBe(1);
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
  }
  finally {
    Object.defineProperty(globalThis, 'TextDecoder', { configurable: true, value: previous });
  }
});
test('current401 aborts the response without acquiring or reading its body', async () => {
  const getReader = jest.fn();
  const fetchMock = jest.fn().mockResolvedValue({ status: 401, body: { getReader } });
  await expect(createLocalS2Client({ fetchImpl: fetchMock }).questionnaire(credential())).rejects.toMatchObject({ code: 'SESSION_INVALID' });
  expect(getReader).not.toHaveBeenCalled();
  expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
});
