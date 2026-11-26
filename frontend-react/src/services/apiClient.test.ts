import { createApiClient, DEFAULT_API_BASE_URL, getApiBaseUrl } from './apiClient';

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
