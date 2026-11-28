import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PortfolioAnalyticsPanel } from './PortfolioAnalyticsPanel';
import {
  PortfolioAnalytics,
  PortfolioApi,
  PortfolioApiError,
} from '../services/portfolioApi';
import { LocalSessionProvider } from '../context/LocalSessionContext';
import { LocalPortfolioPage } from '../pages/LocalPortfolioPage';
import { clientMock } from '../testHelpers/localApplication';

jest.mock(
  'recharts',
  () => {
    const React = require('react');
    const component = (name: string) => ({ children }: { children?: React.ReactNode }) =>
      React.createElement('div', { 'data-testid': `recharts-${name}` }, children);
    return {
      Bar: component('Bar'),
      BarChart: component('BarChart'),
      CartesianGrid: component('CartesianGrid'),
      ResponsiveContainer: component('ResponsiveContainer'),
      Tooltip: component('Tooltip'),
      XAxis: component('XAxis'),
      YAxis: component('YAxis'),
    };
  },
  { virtual: true },
);

function makeAnalytics(overrides: Partial<PortfolioAnalytics> = {}): PortfolioAnalytics {
  return {
    portfolio_id: 'pg-port-1',
    backendMode: 'postgres',
    status: 'COMPLETE',
    dataStatus: 'CACHED',
    dataAsOf: '2026-11-27T00:00:00Z',
    sourceLabel: 'PostgreSQL / S3-PA01 Analytics API',
    observation_count: 60,
    benchmark_symbol: 'SPY',
    confidence_level: 0.95,
    risk_free_rate: {
      annual_rate: 0.0425,
      source: 'US Treasury 3M',
      as_of: '2026-11-25',
    },
    returns: {
      cumulative: 0.145,
      annualized: 0.21,
      daily_mean: 0.0012,
    },
    annualized_volatility: 0.155,
    sharpe_ratio: 1.0806,
    beta: 0.94,
    value_at_risk: {
      historical: 245.5,
      parametric: 260.25,
      confidence_level: 0.95,
      horizon_days: 1,
    },
    current_value: 10000,
    hhi: 0.388889,
    top_holdings: [
      { symbol: 'MSFT', current_value: 5000, weight: 0.5 },
      { symbol: 'AAPL', current_value: 3333.33, weight: 0.333333 },
      { symbol: 'BND', current_value: 1666.67, weight: 0.166667 },
    ],
    limitations: [],
    ...overrides,
  };
}

function makeMockApi(overrides: Partial<PortfolioApi> = {}): jest.Mocked<PortfolioApi> {
  return {
    mode: 'postgres',
    supportsHistoricalAnalytics: true,
    listPortfolios: jest.fn(async () => []),
    getPortfolio: jest.fn(),
    listHoldings: jest.fn(async () => []),
    getAnalytics: jest.fn(async () => makeAnalytics()),
    ...overrides,
  } as jest.Mocked<PortfolioApi>;
}

describe('PortfolioAnalyticsPanel', () => {
  test('renders empty state when no portfolio is selected', () => {
    const api = makeMockApi();
    render(<PortfolioAnalyticsPanel portfolioId={null} api={api} />);
    expect(screen.getByTestId('portfolio-analytics-empty')).toBeInTheDocument();
    expect(api.getAnalytics).not.toHaveBeenCalled();
  });

  test('renders complete Postgres analytics, risk-free metadata, top holdings table, and chart', async () => {
    const api = makeMockApi();
    render(
      <PortfolioAnalyticsPanel
        portfolioId="pg-port-1"
        portfolioName="Core Growth"
        currency="USD"
        api={api}
      />,
    );

    expect(screen.getByTestId('analytics-loading')).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTestId('analytics-content')).toBeInTheDocument());
    expect(screen.getByTestId('analytics-backend-badge')).toHaveTextContent('PostgreSQL Analytics');
    expect(screen.getByTestId('analytics-status-badge')).toHaveTextContent('COMPLETE');
    expect(screen.getByTestId('analytics-current-value')).toHaveTextContent('$10,000.00');
    expect(screen.getByTestId('analytics-hhi')).toHaveTextContent('0.388889');
    expect(screen.getByTestId('analytics-cumulative-return')).toHaveTextContent('14.50%');
    expect(screen.getByTestId('analytics-annualized-return')).toHaveTextContent('21.00%');
    expect(screen.getByTestId('analytics-volatility')).toHaveTextContent('15.50%');
    expect(screen.getByTestId('analytics-sharpe')).toHaveTextContent('1.0806');
    expect(screen.getByTestId('analytics-beta')).toHaveTextContent('0.9400');
    expect(screen.getByTestId('analytics-historical-var')).toHaveTextContent('$245.50');
    expect(screen.getByTestId('analytics-parametric-var')).toHaveTextContent('$260.25');
    expect(screen.getByTestId('analytics-risk-free-rate')).toHaveTextContent('US Treasury 3M');
    expect(screen.getByTestId('analytics-weights-chart')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Top holdings concentration' })).toBeInTheDocument();
  });

  test('re-queries analytics when benchmark, VaR confidence, or topN changes', async () => {
    const api = makeMockApi();
    render(<PortfolioAnalyticsPanel portfolioId="pg-port-1" api={api} />);

    await waitFor(() => expect(screen.getByTestId('analytics-content')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('VaR confidence'), { target: { value: '0.99' } });
    await waitFor(() =>
      expect(api.getAnalytics).toHaveBeenLastCalledWith(
        'pg-port-1',
        { benchmark: 'SPY', topN: 5, confidenceLevel: 0.99 },
        expect.any(AbortSignal),
      ),
    );

    fireEvent.change(screen.getByLabelText('Top holdings'), { target: { value: '10' } });
    await waitFor(() =>
      expect(api.getAnalytics).toHaveBeenLastCalledWith(
        'pg-port-1',
        { benchmark: 'SPY', topN: 10, confidenceLevel: 0.99 },
        expect.any(AbortSignal),
      ),
    );

    fireEvent.change(screen.getByLabelText('Benchmark'), { target: { value: 'qqq' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh analytics' }));
    await waitFor(() =>
      expect(api.getAnalytics).toHaveBeenLastCalledWith(
        'pg-port-1',
        { benchmark: 'QQQ', topN: 10, confidenceLevel: 0.99 },
        expect.any(AbortSignal),
      ),
    );
  });

  test('renders INSUFFICIENT_DATA honestly while preserving snapshot HHI and top holdings', async () => {
    const api = makeMockApi({
      getAnalytics: jest.fn(async () =>
        makeAnalytics({
          status: 'INSUFFICIENT_DATA',
          dataStatus: 'UNAVAILABLE',
          observation_count: 0,
          returns: { cumulative: null, annualized: null, daily_mean: null },
          annualized_volatility: null,
          sharpe_ratio: null,
          beta: null,
          value_at_risk: {
            historical: null,
            parametric: null,
            confidence_level: 0.95,
            horizon_days: 1,
          },
          hhi: 0.5,
          limitations: ['Historical metrics are unavailable until aligned daily close-price history is supplied.'],
        }),
      ),
    });

    render(<PortfolioAnalyticsPanel portfolioId="pg-port-1" api={api} />);

    await waitFor(() => expect(screen.getByTestId('analytics-insufficient-data')).toBeInTheDocument());
    expect(screen.getByTestId('analytics-hhi')).toHaveTextContent('0.500000');
    expect(screen.getByTestId('analytics-cumulative-return')).toHaveTextContent('Unavailable');
    expect(screen.getByTestId('analytics-sharpe')).toHaveTextContent('Unavailable');
    expect(screen.getByTestId('analytics-historical-var')).toHaveTextContent('Unavailable');
    expect(screen.getByText(/Historical metrics are unavailable/)).toBeInTheDocument();
  });

  test('handles API failure with retry action', async () => {
    const api = makeMockApi({
      getAnalytics: jest
        .fn()
        .mockRejectedValueOnce(new PortfolioApiError('Analytics temporarily unavailable', 'API_UNAVAILABLE'))
        .mockResolvedValueOnce(makeAnalytics()),
    });

    render(<PortfolioAnalyticsPanel portfolioId="pg-port-1" api={api} />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Analytics temporarily unavailable');

    fireEvent.click(screen.getByRole('button', { name: 'Retry analytics' }));
    await waitFor(() => expect(screen.getByTestId('analytics-content')).toBeInTheDocument());
    expect(api.getAnalytics).toHaveBeenCalledTimes(2);
  });
});

describe('LocalPortfolioPage with /capabilities backend resolution', () => {
  test('loads PostgreSQL portfolios, holdings, and analytics when /capabilities selects postgres', async () => {
    const api = makeMockApi({
      listPortfolios: jest.fn(async () => [
        {
          portfolio_id: 'pg-port-1',
          name: 'Postgres Core',
          description: 'Backed by Postgres',
          portfolio_type: 'INDIVIDUAL',
          currency: 'USD',
          total_value: 10000,
          total_cost: 8500,
          total_gain_loss: 1500,
          total_gain_loss_pct: 17.65,
          holdings_count: 1,
          created_at: null,
          updated_at: null,
        },
      ]),
      listHoldings: jest.fn(async () => [
        {
          holding_id: 'pg-hold-1',
          portfolio_id: 'pg-port-1',
          symbol: 'MSFT',
          display_name: 'MSFT',
          asset_class: 'EQUITY',
          sector: 'Technology',
          quantity: 10,
          average_cost: 350,
          current_price: 400,
          current_value: 4000,
          total_cost: 3500,
          unrealized_gain_loss: 500,
          unrealized_gain_loss_pct: 14.29,
          weight_pct: 100,
          is_stale: false,
        },
      ]),
    });

    const resolveApi = jest.fn(async () => ({
      api,
      capabilities: {
        mode: 'postgres' as const,
        portfolioEnabled: true,
        capabilities: { portfolio: true },
        persistence: 'postgresql',
      },
    }));

    const mockClient = clientMock();
    render(
      <LocalSessionProvider client={mockClient}>
        <LocalPortfolioPage resolveApi={resolveApi} />
      </LocalSessionProvider>,
    );

    await screen.findByRole('heading', { name: 'Postgres Core' });
    await screen.findByText(/10 units/);
    await waitFor(() => expect(screen.getByTestId('analytics-content')).toBeInTheDocument());
    expect(screen.getByTestId('analytics-sharpe')).toHaveTextContent('1.0806');
  });

  test('shows explicit local-login guidance when /capabilities selects local without local persona', async () => {
    const api = makeMockApi({ mode: 'local', supportsHistoricalAnalytics: false });
    const resolveApi = jest.fn(async () => ({
      api,
      capabilities: {
        mode: 'local' as const,
        portfolioEnabled: true,
        capabilities: { portfolio: true },
        persistence: 'sqlite',
      },
    }));

    const mockClient = clientMock();
    render(
      <LocalSessionProvider client={mockClient}>
        <LocalPortfolioPage resolveApi={resolveApi} />
      </LocalSessionProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId('pg-local-mode-notice')).toHaveTextContent(
        /Local SQLite portfolio mode is active/,
      ),
    );
  });

  test('renders PortfolioAnalyticsPanel in local snapshot mode without historical controls', async () => {
    const localApi = {
      ...makeMockApi({ mode: 'local', supportsHistoricalAnalytics: false }),
      getAnalytics: jest.fn(async () =>
        makeAnalytics({
          backendMode: 'local',
          status: 'INSUFFICIENT_DATA',
          dataStatus: 'CACHED',
          observation_count: 0,
          sourceLabel: 'Local SQLite Manual Portfolio (Synthetic Snapshot)',
          returns: { cumulative: null, annualized: null, daily_mean: null },
          annualized_volatility: null,
          sharpe_ratio: null,
          beta: null,
          value_at_risk: {
            historical: null,
            parametric: null,
            confidence_level: 0.95,
            horizon_days: 1,
          },
          hhi: 0.52,
          limitations: ['Local SQLite manual portfolios track synthetic current-snapshot valuation only.'],
        }),
      ),
    };

    render(
      <PortfolioAnalyticsPanel
        portfolioId="local-port-1"
        portfolioName="Local Practice"
        currency="USD"
        api={localApi}
      />,
    );

    await waitFor(() => expect(screen.getByTestId('analytics-content')).toBeInTheDocument());
    expect(screen.getByTestId('analytics-backend-badge')).toHaveTextContent('Local SQLite Snapshot');
    expect(screen.queryByRole('button', { name: 'Refresh analytics' })).not.toBeInTheDocument();
    expect(screen.getByTestId('analytics-hhi')).toHaveTextContent('0.520000');
    expect(screen.getByTestId('analytics-cumulative-return')).toHaveTextContent('Unavailable');
  });
});
