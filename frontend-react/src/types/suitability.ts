/**
 * TypeScript type definitions for the FinEx Suitability Engine (S3-LI01 / S3-NI02).
 */

export type RiskCategory = 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';
export type AssetClass = 'EQUITY' | 'FIXED_INCOME' | 'CASH';
export type DriftStatus = 'OVERWEIGHT' | 'UNDERWEIGHT' | 'BALANCED';
export type RebalanceAction = 'INCREASE' | 'REDUCE' | 'HOLD';

export interface TargetAllocationItem {
  asset_class: string;
  target_weight: number;
  target_pct: number;
  benchmark_symbol: string;
  benchmark_name: string;
}

export interface TargetAllocationResponse {
  risk_category: string;
  model_code: string;
  model_name: string;
  version: string;
  description: string;
  allocations: TargetAllocationItem[];
  invariants_satisfied: boolean;
  educational_disclaimer: string;
}

export interface CurrentAllocationItem {
  asset_class: string;
  weight: number;
  value?: number;
}

export interface AllocationDriftItem {
  asset_class: string;
  current_weight: number;
  current_pct: number;
  target_weight: number;
  target_pct: number;
  drift: number;
  drift_pct: number;
  status: DriftStatus;
  action: RebalanceAction;
}

export interface RebalancePlanItem {
  asset_class: string;
  current_weight: number;
  target_weight: number;
  drift: number;
  adjustment_weight: number;
  direction: RebalanceAction;
  indicative_amount?: number | null;
  benchmark_symbol?: string | null;
  benchmark_name?: string | null;
  explanation: string;
}

export interface SuitabilityRebalanceRequest {
  risk_category?: string;
  questionnaire_answers?: Array<{ question_id: string; answer_value: unknown }>;
  portfolio_id?: string;
  current_allocation?: CurrentAllocationItem[];
  portfolio_value?: number;
  drift_threshold?: number;
}

export interface SuitabilityRebalanceResponse {
  risk_category: string;
  model_code: string;
  portfolio_id?: string | null;
  portfolio_value?: number | null;
  risk_score_summary?: Record<string, unknown> | null;
  drift_summary: AllocationDriftItem[];
  rebalance_plan: RebalancePlanItem[];
  max_drift: number;
  rebalance_required: boolean;
  is_empty_portfolio: boolean;
  educational_disclaimer: string;
}
