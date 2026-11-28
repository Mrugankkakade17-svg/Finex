import { createApiClient } from './apiClient';
import {
  choosePortfolioBackendMode,
  createLocalPortfolioApi,
  createPostgresPortfolioApi,
  fetchPortfolioCapabilities,
  mapLocalMetricsToAnalytics,
  PortfolioApiError,
  resolvePortfolioApi,
} from './portfolioApi';
import { clearActiveAuthSession, realAuthService } from './authService';
import { s2Mock, s2Response, portfolioId, s2Scope, s2Time } from '../testHelpers/localS2';
import { FIXTURE_AS_OF, PORTFOLIO_LIMITATIONS, PortfolioMetrics } from './localS2Models';
import { LocalApplicationError } from './localApplicationClient';
import { LocalS2Capabilities, missingS2Capabilities } from '../context/localS2Capabilities';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    redirected: false,
    headers: { get: () => 'application/json' },
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

function envelope(data: unknown, dataStatus = 'CACHED', dataAsOf: string | null = null) {
  return {
    success: true,
    message: 'OK',
    data,
    meta: {
      apiVersion: 'v1',
      dataStatus,
      dataAsOf,
      correlationId: 'test-corr-id',
    },
  };
}

function localDomainFromMock(): LocalS2Capabilities {
  const mock = s2Mock();
  const base = missingS2Capabilities();
  return {
    ...base,
    portfolios: async () => ({ status: 'success', value: await mock.portfolios('t') }),
    portfolio: async (id) => ({ status: 'success', value: await mock.portfolio('t', id) }),
    holdings: async (id) => ({ status: 'success', value: await mock.holdings('t', id) }),
    metrics: async (id) => ({ status: 'success', value: await mock.metrics('t', id) }),
  };
}

describe('portfolioApi capabilities selection and adapters', () => {
  beforeEach(() => {
    sessionStorage.clear();
    clearActiveAuthSession();
  });

  test('choosePortfolioBackendMode selects postgres or local from explicit capabilities', () => {
    expect(
      choosePortfolioBackendMode({
        persistence: 'postgresql',
        capabilities: { portfolio: true },
      }),
    ).toMatchObject({ mode: 'postgres', portfolioEnabled: true, persistence: 'postgresql' });

    expect(
      choosePortfolioBackendMode({
        persistence: 'sqlite',
        capabilities: { portfolio: true },
      }),
    ).toMatchObject({ mode: 'local', portfolioEnabled: true, persistence: 'sqlite' });

    expect(
      choosePortfolioBackendMode({
        capabilities: { portfolio: true, portfolio_analytics: true },
      }),
    ).toMatchObject({ mode: 'postgres', portfolioEnabled: true });

    expect(
      choosePortfolioBackendMode(
        {
          capabilities: { portfolio: true, market: false },
        },
        { hasLocalSession: false, hasRealAuthToken: true },
      ),
    ).toMatchObject({ mode: 'postgres', portfolioEnabled: true });

    expect(
      choosePortfolioBackendMode(
        {
          capabilities: { portfolio: true, market: false },
        },
        { hasLocalSession: true, hasRealAuthToken: true },
      ),
    ).toMatchObject({ mode: 'local', portfolioEnabled: true });
  });

  test('fetchPortfolioCapabilities queries /api/v1/capabilities and resolvePortfolioApi returns PostgresPortfolioApi', async () => {
    const fetchMock = jest.fn(async (url: RequestInfo | URL) => {
      expect(new URL(String(url)).pathname).toBe('/api/v1/capabilities');
      return jsonResponse(
        200,
        envelope({
          persistence: 'postgresql',
          capabilities: { portfolio: true },
        }),
      );
    }) as unknown as typeof fetch;

    const apiClient = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImpl: fetchMock });
    const caps = await fetchPortfolioCapabilities({ apiClient });
    expect(caps.mode).toBe('postgres');

    const resolved = await resolvePortfolioApi({
      apiClient,
      getAuthToken: () => 'jwt-token-abc',
    });
    expect(resolved.api.mode).toBe('postgres');
    expect(resolved.api.supportsHistoricalAnalytics).toBe(true);
  });

  test('resolvePortfolioApi rejects when portfolio capability is disabled', async () => {
    const fetchMock = jest.fn(async () =>
      jsonResponse(
        200,
        envelope({
          persistence: 'postgresql',
          capabilities: { portfolio: false },
        }),
      ),
    ) as unknown as typeof fetch;

    const apiClient = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImpl: fetchMock });
    await expect(resolvePortfolioApi({ apiClient })).rejects.toMatchObject({
      code: 'PORTFOLIO_UNAVAILABLE',
    });
  });

  test('PostgresPortfolioApi fetches portfolios, holdings, and analytics with query params and bearer token', async () => {
    const requests: Array<{ path: string; auth?: string }> = [];
    const fetchMock = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const parsed = new URL(String(url));
      const headers = init?.headers as Record<string, string>;
      requests.push({ path: parsed.pathname + parsed.search, auth: headers.Authorization });

      if (parsed.pathname === '/api/v1/portfolios') {
        return jsonResponse(
          200,
          envelope([
            {
              portfolio_id: 'pg-port-1',
              user_id: 'user-1',
              name: 'Core Growth',
              description: 'Long term equity',
              portfolio_type: 'GROWTH',
              currency: 'USD',
              total_value: 1500,
              total_cost: 1200,
              total_gain_loss: 300,
              total_gain_loss_pct: 25,
              holdings_count: 2,
            },
          ]),
        );
      }

      if (parsed.pathname === '/api/v1/portfolios/pg-port-1/holdings') {
        return jsonResponse(
          200,
          envelope([
            {
              holding_id: 'h-1',
              portfolio_id: 'pg-port-1',
              user_id: 'user-1',
              symbol: 'AAPL',
              asset_class: 'EQUITY',
              sector: 'Technology',
              quantity: 5,
              avg_buy_price: 150,
              current_price: 200,
              current_value: 1000,
              total_cost: 750,
              unrealized_gain_loss: 250,
              unrealized_gain_loss_pct: 33.33,
              weight_pct: 66.67,
              is_stale: false,
            },
          ]),
        );
      }

      if (parsed.pathname === '/api/v1/portfolios/pg-port-1/analytics') {
        return jsonResponse(
          200,
          envelope(
            {
              portfolio_id: 'pg-port-1',
              status: 'COMPLETE',
              observation_count: 30,
              benchmark_symbol: 'QQQ',
              confidence_level: 0.99,
              risk_free_rate: {
                annual_rate: 0.04,
                source: 'US Treasury 3M',
                as_of: '2026-11-01',
              },
              returns: {
                cumulative: 0.12,
                annualized: 0.18,
                daily_mean: 0.0007,
              },
              annualized_volatility: 0.16,
              sharpe_ratio: 0.875,
              beta: 1.05,
              value_at_risk: {
                historical: 42.5,
                parametric: 45.1,
                confidence_level: 0.99,
                horizon_days: 1,
              },
              current_value: 1500,
              hhi: 0.555556,
              top_holdings: [
                { symbol: 'AAPL', current_value: 1000, weight: 0.666667 },
                { symbol: 'MSFT', current_value: 500, weight: 0.333333 },
              ],
              limitations: [],
            },
            'CACHED',
          ),
        );
      }

      return jsonResponse(404, { success: false, message: 'Not found' });
    }) as unknown as typeof fetch;

    const api = createPostgresPortfolioApi({
      apiClient: createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImpl: fetchMock }),
      getAuthToken: () => 'pg-secret-token',
    });

    const portfolios = await api.listPortfolios();
    expect(portfolios).toHaveLength(1);
    expect(portfolios[0].portfolio_id).toBe('pg-port-1');

    const holdings = await api.listHoldings('pg-port-1');
    expect(holdings).toHaveLength(1);
    expect(holdings[0].symbol).toBe('AAPL');

    const analytics = await api.getAnalytics('pg-port-1', {
      benchmark: 'qqq',
      topN: 3,
      confidenceLevel: 0.99,
    });
    expect(analytics.backendMode).toBe('postgres');
    expect(analytics.status).toBe('COMPLETE');
    expect(analytics.sharpe_ratio).toBe(0.875);
    expect(analytics.beta).toBe(1.05);
    expect(analytics.value_at_risk.historical).toBe(42.5);
    expect(analytics.top_holdings[0].symbol).toBe('AAPL');

    expect(requests).toEqual([
      { path: '/api/v1/portfolios', auth: 'Bearer pg-secret-token' },
      { path: '/api/v1/portfolios/pg-port-1/holdings', auth: 'Bearer pg-secret-token' },
      {
        path: '/api/v1/portfolios/pg-port-1/analytics?benchmark=QQQ&top_n=3&confidence_level=0.99',
        auth: 'Bearer pg-secret-token',
      },
    ]);
  });

  test('PostgresPortfolioApi fails closed without auth token and maps HTTP errors cleanly', async () => {
    const fetchMock = jest.fn(async () =>
      jsonResponse(404, {
        success: false,
        message: 'Portfolio missing',
        error_code: 'PORTFOLIO_NOT_FOUND',
        error: { code: 'PORTFOLIO_NOT_FOUND', message: 'Portfolio missing' },
      }),
    ) as unknown as typeof fetch;

    const apiClient = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImpl: fetchMock });

    const unauthApi = createPostgresPortfolioApi({ apiClient, getAuthToken: () => null });
    await expect(unauthApi.listPortfolios()).rejects.toMatchObject({
      code: 'UNAUTHORIZED',
      status: 401,
    });

    const authApi = createPostgresPortfolioApi({ apiClient, getAuthToken: () => 'token-1' });
    await expect(authApi.getAnalytics('missing-id')).rejects.toMatchObject({
      code: 'PORTFOLIO_NOT_FOUND',
      status: 404,
      retryable: false,
    });
  });

  test('LocalPortfolioApi maps local metrics honestly without inventing historical returns or VaR', async () => {
    const completeMetrics: PortfolioMetrics = {
      ...s2Scope,
      metrics_version: 'portfolio_metrics.v1',
      formula_version: 'manual_portfolio_math.v1',
      catalog_version: 'synthetic_catalog.v1',
      quote_snapshot_version: 'synthetic_quotes.v1',
      portfolio_id: portfolioId,
      currency: 'USD',
      valuation_status: 'COMPLETE',
      source: 'finex.synthetic.portfolio',
      source_type: 'SYNTHETIC',
      fixture_as_of: FIXTURE_AS_OF,
      calculated_at: s2Time,
      missing_instrument_ids: [],
      limitations: [...PORTFOLIO_LIMITATIONS],
      holdings: [
        {
          instrument_id: 'SYN:AAPL',
          display_name: 'Synthetic Apple example',
          asset_class: 'EQUITY',
          sector: 'TECHNOLOGY',
          currency: 'USD',
          holding_version: 'holding.v1',
          portfolio_id: portfolioId,
          holding_id: '00000000-0000-4000-8000-000000000010',
          quantity: '2.000000',
          average_cost: '100.0000',
          cost_basis: '200.00',
          quote: {
            unit_price: '150.0000',
            data_status: 'CACHED',
            quote_as_of: FIXTURE_AS_OF,
            reason: null,
          },
          market_value: '300.00',
          gain_loss: '100.00',
          gain_loss_percent: '50.00',
          weight_percent: '60.00',
        },
        {
          instrument_id: 'SYN:MSFT',
          display_name: 'Synthetic Microsoft example',
          asset_class: 'EQUITY',
          sector: 'TECHNOLOGY',
          currency: 'USD',
          holding_version: 'holding.v1',
          portfolio_id: portfolioId,
          holding_id: '00000000-0000-4000-8000-000000000011',
          quantity: '1.000000',
          average_cost: '180.0000',
          cost_basis: '180.00',
          quote: {
            unit_price: '200.0000',
            data_status: 'CACHED',
            quote_as_of: FIXTURE_AS_OF,
            reason: null,
          },
          market_value: '200.00',
          gain_loss: '20.00',
          gain_loss_percent: '11.11',
          weight_percent: '40.00',
        },
      ],
      totals: {
        cost_basis: '380.00',
        market_value: '500.00',
        gain_loss: '120.00',
        gain_loss_percent: '31.58',
        allocation_by_asset_class: [{ group: 'EQUITY', market_value: '500.00', weight_percent: '100.00' }],
        allocation_by_sector: [{ group: 'TECHNOLOGY', market_value: '500.00', weight_percent: '100.00' }],
        concentration_percent: '60.00',
        hhi: '0.520000',
        educational_spread_percent: '40.00',
      },
    };

    const mapped = mapLocalMetricsToAnalytics(s2Response(completeMetrics, FIXTURE_AS_OF), {
      topN: 1,
    });
    expect(mapped.backendMode).toBe('local');
    expect(mapped.status).toBe('INSUFFICIENT_DATA');
    expect(mapped.current_value).toBe(500);
    expect(mapped.hhi).toBe(0.52);
    expect(mapped.top_holdings).toEqual([{ symbol: 'AAPL', current_value: 300, weight: 0.6 }]);
    expect(mapped.returns).toEqual({ cumulative: null, annualized: null, daily_mean: null });
    expect(mapped.sharpe_ratio).toBeNull();
    expect(mapped.beta).toBeNull();
    expect(mapped.value_at_risk.historical).toBeNull();
    expect(mapped.value_at_risk.parametric).toBeNull();

    const domain = localDomainFromMock();
    domain.metrics = async () => ({ status: 'error', error: new LocalApplicationError('LOCAL_STORE_UNAVAILABLE') });
    const localApi = createLocalPortfolioApi(domain);
    await expect(localApi.getAnalytics(portfolioId)).rejects.toBeInstanceOf(PortfolioApiError);
  });

  test('authService import remains valid when checking default token resolution', () => {
    expect(typeof realAuthService.login).toBe('function');
  });
});
