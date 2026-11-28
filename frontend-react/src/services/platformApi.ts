import { ApiClient, ApiClientError, finexApiClient } from './apiClient';
import { getActiveAuthSession } from './authService';

// Kept in memory only for the active local persona session; never persisted to browser storage.
let activeLocalSessionToken: string | null = null;

export function setActiveLocalSessionToken(token: string | null): void {
  activeLocalSessionToken = token;
}

export function getActivePlatformBearerToken(): string | null {
  return getActiveAuthSession()?.access_token ?? activeLocalSessionToken;
}

export interface GoalProjection {
  year: number;
  projected_balance: string | number;
  contributions_total: string | number;
  growth_total: string | number;
}

export interface GoalRecord {
  goal_id: string;
  title: string;
  target_amount: string | number;
  current_amount: string | number;
  horizon_years: number;
  monthly_contribution: string | number;
  expected_annual_return_pct: string | number;
  projected_final_amount: string | number;
  shortfall_or_surplus: string | number;
  is_on_track: boolean;
  assumptions_statement: string;
  projections: GoalProjection[];
}

export interface GoalCreateInput {
  title: string;
  target_amount: number;
  current_amount: number;
  horizon_years: number;
  monthly_contribution: number;
  expected_annual_return_pct: number;
}

export type AlertConditionType =
  | 'PRICE_THRESHOLD'
  | 'PCT_CHANGE'
  | 'CONCENTRATION_LIMIT'
  | 'GOAL_OFF_TRACK';

export type ComparisonOperator = 'GT' | 'LT' | 'GTE' | 'LTE' | 'EQ';

export interface AlertRuleCreateInput {
  rule_name: string;
  condition_type: AlertConditionType;
  target_symbol_or_goal: string;
  comparison_operator: ComparisonOperator;
  threshold_value: number;
  cooldown_minutes: number;
}

export interface AlertRule {
  rule_id: string;
  rule_name: string;
  condition_type: AlertConditionType | string;
  target_symbol_or_goal: string;
  comparison_operator: ComparisonOperator | string;
  threshold_value: number;
  cooldown_minutes: number;
  is_active: boolean;
  created_at: string;
}

export interface NotificationItem {
  notification_id: string;
  rule_id: string | null;
  title: string;
  body: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  created_at: string;
  is_read: boolean;
}

export interface NotificationListResult {
  unread_count: number;
  notifications: NotificationItem[];
}

export interface FeatureFlagStatus {
  flag_key: string;
  description: string;
  enabled: boolean;
  owner: string;
  safe_fallback: string;
}

export interface DependencyHealth {
  name: string;
  status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE';
  latency_ms: number;
  message?: string | null;
}

export interface SystemObservabilityReport {
  environment: string;
  app_version: string;
  uptime_seconds: number;
  healthy: boolean;
  active_feature_flags: FeatureFlagStatus[];
  dependencies: DependencyHealth[];
  error_rate_p95_ms: number;
  rollback_target_sha: string;
}

export interface ReleasePreflightCheck {
  release_tag: string;
  commit_sha: string;
  migrations_single_headed: boolean;
  security_scan_clean: boolean;
  ai_safety_eval_passed: boolean;
  accessibility_pass_rate_pct: number;
  anand_uat_approved: boolean;
  ready_for_promotion: boolean;
}

export interface CapabilitiesSummary {
  mounted: boolean;
  capabilities: Record<string, boolean>;
}

export class PlatformApiError extends Error {
  readonly code: string;
  readonly status?: number;

  constructor(message: string, code = 'API_UNAVAILABLE', status?: number) {
    super(message);
    this.name = 'PlatformApiError';
    this.code = code;
    this.status = status;
  }
}

export interface PlatformApiClient {
  getCapabilities(signal?: AbortSignal): Promise<CapabilitiesSummary>;
  listGoals(signal?: AbortSignal): Promise<GoalRecord[]>;
  createGoal(input: GoalCreateInput, signal?: AbortSignal): Promise<GoalRecord>;
  getGoal(goalId: string, signal?: AbortSignal): Promise<GoalRecord>;
  listAlertRules(signal?: AbortSignal): Promise<AlertRule[]>;
  createAlertRule(input: AlertRuleCreateInput, signal?: AbortSignal): Promise<AlertRule>;
  deleteAlertRule(ruleId: string, signal?: AbortSignal): Promise<{ rule_id: string; deleted: boolean }>;
  listNotifications(signal?: AbortSignal): Promise<NotificationListResult>;
  markNotificationRead(notifId: string, signal?: AbortSignal): Promise<NotificationItem>;
  getObservability(signal?: AbortSignal): Promise<SystemObservabilityReport>;
  listFlags(signal?: AbortSignal): Promise<FeatureFlagStatus[]>;
  toggleFlag(flagKey: string, enabled: boolean, signal?: AbortSignal): Promise<FeatureFlagStatus>;
  getPreflight(signal?: AbortSignal): Promise<ReleasePreflightCheck>;
}

export interface PlatformApiConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function mapStatusMessage(status: number, serverMessage?: string): { code: string; message: string } {
  if (status === 401) {
    return {
      code: 'AUTHENTICATION_REQUIRED',
      message: serverMessage || 'Authentication is required to access this data.',
    };
  }
  if (status === 403) {
    return {
      code: 'FORBIDDEN',
      message: serverMessage || 'You do not have permission for this action.',
    };
  }
  if (status === 404) {
    return {
      code: 'NOT_FOUND',
      message: serverMessage || 'The requested resource was not found.',
    };
  }
  if (status === 422) {
    return {
      code: 'VALIDATION_ERROR',
      message: serverMessage || 'Please check the submitted values and try again.',
    };
  }
  return {
    code: 'API_ERROR',
    message: serverMessage || 'The FinEx service could not complete this request.',
  };
}

export function createPlatformApiClient(config: PlatformApiConfig = {}): PlatformApiClient {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? 8000;

  async function request<T>(
    path: string,
    method: 'GET' | 'POST' | 'DELETE',
    body?: unknown,
    signal?: AbortSignal
  ): Promise<T> {
    if (signal?.aborted) {
      throw new PlatformApiError('The request was cancelled.', 'REQUEST_CANCELLED');
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

      const token = config.getAuthToken?.() ?? undefined;
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
          (typeof record?.error_code === 'string' && record.error_code) ||
          (typeof errorDetail?.code === 'string' && errorDetail.code) ||
          undefined;
        const serverMessage =
          (typeof errorDetail?.message === 'string' && errorDetail.message) ||
          (typeof record?.message === 'string' && record.message) ||
          (typeof record?.detail === 'string' && record.detail) ||
          undefined;
        const mapped = mapStatusMessage(response.status, serverMessage);
        throw new PlatformApiError(mapped.message, serverCode || mapped.code, response.status);
      }

      if (!record || record.success !== true || !('data' in record)) {
        throw new PlatformApiError('Received an unexpected response format from the FinEx API.', 'RESPONSE_INVALID');
      }

      return record.data as T;
    } catch (error) {
      if (error instanceof PlatformApiError) {
        throw error;
      }
      if (timedOut) {
        throw new PlatformApiError('The FinEx API request timed out. Please retry.', 'REQUEST_TIMEOUT');
      }
      if (signal?.aborted) {
        throw new PlatformApiError('The request was cancelled.', 'REQUEST_CANCELLED');
      }
      if (error instanceof ApiClientError) {
        throw new PlatformApiError(error.message, error.code);
      }
      throw new PlatformApiError(
        'The FinEx API is currently unreachable. Check that the backend is running and retry.',
        'API_UNAVAILABLE'
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onCallerAbort);
    }
  }

  return {
    async getCapabilities(signal?: AbortSignal): Promise<CapabilitiesSummary> {
      try {
        const data = await request<Record<string, unknown>>('/api/v1/capabilities', 'GET', undefined, signal);
        const capsRecord =
          asRecord(data?.capabilities) ?? asRecord(data?.features) ?? asRecord(data);
        const capabilities: Record<string, boolean> = {};
        if (capsRecord) {
          for (const [key, value] of Object.entries(capsRecord)) {
            if (typeof value === 'boolean') {
              capabilities[key] = value;
            }
          }
        }
        return { mounted: true, capabilities };
      } catch (error) {
        if (error instanceof PlatformApiError && error.code === 'REQUEST_CANCELLED') {
          throw error;
        }
        return { mounted: false, capabilities: {} };
      }
    },

    listGoals: (signal) => request<GoalRecord[]>('/api/v1/goals', 'GET', undefined, signal),
    createGoal: (input, signal) => request<GoalRecord>('/api/v1/goals', 'POST', input, signal),
    getGoal: (goalId, signal) =>
      request<GoalRecord>(`/api/v1/goals/${encodeURIComponent(goalId)}`, 'GET', undefined, signal),

    listAlertRules: (signal) => request<AlertRule[]>('/api/v1/alerts/rules', 'GET', undefined, signal),
    createAlertRule: (input, signal) => request<AlertRule>('/api/v1/alerts/rules', 'POST', input, signal),
    deleteAlertRule: (ruleId, signal) =>
      request<{ rule_id: string; deleted: boolean }>(
        `/api/v1/alerts/rules/${encodeURIComponent(ruleId)}`,
        'DELETE',
        undefined,
        signal
      ),
    listNotifications: (signal) =>
      request<NotificationListResult>('/api/v1/alerts/notifications', 'GET', undefined, signal),
    markNotificationRead: (notifId, signal) =>
      request<NotificationItem>(
        `/api/v1/alerts/notifications/${encodeURIComponent(notifId)}/read`,
        'POST',
        undefined,
        signal
      ),

    getObservability: (signal) =>
      request<SystemObservabilityReport>('/api/v1/ops/observability', 'GET', undefined, signal),
    listFlags: (signal) => request<FeatureFlagStatus[]>('/api/v1/ops/flags', 'GET', undefined, signal),
    toggleFlag: (flagKey, enabled, signal) =>
      request<FeatureFlagStatus>(
        `/api/v1/ops/flags/${encodeURIComponent(flagKey)}/toggle?enabled=${enabled ? 'true' : 'false'}`,
        'POST',
        undefined,
        signal
      ),
    getPreflight: (signal) =>
      request<ReleasePreflightCheck>('/api/v1/ops/preflight', 'GET', undefined, signal),
  };
}

export const platformApi: PlatformApiClient = createPlatformApiClient({
  getAuthToken: getActivePlatformBearerToken,
});
