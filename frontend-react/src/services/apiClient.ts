/** Shared React HTTP client. Route-specific services keep decoding their own contracts. */

export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

export interface ApiClientConfig {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export interface ApiRequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: HeadersInit;
  accessToken?: string;
}

export interface ApiClient {
  readonly baseUrl: string;
  request(path: string, options?: ApiRequestOptions): Promise<Response>;
}

export class ApiClientError extends Error {
  readonly code: string;

  constructor(message: string, code = 'API_REQUEST_FAILED') {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
  }
}

export function getApiBaseUrl(): string {
  return normalizeApiBaseUrl(process.env.REACT_APP_FINEX_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL);
}

export function normalizeApiBaseUrl(value: string): string {
  try {
    const url = new URL(value.trim());
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password ||
        url.search || url.hash || (url.pathname !== '/' && url.pathname !== '')) {
      throw new Error('invalid origin');
    }
    return url.origin;
  } catch {
    throw new ApiClientError('Configure a valid HTTP(S) FinEx API origin.', 'API_ORIGIN_INVALID');
  }
}

export function createApiClient(config: ApiClientConfig = {}): ApiClient {
  const baseUrl = normalizeApiBaseUrl(config.baseUrl || getApiBaseUrl());
  return {
    baseUrl,
    async request(path, options = {}) {
      if (!path.startsWith('/') || path.startsWith('//')) {
        throw new ApiClientError('API routes must be absolute paths on the configured origin.', 'API_PATH_INVALID');
      }
      const url = new URL(path, `${baseUrl}/`);
      if (url.origin !== baseUrl) {
        throw new ApiClientError('API routes must stay on the configured origin.', 'API_PATH_INVALID');
      }
      if (options.accessToken !== undefined && !/^[A-Za-z0-9._~-]+$/.test(options.accessToken)) {
        throw new ApiClientError('The API access token is invalid.', 'API_TOKEN_INVALID');
      }

      const { accessToken, headers: suppliedHeaders, ...init } = options;
      const headers: Record<string, string> = {};
      if (suppliedHeaders instanceof Headers) {
        suppliedHeaders.forEach((value, key) => { headers[key] = value; });
      } else if (Array.isArray(suppliedHeaders)) {
        suppliedHeaders.forEach(([key, value]) => { headers[key] = value; });
      } else if (suppliedHeaders) {
        Object.assign(headers, suppliedHeaders);
      }
      if (!Object.keys(headers).some((key) => key.toLowerCase() === 'accept')) headers.Accept = 'application/json';
      if (accessToken !== undefined) headers.Authorization = `Bearer ${accessToken}`;

      const sender = config.fetchImpl ?? (typeof globalThis.fetch === 'function' ? globalThis.fetch.bind(globalThis) : undefined);
      if (!sender) throw new ApiClientError('The FinEx API is unavailable.', 'API_UNAVAILABLE');
      try {
        return await sender(url.toString(), {
          ...init,
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
          headers,
        });
      } catch {
        throw new ApiClientError('The FinEx API is unavailable. Check the connection and retry.', 'API_UNAVAILABLE');
      }
    },
  };
}

/** Default app client for pages; the configured origin is supplied at build/runtime config. */
export const finexApiClient = createApiClient();

