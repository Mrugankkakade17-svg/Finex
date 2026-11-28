import React, { useCallback, useEffect, useId, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Calendar,
  CheckCircle2,
  Edit3,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ApiClient, ApiClientError, finexApiClient } from '../services/apiClient';
import { getActiveAuthSession } from '../services/authService';

export interface GoalProjection {
  year: number;
  projected_balance: string;
  contributions_total: string;
  growth_total: string;
}

export interface GoalRecord {
  goal_id: string;
  title: string;
  target_amount: string;
  current_amount: string;
  horizon_years: number;
  monthly_contribution: string;
  expected_annual_return_pct: string;
  projected_final_amount: string;
  shortfall_or_surplus: string;
  is_on_track: boolean;
  assumptions_statement: string;
  projections: GoalProjection[];
  target_date: string | null;
}

export interface GoalCreateInput {
  title: string;
  target_amount: number;
  current_amount: number;
  horizon_years: number;
  monthly_contribution: number;
  expected_annual_return_pct: number;
  target_date?: string | null;
}

export interface GoalUpdateInput {
  title?: string;
  target_amount?: number;
  current_amount?: number;
  horizon_years?: number;
  monthly_contribution?: number;
  expected_annual_return_pct?: number;
  target_date?: string | null;
}

export interface GoalContributionRecord {
  contribution_id: string;
  goal_id: string;
  amount: string;
  contribution_date: string;
  note: string | null;
  created_at: string;
}

export interface GoalContributionCreateInput {
  amount: number;
  contribution_date: string;
  note?: string | null;
}

export interface GoalProgressRecord {
  goal_id: string;
  title: string;
  target_amount: string;
  current_amount: string;
  remaining_amount: string;
  surplus_amount: string;
  progress_pct: string;
  total_contributed: string;
  contributions_count: number;
  last_contribution_date: string | null;
  as_of_date: string;
  target_date: string | null;
  horizon_years: number;
  months_remaining: number;
  is_overdue: boolean;
  is_completed: boolean;
  configured_monthly_contribution: string;
  expected_annual_return_pct: string;
  required_monthly_contribution: string | null;
  monthly_contribution_gap: string | null;
  is_on_track: boolean;
  formula_summary: string;
  assumptions_statement: string;
}

export interface GoalContributionResult {
  contribution: GoalContributionRecord;
  goal: GoalRecord;
  progress: GoalProgressRecord;
}

export interface GoalsApi {
  listGoals(signal?: AbortSignal): Promise<GoalRecord[]>;
  createGoal(input: GoalCreateInput, signal?: AbortSignal): Promise<GoalRecord>;
  updateGoal(goalId: string, input: GoalUpdateInput, signal?: AbortSignal): Promise<GoalRecord>;
  deleteGoal(goalId: string, signal?: AbortSignal): Promise<{ goal_id: string; deleted: boolean }>;
  getGoalProgress(goalId: string, signal?: AbortSignal): Promise<GoalProgressRecord>;
  listContributions(goalId: string, signal?: AbortSignal): Promise<GoalContributionRecord[]>;
  recordContribution(
    goalId: string,
    input: GoalContributionCreateInput,
    signal?: AbortSignal,
  ): Promise<GoalContributionResult>;
}

export interface GoalsApiConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

export class GoalsApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly retryable: boolean;

  constructor(
    message: string,
    code = 'API_UNAVAILABLE',
    options?: { status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = 'GoalsApiError';
    this.code = code;
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
  }
}

export interface GoalsPageProps {
  api?: GoalsApi;
}

const DEFAULT_TIMEOUT_MS = 8000;
const NON_RETRYABLE_CODES = new Set([
  'UNAUTHORIZED',
  'FORBIDDEN',
  'GOAL_NOT_FOUND',
  'VALIDATION_ERROR',
]);

function readSessionStorageToken(): string | null {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage.getItem('finex_access_token');
    }
  } catch {
    return null;
  }
  return null;
}

function resolveDefaultAuthToken(): string | null {
  return getActiveAuthSession()?.access_token ?? readSessionStorageToken();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asRequiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new GoalsApiError(`Invalid ${field} received from goals API.`, 'RESPONSE_INVALID');
  }
  return value.trim();
}

function asOptionalString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  return null;
}

function asDecimalString(value: unknown, field: string): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2);
  }
  if (typeof value === 'string' && value.trim().length > 0 && Number.isFinite(Number(value))) {
    return value.trim();
  }
  throw new GoalsApiError(`Invalid ${field} received from goals API.`, 'RESPONSE_INVALID');
}

function asOptionalDecimalString(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  return asDecimalString(value, field);
}

function asNumber(value: unknown, field: string): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  throw new GoalsApiError(`Invalid ${field} received from goals API.`, 'RESPONSE_INVALID');
}

function asBoolean(value: unknown, field: string): boolean {
  if (typeof value === 'boolean') return value;
  throw new GoalsApiError(`Invalid ${field} received from goals API.`, 'RESPONSE_INVALID');
}

function decodeProjection(raw: unknown): GoalProjection {
  const rec = asRecord(raw);
  if (!rec) {
    throw new GoalsApiError('Invalid projection row in goal payload.', 'RESPONSE_INVALID');
  }
  return {
    year: asNumber(rec.year, 'year'),
    projected_balance: asDecimalString(rec.projected_balance, 'projected_balance'),
    contributions_total: asDecimalString(rec.contributions_total, 'contributions_total'),
    growth_total: asDecimalString(rec.growth_total, 'growth_total'),
  };
}

function decodeGoal(raw: unknown): GoalRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new GoalsApiError('Invalid goal payload received from API.', 'RESPONSE_INVALID');
  }
  const projections = Array.isArray(rec.projections) ? rec.projections.map(decodeProjection) : [];
  return {
    goal_id: asRequiredString(rec.goal_id, 'goal_id'),
    title: asRequiredString(rec.title, 'title'),
    target_amount: asDecimalString(rec.target_amount, 'target_amount'),
    current_amount: asDecimalString(rec.current_amount, 'current_amount'),
    horizon_years: asNumber(rec.horizon_years, 'horizon_years'),
    monthly_contribution: asDecimalString(rec.monthly_contribution, 'monthly_contribution'),
    expected_annual_return_pct: asDecimalString(
      rec.expected_annual_return_pct,
      'expected_annual_return_pct',
    ),
    projected_final_amount: asDecimalString(
      rec.projected_final_amount,
      'projected_final_amount',
    ),
    shortfall_or_surplus: asDecimalString(rec.shortfall_or_surplus, 'shortfall_or_surplus'),
    is_on_track: asBoolean(rec.is_on_track, 'is_on_track'),
    assumptions_statement:
      asOptionalString(rec.assumptions_statement) ??
      'Deterministic model based on constant monthly compounding. No guarantee of future performance.',
    projections,
    target_date: asOptionalString(rec.target_date),
  };
}

function decodeContribution(raw: unknown): GoalContributionRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new GoalsApiError('Invalid contribution payload received from API.', 'RESPONSE_INVALID');
  }
  return {
    contribution_id: asRequiredString(rec.contribution_id, 'contribution_id'),
    goal_id: asRequiredString(rec.goal_id, 'goal_id'),
    amount: asDecimalString(rec.amount, 'amount'),
    contribution_date: asRequiredString(rec.contribution_date, 'contribution_date'),
    note: asOptionalString(rec.note),
    created_at: asRequiredString(rec.created_at, 'created_at'),
  };
}

function decodeProgress(raw: unknown): GoalProgressRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new GoalsApiError('Invalid goal progress payload received from API.', 'RESPONSE_INVALID');
  }
  return {
    goal_id: asRequiredString(rec.goal_id, 'goal_id'),
    title: asRequiredString(rec.title, 'title'),
    target_amount: asDecimalString(rec.target_amount, 'target_amount'),
    current_amount: asDecimalString(rec.current_amount, 'current_amount'),
    remaining_amount: asDecimalString(rec.remaining_amount, 'remaining_amount'),
    surplus_amount: asDecimalString(rec.surplus_amount, 'surplus_amount'),
    progress_pct: asDecimalString(rec.progress_pct, 'progress_pct'),
    total_contributed: asDecimalString(rec.total_contributed, 'total_contributed'),
    contributions_count: asNumber(rec.contributions_count, 'contributions_count'),
    last_contribution_date: asOptionalString(rec.last_contribution_date),
    as_of_date: asRequiredString(rec.as_of_date, 'as_of_date'),
    target_date: asOptionalString(rec.target_date),
    horizon_years: asNumber(rec.horizon_years, 'horizon_years'),
    months_remaining: asNumber(rec.months_remaining, 'months_remaining'),
    is_overdue: asBoolean(rec.is_overdue, 'is_overdue'),
    is_completed: asBoolean(rec.is_completed, 'is_completed'),
    configured_monthly_contribution: asDecimalString(
      rec.configured_monthly_contribution,
      'configured_monthly_contribution',
    ),
    expected_annual_return_pct: asDecimalString(
      rec.expected_annual_return_pct,
      'expected_annual_return_pct',
    ),
    required_monthly_contribution: asOptionalDecimalString(
      rec.required_monthly_contribution,
      'required_monthly_contribution',
    ),
    monthly_contribution_gap: asOptionalDecimalString(
      rec.monthly_contribution_gap,
      'monthly_contribution_gap',
    ),
    is_on_track: asBoolean(rec.is_on_track, 'is_on_track'),
    formula_summary:
      asOptionalString(rec.formula_summary) ??
      'Annuity-due deterministic compounding formula.',
    assumptions_statement:
      asOptionalString(rec.assumptions_statement) ??
      'Deterministic model based on constant monthly compounding. No guarantee of future performance.',
  };
}

function mapGoalsError(status: number, code: string, serverMessage?: string): GoalsApiError {
  if (status === 401 || code === 'UNAUTHORIZED') {
    return new GoalsApiError(
      serverMessage || 'Sign in with an active FinEx session to access your saved goals.',
      'UNAUTHORIZED',
      { status, retryable: false },
    );
  }
  if (status === 404 || code === 'GOAL_NOT_FOUND') {
    return new GoalsApiError(serverMessage || 'The requested goal was not found.', 'GOAL_NOT_FOUND', {
      status,
      retryable: false,
    });
  }
  if (status === 422 || code === 'VALIDATION_ERROR') {
    return new GoalsApiError(
      serverMessage || 'Check the goal inputs and try again.',
      'VALIDATION_ERROR',
      { status, retryable: false },
    );
  }
  const retryable = status >= 500 || !NON_RETRYABLE_CODES.has(code);
  return new GoalsApiError(
    serverMessage || 'Unable to complete the goals request.',
    code || 'GOALS_REQUEST_FAILED',
    { status, retryable },
  );
}

export function createGoalsApi(config: GoalsApiConfig = {}): GoalsApi {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const getAuthToken = config.getAuthToken ?? resolveDefaultAuthToken;

  async function requestEnvelope(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<unknown> {
    if (signal?.aborted) {
      throw new GoalsApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
        retryable: true,
      });
    }

    const controller = new AbortController();
    let timedOut = false;
    const onCallerAbort = () => controller.abort();
    signal?.addEventListener('abort', onCallerAbort, { once: true });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    try {
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
      }
      const token = getAuthToken();
      const response = await client.request(path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        ...(token ? { accessToken: token } : {}),
      });

      const payload = await response.json().catch(() => null);
      const record = asRecord(payload);

      if (!response.ok) {
        const errorDetail = asRecord(record?.error);
        const serverCode =
          (typeof errorDetail?.code === 'string' && errorDetail.code) ||
          (typeof record?.error_code === 'string' && record.error_code) ||
          (response.status === 401
            ? 'UNAUTHORIZED'
            : response.status === 404
              ? 'GOAL_NOT_FOUND'
              : response.status === 422
                ? 'VALIDATION_ERROR'
                : 'API_ERROR');
        const serverMessage =
          (typeof errorDetail?.message === 'string' && errorDetail.message) ||
          (typeof record?.message === 'string' && record.message) ||
          (typeof record?.detail === 'string' && record.detail) ||
          undefined;
        throw mapGoalsError(response.status, serverCode, serverMessage);
      }

      if (!record || record.success !== true || !('data' in record)) {
        throw new GoalsApiError(
          'Received an unexpected response format from the goals API.',
          'RESPONSE_INVALID',
          { status: response.status, retryable: true },
        );
      }
      return record.data;
    } catch (error) {
      if (error instanceof GoalsApiError) throw error;
      if (timedOut) {
        throw new GoalsApiError('The goals request timed out. Please retry.', 'REQUEST_TIMEOUT', {
          retryable: true,
        });
      }
      if (signal?.aborted) {
        throw new GoalsApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (error instanceof ApiClientError) {
        throw new GoalsApiError(error.message, error.code, { retryable: true });
      }
      throw new GoalsApiError(
        'Goals service is temporarily unreachable. Check the backend and retry.',
        'API_UNAVAILABLE',
        { retryable: true },
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onCallerAbort);
    }
  }

  return {
    async listGoals(signal?: AbortSignal): Promise<GoalRecord[]> {
      const data = await requestEnvelope('/api/v1/goals', 'GET', undefined, signal);
      if (!Array.isArray(data)) {
        throw new GoalsApiError('Expected a list of goals from the API.', 'RESPONSE_INVALID');
      }
      return data.map(decodeGoal);
    },

    async createGoal(input: GoalCreateInput, signal?: AbortSignal): Promise<GoalRecord> {
      const data = await requestEnvelope('/api/v1/goals', 'POST', input, signal);
      return decodeGoal(data);
    },

    async updateGoal(
      goalId: string,
      input: GoalUpdateInput,
      signal?: AbortSignal,
    ): Promise<GoalRecord> {
      const data = await requestEnvelope(
        `/api/v1/goals/${encodeURIComponent(goalId)}`,
        'PUT',
        input,
        signal,
      );
      return decodeGoal(data);
    },

    async deleteGoal(
      goalId: string,
      signal?: AbortSignal,
    ): Promise<{ goal_id: string; deleted: boolean }> {
      const data = await requestEnvelope(
        `/api/v1/goals/${encodeURIComponent(goalId)}`,
        'DELETE',
        undefined,
        signal,
      );
      const rec = asRecord(data);
      return {
        goal_id: asOptionalString(rec?.goal_id) ?? goalId,
        deleted: rec?.deleted === true,
      };
    },

    async getGoalProgress(goalId: string, signal?: AbortSignal): Promise<GoalProgressRecord> {
      const data = await requestEnvelope(
        `/api/v1/goals/${encodeURIComponent(goalId)}/progress`,
        'GET',
        undefined,
        signal,
      );
      return decodeProgress(data);
    },

    async listContributions(
      goalId: string,
      signal?: AbortSignal,
    ): Promise<GoalContributionRecord[]> {
      const data = await requestEnvelope(
        `/api/v1/goals/${encodeURIComponent(goalId)}/contributions`,
        'GET',
        undefined,
        signal,
      );
      if (!Array.isArray(data)) {
        throw new GoalsApiError('Expected a list of contributions from the API.', 'RESPONSE_INVALID');
      }
      return data.map(decodeContribution);
    },

    async recordContribution(
      goalId: string,
      input: GoalContributionCreateInput,
      signal?: AbortSignal,
    ): Promise<GoalContributionResult> {
      const data = await requestEnvelope(
        `/api/v1/goals/${encodeURIComponent(goalId)}/contributions`,
        'POST',
        input,
        signal,
      );
      const rec = asRecord(data);
      if (!rec) {
        throw new GoalsApiError('Invalid contribution response payload.', 'RESPONSE_INVALID');
      }
      return {
        contribution: decodeContribution(rec.contribution),
        goal: decodeGoal(rec.goal),
        progress: decodeProgress(rec.progress),
      };
    },
  };
}

export const defaultGoalsApi = createGoalsApi();

function toNum(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatUsd(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return 'Unavailable';
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed)) return 'Unavailable';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface GoalFormValues {
  title: string;
  target_amount: string;
  current_amount: string;
  horizon_years: string;
  monthly_contribution: string;
  expected_annual_return_pct: string;
  target_date: string;
}

const DEFAULT_CREATE_FORM: GoalFormValues = {
  title: '',
  target_amount: '100000',
  current_amount: '10000',
  horizon_years: '10',
  monthly_contribution: '500',
  expected_annual_return_pct: '6.0',
  target_date: '',
};

function validateGoalForm(form: GoalFormValues): { payload?: GoalCreateInput; error?: string } {
  const title = form.title.trim();
  const target_amount = Number(form.target_amount);
  const current_amount = Number(form.current_amount);
  const horizon_years = Number(form.horizon_years);
  const monthly_contribution = Number(form.monthly_contribution);
  const expected_annual_return_pct = Number(form.expected_annual_return_pct);
  const targetDateTrimmed = form.target_date.trim();

  if (!title || title.length > 100) {
    return { error: 'Goal title must be between 1 and 100 characters.' };
  }
  if (!Number.isFinite(target_amount) || target_amount <= 0) {
    return { error: 'Target amount must be greater than zero.' };
  }
  if (!Number.isFinite(current_amount) || current_amount < 0) {
    return { error: 'Current saved amount cannot be negative.' };
  }
  if (!Number.isInteger(horizon_years) || horizon_years < 1 || horizon_years > 50) {
    return { error: 'Horizon must be a whole number between 1 and 50 years.' };
  }
  if (!Number.isFinite(monthly_contribution) || monthly_contribution < 0) {
    return { error: 'Monthly contribution cannot be negative.' };
  }
  if (
    !Number.isFinite(expected_annual_return_pct) ||
    expected_annual_return_pct < 0 ||
    expected_annual_return_pct > 30
  ) {
    return { error: 'Expected annual return must be between 0% and 30%.' };
  }
  if (targetDateTrimmed && !/^\d{4}-\d{2}-\d{2}$/.test(targetDateTrimmed)) {
    return { error: 'Target date must use YYYY-MM-DD format.' };
  }

  return {
    payload: {
      title,
      target_amount,
      current_amount,
      horizon_years,
      monthly_contribution,
      expected_annual_return_pct,
      target_date: targetDateTrimmed ? targetDateTrimmed : null,
    },
  };
}

export const GoalsPage: React.FC<GoalsPageProps> = ({ api = defaultGoalsApi }) => {
  const overviewChartGradId = useId().replace(/:/g, '');
  const [goals, setGoals] = useState<GoalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);

  const [overviewView, setOverviewView] = useState<'chart' | 'table'>('chart');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<GoalFormValues>(DEFAULT_CREATE_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<'chart' | 'table'>('chart');
  const [progressByGoal, setProgressByGoal] = useState<Record<string, GoalProgressRecord>>({});
  const [contributionsByGoal, setContributionsByGoal] = useState<
    Record<string, GoalContributionRecord[]>
  >({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [contributionAmount, setContributionAmount] = useState('250');
  const [contributionDate, setContributionDate] = useState(todayIso);
  const [contributionNote, setContributionNote] = useState('');
  const [submittingContribution, setSubmittingContribution] = useState(false);
  const [contributionError, setContributionError] = useState<string | null>(null);

  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<GoalFormValues>(DEFAULT_CREATE_FORM);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadGoals = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const list = await api.listGoals(signal);
        if (signal?.aborted) return;
        setGoals(list);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof GoalsApiError && err.code === 'REQUEST_CANCELLED') return;
        setError({
          message: err instanceof Error ? err.message : 'Unable to load financial goals.',
          code: err instanceof GoalsApiError ? err.code : undefined,
        });
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [api],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadGoals(controller.signal);
    return () => controller.abort();
  }, [loadGoals]);

  const loadGoalDetails = useCallback(
    async (goalId: string, signal?: AbortSignal) => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const [progress, contributions] = await Promise.all([
          api.getGoalProgress(goalId, signal),
          api.listContributions(goalId, signal),
        ]);
        if (signal?.aborted) return;
        setProgressByGoal((prev) => ({ ...prev, [goalId]: progress }));
        setContributionsByGoal((prev) => ({ ...prev, [goalId]: contributions }));
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof GoalsApiError && err.code === 'REQUEST_CANCELLED') return;
        setDetailError(
          err instanceof Error ? err.message : 'Unable to load goal progress and contributions.',
        );
      } finally {
        if (!signal?.aborted) {
          setDetailLoading(false);
        }
      }
    },
    [api],
  );

  const handleToggleDetails = (goalId: string) => {
    if (selectedGoalId === goalId) {
      setSelectedGoalId(null);
      setDetailError(null);
      setContributionError(null);
      return;
    }
    setSelectedGoalId(goalId);
    setContributionError(null);
    void loadGoalDetails(goalId);
  };

  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const validated = validateGoalForm(createForm);
    if (validated.error || !validated.payload) {
      setCreateError(validated.error ?? 'Invalid goal fields.');
      return;
    }

    setCreating(true);
    try {
      const created = await api.createGoal(validated.payload);
      setGoals((prev) => [created, ...prev]);
      setCreateForm(DEFAULT_CREATE_FORM);
      setShowCreateForm(false);
      setSelectedGoalId(created.goal_id);
      void loadGoalDetails(created.goal_id);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create goal.');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (goal: GoalRecord) => {
    setEditingGoalId(goal.goal_id);
    setEditError(null);
    setEditForm({
      title: goal.title,
      target_amount: goal.target_amount,
      current_amount: goal.current_amount,
      horizon_years: String(goal.horizon_years),
      monthly_contribution: goal.monthly_contribution,
      expected_annual_return_pct: goal.expected_annual_return_pct,
      target_date: goal.target_date ?? '',
    });
  };

  const handleSaveEdit = async (e: React.FormEvent, goalId: string) => {
    e.preventDefault();
    setEditError(null);
    const validated = validateGoalForm(editForm);
    if (validated.error || !validated.payload) {
      setEditError(validated.error ?? 'Invalid goal update.');
      return;
    }
    setSavingEdit(true);
    try {
      const updated = await api.updateGoal(goalId, validated.payload);
      setGoals((prev) => prev.map((g) => (g.goal_id === goalId ? updated : g)));
      setEditingGoalId(null);
      if (selectedGoalId === goalId) {
        void loadGoalDetails(goalId);
      }
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Failed to update goal.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteGoal = async (goalId: string) => {
    setActionError(null);
    setDeletingId(goalId);
    try {
      await api.deleteGoal(goalId);
      setGoals((prev) => prev.filter((g) => g.goal_id !== goalId));
      if (selectedGoalId === goalId) {
        setSelectedGoalId(null);
      }
      setConfirmDeleteId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete goal.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleRecordContribution = async (e: React.FormEvent, goalId: string) => {
    e.preventDefault();
    setContributionError(null);
    const amount = Number(contributionAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setContributionError('Contribution amount must be greater than zero.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(contributionDate.trim())) {
      setContributionError('Contribution date must use YYYY-MM-DD format.');
      return;
    }
    const note = contributionNote.trim();
    if (note.length > 200) {
      setContributionError('Note must be 200 characters or fewer.');
      return;
    }

    setSubmittingContribution(true);
    try {
      const result = await api.recordContribution(goalId, {
        amount,
        contribution_date: contributionDate.trim(),
        note: note || null,
      });
      setGoals((prev) => prev.map((g) => (g.goal_id === goalId ? result.goal : g)));
      setProgressByGoal((prev) => ({ ...prev, [goalId]: result.progress }));
      setContributionsByGoal((prev) => ({
        ...prev,
        [goalId]: [result.contribution, ...(prev[goalId] ?? [])],
      }));
      setContributionNote('');
    } catch (err) {
      setContributionError(err instanceof Error ? err.message : 'Failed to record contribution.');
    } finally {
      setSubmittingContribution(false);
    }
  };

  const overviewChartData = useMemo(
    () =>
      goals.map((goal) => {
        const target = toNum(goal.target_amount);
        const current = toNum(goal.current_amount);
        const projected = toNum(goal.projected_final_amount);
        const fundedPct = target > 0 ? Math.min(100, (current / target) * 100) : 0;
        return {
          goal_id: goal.goal_id,
          name: goal.title.length > 18 ? `${goal.title.slice(0, 17)}…` : goal.title,
          fullTitle: goal.title,
          currentAmount: current,
          projectedAmount: projected,
          targetAmount: target,
          fundedPct: Number(fundedPct.toFixed(1)),
          isOnTrack: goal.is_on_track,
        };
      }),
    [goals],
  );

  const selectedGoal = goals.find((g) => g.goal_id === selectedGoalId) ?? null;
  const selectedProgress = selectedGoal ? progressByGoal[selectedGoal.goal_id] ?? null : null;
  const selectedContributions = selectedGoal
    ? contributionsByGoal[selectedGoal.goal_id] ?? []
    : [];

  const selectedProjectionData = useMemo(
    () =>
      (selectedGoal?.projections ?? []).map((row) => ({
        yearLabel: `Yr ${row.year}`,
        year: row.year,
        projectedBalance: toNum(row.projected_balance),
        contributionsTotal: toNum(row.contributions_total),
        growthTotal: toNum(row.growth_total),
      })),
    [selectedGoal],
  );

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '14px',
          marginBottom: '20px',
        }}
      >
        <div>
          <p className="local-eyebrow">FOR YOUR GOALS</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Financial Goal Planning &amp; Progress
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Server-persisted goals, deterministic compounding projections, and contribution progress
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
          <span className="badge badge-info" data-testid="goals-capability-badge">
            <BookOpen size={13} aria-hidden="true" /> EDUCATIONAL
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadGoals()}
            disabled={loading}
          >
            <RefreshCw size={15} aria-hidden="true" /> Refresh
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setShowCreateForm((v) => !v);
              setCreateError(null);
            }}
          >
            <Plus size={16} aria-hidden="true" /> Add New Goal
          </button>
        </div>
      </div>

      <section
        aria-label="Educational goal planning notice"
        className="glass-card"
        style={{
          padding: '14px 18px',
          marginBottom: '22px',
          borderLeft: '4px solid var(--color-accent-violet)',
          fontSize: '0.86rem',
          color: 'var(--color-text-muted)',
        }}
      >
        <strong style={{ color: 'var(--color-text)' }}>EDUCATIONAL · Deterministic Model:</strong>{' '}
        Projections and monthly savings targets use constant monthly annuity-due compounding on your
        saved goal inputs. Results are educational simulations, not personalized financial advice.
      </section>

      {actionError && (
        <div
          role="alert"
          style={{
            padding: '12px 16px',
            borderRadius: '12px',
            marginBottom: '18px',
            background: 'rgba(217, 72, 59, 0.12)',
            border: '1px solid rgba(217, 72, 59, 0.4)',
            color: '#B42318',
            fontWeight: 600,
          }}
        >
          {actionError}
        </div>
      )}

      {showCreateForm && (
        <form
          onSubmit={handleCreateGoal}
          className="glass-card"
          data-testid="goal-create-form"
          style={{
            padding: '24px',
            marginBottom: '24px',
          }}
        >
          <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', marginBottom: '16px' }}>
            Create Financial Goal
          </h3>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '14px',
            }}
          >
            <div>
              <label
                htmlFor="goal-create-title"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Goal Title
              </label>
              <input
                id="goal-create-title"
                type="text"
                placeholder="e.g. Emergency Fund"
                value={createForm.title}
                onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-target"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Target Amount ($)
              </label>
              <input
                id="goal-create-target"
                type="number"
                min="1"
                step="0.01"
                value={createForm.target_amount}
                onChange={(e) => setCreateForm((f) => ({ ...f, target_amount: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-current"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Current Saved ($)
              </label>
              <input
                id="goal-create-current"
                type="number"
                min="0"
                step="0.01"
                value={createForm.current_amount}
                onChange={(e) => setCreateForm((f) => ({ ...f, current_amount: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-horizon"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Horizon (Years)
              </label>
              <input
                id="goal-create-horizon"
                type="number"
                min="1"
                max="50"
                step="1"
                value={createForm.horizon_years}
                onChange={(e) => setCreateForm((f) => ({ ...f, horizon_years: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-monthly"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Monthly Contribution ($)
              </label>
              <input
                id="goal-create-monthly"
                type="number"
                min="0"
                step="0.01"
                value={createForm.monthly_contribution}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, monthly_contribution: e.target.value }))
                }
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-return"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Expected Annual Return (%)
              </label>
              <input
                id="goal-create-return"
                type="number"
                min="0"
                max="30"
                step="0.1"
                value={createForm.expected_annual_return_pct}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, expected_annual_return_pct: e.target.value }))
                }
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label
                htmlFor="goal-create-target-date"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '6px' }}
              >
                Target Date (Optional)
              </label>
              <input
                id="goal-create-target-date"
                type="date"
                value={createForm.target_date}
                onChange={(e) => setCreateForm((f) => ({ ...f, target_date: e.target.value }))}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          {createError && (
            <div role="alert" style={{ color: '#B42318', fontWeight: 600, marginTop: '12px' }}>
              {createError}
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
            <button type="submit" className="btn-primary" disabled={creating}>
              <Sparkles size={16} aria-hidden="true" /> {creating ? 'Saving…' : 'Save Goal'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setShowCreateForm(false);
                setCreateError(null);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div
          role="status"
          data-testid="goals-loading"
          className="glass-card"
          style={{ padding: '36px', textAlign: 'center', color: 'var(--color-text-muted)' }}
        >
          Loading your financial goals and projections…
        </div>
      ) : error ? (
        <div
          role="alert"
          data-testid="goals-error"
          className="glass-card"
          style={{
            padding: '24px',
            border: '1px solid rgba(217, 72, 59, 0.45)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#B42318' }}>
            <AlertTriangle size={20} aria-hidden="true" />
            <div>
              <strong>Unable to load goals.</strong> {error.message}
            </div>
          </div>
          <button type="button" className="btn-secondary" onClick={() => void loadGoals()}>
            <RefreshCw size={14} aria-hidden="true" /> Retry
          </button>
        </div>
      ) : goals.length === 0 ? (
        <div
          data-testid="goals-empty"
          className="glass-card"
          style={{ padding: '40px 24px', textAlign: 'center' }}
        >
          <Target size={32} color="var(--color-accent-coral)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', marginBottom: '8px' }}>
            No financial goals saved yet
          </h3>
          <p style={{ color: 'var(--color-text-muted)', marginBottom: '18px' }}>
            Create a goal to compute deterministic compounding projections, progress charts, and
            required monthly savings.
          </p>
          <button type="button" className="btn-primary" onClick={() => setShowCreateForm(true)}>
            <Plus size={16} aria-hidden="true" /> Create Your First Goal
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Overview Progress Chart across all goals */}
          <section
            className="glass-card"
            aria-label="Goals funding progress overview"
            data-testid="goals-overview-section"
            style={{ padding: '24px' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
                marginBottom: '16px',
              }}
            >
              <div>
                <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)' }}>
                  Goal Funding &amp; Projection Comparison
                </h3>
                <p style={{ fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
                  Current balance vs projected final amount vs target across {goals.length} saved{' '}
                  {goals.length === 1 ? 'goal' : 'goals'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  aria-pressed={overviewView === 'chart'}
                  className={overviewView === 'chart' ? 'btn-primary' : 'btn-secondary'}
                  onClick={() => setOverviewView('chart')}
                >
                  Chart
                </button>
                <button
                  type="button"
                  aria-pressed={overviewView === 'table'}
                  className={overviewView === 'table' ? 'btn-primary' : 'btn-secondary'}
                  onClick={() => setOverviewView('table')}
                >
                  Table
                </button>
              </div>
            </div>

            {overviewView === 'chart' ? (
              <div
                data-testid="goals-overview-chart"
                role="img"
                aria-label="Goal funding comparison chart"
                style={{ width: '100%', height: 280 }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={overviewChartData}
                    margin={{ top: 10, right: 16, left: 8, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E6E8E7" />
                    <XAxis dataKey="name" tick={{ fill: '#667085', fontSize: 12 }} />
                    <YAxis
                      tickFormatter={(val: number) => `$${Math.round(val).toLocaleString('en-US')}`}
                      tick={{ fill: '#667085', fontSize: 12 }}
                      width={82}
                    />
                    <Tooltip
                      formatter={(val: unknown, name: unknown) => [
                        formatUsd(Number(val)),
                        String(name ?? ''),
                      ]}
                    />
                    <Legend />
                    <Bar
                      dataKey="currentAmount"
                      name="Current Saved"
                      fill="#2F6B5F"
                      radius={[4, 4, 0, 0]}
                      isAnimationActive={false}
                    />
                    <Bar
                      dataKey="projectedAmount"
                      name="Projected Final"
                      fill="#6366F1"
                      radius={[4, 4, 0, 0]}
                      isAnimationActive={false}
                    />
                    <Bar
                      dataKey="targetAmount"
                      name="Target Amount"
                      fill="#ED795D"
                      radius={[4, 4, 0, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table
                  aria-label="Goal funding comparison table"
                  style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: '1px solid var(--color-surface-divider)',
                        textAlign: 'left',
                      }}
                    >
                      <th style={{ padding: '8px' }}>Goal</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Current Saved</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Projected Final</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Target Amount</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Funded</th>
                      <th style={{ padding: '8px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overviewChartData.map((row) => (
                      <tr
                        key={row.goal_id}
                        style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                      >
                        <td style={{ padding: '8px', fontWeight: 600 }}>{row.fullTitle}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          {formatUsd(row.currentAmount)}
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          {formatUsd(row.projectedAmount)}
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>
                          {formatUsd(row.targetAmount)}
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>{row.fundedPct}%</td>
                        <td style={{ padding: '8px' }}>
                          {row.isOnTrack ? 'On Track' : 'Off Track'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Saved Goal Cards */}
          <div
            data-testid="goals-list"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '22px',
            }}
          >
            {goals.map((goal) => {
              const target = toNum(goal.target_amount);
              const current = toNum(goal.current_amount);
              const surplus = toNum(goal.shortfall_or_surplus);
              const pct =
                target > 0 ? Math.min(100, Math.max(0, Math.round((current / target) * 100))) : 0;
              const isSelected = selectedGoalId === goal.goal_id;
              const isEditing = editingGoalId === goal.goal_id;

              return (
                <article
                  key={goal.goal_id}
                  data-testid={`goal-card-${goal.goal_id}`}
                  className="glass-card"
                  style={{ padding: '24px', borderRadius: '20px' }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '10px',
                      marginBottom: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {goal.is_on_track ? (
                        <Target size={19} color="var(--color-accent-coral)" aria-hidden="true" />
                      ) : (
                        <TrendingUp
                          size={19}
                          color="var(--color-accent-violet)"
                          aria-hidden="true"
                        />
                      )}
                      <h3 style={{ fontSize: '1.1rem', color: 'var(--color-text)', margin: 0 }}>
                        {goal.title}
                      </h3>
                    </div>
                    <span
                      className={goal.is_on_track ? 'badge badge-success' : 'badge badge-warning'}
                    >
                      {goal.is_on_track ? 'On Track' : 'Off Track'}
                    </span>
                  </div>

                  <div
                    style={{
                      fontSize: '1.65rem',
                      fontWeight: 800,
                      color: 'var(--color-text)',
                      marginBottom: '4px',
                    }}
                  >
                    {formatUsd(goal.target_amount)}
                  </div>
                  <div
                    style={{
                      fontSize: '0.84rem',
                      color: 'var(--color-text-muted)',
                      marginBottom: '14px',
                    }}
                  >
                    Saved: <strong>{formatUsd(goal.current_amount)}</strong> ({pct}%) · Horizon:{' '}
                    {goal.horizon_years} {goal.horizon_years === 1 ? 'yr' : 'yrs'}
                    {goal.target_date ? ` · Target date: ${goal.target_date}` : ''}
                  </div>

                  <div
                    role="progressbar"
                    aria-label={`${goal.title} progress`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={pct}
                    style={{
                      height: '8px',
                      background: 'var(--color-surface-divider)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                      marginBottom: '14px',
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: '100%',
                        background: goal.is_on_track
                          ? 'linear-gradient(90deg, #2F6B5F, #6366F1)'
                          : 'linear-gradient(90deg, #ED795D, #C97A10)',
                      }}
                    />
                  </div>

                  <div
                    style={{
                      display: 'grid',
                      gap: '6px',
                      fontSize: '0.84rem',
                      color: 'var(--color-text-muted)',
                      marginBottom: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Calendar size={14} aria-hidden="true" />
                      Monthly Contribution: <strong>{formatUsd(goal.monthly_contribution)}</strong> (
                      {goal.expected_annual_return_pct}%/yr)
                    </div>
                    <div>
                      Projected Final Value: <strong>{formatUsd(goal.projected_final_amount)}</strong>{' '}
                      (
                      {surplus >= 0
                        ? `Surplus ${formatUsd(surplus)}`
                        : `Shortfall ${formatUsd(Math.abs(surplus))}`}
                      )
                    </div>
                  </div>

                  {isEditing ? (
                    <form
                      onSubmit={(e) => void handleSaveEdit(e, goal.goal_id)}
                      data-testid={`goal-edit-form-${goal.goal_id}`}
                      style={{
                        padding: '14px',
                        borderRadius: '12px',
                        background: 'var(--color-surface-elevated)',
                        border: '1px solid var(--color-surface-divider)',
                        marginBottom: '12px',
                        display: 'grid',
                        gap: '10px',
                      }}
                    >
                      <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                        Title
                        <input
                          type="text"
                          value={editForm.title}
                          onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                          style={{ width: '100%', marginTop: '4px' }}
                        />
                      </label>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                          Target ($)
                          <input
                            type="number"
                            min="1"
                            step="0.01"
                            value={editForm.target_amount}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, target_amount: e.target.value }))
                            }
                            style={{ width: '100%', marginTop: '4px' }}
                          />
                        </label>
                        <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                          Monthly ($)
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={editForm.monthly_contribution}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, monthly_contribution: e.target.value }))
                            }
                            style={{ width: '100%', marginTop: '4px' }}
                          />
                        </label>
                        <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                          Horizon (Yrs)
                          <input
                            type="number"
                            min="1"
                            max="50"
                            value={editForm.horizon_years}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, horizon_years: e.target.value }))
                            }
                            style={{ width: '100%', marginTop: '4px' }}
                          />
                        </label>
                        <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                          Target Date
                          <input
                            type="date"
                            value={editForm.target_date}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, target_date: e.target.value }))
                            }
                            style={{ width: '100%', marginTop: '4px' }}
                          />
                        </label>
                      </div>
                      {editError && (
                        <div role="alert" style={{ color: '#B42318', fontSize: '0.82rem' }}>
                          {editError}
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button type="submit" className="btn-primary" disabled={savingEdit}>
                          {savingEdit ? 'Updating…' : 'Save Changes'}
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => setEditingGoalId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  ) : null}

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    <button
                      type="button"
                      className={isSelected ? 'btn-primary' : 'btn-secondary'}
                      onClick={() => handleToggleDetails(goal.goal_id)}
                      style={{ fontSize: '0.82rem', padding: '8px 12px' }}
                    >
                      {isSelected ? 'Hide Progress & Chart' : 'View Progress & Chart'}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => startEdit(goal)}
                      style={{ fontSize: '0.82rem', padding: '8px 12px' }}
                    >
                      <Edit3 size={14} aria-hidden="true" /> Edit
                    </button>
                    {confirmDeleteId === goal.goal_id ? (
                      <>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={deletingId === goal.goal_id}
                          onClick={() => void handleDeleteGoal(goal.goal_id)}
                          style={{
                            fontSize: '0.82rem',
                            padding: '8px 12px',
                            color: '#B42318',
                            borderColor: 'rgba(217, 72, 59, 0.45)',
                          }}
                        >
                          {deletingId === goal.goal_id ? 'Deleting…' : 'Confirm Delete'}
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => setConfirmDeleteId(null)}
                          style={{ fontSize: '0.82rem', padding: '8px 12px' }}
                        >
                          Keep
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setConfirmDeleteId(goal.goal_id)}
                        style={{ fontSize: '0.82rem', padding: '8px 12px' }}
                      >
                        <Trash2 size={14} aria-hidden="true" /> Delete
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          {/* Selected Goal Progress Chart, Formula Plan & Contributions Panel */}
          {selectedGoal && (
            <section
              className="glass-card"
              data-testid={`goal-detail-${selectedGoal.goal_id}`}
              aria-label={`${selectedGoal.title} detailed progress and projections`}
              style={{ padding: '26px' }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                  marginBottom: '18px',
                }}
              >
                <div>
                  <h3 style={{ fontSize: '1.25rem', color: 'var(--color-text)' }}>
                    {selectedGoal.title} — Compounding Trajectory &amp; Savings Plan
                  </h3>
                  <p style={{ fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
                    {selectedGoal.assumptions_statement}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    aria-pressed={detailTab === 'chart'}
                    className={detailTab === 'chart' ? 'btn-primary' : 'btn-secondary'}
                    onClick={() => setDetailTab('chart')}
                  >
                    Growth Chart
                  </button>
                  <button
                    type="button"
                    aria-pressed={detailTab === 'table'}
                    className={detailTab === 'table' ? 'btn-primary' : 'btn-secondary'}
                    onClick={() => setDetailTab('table')}
                  >
                    Yearly Schedule
                  </button>
                </div>
              </div>

              {detailLoading ? (
                <div role="status" style={{ padding: '16px 0', color: 'var(--color-text-muted)' }}>
                  Loading goal progress and contribution history…
                </div>
              ) : detailError ? (
                <div role="alert" style={{ color: '#B42318', marginBottom: '16px' }}>
                  {detailError}
                </div>
              ) : selectedProgress ? (
                <div
                  data-testid="goal-progress-summary"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
                    gap: '12px',
                    marginBottom: '20px',
                  }}
                >
                  <div className="local-s2-row" style={{ margin: 0 }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      Progress
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                      {selectedProgress.progress_pct}%
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      Remaining: {formatUsd(selectedProgress.remaining_amount)}
                    </div>
                  </div>
                  <div className="local-s2-row" style={{ margin: 0 }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      Required Monthly Contribution
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                      {selectedProgress.required_monthly_contribution === null
                        ? 'N/A (0 months left)'
                        : formatUsd(selectedProgress.required_monthly_contribution)}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      Months remaining: {selectedProgress.months_remaining}
                      {selectedProgress.is_overdue ? ' · Overdue' : ''}
                    </div>
                  </div>
                  <div className="local-s2-row" style={{ margin: 0 }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      Recorded Contributions
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                      {formatUsd(selectedProgress.total_contributed)}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      {selectedProgress.contributions_count}{' '}
                      {selectedProgress.contributions_count === 1 ? 'entry' : 'entries'}
                    </div>
                  </div>
                  <div className="local-s2-row" style={{ margin: 0 }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      Monthly Gap
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                      {selectedProgress.monthly_contribution_gap === null
                        ? 'N/A'
                        : formatUsd(selectedProgress.monthly_contribution_gap)}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      {selectedProgress.is_completed
                        ? 'Goal funded'
                        : selectedProgress.is_on_track
                          ? 'Configured pace meets target'
                          : 'Below required pace'}
                    </div>
                  </div>
                </div>
              ) : null}

              {selectedProgress && (
                <p
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: '18px',
                  }}
                >
                  <strong>Formula:</strong> {selectedProgress.formula_summary}
                </p>
              )}

              {selectedProjectionData.length > 0 &&
                (detailTab === 'chart' ? (
                  <div
                    data-testid={`goal-projection-chart-${selectedGoal.goal_id}`}
                    role="img"
                    aria-label={`${selectedGoal.title} yearly projection growth chart`}
                    style={{ width: '100%', height: 290, marginBottom: '22px' }}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={selectedProjectionData}
                        margin={{ top: 10, right: 16, left: 8, bottom: 8 }}
                      >
                        <defs>
                          <linearGradient
                            id={`goalProjFill-${overviewChartGradId}`}
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop offset="5%" stopColor="#2F6B5F" stopOpacity={0.26} />
                            <stop offset="95%" stopColor="#2F6B5F" stopOpacity={0.03} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E6E8E7" />
                        <XAxis dataKey="yearLabel" tick={{ fill: '#667085', fontSize: 12 }} />
                        <YAxis
                          tickFormatter={(val: number) =>
                            `$${Math.round(val).toLocaleString('en-US')}`
                          }
                          tick={{ fill: '#667085', fontSize: 12 }}
                          width={82}
                        />
                        <Tooltip
                          formatter={(val: unknown, name: unknown) => [
                            formatUsd(Number(val)),
                            String(name ?? ''),
                          ]}
                        />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="projectedBalance"
                          name="Projected Balance"
                          stroke="#2F6B5F"
                          strokeWidth={2}
                          fill={`url(#goalProjFill-${overviewChartGradId})`}
                          isAnimationActive={false}
                        />
                        <Area
                          type="monotone"
                          dataKey="contributionsTotal"
                          name="Total Contributions"
                          stroke="#6366F1"
                          strokeWidth={2}
                          fillOpacity={0}
                          isAnimationActive={false}
                        />
                        <Area
                          type="monotone"
                          dataKey="growthTotal"
                          name="Compounded Growth"
                          stroke="#ED795D"
                          strokeWidth={2}
                          fillOpacity={0}
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto', marginBottom: '22px' }}>
                    <table
                      aria-label={`${selectedGoal.title} yearly projection schedule`}
                      style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}
                    >
                      <thead>
                        <tr
                          style={{
                            borderBottom: '1px solid var(--color-surface-divider)',
                            textAlign: 'left',
                          }}
                        >
                          <th style={{ padding: '8px' }}>Year</th>
                          <th style={{ padding: '8px', textAlign: 'right' }}>Projected Balance</th>
                          <th style={{ padding: '8px', textAlign: 'right' }}>Total Contributions</th>
                          <th style={{ padding: '8px', textAlign: 'right' }}>Compounded Growth</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedGoal.projections.map((row) => (
                          <tr
                            key={row.year}
                            style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                          >
                            <td style={{ padding: '8px' }}>Year {row.year}</td>
                            <td style={{ padding: '8px', textAlign: 'right' }}>
                              {formatUsd(row.projected_balance)}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'right' }}>
                              {formatUsd(row.contributions_total)}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'right' }}>
                              {formatUsd(row.growth_total)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}

              {/* Record Contribution & Contribution History */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: '20px',
                  borderTop: '1px solid var(--color-surface-divider)',
                  paddingTop: '18px',
                }}
              >
                <form
                  onSubmit={(e) => void handleRecordContribution(e, selectedGoal.goal_id)}
                  data-testid={`goal-contribution-form-${selectedGoal.goal_id}`}
                >
                  <h4 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--color-text)' }}>
                    Record Contribution
                  </h4>
                  <div style={{ display: 'grid', gap: '10px' }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                      Contribution Amount ($)
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={contributionAmount}
                        onChange={(e) => setContributionAmount(e.target.value)}
                        style={{ width: '100%', marginTop: '4px' }}
                      />
                    </label>
                    <label style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                      Contribution Date
                      <input
                        type="date"
                        value={contributionDate}
                        onChange={(e) => setContributionDate(e.target.value)}
                        style={{ width: '100%', marginTop: '4px' }}
                      />
                    </label>
                    <label style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                      Note (Optional)
                      <input
                        type="text"
                        maxLength={200}
                        placeholder="e.g. November savings transfer"
                        value={contributionNote}
                        onChange={(e) => setContributionNote(e.target.value)}
                        style={{ width: '100%', marginTop: '4px' }}
                      />
                    </label>
                  </div>
                  {contributionError && (
                    <div role="alert" style={{ color: '#B42318', fontSize: '0.82rem', marginTop: '8px' }}>
                      {contributionError}
                    </div>
                  )}
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={submittingContribution}
                    style={{ marginTop: '12px' }}
                  >
                    <CheckCircle2 size={15} aria-hidden="true" />{' '}
                    {submittingContribution ? 'Recording…' : 'Record Contribution'}
                  </button>
                </form>

                <div data-testid={`goal-contributions-${selectedGoal.goal_id}`}>
                  <h4 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--color-text)' }}>
                    Contribution History
                  </h4>
                  {selectedContributions.length === 0 ? (
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                      No contributions recorded for this goal yet.
                    </p>
                  ) : (
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '8px' }}>
                      {selectedContributions.map((item) => (
                        <li
                          key={item.contribution_id}
                          style={{
                            padding: '10px 12px',
                            borderRadius: '10px',
                            background: 'var(--color-surface-elevated)',
                            border: '1px solid var(--color-surface-divider)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: '10px',
                            fontSize: '0.85rem',
                          }}
                        >
                          <div>
                            <strong>{formatUsd(item.amount)}</strong>
                            {item.note ? ` · ${item.note}` : ''}
                          </div>
                          <span style={{ color: 'var(--color-text-muted)' }}>
                            {item.contribution_date}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
};
