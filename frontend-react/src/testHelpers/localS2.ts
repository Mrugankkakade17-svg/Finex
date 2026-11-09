/** Handcrafted synthetic DTOs for unit tests only; production never falls back to these. */
import { LOCAL_SCOPE, LOCAL_CONTRACT_VERSION } from '../services/localApplicationClient';
import { Catalog, Holding, LocalQuestionnaire, LocalRiskDraft, LocalS2Response, Portfolio, PortfolioMetrics, RiskInput, SavedRisk, FIXTURE_AS_OF, PORTFOLIO_LIMITATIONS, RISK_QUESTION_IDS } from '../services/localS2Models';
import { LocalS2Api } from '../services/localS2Client';
import { readFileSync } from 'fs';
import { join } from 'path';
export const s2Scope = { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION } as const;
export const s2Time = '2026-10-11T12:00:00.123456+00:00';
export const portfolioId = '00000000-0000-4000-8000-000000000001';
export const holdingId = '00000000-0000-4000-8000-000000000002';
export const assessmentId = '00000000-0000-4000-8000-000000000003';
export function inputFixture(): RiskInput {
  return { questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1', answers: RISK_QUESTION_IDS.map((id) => ({ question_id: id, answer_code: id + '_C' })) };
}
export function questionnaireFixture(): LocalQuestionnaire {
  return { ...s2Scope, questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1',
    scoring_version: 'deterministic_v1.0.0', explanation_version: 'educational_v1.0.0', rules_sha256: 'a'.repeat(64),
    questions: RISK_QUESTION_IDS.map((id) => ({ question_id: id, dimension: id.startsWith('W') ? 'willingness' : 'capacity', text: 'Synthetic server question ' + id,
      options: ['A', 'B', 'C', 'D', 'E'].map((letter) => ({ code: id + '_' + letter, label: 'Synthetic option ' + letter })) })),
    limitation: { code: 'EDUCATIONAL_SELF_REPORTED_PROFILE', message: 'Self-reported educational example, not investment advice.' } };
}
export function draftFixture(): LocalRiskDraft {
  return { ...s2Scope, questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1', answers: [], updated_at: null };
}
export function savedFixture(): SavedRisk {
  const q = questionnaireFixture();
  return { ...s2Scope, persisted: true, assessment_id: assessmentId, created_at: s2Time,
    input: inputFixture(), explanation_version: 'educational_v1.0.0', rules_sha256: q.rules_sha256,
    rules_snapshot: JSON.parse(readFileSync(join(process.cwd(), '..', 'backend', 'data', 'questionnaire', 'risk_questionnaire_v1.json'), 'utf8')) as Record<string, unknown>,
    assessment: { contract_version: 's2-risk-contract/v1.0', questionnaire_id: q.questionnaire_id, questionnaire_version: q.questionnaire_version,
      scoring_version: q.scoring_version, willingness_score: 50, capacity_score: 50, composite_score: 50, risk_category: { code: 'MODERATE', label: 'Moderate' },
      calculated_at: s2Time, limitation: q.limitation, informational_tension: null },
    explanation: { summary: 'Synthetic server explanation', dimensions: 'Two self-reported dimensions.', method: 'Server deterministic rules, no client scoring.',
      questionnaire_version: 'v1', scoring_version: q.scoring_version, calculated_at: s2Time, limitation: q.limitation.message } };
}
export function portfolioFixture(): Portfolio {
  return { ...s2Scope, portfolio_version: 'portfolio.v1', portfolio_id: portfolioId, name: 'Synthetic manual example', description: null, currency: 'USD', created_at: s2Time, updated_at: s2Time };
}
export function catalogFixture(): Catalog {
  return { ...s2Scope, catalog_version: 'synthetic_catalog.v1', currency: 'USD', count: 2, items: [
      { instrument_id: 'SYN:AAPL', display_name: 'Synthetic Apple example', asset_class: 'EQUITY', sector: 'TECHNOLOGY', currency: 'USD' },
      { instrument_id: 'SYN:UNAVAILABLE', display_name: 'Synthetic unavailable-price example', asset_class: 'EQUITY', sector: 'GENERAL', currency: 'USD' }
    ] };
}
export function emptyMetrics(): PortfolioMetrics {
  return { ...s2Scope, metrics_version: 'portfolio_metrics.v1', formula_version: 'manual_portfolio_math.v1', catalog_version: 'synthetic_catalog.v1', quote_snapshot_version: 'synthetic_quotes.v1', portfolio_id: portfolioId, currency: 'USD', valuation_status: 'EMPTY', source: 'finex.synthetic.portfolio', source_type: 'SYNTHETIC', fixture_as_of: FIXTURE_AS_OF, calculated_at: s2Time, missing_instrument_ids: [], limitations: [...PORTFOLIO_LIMITATIONS], holdings: [], totals: { cost_basis: '0.00', market_value: '0.00', gain_loss: '0.00', gain_loss_percent: null, allocation_by_asset_class: [], allocation_by_sector: [], concentration_percent: null, hhi: null, educational_spread_percent: null } };
}
export function s2Response<T>(data: T, asOf: string | null = null, status: 'CACHED' | 'UNAVAILABLE' = 'CACHED'): LocalS2Response<T> {
  return { data, meta: { apiVersion: 'v1', dataStatus: status, dataAsOf: asOf, correlationId: 's2-unit' } };
}
export function holdingFixture(): Holding {
  return { ...s2Scope, ...catalogFixture().items[0], holding_version: 'holding.v1', catalog_version: 'synthetic_catalog.v1', portfolio_id: portfolioId, holding_id: holdingId, quantity: '10.000000', average_cost: '150.0000', created_at: s2Time, updated_at: s2Time };
}
export function s2Mock(): jest.Mocked<LocalS2Api> {
  let draft = draftFixture(), portfolios: Portfolio[] = [], holdings: Holding[] = [], history: SavedRisk[] = [];
  let sequence = 10;
  const id = () => '00000000-0000-4000-8000-' + String(sequence++).padStart(12, '0');
  const api: LocalS2Api = {
    questionnaire: async () => s2Response(questionnaireFixture()), riskDraft: async () => s2Response(draft, draft.updated_at),
    saveRiskDraft: async (_token, input) => {
      draft = { ...s2Scope, ...input, answers: input.answers.map((a) => ({ ...a })), updated_at: s2Time };
      return s2Response(draft, s2Time);
    },
    submitRisk: async (_token, input) => {
      const old = history.find((r) => r.assessment_id === input.idempotency_key);
      if (old)
        return s2Response(old, old.created_at);
      const saved = { ...savedFixture(), assessment_id: input.idempotency_key, input: { questionnaire_id: input.questionnaire_id, questionnaire_version: input.questionnaire_version, answers: input.answers.map((a) => ({ ...a })) } };
      history.unshift(saved);
      return s2Response(saved, saved.created_at);
    },
    riskHistory: async () => s2Response({ ...s2Scope, items: history.slice(0, 2), next_cursor: null }),
    riskDetail: async (_t, id) => {
      const saved = history.find((r) => r.assessment_id === id) || { ...savedFixture(), assessment_id: id };
      return s2Response(saved, saved.created_at);
    },
    catalog: async () => s2Response(catalogFixture()), portfolios: async () => s2Response({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [...portfolios], count: portfolios.length }),
    portfolio: async (_t, id) => s2Response(portfolios.find((r) => r.portfolio_id === id) || portfolioFixture(), s2Time),
    createPortfolio: async (_t, input) => {
      const p = { ...portfolioFixture(), ...input, portfolio_id: id() };
      portfolios.push(p);
      return s2Response(p, p.updated_at);
    },
    updatePortfolio: async (_t, id, input) => {
      const p = { ...portfolioFixture(), ...input, portfolio_id: id };
      portfolios = portfolios.map((old) => old.portfolio_id === id ? p : old);
      return s2Response(p, p.updated_at);
    },
    deletePortfolio: async (_t, id) => {
      portfolios = portfolios.filter((r) => r.portfolio_id !== id);
      holdings = holdings.filter((r) => r.portfolio_id !== id);
      return s2Response({ ...s2Scope, portfolio_version: 'portfolio.v1', portfolio_id: id, entity_type: 'portfolio', deleted: true });
    },
    holdings: async (_t, id) => {
      const items = holdings.filter((r) => r.portfolio_id === id);
      return s2Response({ ...s2Scope, holding_version: 'holding.v1', catalog_version: 'synthetic_catalog.v1', portfolio_id: id, items, count: items.length });
    },
    holding: async (_t, _id, h) => s2Response(holdings.find((r) => r.holding_id === h) || holdingFixture(), s2Time),
    createHolding: async (_t, p, input) => {
      const h = { ...holdingFixture(), ...input, ...catalogFixture().items.find((r) => r.instrument_id === input.instrument_id)!, portfolio_id: p, holding_id: id() };
      holdings.push(h);
      return s2Response(h, h.updated_at);
    },
    updateHolding: async (_t, p, h, input) => {
      const item = { ...(holdings.find((r) => r.holding_id === h) || holdingFixture()), ...input, portfolio_id: p, holding_id: h };
      holdings = holdings.map((old) => old.holding_id === h ? item : old);
      return s2Response(item, item.updated_at);
    },
    deleteHolding: async (_t, p, h) => {
      holdings = holdings.filter((r) => r.holding_id !== h);
      return s2Response({ ...s2Scope, holding_version: 'holding.v1', portfolio_id: p, holding_id: h, entity_type: 'holding', deleted: true });
    },
    metrics: async (_t, p) => s2Response({ ...emptyMetrics(), portfolio_id: p }),
  };
  return {
    questionnaire: jest.fn(api.questionnaire), riskDraft: jest.fn(api.riskDraft), saveRiskDraft: jest.fn(api.saveRiskDraft),
    submitRisk: jest.fn(api.submitRisk), riskHistory: jest.fn(api.riskHistory), riskDetail: jest.fn(api.riskDetail),
    catalog: jest.fn(api.catalog), portfolios: jest.fn(api.portfolios), portfolio: jest.fn(api.portfolio),
    createPortfolio: jest.fn(api.createPortfolio), updatePortfolio: jest.fn(api.updatePortfolio), deletePortfolio: jest.fn(api.deletePortfolio),
    holdings: jest.fn(api.holdings), holding: jest.fn(api.holding), createHolding: jest.fn(api.createHolding),
    updateHolding: jest.fn(api.updateHolding), deleteHolding: jest.fn(api.deleteHolding), metrics: jest.fn(api.metrics),
  };
}
