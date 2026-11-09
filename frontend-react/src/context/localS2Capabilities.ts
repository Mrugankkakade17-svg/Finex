import { LocalApplicationError } from '../services/localApplicationClient';
import { LocalS2Api } from '../services/localS2Client';
export type DomainOutcome<T> = {
  status: 'success';
  value: T;
} | {
  status: 'error';
  error: LocalApplicationError;
} | {
  status: 'cancelled';
};
type Capability<F> = F extends (token: string, ...args: infer A) => Promise<infer R> ? (...args: A) => Promise<DomainOutcome<R>> : never;
/** Only named domain operations cross the context. No bearer, adapter or generic authenticated callback. */
export type LocalS2Capabilities = {
  [K in keyof LocalS2Api]: Capability<LocalS2Api[K]>;
};
export function missingS2Capabilities(): LocalS2Capabilities {
  const missing = async () => ({ status: 'error' as const, error: new LocalApplicationError('S2_UNAVAILABLE') });
  return { questionnaire: missing, riskDraft: missing, saveRiskDraft: missing, submitRisk: missing, riskHistory: missing, riskDetail: missing,
    catalog: missing, portfolios: missing, portfolio: missing, createPortfolio: missing, updatePortfolio: missing, deletePortfolio: missing,
    holdings: missing, holding: missing, createHolding: missing, updateHolding: missing, deleteHolding: missing, metrics: missing };
}
