import { createApiClient } from './apiClient';
import { clearActiveAuthSession, realAuthService } from './authService';
import {
  createPlatformApiClient,
  platformApi,
  setActiveLocalSessionToken,
} from './platformApi';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe('platformApi', () => {
  test('uses shared ApiClient to unwrap FinEx v1 envelopes and send bearer headers', async () => {
    const fetchMock = jest.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        message: 'Goals retrieved',
        data: [{ goal_id: 'g-1', title: 'Emergency Fund' }],
        meta: { correlationId: 'cid-1', apiVersion: 'v1', dataStatus: 'LIVE', dataAsOf: null },
      })
    );

    const api = createPlatformApiClient({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
      getAuthToken: () => 'test-token-123',
    });

    const goals = await api.listGoals();
    expect(goals).toHaveLength(1);
    expect(goals[0].title).toBe('Emergency Fund');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/goals',
      expect.objectContaining({
        method: 'GET',
        credentials: 'omit',
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token-123',
        }),
      })
    );
  });

  test('getCapabilities parses /api/v1/capabilities and falls back safely on 404', async () => {
    const notFoundFetch = jest.fn().mockResolvedValue(jsonResponse({ detail: 'Not Found' }, 404));
    const apiMissing = createPlatformApiClient({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: notFoundFetch as unknown as typeof fetch,
      }),
    });
    expect(await apiMissing.getCapabilities()).toEqual({ mounted: false, capabilities: {} });

    const okFetch = jest.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        data: { capabilities: { goals: true, alerts: false, operations: false } },
      })
    );
    const apiPresent = createPlatformApiClient({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: okFetch as unknown as typeof fetch,
      }),
    });
    expect(await apiPresent.getCapabilities()).toEqual({
      mounted: true,
      capabilities: { goals: true, alerts: false, operations: false },
    });
  });

  test('maps 403 and network errors to PlatformApiError with safe codes', async () => {
    const forbiddenFetch = jest
      .fn()
      .mockResolvedValue(jsonResponse({ detail: 'Admin role required' }, 403));
    const api = createPlatformApiClient({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: forbiddenFetch as unknown as typeof fetch,
      }),
    });

    await expect(api.toggleFlag('FEATURE_AI_ASSISTANT', false)).rejects.toMatchObject({
      code: 'FORBIDDEN',
      status: 403,
      message: 'Admin role required',
    });

    const offlineFetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    const offlineApi = createPlatformApiClient({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: offlineFetch as unknown as typeof fetch,
      }),
    });
    await expect(offlineApi.listGoals()).rejects.toMatchObject({
      code: 'API_UNAVAILABLE',
    });
  });

  describe('default platformApi bearer wiring', () => {
    const originalFetch = globalThis.fetch;

    afterEach(() => {
      globalThis.fetch = originalFetch;
      clearActiveAuthSession();
      setActiveLocalSessionToken(null);
    });

    test('attaches bearer token from realAuthService active session and clears on logout', async () => {
      const fetchMock = jest
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({
            success: true,
            data: {
              access_token: 'header.payload.sig',
              refresh_token: 'refresh.token.val',
              token_type: 'bearer',
            },
          })
        )
        .mockResolvedValueOnce(
          jsonResponse({
            success: true,
            data: [],
            meta: { correlationId: 'cid-2', apiVersion: 'v1', dataStatus: 'LIVE', dataAsOf: null },
          })
        )
        .mockResolvedValueOnce(
          jsonResponse({
            success: true,
            data: [],
            meta: { correlationId: 'cid-3', apiVersion: 'v1', dataStatus: 'LIVE', dataAsOf: null },
          })
        );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      await realAuthService.login('user@finex.app', 'Password123!');
      await platformApi.listGoals();

      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        'http://127.0.0.1:8000/api/v1/goals',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer header.payload.sig',
          }),
        })
      );

      clearActiveAuthSession();
      await platformApi.listGoals();
      const thirdCallInit = fetchMock.mock.calls[2][1] as RequestInit;
      expect((thirdCallInit.headers as Record<string, string>).Authorization).toBeUndefined();
    });

    test('attaches bearer token from active local persona session when no real JWT is active', async () => {
      const fetchMock = jest.fn().mockResolvedValue(
        jsonResponse({
          success: true,
          data: [],
          meta: { correlationId: 'cid-4', apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null },
        })
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      setActiveLocalSessionToken('local_persona_token_0000000000000000000000000');
      await platformApi.listAlertRules();

      expect(fetchMock).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/v1/alerts/rules',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer local_persona_token_0000000000000000000000000',
          }),
        })
      );
    });
  });
});
