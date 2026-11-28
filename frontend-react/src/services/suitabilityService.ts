import { ApiClient, finexApiClient } from './apiClient';
import { getActiveAuthSession } from './authService';
import {
  SuitabilityRebalanceRequest,
  SuitabilityRebalanceResponse,
  TargetAllocationResponse,
} from '../types/suitability';

export class SuitabilityApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly retryable: boolean;

  constructor(
    message: string,
    code = 'API_UNAVAILABLE',
    options?: { status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = 'SuitabilityApiError';
    this.code = code;
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
  }
}

export interface SuitabilityApiConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

export interface SuitabilityApi {
  getTargetAllocation(riskCategory: string, signal?: AbortSignal): Promise<TargetAllocationResponse>;
  evaluateRebalancePlan(
    request: SuitabilityRebalanceRequest,
    signal?: AbortSignal,
  ): Promise<SuitabilityRebalanceResponse>;
}

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

export function createSuitabilityApi(config: SuitabilityApiConfig = {}): SuitabilityApi {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? 10000;
  const getAuthToken = config.getAuthToken ?? resolveDefaultAuthToken;

  async function sendRequest<T>(
    path: string,
    method: 'GET' | 'POST',
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    if (signal?.aborted) {
      throw new SuitabilityApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
        retryable: true,
      });
    }

    const controller = new AbortController();
    const onCallerAbort = () => controller.abort();
    signal?.addEventListener('abort', onCallerAbort, { once: true });
    const timer = setTimeout(() => {
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
            : response.status === 403
              ? 'FORBIDDEN'
              : response.status === 404
                ? 'NOT_FOUND'
                : response.status === 422
                  ? 'VALIDATION_ERROR'
                  : 'API_ERROR');
        const serverMessage =
          (typeof errorDetail?.message === 'string' && errorDetail.message) ||
          (typeof record?.message === 'string' && record.message) ||
          (typeof record?.detail === 'string' && record.detail) ||
          'Suitability service request failed.';
        throw new SuitabilityApiError(serverMessage, serverCode, {
          status: response.status,
          retryable: response.status >= 500,
        });
      }

      if (!record || !('data' in record)) {
        throw new SuitabilityApiError('Malformed suitability response envelope.', 'MALFORMED_RESPONSE');
      }

      return record.data as T;
    } catch (err) {
      if (err instanceof SuitabilityApiError) {
        throw err;
      }
      if (controller.signal.aborted) {
        throw new SuitabilityApiError('Request timed out. Please retry.', 'TIMEOUT', {
          retryable: true,
        });
      }
      throw new SuitabilityApiError(
        err instanceof Error ? err.message : 'Unable to connect to suitability engine.',
        'NETWORK_ERROR',
        { retryable: true },
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onCallerAbort);
    }
  }

  return {
    async getTargetAllocation(riskCategory: string, signal?: AbortSignal): Promise<TargetAllocationResponse> {
      const normalized = encodeURIComponent(riskCategory.trim().toUpperCase());
      return sendRequest<TargetAllocationResponse>(
        `/api/v1/suitability/allocation/${normalized}`,
        'GET',
        undefined,
        signal,
      );
    },

    async evaluateRebalancePlan(
      request: SuitabilityRebalanceRequest,
      signal?: AbortSignal,
    ): Promise<SuitabilityRebalanceResponse> {
      return sendRequest<SuitabilityRebalanceResponse>(
        '/api/v1/suitability/rebalance',
        'POST',
        request,
        signal,
      );
    },
  };
}

export const suitabilityService = createSuitabilityApi();
