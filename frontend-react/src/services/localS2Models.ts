import { LocalApplicationError, LOCAL_SCOPE, LOCAL_CONTRACT_VERSION } from './localApplicationBoundary';
export const RISK_QUESTION_IDS = ['W1', 'W2', 'W3', 'W4', 'W5', 'C1', 'C2', 'C3', 'C4', 'C5'] as const;
export const FIXTURE_AS_OF = '2026-01-01T00:00:00Z';
export const PORTFOLIO_LIMITATIONS = ['SYNTHETIC_QUOTES_NOT_MARKET_DATA', 'MANUAL_HOLDINGS_NOT_BROKER_POSITIONS',
  'SPREAD_IS_ALLOCATION_ONLY', 'NO_FUND_LOOKTHROUGH_OR_SUITABILITY'] as const;
export interface LocalScope {
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
}
export interface LocalS2Metadata {
  apiVersion: 'v1';
  dataStatus: 'CACHED' | 'UNAVAILABLE';
  dataAsOf: string | null;
  correlationId: string;
}
export interface LocalS2Response<T> {
  data: T;
  meta: LocalS2Metadata;
}
export interface RiskAnswer {
  question_id: string;
  answer_code: string;
}
export interface RiskInput {
  questionnaire_id: 'risk_questionnaire_v1';
  questionnaire_version: 'v1';
  answers: RiskAnswer[];
}
export interface RiskSubmission extends RiskInput {
  idempotency_key: string;
}
export interface RiskLimitation {
  code: 'EDUCATIONAL_SELF_REPORTED_PROFILE';
  message: string;
}
export interface RiskQuestion {
  question_id: string;
  dimension: 'willingness' | 'capacity';
  text: string;
  options: {
    code: string;
    label: string;
  }[];
}
export interface LocalQuestionnaire extends LocalScope {
  questionnaire_id: 'risk_questionnaire_v1';
  questionnaire_version: 'v1';
  scoring_version: 'deterministic_v1.0.0';
  explanation_version: 'educational_v1.0.0';
  rules_sha256: string;
  questions: RiskQuestion[];
  limitation: RiskLimitation;
}
export interface LocalRiskDraft extends LocalScope, RiskInput {
  updated_at: string | null;
}
export interface RiskResult {
  contract_version: 's2-risk-contract/v1.0';
  questionnaire_id: 'risk_questionnaire_v1';
  questionnaire_version: 'v1';
  scoring_version: 'deterministic_v1.0.0';
  willingness_score: number;
  capacity_score: number;
  composite_score: number;
  risk_category: {
    code: 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';
    label: 'Conservative' | 'Moderate' | 'Aggressive';
  };
  calculated_at: string;
  limitation: RiskLimitation;
  informational_tension: {
    code: 'CAPACITY_BELOW_WILLINGNESS' | 'WILLINGNESS_BELOW_CAPACITY';
    message: string;
  } | null;
}
export interface RiskExplanation {
  summary: string;
  dimensions: string;
  method: string;
  questionnaire_version: 'v1';
  scoring_version: 'deterministic_v1.0.0';
  calculated_at: string;
  limitation: string;
}
export interface SavedRisk extends LocalScope {
  persisted: true;
  assessment_id: string;
  created_at: string;
  input: RiskInput;
  assessment: RiskResult;
  explanation: RiskExplanation;
  explanation_version: 'educational_v1.0.0';
  rules_sha256: string;
  rules_snapshot: Record<string, unknown>;
}
export interface RiskHistory extends LocalScope {
  items: SavedRisk[];
  next_cursor: string | null;
}
export interface PortfolioInput {
  portfolio_version: 'portfolio.v1';
  name: string;
  description: string | null;
  currency: 'USD';
}
export interface Portfolio extends LocalScope, PortfolioInput {
  portfolio_id: string;
  created_at: string;
  updated_at: string;
}
export interface PortfolioList extends LocalScope {
  portfolio_version: 'portfolio.v1';
  items: Portfolio[];
  count: number;
}
export interface CatalogItem {
  instrument_id: string;
  display_name: string;
  asset_class: string;
  sector: string;
  currency: 'USD';
}
export interface Catalog extends LocalScope {
  catalog_version: 'synthetic_catalog.v1';
  currency: 'USD';
  items: CatalogItem[];
  count: number;
}
export interface HoldingUpdate {
  holding_version: 'holding.v1';
  quantity: string;
  average_cost: string;
  currency: 'USD';
}
export interface HoldingInput extends HoldingUpdate {
  instrument_id: string;
}
export interface Holding extends LocalScope, CatalogItem, HoldingUpdate {
  catalog_version: 'synthetic_catalog.v1';
  portfolio_id: string;
  holding_id: string;
  created_at: string;
  updated_at: string;
}
export interface HoldingList extends LocalScope {
  holding_version: 'holding.v1';
  catalog_version: 'synthetic_catalog.v1';
  portfolio_id: string;
  items: Holding[];
  count: number;
}
export interface PortfolioDeletion extends LocalScope {
  portfolio_version: 'portfolio.v1';
  portfolio_id: string;
  entity_type: 'portfolio';
  deleted: true;
}
export interface HoldingDeletion extends LocalScope {
  holding_version: 'holding.v1';
  portfolio_id: string;
  holding_id: string;
  entity_type: 'holding';
  deleted: true;
}
export interface MetricQuote {
  unit_price: string | null;
  data_status: 'CACHED' | 'UNAVAILABLE';
  quote_as_of: typeof FIXTURE_AS_OF | null;
  reason: 'SYNTHETIC_QUOTE_UNAVAILABLE' | null;
}
export interface MetricHolding extends CatalogItem, HoldingUpdate {
  portfolio_id: string;
  holding_id: string;
  cost_basis: string;
  quote: MetricQuote;
  market_value: string | null;
  gain_loss: string | null;
  gain_loss_percent: string | null;
  weight_percent: string | null;
}
export interface Allocation {
  group: string;
  market_value: string;
  weight_percent: string | null;
}
export interface PortfolioTotals {
  cost_basis: string;
  market_value: string | null;
  gain_loss: string | null;
  gain_loss_percent: string | null;
  allocation_by_asset_class: Allocation[] | null;
  allocation_by_sector: Allocation[] | null;
  concentration_percent: string | null;
  hhi: string | null;
  educational_spread_percent: string | null;
}
export interface PortfolioMetrics extends LocalScope {
  metrics_version: 'portfolio_metrics.v1';
  formula_version: 'manual_portfolio_math.v1';
  catalog_version: 'synthetic_catalog.v1';
  quote_snapshot_version: 'synthetic_quotes.v1';
  portfolio_id: string;
  currency: 'USD';
  valuation_status: 'COMPLETE' | 'EMPTY' | 'INCOMPLETE' | 'UNAVAILABLE';
  source: 'finex.synthetic.portfolio';
  source_type: 'SYNTHETIC';
  fixture_as_of: typeof FIXTURE_AS_OF;
  calculated_at: string;
  missing_instrument_ids: string[];
  limitations: string[];
  holdings: MetricHolding[];
  totals: PortfolioTotals;
}
export function invalidS2(): never {
  throw new LocalApplicationError('RESPONSE_INVALID');
}
export function objectS2(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return invalidS2();
  return value as Record<string, unknown>;
}
export function exactS2(value: unknown, keys: string[]): Record<string, unknown> {
  const data = objectS2(value);
  if (Object.keys(data).length !== keys.length || keys.some((key) => !Object.prototype.hasOwnProperty.call(data, key)))
    return invalidS2();
  return data;
}
const scopeKeys = ['scope', 'contract_version'];
function scoped(value: unknown, keys: string[]) {
  const data = exactS2(value, [...scopeKeys, ...keys]);
  if (data.scope !== LOCAL_SCOPE || data.contract_version !== LOCAL_CONTRACT_VERSION)
    return invalidS2();
  return data;
}
export function textS2(value: unknown, max = 4096, empty = false): string {
  if (typeof value !== 'string' || (!empty && !value) || Array.from(value).length > max)
    return invalidS2();
  return value;
}
export function utcS2(value: unknown): string {
  const s = textS2(value, 40);
  const p = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|\+00:00)$/.exec(s);
  const d = new Date(s);
  if (!p || !Number.isFinite(d.getTime()) || d.getUTCFullYear() !== +p[1] || d.getUTCMonth() + 1 !== +p[2] ||
    d.getUTCDate() !== +p[3] || d.getUTCHours() !== +p[4] || d.getUTCMinutes() !== +p[5] || d.getUTCSeconds() !== +p[6])
    return invalidS2();
  return s;
}
/** Compare UTC instants at microsecond precision; never use times to reorder risk history. */
export function utcInstant(value: string): string {
  const time = utcS2(value).replace('+00:00', 'Z');
  const parts = time.slice(0, -1).split('.');
  return parts[0] + '.' + (parts[1] || '').padEnd(6, '0');
}
export function uuidS2(value: unknown): string {
  const s = textS2(value, 36);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(s))
    return invalidS2();
  return s;
}
export function cursorS2(value: unknown): string | null {
  if (value === null)
    return null;
  const s = textS2(value, 19);
  if (!/^[1-9][0-9]*$/.test(s) || (s.length === 19 && s > '9223372036854775807'))
    return invalidS2();
  return s;
}
function arrayS2(value: unknown, max: number): unknown[] {
  if (!Array.isArray(value) || value.length > max)
    return invalidS2();
  return value;
}
function literal<T extends string>(value: unknown, expected: T): T {
  if (value !== expected)
    return invalidS2();
  return expected;
}
const base: LocalScope = { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION };
function riskVersions(data: Record<string, unknown>) {
  literal(data.questionnaire_id, 'risk_questionnaire_v1');
  literal(data.questionnaire_version, 'v1');
}
export function riskInput(value: unknown, complete = false): RiskInput {
  const d = exactS2(value, ['questionnaire_id', 'questionnaire_version', 'answers']);
  riskVersions(d);
  const answers = arrayS2(d.answers, 10).map((value) => {
    const a = exactS2(value, ['question_id', 'answer_code']);
    const question_id = textS2(a.question_id, 2), answer_code = textS2(a.answer_code, 4);
    if (!RISK_QUESTION_IDS.some((id) => id === question_id) || !new RegExp('^' + question_id + '_[A-E]$').test(answer_code))
      return invalidS2();
    return { question_id, answer_code };
  });
  if (new Set(answers.map((a) => a.question_id)).size !== answers.length || (complete && answers.length !== 10))
    return invalidS2();
  return { questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1', answers };
}
export function sameRiskInput(a: RiskInput, b: RiskInput): boolean {
  return a.questionnaire_id === b.questionnaire_id && a.questionnaire_version === b.questionnaire_version && a.answers.length === b.answers.length &&
    a.answers.every((answer) => b.answers.some((other) => answer.question_id === other.question_id && answer.answer_code === other.answer_code));
}
function limitation(value: unknown): RiskLimitation {
  const d = exactS2(value, ['code', 'message']);
  return { code: literal(d.code, 'EDUCATIONAL_SELF_REPORTED_PROFILE'), message: textS2(d.message) };
}
function digest(value: unknown) {
  const s = textS2(value, 64);
  if (!/^[0-9a-f]{64}$/.test(s))
    return invalidS2();
  return s;
}
export function decodeQuestionnaire(value: unknown): LocalQuestionnaire {
  const d = scoped(value, ['questionnaire_id', 'questionnaire_version', 'scoring_version', 'explanation_version', 'rules_sha256', 'questions', 'limitation']);
  riskVersions(d);
  const questions: RiskQuestion[] = arrayS2(d.questions, 10).map((value, i) => {
    const q = exactS2(value, ['question_id', 'dimension', 'text', 'options']);
    if (q.question_id !== RISK_QUESTION_IDS[i] || q.dimension !== (i < 5 ? 'willingness' : 'capacity'))
      return invalidS2();
    const options = arrayS2(q.options, 5).map((value, n) => {
      const o = exactS2(value, ['code', 'label']);
      if (o.code !== q.question_id + '_' + 'ABCDE'[n])
        return invalidS2();
      return { code: textS2(o.code, 4), label: textS2(o.label) };
    });
    if (options.length !== 5)
      return invalidS2();
    return { question_id: textS2(q.question_id, 2), dimension: i < 5 ? 'willingness' : 'capacity', text: textS2(q.text), options };
  });
  if (questions.length !== 10)
    return invalidS2();
  return { ...base, questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1',
    scoring_version: literal(d.scoring_version, 'deterministic_v1.0.0'), explanation_version: literal(d.explanation_version, 'educational_v1.0.0'),
    rules_sha256: digest(d.rules_sha256), questions, limitation: limitation(d.limitation) };
}
export function decodeRiskDraft(value: unknown): LocalRiskDraft {
  const d = scoped(value, ['questionnaire_id', 'questionnaire_version', 'answers', 'updated_at']);
  const input = riskInput({ questionnaire_id: d.questionnaire_id, questionnaire_version: d.questionnaire_version, answers: d.answers });
  const updated_at = d.updated_at === null ? null : utcS2(d.updated_at);
  if (input.answers.length && updated_at === null)
    return invalidS2();
  return { ...base, ...input, updated_at };
}
function score(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 100)
    return invalidS2();
  return value;
}
export function utf8Length(value: string): number {
  let count = 0;
  for (const c of Array.from(value)) {
    const n = c.codePointAt(0)!;
    count += n < 128 ? 1 : n < 2048 ? 2 : n < 65536 ? 3 : 4;
  }
  return count;
}
export function decodeSavedRisk(value: unknown): SavedRisk {
  const d = scoped(value, ['persisted', 'assessment_id', 'created_at', 'input', 'assessment', 'explanation', 'explanation_version', 'rules_sha256', 'rules_snapshot']);
  if (d.persisted !== true)
    return invalidS2();
  const input = riskInput(d.input, true), created_at = utcS2(d.created_at);
  const a = exactS2(d.assessment, ['contract_version', 'questionnaire_id', 'questionnaire_version', 'scoring_version', 'willingness_score', 'capacity_score', 'composite_score', 'risk_category', 'calculated_at', 'limitation', 'informational_tension']);
  riskVersions(a);
  const c = exactS2(a.risk_category, ['code', 'label']);
  const categories = { CONSERVATIVE: 'Conservative', MODERATE: 'Moderate', AGGRESSIVE: 'Aggressive' } as const;
  if (typeof c.code !== 'string' || !Object.prototype.hasOwnProperty.call(categories, c.code) || categories[c.code as keyof typeof categories] !== c.label)
    return invalidS2();
  let tension: RiskResult['informational_tension'] = null;
  if (a.informational_tension !== null) {
    const t = exactS2(a.informational_tension, ['code', 'message']);
    if (t.code !== 'CAPACITY_BELOW_WILLINGNESS' && t.code !== 'WILLINGNESS_BELOW_CAPACITY')
      return invalidS2();
    tension = { code: t.code, message: textS2(t.message) };
  }
  const assessment: RiskResult = { contract_version: literal(a.contract_version, 's2-risk-contract/v1.0'), questionnaire_id: input.questionnaire_id,
    questionnaire_version: input.questionnaire_version, scoring_version: literal(a.scoring_version, 'deterministic_v1.0.0'),
    willingness_score: score(a.willingness_score), capacity_score: score(a.capacity_score), composite_score: score(a.composite_score),
    risk_category: { code: c.code as RiskResult['risk_category']['code'], label: c.label as RiskResult['risk_category']['label'] },
    calculated_at: utcS2(a.calculated_at), limitation: limitation(a.limitation), informational_tension: tension };
  const e = exactS2(d.explanation, ['summary', 'dimensions', 'method', 'questionnaire_version', 'scoring_version', 'calculated_at', 'limitation']);
  const explanation: RiskExplanation = { summary: textS2(e.summary), dimensions: textS2(e.dimensions), method: textS2(e.method),
    questionnaire_version: literal(e.questionnaire_version, 'v1'), scoring_version: literal(e.scoring_version, 'deterministic_v1.0.0'),
    calculated_at: utcS2(e.calculated_at), limitation: textS2(e.limitation) };
  if (utcInstant(assessment.calculated_at) !== utcInstant(created_at) || utcInstant(explanation.calculated_at) !== utcInstant(created_at) ||
    explanation.limitation !== assessment.limitation.message)
    return invalidS2();
  const rules = objectS2(d.rules_snapshot);
  let serialized: string;
  try {
    serialized = JSON.stringify(rules);
  }
  catch {
    return invalidS2();
  }
  // Server validates canonical policy/hash/calculation. Do not re-hash JSON.stringify or re-score here.
  const snapshotQuestionnaire = objectS2(rules.questionnaire);
  if (utf8Length(serialized) > 65536 || snapshotQuestionnaire.questionnaire_id !== input.questionnaire_id || snapshotQuestionnaire.version_label !== input.questionnaire_version ||
    snapshotQuestionnaire.status !== 'APPROVED')
    return invalidS2();
  return { ...base, persisted: true, assessment_id: uuidS2(d.assessment_id), created_at, input, assessment, explanation,
    explanation_version: literal(d.explanation_version, 'educational_v1.0.0'), rules_sha256: digest(d.rules_sha256), rules_snapshot: JSON.parse(serialized) as Record<string, unknown> };
}
export function decodeRiskHistory(value: unknown): RiskHistory {
  const d = scoped(value, ['items', 'next_cursor']);
  const items = arrayS2(d.items, 2).map(decodeSavedRisk);
  const next_cursor = cursorS2(d.next_cursor);
  if (new Set(items.map((i) => i.assessment_id)).size !== items.length || (next_cursor !== null && items.length !== 2))
    return invalidS2();
  return { ...base, items, next_cursor };
}
function trimmed(value: unknown, max: number, empty = false): string {
  const s = textS2(value, max, empty);
  if (s !== s.trim())
    return invalidS2();
  return s;
}
function instrument(value: unknown): string {
  const s = textS2(value, 36);
  if (!/^SYN:[A-Z][A-Z0-9_]{0,31}$/.test(s))
    return invalidS2();
  return s;
}
function group(value: unknown): string {
  const s = textS2(value, 32);
  if (!/^[A-Z][A-Z0-9_]{0,31}$/.test(s))
    return invalidS2();
  return s;
}
const catalogKeys = ['instrument_id', 'display_name', 'asset_class', 'sector', 'currency'];
function catalogItem(d: Record<string, unknown>): CatalogItem {
  return { instrument_id: instrument(d.instrument_id), display_name: trimmed(d.display_name, 100), asset_class: group(d.asset_class), sector: group(d.sector), currency: literal(d.currency, 'USD') };
}
function count(value: unknown, length: number, max: number): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value !== length || length > max)
    return invalidS2();
  return value;
}
function sortedUnique(values: string[]): void {
  if (values.some((s, i) => i > 0 && values[i - 1] >= s))
    invalidS2();
}
function recordOrder<T extends {
  created_at: string;
}>(items: T[], id: (value: T) => string): void {
  const keys = items.map((i) => utcInstant(i.created_at) + ':' + id(i));
  sortedUnique(keys);
  if (new Set(items.map(id)).size !== items.length)
    invalidS2();
}
function times(d: Record<string, unknown>) {
  const created_at = utcS2(d.created_at), updated_at = utcS2(d.updated_at);
  if (utcInstant(updated_at) < utcInstant(created_at))
    return invalidS2();
  return { created_at, updated_at };
}
export function decodeCatalog(value: unknown): Catalog {
  const d = scoped(value, ['catalog_version', 'currency', 'items', 'count']);
  const items = arrayS2(d.items, 128).map((v) => catalogItem(exactS2(v, catalogKeys)));
  if (!items.length)
    return invalidS2();
  sortedUnique(items.map((i) => i.instrument_id));
  return { ...base, catalog_version: literal(d.catalog_version, 'synthetic_catalog.v1'), currency: literal(d.currency, 'USD'), items, count: count(d.count, items.length, 128) };
}
export function decodePortfolio(value: unknown): Portfolio {
  const d = scoped(value, ['portfolio_version', 'portfolio_id', 'name', 'description', 'currency', 'created_at', 'updated_at']);
  return { ...base, portfolio_version: literal(d.portfolio_version, 'portfolio.v1'), portfolio_id: uuidS2(d.portfolio_id), name: trimmed(d.name, 100),
    description: d.description === null ? null : trimmed(d.description, 500, true), currency: literal(d.currency, 'USD'), ...times(d) };
}
export function decodePortfolioList(value: unknown): PortfolioList {
  const d = scoped(value, ['portfolio_version', 'items', 'count']);
  const items = arrayS2(d.items, 20).map(decodePortfolio);
  recordOrder(items, (i) => i.portfolio_id);
  return { ...base, portfolio_version: literal(d.portfolio_version, 'portfolio.v1'), items, count: count(d.count, items.length, 20) };
}
function canonicalDecimal(value: unknown, places: 4 | 6, positive: boolean): string {
  const s = textS2(value, 32);
  try {
    if (decimalInput(s, places, positive) !== s)
      return invalidS2();
  }
  catch {
    return invalidS2();
  }
  return s;
}
export function decodeHolding(value: unknown): Holding {
  const d = scoped(value, [...catalogKeys, 'holding_version', 'catalog_version', 'portfolio_id', 'holding_id', 'quantity', 'average_cost', 'created_at', 'updated_at']);
  return { ...base, ...catalogItem(d), holding_version: literal(d.holding_version, 'holding.v1'), catalog_version: literal(d.catalog_version, 'synthetic_catalog.v1'),
    portfolio_id: uuidS2(d.portfolio_id), holding_id: uuidS2(d.holding_id), quantity: canonicalDecimal(d.quantity, 6, true), average_cost: canonicalDecimal(d.average_cost, 4, false), ...times(d) };
}
export function decodeHoldingList(value: unknown): HoldingList {
  const d = scoped(value, ['holding_version', 'catalog_version', 'portfolio_id', 'items', 'count']);
  const id = uuidS2(d.portfolio_id), items = arrayS2(d.items, 100).map(decodeHolding);
  recordOrder(items, (i) => i.holding_id);
  if (items.some((i) => i.portfolio_id !== id) || new Set(items.map((i) => i.instrument_id)).size !== items.length)
    return invalidS2();
  return { ...base, holding_version: literal(d.holding_version, 'holding.v1'), catalog_version: literal(d.catalog_version, 'synthetic_catalog.v1'), portfolio_id: id, items, count: count(d.count, items.length, 100) };
}
export function decodePortfolioDeletion(value: unknown): PortfolioDeletion {
  const d = scoped(value, ['portfolio_version', 'portfolio_id', 'entity_type', 'deleted']);
  if (d.deleted !== true)
    return invalidS2();
  return { ...base, portfolio_version: literal(d.portfolio_version, 'portfolio.v1'), portfolio_id: uuidS2(d.portfolio_id), entity_type: literal(d.entity_type, 'portfolio'), deleted: true };
}
export function decodeHoldingDeletion(value: unknown): HoldingDeletion {
  const d = scoped(value, ['holding_version', 'portfolio_id', 'holding_id', 'entity_type', 'deleted']);
  if (d.deleted !== true)
    return invalidS2();
  return { ...base, holding_version: literal(d.holding_version, 'holding.v1'), portfolio_id: uuidS2(d.portfolio_id), holding_id: uuidS2(d.holding_id), entity_type: literal(d.entity_type, 'holding'), deleted: true };
}
function numberText(value: unknown, places: 2 | 6, min: string, max: string): string {
  const s = textS2(value, 32);
  if (!new RegExp('^-?(?:0|[1-9][0-9]{0,18})\\.[0-9]{' + places + '}$').test(s) || (s[0] === '-' && /^-0\.0+$/.test(s)))
    return invalidS2();
  const compare = (a: string, b: string): number => {
    const negativeA = a[0] === '-', negativeB = b[0] === '-';
    if (negativeA !== negativeB)
      return negativeA ? -1 : 1;
    const normalize = (v: string) => v.replace('-', '').replace('.', '').replace(/^0+/, '') || '0';
    const x = normalize(a), y = normalize(b);
    const result = x.length === y.length ? x === y ? 0 : x < y ? -1 : 1 : x.length < y.length ? -1 : 1;
    return negativeA ? -result : result;
  };
  if (compare(s, min) < 0 || compare(s, max) > 0)
    return invalidS2();
  return s;
}
const money = (v: unknown) => numberText(v, 2, '0.00', '100000000000000.00');
const gain = (v: unknown) => numberText(v, 2, '-100000000000000.00', '100000000000000.00');
const percent = (v: unknown) => numberText(v, 2, '0.00', '100.00');
const gainPercent = (v: unknown) => numberText(v, 2, '-100.00', '1000000000000000000.00');
function nullable<T>(value: unknown, decode: (v: unknown) => T): T | null {
  return value === null ? null : decode(value);
}
function allocations(value: unknown): Allocation[] | null {
  if (value === null)
    return null;
  const items = arrayS2(value, 100).map((value) => {
    const d = exactS2(value, ['group', 'market_value', 'weight_percent']);
    return { group: group(d.group), market_value: money(d.market_value), weight_percent: nullable(d.weight_percent, percent) };
  });
  sortedUnique(items.map((i) => i.group));
  return items;
}
export function decodeMetrics(value: unknown): PortfolioMetrics {
  const d = scoped(value, ['metrics_version', 'formula_version', 'catalog_version', 'quote_snapshot_version', 'portfolio_id', 'currency', 'valuation_status', 'source', 'source_type', 'fixture_as_of', 'calculated_at', 'missing_instrument_ids', 'limitations', 'holdings', 'totals']);
  const id = uuidS2(d.portfolio_id);
  const holdings: MetricHolding[] = arrayS2(d.holdings, 100).map((value) => {
    const h = exactS2(value, [...catalogKeys, 'holding_version', 'portfolio_id', 'holding_id', 'quantity', 'average_cost', 'cost_basis', 'quote', 'market_value', 'gain_loss', 'gain_loss_percent', 'weight_percent']);
    const q = exactS2(h.quote, ['unit_price', 'data_status', 'quote_as_of', 'reason']);
    let quote: MetricQuote;
    if (q.data_status === 'CACHED') {
      if (q.quote_as_of !== FIXTURE_AS_OF || q.reason !== null)
        return invalidS2();
      quote = { unit_price: canonicalDecimal(q.unit_price, 4, true), data_status: 'CACHED', quote_as_of: FIXTURE_AS_OF, reason: null };
    }
    else {
      if (q.data_status !== 'UNAVAILABLE' || q.unit_price !== null || q.quote_as_of !== null || q.reason !== 'SYNTHETIC_QUOTE_UNAVAILABLE')
        return invalidS2();
      quote = { unit_price: null, data_status: 'UNAVAILABLE', quote_as_of: null, reason: 'SYNTHETIC_QUOTE_UNAVAILABLE' };
    }
    const row: MetricHolding = { ...catalogItem(h), holding_version: literal(h.holding_version, 'holding.v1'), portfolio_id: uuidS2(h.portfolio_id), holding_id: uuidS2(h.holding_id),
      quantity: canonicalDecimal(h.quantity, 6, true), average_cost: canonicalDecimal(h.average_cost, 4, false), cost_basis: money(h.cost_basis), quote,
      market_value: nullable(h.market_value, money), gain_loss: nullable(h.gain_loss, gain), gain_loss_percent: nullable(h.gain_loss_percent, gainPercent), weight_percent: nullable(h.weight_percent, percent) };
    if (row.portfolio_id !== id || (quote.data_status === 'UNAVAILABLE' ? [row.market_value, row.gain_loss, row.gain_loss_percent, row.weight_percent].some((v) => v !== null) :
      row.market_value === null || row.gain_loss === null || ((row.cost_basis === '0.00') !== (row.gain_loss_percent === null))))
      return invalidS2();
    return row;
  });
  if (new Set(holdings.map((h) => h.holding_id)).size !== holdings.length || new Set(holdings.map((h) => h.instrument_id)).size !== holdings.length)
    return invalidS2();
  const missing = holdings.filter((h) => h.quote.data_status === 'UNAVAILABLE').map((h) => h.instrument_id).sort();
  const receivedMissing = arrayS2(d.missing_instrument_ids, 100).map(instrument);
  if (JSON.stringify(missing) !== JSON.stringify(receivedMissing))
    return invalidS2();
  const status = !holdings.length ? 'EMPTY' : !missing.length ? 'COMPLETE' : missing.length === holdings.length ? 'UNAVAILABLE' : 'INCOMPLETE';
  if (d.valuation_status !== status || JSON.stringify(d.limitations) !== JSON.stringify(PORTFOLIO_LIMITATIONS))
    return invalidS2();
  const t = exactS2(d.totals, ['cost_basis', 'market_value', 'gain_loss', 'gain_loss_percent', 'allocation_by_asset_class', 'allocation_by_sector', 'concentration_percent', 'hhi', 'educational_spread_percent']);
  const totals: PortfolioTotals = { cost_basis: money(t.cost_basis), market_value: nullable(t.market_value, money), gain_loss: nullable(t.gain_loss, gain), gain_loss_percent: nullable(t.gain_loss_percent, gainPercent),
    allocation_by_asset_class: allocations(t.allocation_by_asset_class), allocation_by_sector: allocations(t.allocation_by_sector), concentration_percent: nullable(t.concentration_percent, percent),
    hhi: nullable(t.hhi, (v) => numberText(v, 6, '0.000000', '1.000000')), educational_spread_percent: nullable(t.educational_spread_percent, percent) };
  const partial = status === 'INCOMPLETE' || status === 'UNAVAILABLE';
  if (partial ? [totals.market_value, totals.gain_loss, totals.gain_loss_percent, totals.allocation_by_asset_class, totals.allocation_by_sector, totals.concentration_percent, totals.hhi, totals.educational_spread_percent].some((v) => v !== null) || holdings.some((h) => h.weight_percent !== null) :
    totals.market_value === null || totals.gain_loss === null || totals.allocation_by_asset_class === null || totals.allocation_by_sector === null || (totals.cost_basis === '0.00') !== (totals.gain_loss_percent === null))
    return invalidS2();
  if (!partial) {
    const zero = totals.market_value === '0.00';
    const assetGroups = Array.from(new Set(holdings.map((h) => h.asset_class))).sort();
    const sectorGroups = Array.from(new Set(holdings.map((h) => h.sector))).sort();
    if (JSON.stringify(totals.allocation_by_asset_class!.map((a) => a.group)) !== JSON.stringify(assetGroups) ||
      JSON.stringify(totals.allocation_by_sector!.map((a) => a.group)) !== JSON.stringify(sectorGroups))
      return invalidS2();
    if ([totals.concentration_percent, totals.hhi, totals.educational_spread_percent].some((v) => (v === null) !== zero) || holdings.some((h) => (h.weight_percent === null) !== zero) ||
      [totals.allocation_by_asset_class!, totals.allocation_by_sector!].some((a) => a.some((r) => (r.weight_percent === null) !== zero)))
      return invalidS2();
  }
  if (status === 'EMPTY' && (totals.cost_basis !== '0.00' || totals.market_value !== '0.00' || totals.gain_loss !== '0.00' || totals.allocation_by_asset_class!.length || totals.allocation_by_sector!.length))
    return invalidS2();
  return { ...base, metrics_version: literal(d.metrics_version, 'portfolio_metrics.v1'), formula_version: literal(d.formula_version, 'manual_portfolio_math.v1'),
    catalog_version: literal(d.catalog_version, 'synthetic_catalog.v1'), quote_snapshot_version: literal(d.quote_snapshot_version, 'synthetic_quotes.v1'), portfolio_id: id, currency: literal(d.currency, 'USD'),
    valuation_status: status, source: literal(d.source, 'finex.synthetic.portfolio'), source_type: literal(d.source_type, 'SYNTHETIC'), fixture_as_of: literal(d.fixture_as_of, FIXTURE_AS_OF),
    calculated_at: utcS2(d.calculated_at), missing_instrument_ids: missing, limitations: [...PORTFOLIO_LIMITATIONS], holdings, totals };
}
/** Input convenience only: exact lexical decimal padding, never financial calculation. */
export function decimalInput(value: string, places: 4 | 6, positive: boolean): string {
  if (!new RegExp('^(?:0|[1-9][0-9]{0,6})(?:\\.[0-9]{1,' + places + '})?$').test(value))
    throw new LocalApplicationError('VALIDATION_ERROR');
  const [whole, fraction = ''] = value.split('.');
  const result = whole + '.' + fraction.padEnd(places, '0');
  const units = (whole + fraction.padEnd(places, '0')).replace(/^0+/, '') || '0';
  const maximum = '1000000' + '0'.repeat(places);
  if ((positive && units === '0') || units.length > maximum.length || (units.length === maximum.length && units > maximum))
    throw new LocalApplicationError('VALIDATION_ERROR');
  return result;
}
export function sameDecimal(a: string, b: string, places: 4 | 6): boolean {
  return decimalInput(a, places, false) === decimalInput(b, places, false);
}
