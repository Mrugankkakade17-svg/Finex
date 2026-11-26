import { createApiClient, DEFAULT_API_BASE_URL, getApiBaseUrl } from './apiClient';
import { clearActiveAuthSession, getActiveAuthSession, realAuthService } from './authService';
import { finexApiClient } from './apiClient';

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

  test.each(['javascript:alert(1)', 'https://user:pass@example.test', 'https://example.test/path']) (
    'rejects invalid API origin %s', (baseUrl) => {
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
  afterEach(() => {
    clearActiveAuthSession();
    jest.restoreAllMocks();
  });

  test('login posts credentials to the auth API and keeps returned tokens in memory', async () => {
    const tokens = { access_token: 'access.token', refresh_token: 'refresh.token', token_type: 'bearer' };
    const request = jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: true, json: async () => ({ data: { ...tokens, user: { id: 12, email: 'learner@example.test', name: 'Learner' } } }),
    } as Response);

    await realAuthService.login('learner@example.test', 'safe-password');

    expect(request).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'learner@example.test', password: 'safe-password' }),
    }));
    expect(getActiveAuthSession()).toEqual(tokens);
    expect(localStorage.length).toBe(0);
  });

  test('registration uses the documented API fields and does not activate the returned tokens', async () => {
    const request = jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: true, json: async () => ({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } }),
    } as Response);

    await realAuthService.register('Learner One', 'learner@example.test', 'safe-password');

    expect(request).toHaveBeenCalledWith('/api/v1/auth/register', expect.objectContaining({
      body: JSON.stringify({ name: 'Learner One', email: 'learner@example.test', password: 'safe-password' }),
    }));
    expect(getActiveAuthSession()).toBeNull();
  });

  test('shows the PostgreSQL auth contract duplicate-email error safely', async () => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValue({
      ok: false, json: async () => ({ error: { code: 'EMAIL_EXISTS', message: 'Email already registered' } }),
    } as Response);

    await expect(realAuthService.register('Learner One', 'learner@example.test', 'safe-password'))
      .rejects.toMatchObject({ code: 'EMAIL_EXISTS', message: 'An account with this email already exists.' });
  });
});

