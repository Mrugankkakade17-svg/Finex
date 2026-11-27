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

interface AuthFieldError {
  field?: string;
  code?: string;
}

interface AuthEnvelope {
  data?: Partial<AuthTokens>;
  error?: { code?: string; message?: string; fieldErrors?: AuthFieldError[] };
}

const FIELD_VALIDATION_MESSAGES: Record<string, Record<string, string>> = {
  name: {
    REQUIRED: 'Full name is required.',
    TOO_SHORT: 'Full name must be at least 2 characters.',
    TOO_LONG: 'Full name must be 100 characters or fewer.',
    INVALID_FORMAT: 'Enter a valid full name.',
  },
  email: {
    REQUIRED: 'Email is required.',
    INVALID_FORMAT: 'Enter a valid email address.',
  },
  password: {
    REQUIRED: 'Password is required.',
    TOO_SHORT: 'Password must be at least 8 characters.',
    TOO_LONG: 'Password must be 64 characters or fewer.',
    INVALID_FORMAT: 'Enter a valid password.',
  },
};

function mapFieldValidationErrors(rawFieldErrors?: AuthFieldError[]): Record<string, string> {
  const mapped: Record<string, string> = {};
  if (!Array.isArray(rawFieldErrors)) return mapped;

  for (const item of rawFieldErrors) {
    const field = typeof item?.field === 'string' ? item.field : '';
    const fieldCode = typeof item?.code === 'string' ? item.code : '';
    if (!field || !(field in FIELD_VALIDATION_MESSAGES)) continue;
    mapped[field] =
      FIELD_VALIDATION_MESSAGES[field][fieldCode] || 'Please check this field.';
  }
  return mapped;
}

function mapAuthError(status: number, body: AuthEnvelope): ApiClientError {
  const rawCode = typeof body.error?.code === 'string' ? body.error.code : '';
  const code = rawCode || (status === 422 ? 'VALIDATION_ERROR' : 'AUTH_REQUEST_FAILED');

  if (code === 'VALIDATION_ERROR' || status === 422) {
    const fieldErrors = mapFieldValidationErrors(body.error?.fieldErrors);
    const messages = Object.values(fieldErrors);
    const summary =
      messages.length > 0
        ? messages.join(' ')
        : 'Please check your details and try again.';
    return new ApiClientError(summary, 'VALIDATION_ERROR', { status, fieldErrors });
  }

  const message =
    code === 'RATE_LIMIT_EXCEEDED'
      ? 'Too many failed attempts. Please wait before trying again.'
      : code === 'EMAIL_EXISTS'
        ? 'An account with this email already exists.'
        : code === 'INVALID_CREDENTIALS'
          ? 'Email or password is incorrect.'
          : code === 'DATABASE_UNAVAILABLE'
            ? 'The account service is temporarily unavailable. Please try again later.'
            : 'We could not complete that request. Check your details and try again.';

  return new ApiClientError(message, code, { status });
}

function decodeTokens(value: unknown): AuthTokens {
  if (!value || typeof value !== 'object') {
    throw new ApiClientError('The authentication response was invalid.');
  }
  const body = value as AuthEnvelope;
  const tokens = body.data;
  if (
    typeof tokens?.access_token !== 'string' ||
    !tokens.access_token ||
    typeof tokens.refresh_token !== 'string' ||
    !tokens.refresh_token ||
    tokens.token_type !== 'bearer'
  ) {
    throw new ApiClientError('The authentication response was invalid.');
  }
  return {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    token_type: 'bearer',
  };
}

async function send(
  path: string,
  payload: Record<string, string>,
  activateSession = false,
): Promise<AuthTokens> {
  const response = await finexApiClient.request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let body: AuthEnvelope;
  try {
    body = (await response.json()) as AuthEnvelope;
  } catch {
    throw new ApiClientError(
      'The authentication service returned an unreadable response.',
      'AUTH_RESPONSE_UNREADABLE',
      { status: response.status },
    );
  }
  if (!response.ok) {
    throw mapAuthError(response.status, body || {});
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

// Retained for PR #150 demo login / legacy components; active local routes use LocalSessionContext.
export interface LoginRequest {
  displayName?: string;
  email?: string;
}

export interface LoginResponse {
  user: User;
  isAuthenticated: boolean;
}

const DEFAULT_USER: User = {
  userId: 'usr_finex_member_01',
  displayName: 'Investor',
  email: 'member@finex.app',
  avatarUrl:
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  onboardingStatus: 'COMPLETED',
  riskProfile: 'MODERATE',
  preferredCurrency: 'INR',
};

export const authService = {
  login: async (request?: LoginRequest): Promise<LoginResponse> => {
    await new Promise((resolve) => setTimeout(resolve, 180));
    const cleanName = request?.displayName?.trim();
    const generatedEmail =
      request?.email?.trim() ||
      (cleanName
        ? `${cleanName.toLowerCase().replace(/[^a-z0-9]/g, '.')}@finex.app`
        : DEFAULT_USER.email);

    return {
      user: {
        ...DEFAULT_USER,
        ...(cleanName ? { displayName: cleanName } : {}),
        email: generatedEmail,
      },
      isAuthenticated: true,
    };
  },

  logout: async (): Promise<void> => {
    await new Promise((resolve) => setTimeout(resolve, 120));
  },

  getCurrentUser: async (): Promise<User> => {
    await new Promise((resolve) => setTimeout(resolve, 120));
    const saved = localStorage.getItem('finex_auth_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // Fallback to default user
      }
    }
    return DEFAULT_USER;
  },
};
