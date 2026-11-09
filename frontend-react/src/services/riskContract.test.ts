import fixtures from '../data/s2RiskFixtures.v1.json';
import { createRiskClient, RiskRequest, RiskClientError } from './riskContract';

test.each(fixtures.cases.map((item) => [item.case_id, item] as const))(
  'fixture adapter faithfully replays %s without computing scores',
  async (_id, fixture) => {
    const client = createRiskClient({ mode: 'fixture', apiBaseUrl: 'http://127.0.0.1:8000' });
    if ('error_code' in fixture) {
      await expect(client.submit(fixture.request as RiskRequest)).rejects.toMatchObject({
        code: fixture.error_code,
      });
    } else {
      const response = await client.submit(fixture.request as RiskRequest);
      expect(response).toEqual(fixture.response);
      response.assessment.composite_score = 999;
      expect(
        (await client.submit(fixture.request as RiskRequest)).assessment.composite_score,
      ).not.toBe(999);
    }
  },
);

test('fixture adapter rejects unknown vectors rather than inventing a score', async () => {
  const request = JSON.parse(JSON.stringify(fixtures.cases[3].request));
  request.answers[0].answer_code = 'W1_D';
  await expect(
    createRiskClient({ mode: 'fixture', apiBaseUrl: '' }).submit(request),
  ).rejects.toMatchObject({ code: 'FIXTURE_VECTOR_UNAVAILABLE' });
});

test('HTTP client sends only versioned input and preserves safe API errors', async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: false,
    json: async () => ({
      error: { code: 'MISSING_REQUIRED_QUESTION', message: 'private-input' },
    }),
  });
  const client = createRiskClient({ mode: 'api', apiBaseUrl: 'http://127.0.0.1:8000' }, fetcher);
  await expect(
    client.submit(fixtures.cases[3].request as RiskRequest, 'web-s2-proof'),
  ).rejects.toMatchObject({ code: 'MISSING_REQUIRED_QUESTION' });
  const options = fetcher.mock.calls[0][1];
  expect(options.credentials).toBe('omit');
  expect(options.headers['X-Correlation-ID']).toBe('web-s2-proof');
  expect(JSON.parse(options.body)).toEqual(fixtures.cases[3].request);
});

test('HTTP client rejects contract drift and non-local configuration', async () => {
  const invalid = JSON.parse(JSON.stringify(fixtures.cases[3].response));
  invalid.assessment.questionnaire_version = 'v99';
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ success: true, data: invalid }) });
  await expect(
    createRiskClient({ mode: 'api', apiBaseUrl: 'http://127.0.0.1:8000' }, fetcher).submit(
      fixtures.cases[3].request as RiskRequest,
    ),
  ).rejects.toBeInstanceOf(RiskClientError);
  expect(() =>
    createRiskClient({ mode: 'api', apiBaseUrl: 'https://example.com' }, fetcher),
  ).toThrow(/local/i);
});

test('object key order cannot change fixture selection', async () => {
  const request = fixtures.cases[3].request;
  const reordered = {
    ...request,
    answers: request.answers
      .map((answer) => ({ answer_code: answer.answer_code, question_id: answer.question_id }))
      .reverse(),
  } as RiskRequest;
  const client = createRiskClient({ mode: 'fixture', apiBaseUrl: '' });
  expect(await client.submit(reordered)).toEqual(await client.submit(request as RiskRequest));
});

test.each(['dimension', 'limitation', 'tension'])(
  'HTTP client fails safely when %s metadata is malformed',
  async (field) => {
    const questionnaire = JSON.parse(JSON.stringify(fixtures.questionnaire));
    const result = JSON.parse(JSON.stringify(fixtures.cases[3].response));
    if (field === 'dimension') questionnaire.questions[0].dimension = 'unknown';
    if (field === 'limitation') questionnaire.limitation.code = 'ADVICE';
    if (field === 'tension')
      result.assessment.informational_tension = { code: 'CAPACITY_BELOW_WILLINGNESS', message: {} };
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: field === 'tension' ? result : questionnaire }),
    });
    const client = createRiskClient({ mode: 'api', apiBaseUrl: 'http://localhost:8000' }, fetcher);
    await expect(
      field === 'tension'
        ? client.submit(fixtures.cases[3].request as RiskRequest)
        : client.loadQuestionnaire(),
    ).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  },
);
