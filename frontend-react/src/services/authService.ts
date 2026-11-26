import { ApiClientError, finexApiClient } from './apiClient';
import { User } from '../types/auth';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
}

// Kept only for the current page session. Never write bearer tokens to browser storage.
let activeAuthSession: AuthTokens | null = null;

export function getActiveAuthSession(): AuthTokens | null {
  return activeAuthSession;
}

export function clearActiveAuthSession(): void {
  activeAuthSession = null;
}

interface AuthEnvelope {
  data?: Partial<AuthTokens>;
  error?: { code?: string; message?: string; fieldErrors?: Array<{ field?: string; code?: string }> };
}

function decodeTokens(value: unknown): AuthTokens {
  if (!value || typeof value !== 'object') throw new ApiClientError('The authentication response was invalid.');
  const body = value as AuthEnvelope;
  const tokens = body.data;
  if (typeof tokens?.access_token !== 'string' || !tokens.access_token ||
      typeof tokens.refresh_token !== 'string' || !tokens.refresh_token || tokens.token_type !== 'bearer') {
    throw new ApiClientError('The authentication response was invalid.');
  }
  return {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    token_type: 'bearer',
  };
}

async function send(path: string, payload: Record<string, string>, activateSession = false): Promise<AuthTokens> {
  const response = await finexApiClient.request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let body: AuthEnvelope;
  try {
    body = await response.json() as AuthEnvelope;
  } catch {
    throw new ApiClientError('The authentication service returned an unreadable response.');
  }
  if (!response.ok) {
    const code = body.error?.code || 'AUTH_REQUEST_FAILED';
    const message = code === 'RATE_LIMIT_EXCEEDED'
      ? 'Too many failed attempts. Please wait before trying again.'
      : code === 'EMAIL_EXISTS'
        ? 'An account with this email already exists.'
        : code === 'INVALID_CREDENTIALS'
          ? 'Email or password is incorrect.'
          : code === 'DATABASE_UNAVAILABLE'
            ? 'The account service is temporarily unavailable. Please try again later.'
          : 'We could not complete that request. Check your details and try again.';
    throw new ApiClientError(message, code);
  }
  const tokens = decodeTokens(body);
  if (activateSession) activeAuthSession = tokens;
  return tokens;
}

export const realAuthService = {
  register: async (name: string, email: string, password: string) => {
    activeAuthSession = null;
    await send('/api/v1/auth/register', { name, email, password });
  },
  login: (email: string, password: string) => {
    activeAuthSession = null;
    return send('/api/v1/auth/login', { email, password }, true);
  },
};

// Retained for the disconnected legacy demo screens; the active App routes never mount this context.
export interface LoginRequest { displayName?: string; email?: string }
export interface LoginResponse { user: User; isAuthenticated: boolean }

const LEGACY_DEMO_USER: User = {
  userId: 'usr_alpha_khyati_01', displayName: 'Khyati', email: 'khyati@finex.app',
  avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  onboardingStatus: 'COMPLETED', riskProfile: 'MODERATE', preferredCurrency: 'USD',
};

export const authService = {
  login: async (request?: LoginRequest): Promise<LoginResponse> => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    return {
      user: { ...LEGACY_DEMO_USER, ...(request?.displayName ? { displayName: request.displayName } : {}), ...(request?.email ? { email: request.email } : {}) },
      isAuthenticated: true,
    };
  },
  logout: async (): Promise<void> => {
    await new Promise((resolve) => setTimeout(resolve, 200));
  },
  getCurrentUser: async (): Promise<User> => {
    await new Promise((resolve) => setTimeout(resolve, 200));
    return LEGACY_DEMO_USER;
  },
};

