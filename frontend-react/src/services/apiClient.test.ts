import { ApiClientError, createApiClient, DEFAULT_API_BASE_URL, finexApiClient, getApiBaseUrl } from './apiClient';
import { authService, clearActiveAuthSession, getActiveAuthSession, realAuthService } from './authService';

describe('shared API client', () => {
  test('uses the configured origin and sends bearer credentials without cookies', async () => {
    const fetchImpl = jest.fn().mockResolvedValue({ ok: true } as Response);
    const client = createApiClient({ baseUrl: 'https://api.example.test/', fetchImpl });

    await client.request('/api/v1/private', {
      method: 'POST',
      accessToken: 'safe.token_123',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'yes' }),
    });

    expect(fetchImpl).toHaveBeenCalledWith('https://api.example.test/api/v1/private', expect.objectContaining({
      method: 'POST',
      credentials: 'omit',
      redirect: 'error',
      headers: expect.objectContaining({
        Accept: 'application/json',
        Authorization: 'Bearer safe.token_123',
        'Content-Type': 'application/json',
      }),
    }));
  });

  test('centralizes and normalizes the configured base origin', () => {
    const prior = process.env.REACT_APP_FINEX_API_BASE_URL;
    process.env.REACT_APP_FINEX_API_BASE_URL = 'https://api.example.test/';
    expect(getApiBaseUrl()).toBe('https://api.example.test');
    if (prior === undefined) delete process.env.REACT_APP_FINEX_API_BASE_URL;
    else process.env.REACT_APP_FINEX_API_BASE_URL = prior;
    expect(createApiClient().baseUrl).toBe(DEFAULT_API_BASE_URL);
  });

  test.each(['javascript:alert(1)', 'https://user:pass@example.test', 'https://example.test/path'])(
    'rejects invalid API origin %s',
    (baseUrl) => {
      expect(() => createApiClient({ baseUrl })).toThrow();
    },
  );

  test('rejects routes that escape the configured origin and invalid tokens', async () => {
    const fetchImpl = jest.fn();
    const client = createApiClient({ baseUrl: 'https://api.example.test', fetchImpl });
    await expect(client.request('//other.example/path')).rejects.toMatchObject({ code: 'API_PATH_INVALID' });
    await expect(client.request('/safe', { accessToken: 'not a token' })).rejects.toMatchObject({ code: 'API_TOKEN_INVALID' });
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});

describe('real account auth API integration', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    clearActiveAuthSession();
    jest.restoreAllMocks();
  });

  test('login posts credentials to the auth API and keeps returned tokens in memory', async () => {
    const tokens = { access_token: 'access.token', refresh_token: 'refresh.token', token_type: 'bearer' };
    const request = jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        data: { ...tokens, user: { id: 12, email: 'learner@example.test', name: 'Learner' } },
      }),
    } as Response);

    await realAuthService.login('learner@example.test', 'safe-password');

    expect(request).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'learner@example.test', password: 'safe-password' }),
    }));
    expect(getActiveAuthSession()).toEqual(tokens);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test('registration uses the documented API fields and does not activate the returned tokens', async () => {
    const request = jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } }),
    } as Response);

    await realAuthService.register('Learner One', 'learner@example.test', 'safe-password');

    expect(request).toHaveBeenCalledWith('/api/v1/auth/register', expect.objectContaining({
      body: JSON.stringify({ name: 'Learner One', email: 'learner@example.test', password: 'safe-password' }),
    }));
    expect(getActiveAuthSession()).toBeNull();
  });

  test('maps EMAIL_EXISTS to a user-friendly duplicate-email error', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: { code: 'EMAIL_EXISTS', message: 'Email already registered' } }),
    } as Response);

    await expect(realAuthService.register('Learner One', 'learner@example.test', 'safe-password'))
      .rejects.toMatchObject({ code: 'EMAIL_EXISTS', message: 'An account with this email already exists.' });
  });

  test('maps INVALID_CREDENTIALS to a user-friendly error without keeping tokens', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password' } }),
    } as Response);

    await expect(realAuthService.login('learner@example.test', 'wrong-password'))
      .rejects.toMatchObject({ code: 'INVALID_CREDENTIALS', message: 'Email or password is incorrect.' });
    expect(getActiveAuthSession()).toBeNull();
  });

  test('maps RATE_LIMIT_EXCEEDED to a user-friendly throttling message', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ error: { code: 'RATE_LIMIT_EXCEEDED', message: 'Too many failed login attempts' } }),
    } as Response);

    await expect(realAuthService.login('learner@example.test', 'wrong-password'))
      .rejects.toMatchObject({
        code: 'RATE_LIMIT_EXCEEDED',
        message: 'Too many failed attempts. Please wait before trying again.',
      });
  });

  test('maps DATABASE_UNAVAILABLE to a safe service availability message', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        error: { code: 'DATABASE_UNAVAILABLE', message: 'psycopg connection refused at 10.0.0.12' },
      }),
    } as Response);

    await expect(realAuthService.register('Learner One', 'learner@example.test', 'safe-password'))
      .rejects.toMatchObject({
        code: 'DATABASE_UNAVAILABLE',
        message: 'The account service is temporarily unavailable. Please try again later.',
      });
  });

  test('maps HTTP 422 VALIDATION_ERROR fieldErrors into field-level messages', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Request validation failed',
          fieldErrors: [
            { field: 'name', code: 'TOO_SHORT' },
            { field: 'email', code: 'INVALID_FORMAT' },
            { field: 'password', code: 'TOO_SHORT' },
          ],
        },
      }),
    } as Response);

    try {
      await realAuthService.register('A', 'bad-email', 'short');
      throw new Error('Expected register to reject');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe('VALIDATION_ERROR');
      expect(apiErr.status).toBe(422);
      expect(apiErr.fieldErrors).toEqual({
        name: 'Full name must be at least 2 characters.',
        email: 'Enter a valid email address.',
        password: 'Password must be at least 8 characters.',
      });
      expect(apiErr.message).toContain('Full name must be at least 2 characters.');
    }
  });

  test('handles unexpected API errors and unreadable responses without leaking backend details', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        error: {
          code: 'INTERNAL_SQL_CRASH',
          message: 'FATAL: password authentication failed for db_user secret-pass-123',
        },
      }),
    } as Response);

    try {
      await realAuthService.login('learner@example.test', 'secret-pass-123');
      throw new Error('Expected login to reject');
    } catch (err) {
      const apiErr = err as ApiClientError;
      expect(apiErr.message).toBe('We could not complete that request. Check your details and try again.');
      expect(apiErr.message).not.toContain('FATAL');
      expect(apiErr.message).not.toContain('secret-pass-123');
    }

    jest.spyOn(finexApiClient, 'request').mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON');
      },
    } as unknown as Response);

    await expect(realAuthService.login('learner@example.test', 'safe-password'))
      .rejects.toMatchObject({
        code: 'AUTH_RESPONSE_UNREADABLE',
        message: 'The authentication service returned an unreadable response.',
      });
  });

  test('preserves PR #150 demo authService behavior separately from realAuthService', async () => {
    const result = await authService.login({ displayName: '  Riya  ' });
    expect(result.isAuthenticated).toBe(true);
    expect(result.user.displayName).toBe('Riya');
    expect(result.user.email).toBe('riya@finex.app');
    expect(getActiveAuthSession()).toBeNull();
  });
});
