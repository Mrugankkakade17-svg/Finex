import { catalogFixture, draftFixture, emptyMetrics, holdingFixture, inputFixture, portfolioFixture, questionnaireFixture, savedFixture, s2Scope } from '../testHelpers/localS2';
import { decodeCatalog, decodeMetrics, decodePortfolio, decodePortfolioList, decodeQuestionnaire, decodeRiskDraft, decodeRiskHistory, decodeSavedRisk, cursorS2, decimalInput, sameDecimal, sameRiskInput, utcInstant } from './localS2Models';
import { readFileSync } from 'fs';
import { join } from 'path';
import historical from '../testHelpers/fixtures/localS2PortfolioHistorical.json';
test.each([
  [decodeQuestionnaire, questionnaireFixture], [decodeRiskDraft, draftFixture], [decodeSavedRisk, savedFixture],
  [decodePortfolio, portfolioFixture], [decodeCatalog, catalogFixture], [decodeMetrics, emptyMetrics],
])('a typed decoder accepts its valid scoped versioned server DTO', (decode, fixture) => {
  expect(() => decode(fixture())).not.toThrow();
});
test('nullable draft, persisted original input and microsecond UTC remain exact', () => {
  expect(decodeRiskDraft(draftFixture()).updated_at).toBeNull();
  const result = decodeSavedRisk(savedFixture());
  expect(result.input.answers).toEqual(inputFixture().answers);
  expect(utcInstant(result.created_at)).toBe('2026-10-11T12:00:00.123456');
});
test('saved rules accept the actual accepted engine snapshot nesting without client re-scoring/re-hashing', () => {
  const actualRules = JSON.parse(readFileSync(join(process.cwd(), '..', 'backend', 'data', 'questionnaire', 'risk_questionnaire_v1.json'), 'utf8'));
  expect(() => decodeSavedRisk({ ...savedFixture(), rules_snapshot: actualRules })).not.toThrow();
});
test('history keeps server insertion order, cursor text and the two-item limit', () => {
  const a = savedFixture();
  const b = { ...savedFixture(), assessment_id: '00000000-0000-4000-8000-000000000004', created_at: '2026-10-11T11:00:00Z',
    assessment: { ...a.assessment, calculated_at: '2026-10-11T11:00:00Z' }, explanation: { ...a.explanation, calculated_at: '2026-10-11T11:00:00Z' } };
  const history = decodeRiskHistory({ ...s2Scope, items: [b, a], next_cursor: '9223372036854775807' });
  expect(history.items.map((r) => r.assessment_id)).toEqual([b.assessment_id, a.assessment_id]);
  expect(history.next_cursor).toBe('9223372036854775807');
  expect(() => decodeRiskHistory({ ...s2Scope, items: [a, b, a], next_cursor: null })).toThrow();
});
test.each([0, 1])('a nonfull %s-item history page cannot claim another cursor', (length) => {
  expect(() => decodeRiskHistory({ ...s2Scope, items: length ? [savedFixture()] : [], next_cursor: '1' })).toThrow();
});
test.each(['0', '01', '9223372036854775808', 2, undefined])('invalid history cursor fails closed', (cursor) => {
  expect(() => cursorS2(cursor)).toThrow();
});
test.each(['scope', 'persisted', 'created_at', 'rules_sha256', 'explanation_version'])('incomplete saved %s fails closed', (key) => {
  const value: Record<string, unknown> = { ...savedFixture() };
  delete value[key];
  expect(() => decodeSavedRisk(value)).toThrow();
});
test('question order/options, saved nullability, pilot scope and explanation time cannot drift', () => {
  const q = questionnaireFixture();
  expect(() => decodeQuestionnaire({ ...q, questions: q.questions.slice().reverse() })).toThrow();
  expect(() => decodeQuestionnaire({ ...q, questions: q.questions.map((row) => ({ ...row, options: row.options.slice().reverse() })) })).toThrow();
  const s = savedFixture();
  const { informational_tension, ...missing } = s.assessment;
  expect(() => decodeSavedRisk({ ...s, assessment: missing })).toThrow();
  expect(() => decodeSavedRisk({ ...s, scope: 'local_educational_pilot', persisted: false })).toThrow();
  expect(() => decodeSavedRisk({ ...s, explanation: { ...s.explanation, calculated_at: '2026-10-11T12:00:01Z' } })).toThrow();
});
test('lists reject copied or reverse-ordered records and hidden extra owner fields', () => {
  const a = portfolioFixture(), b = { ...a, portfolio_id: '00000000-0000-4000-8000-000000000005' };
  expect(() => decodePortfolioList({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [a, b], count: 2 })).not.toThrow();
  for (const items of [[a, a], [b, a]])
    expect(() => decodePortfolioList({ ...s2Scope, portfolio_version: 'portfolio.v1', items, count: 2 })).toThrow();
  expect(() => decodePortfolio({ ...a, owner_id: 'private' })).toThrow();
});
test('exact decimal entry permits normalization without float authority or invented money', () => {
  expect(decimalInput('1.2300', 6, true)).toBe('1.230000');
  expect(sameDecimal('1.2300', '1.230000', 6)).toBe(true);
  expect(decimalInput('1000000', 4, false)).toBe('1000000.0000');
  for (const bad of ['01', '+1', '1e2', ' 1', '1.0000001', '1000000.000001', '0'])
    expect(() => decimalInput(bad, 6, true)).toThrow();
  expect(sameRiskInput(inputFixture(), { ...inputFixture(), answers: inputFixture().answers.reverse() })).toBe(true);
});
test('empty metrics cannot invent quote freshness, missing null keys or LIVE values', () => {
  const m = emptyMetrics();
  expect(decodeMetrics(m).totals.market_value).toBe('0.00');
  expect(() => decodeMetrics({ ...m, valuation_status: 'COMPLETE' })).toThrow();
  const { hhi, ...missing } = m.totals;
  expect(() => decodeMetrics({ ...m, totals: missing })).toThrow();
  expect(() => decodeMetrics({ ...m, source_type: 'LIVE' })).toThrow();
});
function completeMetricFixture(zero = false) {
  const original = holdingFixture();
  const { scope, contract_version, catalog_version, created_at, updated_at, ...holding } = original;
  const value = zero ? '0.00' : '2000.00';
  const weight = zero ? null : '100.00';
  return {
    ...emptyMetrics(),
    valuation_status: 'COMPLETE',
    holdings: [{
        ...holding,
        cost_basis: '1500.00',
        quote: { unit_price: zero ? '0.0001' : '200.0000', data_status: 'CACHED', quote_as_of: '2026-01-01T00:00:00Z', reason: null },
        market_value: value,
        gain_loss: zero ? '-1500.00' : '500.00',
        gain_loss_percent: zero ? '-100.00' : '33.33',
        weight_percent: weight,
      }],
    totals: {
      cost_basis: '1500.00', market_value: value, gain_loss: zero ? '-1500.00' : '500.00', gain_loss_percent: zero ? '-100.00' : '33.33',
      allocation_by_asset_class: [{ group: 'EQUITY', market_value: value, weight_percent: weight }],
      allocation_by_sector: [{ group: 'TECHNOLOGY', market_value: value, weight_percent: weight }],
      concentration_percent: weight, hhi: zero ? null : '1.000000', educational_spread_percent: zero ? null : '0.00',
    },
  };
}
test.each([false, true])('COMPLETE allocation group fixture is structurally valid, including rounded zero %s', (zero) => {
  expect(() => decodeMetrics(completeMetricFixture(zero))).not.toThrow();
});
test.each([
  ['allocation_by_asset_class', false], ['allocation_by_sector', false],
  ['allocation_by_asset_class', true], ['allocation_by_sector', true],
] as const)('COMPLETE %s cannot omit the held groups, including zero %s', (key, zero) => {
  const value = completeMetricFixture(zero);
  expect(() => decodeMetrics({ ...value, totals: { ...value.totals, [key]: [] } })).toThrow();
});
test.each(['allocation_by_asset_class', 'allocation_by_sector'] as const)('COMPLETE %s cannot substitute unrelated groups', (key) => {
  const value = completeMetricFixture();
  expect(() => decodeMetrics({ ...value, totals: { ...value.totals, [key]: [{ group: 'UNRELATED', market_value: '2000.00', weight_percent: '100.00' }] } })).toThrow();
});
test('actual golden money bounds are checked as exact strings without recalculation (already enforced controls)', () => {
  const raw = historical.cases.find((entry) => entry.id === 'golden_1')!.body_utf8;
  const value = JSON.parse(raw).data;
  expect(() => decodeMetrics(value)).not.toThrow();
  expect(() => decodeMetrics({ ...value, totals: { ...value.totals, cost_basis: '100000000000000.01' } })).toThrow();
  expect(() => decodeMetrics({ ...value, totals: { ...value.totals, gain_loss_percent: '-101.00' } })).toThrow();
  expect(() => decodeMetrics({ ...value, totals: { ...value.totals, cost_basis: '100000000000000.00', gain_loss_percent: '-100.00' } })).not.toThrow();
  expect(() => decodeMetrics({ ...value, holdings: value.holdings.map((h: Record<string, unknown>) => ({ ...h, gain_loss: '-100000000000000.01' })) })).toThrow();
});
