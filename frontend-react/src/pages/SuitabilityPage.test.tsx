import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SuitabilityPage } from './SuitabilityPage';
import { SuitabilityApi, SuitabilityApiError } from '../services/suitabilityService';
import {
  SuitabilityRebalanceResponse,
  TargetAllocationResponse,
} from '../types/suitability';

jest.mock('recharts', () => {
  const React = require('react');
  const component = (name: string) => ({
    children,
  }: {
    children?: React.ReactNode;
    [key: string]: unknown;
  }) => React.createElement('div', { 'data-testid': `mock-${name}` }, children);
  return {
    ResponsiveContainer: component('ResponsiveContainer'),
    BarChart: component('BarChart'),
    Bar: component('Bar'),
    AreaChart: component('AreaChart'),
    Area: component('Area'),
    XAxis: component('XAxis'),
    YAxis: component('YAxis'),
    Tooltip: component('Tooltip'),
    Legend: component('Legend'),
    CartesianGrid: component('CartesianGrid'),
    PieChart: component('PieChart'),
    Pie: component('Pie'),
    Cell: component('Cell'),
  };
});

const mockTargetResponse: TargetAllocationResponse = {
  risk_category: 'MODERATE',
  model_code: 'MODERATE_V1',
  model_name: 'Moderate Balanced Growth (v1)',
  version: 'v1',
  description: 'Balanced 60/30/10 strategic benchmark allocation.',
  allocations: [
    {
      asset_class: 'EQUITY',
      target_weight: 0.6,
      target_pct: 60.0,
      benchmark_symbol: 'VTI',
      benchmark_name: 'Vanguard Total Stock Market ETF',
    },
    {
      asset_class: 'FIXED_INCOME',
      target_weight: 0.3,
      target_pct: 30.0,
      benchmark_symbol: 'BND',
      benchmark_name: 'Vanguard Total Bond Market ETF',
    },
    {
      asset_class: 'CASH',
      target_weight: 0.1,
      target_pct: 10.0,
      benchmark_symbol: 'SHV',
      benchmark_name: 'iShares Short Treasury Bond ETF',
    },
  ],
  invariants_satisfied: true,
  educational_disclaimer:
    'FinEx educational suitability engine provides non-discretionary simulated target allocation models.',
};

const mockRebalanceResponse: SuitabilityRebalanceResponse = {
  risk_category: 'MODERATE',
  model_code: 'MODERATE_V1',
  portfolio_id: 'port-123',
  portfolio_value: 100000,
  risk_score_summary: null,
  drift_summary: [
    {
      asset_class: 'EQUITY',
      current_weight: 0.72,
      current_pct: 72.0,
      target_weight: 0.6,
      target_pct: 60.0,
      drift: 0.12,
      drift_pct: 12.0,
      status: 'OVERWEIGHT',
      action: 'REDUCE',
    },
    {
      asset_class: 'FIXED_INCOME',
      current_weight: 0.2,
      current_pct: 20.0,
      target_weight: 0.3,
      target_pct: 30.0,
      drift: -0.1,
      drift_pct: -10.0,
      status: 'UNDERWEIGHT',
      action: 'INCREASE',
    },
    {
      asset_class: 'CASH',
      current_weight: 0.08,
      current_pct: 8.0,
      target_weight: 0.1,
      target_pct: 10.0,
      drift: -0.02,
      drift_pct: -2.0,
      status: 'UNDERWEIGHT',
      action: 'INCREASE',
    },
  ],
  rebalance_plan: [
    {
      asset_class: 'EQUITY',
      current_weight: 0.72,
      target_weight: 0.6,
      drift: 0.12,
      adjustment_weight: -0.12,
      direction: 'REDUCE',
      indicative_amount: -12000,
      benchmark_symbol: 'VTI',
      benchmark_name: 'Vanguard Total Stock Market ETF',
      explanation: 'Reduce equity exposure by 12.0% to realign with target 60.0%.',
    },
    {
      asset_class: 'FIXED_INCOME',
      current_weight: 0.2,
      target_weight: 0.3,
      drift: -0.1,
      adjustment_weight: 0.1,
      direction: 'INCREASE',
      indicative_amount: 10000,
      benchmark_symbol: 'BND',
      benchmark_name: 'Vanguard Total Bond Market ETF',
      explanation: 'Increase fixed income exposure by 10.0% to realign with target 30.0%.',
    },
    {
      asset_class: 'CASH',
      current_weight: 0.08,
      target_weight: 0.1,
      drift: -0.02,
      adjustment_weight: 0.02,
      direction: 'INCREASE',
      indicative_amount: 2000,
      benchmark_symbol: 'SHV',
      benchmark_name: 'iShares Short Treasury Bond ETF',
      explanation: 'Increase cash reserve by 2.0% to realign with target 10.0%.',
    },
  ],
  max_drift: 0.12,
  rebalance_required: true,
  is_empty_portfolio: false,
  educational_disclaimer:
    'FinEx educational suitability engine provides non-discretionary simulated models. Not licensed financial advice.',
};

function createMockApi(overrides: Partial<SuitabilityApi> = {}): SuitabilityApi {
  return {
    getTargetAllocation: jest.fn().mockResolvedValue(mockTargetResponse),
    evaluateRebalancePlan: jest.fn().mockResolvedValue(mockRebalanceResponse),
    ...overrides,
  };
}

describe('SuitabilityPage (S3-NI02)', () => {
  it('renders the mandatory permanent EDUCATIONAL banner at all times', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    const banner = screen.getByTestId('suitability-educational-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/EDUCATIONAL ONLY/i);
    expect(banner).toHaveTextContent(/simulated portfolio analysis and educational suitability information/i);

    // Verify it stays present after loading succeeds
    await waitFor(() => {
      expect(screen.queryByTestId('suitability-loading')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('suitability-educational-banner')).toBeInTheDocument();
  });

  it('keeps the EDUCATIONAL banner visible during loading state', () => {
    // Hang promise to keep loading active
    const api = createMockApi({
      getTargetAllocation: () => new Promise(() => {}),
      evaluateRebalancePlan: () => new Promise(() => {}),
    });
    render(<SuitabilityPage api={api} />);

    expect(screen.getByTestId('suitability-educational-banner')).toBeInTheDocument();
    expect(screen.getByTestId('suitability-loading')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /educational suitability notice/i })).toBeInTheDocument();
  });

  it('keeps the EDUCATIONAL banner visible when API error occurs and allows retry', async () => {
    let failedOnce = true;
    const api = createMockApi({
      getTargetAllocation: jest.fn().mockImplementation(() => {
        if (failedOnce) {
          return Promise.reject(new SuitabilityApiError('Backend engine down', 'API_ERROR'));
        }
        return Promise.resolve(mockTargetResponse);
      }),
      evaluateRebalancePlan: jest.fn().mockImplementation(() => {
        if (failedOnce) {
          return Promise.reject(new SuitabilityApiError('Backend engine down', 'API_ERROR'));
        }
        return Promise.resolve(mockRebalanceResponse);
      }),
    });

    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByTestId('suitability-error')).toBeInTheDocument();
    });

    // Banner is still visible during error state
    expect(screen.getByTestId('suitability-educational-banner')).toBeInTheDocument();
    expect(screen.getByText('Backend engine down')).toBeInTheDocument();

    // Click Retry
    failedOnce = false;
    fireEvent.click(screen.getByRole('button', { name: /retry evaluation/i }));

    await waitFor(() => {
      expect(screen.queryByTestId('suitability-error')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('suitability-educational-banner')).toBeInTheDocument();
    expect(screen.getByText('Moderate Balanced Growth (v1)')).toBeInTheDocument();
  });

  it('keeps the EDUCATIONAL banner visible with empty data state', async () => {
    const emptyRebalance: SuitabilityRebalanceResponse = {
      ...mockRebalanceResponse,
      drift_summary: [],
      rebalance_plan: [],
      max_drift: 0,
      is_empty_portfolio: true,
    };
    const api = createMockApi({
      evaluateRebalancePlan: jest.fn().mockResolvedValue(emptyRebalance),
    });

    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByTestId('suitability-empty')).toBeInTheDocument();
    });
    expect(screen.getByTestId('suitability-educational-banner')).toBeInTheDocument();
    expect(screen.getByText(/no suitability data available/i)).toBeInTheDocument();
  });

  it('displays suitability metrics, max drift, and rebalance status', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('Moderate Balanced Growth (v1)')).toBeInTheDocument();
    });

    expect(screen.getByText('12.0%')).toBeInTheDocument(); // max drift
    expect(screen.getByText('REBALANCE SUGGESTED')).toBeInTheDocument();
  });

  it('toggles between chart view and accessible table view', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByTestId('suitability-allocation-chart')).toBeInTheDocument();
      expect(screen.getByTestId('mock-BarChart')).toBeInTheDocument();
    });

    // Switch to Table View
    fireEvent.click(screen.getByRole('button', { name: 'Table View' }));

    expect(screen.getByRole('table', { name: /asset allocation target and current weights table/i })).toBeInTheDocument();
    expect(screen.getAllByText('+12%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('-10%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('-2%').length).toBeGreaterThanOrEqual(1);

    // Switch back to Chart View
    fireEvent.click(screen.getByRole('button', { name: 'Chart View' }));
    await waitFor(() => {
      expect(screen.getByTestId('suitability-allocation-chart')).toBeInTheDocument();
      expect(screen.getByTestId('mock-BarChart')).toBeInTheDocument();
    });
  });

  it('renders per-asset drift bars with directional indicators', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('Per-Asset Allocation Drift')).toBeInTheDocument();
    });

    expect(screen.getByText('+12%')).toBeInTheDocument();
    expect(screen.getByText('Reduce')).toBeInTheDocument();
    expect(screen.getAllByText('Increase')).toHaveLength(2);
  });

  it('renders the detailed rebalance recommendation table with zero-sum invariant notice', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('Educational Rebalance Recommendations')).toBeInTheDocument();
    });

    const table = screen.getByRole('table', { name: /detailed rebalance recommendations by asset class/i });
    expect(table).toBeInTheDocument();

    expect(screen.getByText('VTI')).toBeInTheDocument();
    expect(screen.getByText('BND')).toBeInTheDocument();
    expect(screen.getByText('SHV')).toBeInTheDocument();
    expect(screen.getByText('REDUCE')).toBeInTheDocument();
    expect(screen.getAllByText('INCREASE')).toHaveLength(2);
    expect(screen.getByText(/Zero-sum invariant verified/i)).toBeInTheDocument();
  });

  it('handles risk category selection change and triggers re-fetch', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('Moderate Balanced Growth (v1)')).toBeInTheDocument();
    });

    // Switch to Conservative
    fireEvent.click(screen.getByRole('button', { name: /conservative/i }));

    await waitFor(() => {
      expect(api.getTargetAllocation).toHaveBeenCalledWith('CONSERVATIVE', expect.any(Object));
    });
  });

  it('handles portfolio ID lookup in portfolio mode', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Evaluate Portfolio ID' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Evaluate Portfolio ID' }));

    const input = screen.getByLabelText('Portfolio UUID');
    fireEvent.change(input, { target: { value: '  11111111-2222-3333-4444-555555555555  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load Portfolio' }));

    await waitFor(() => {
      expect(api.evaluateRebalancePlan).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_id: '11111111-2222-3333-4444-555555555555',
        }),
        expect.any(Object),
      );
    });
  });

  it('handles portfolio value input changes and triggers re-fetch with custom capital amount', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Simulated Portfolio Value in USD/i)).toBeInTheDocument();
    });

    const valInput = screen.getByLabelText(/Simulated Portfolio Value in USD/i);
    fireEvent.change(valInput, { target: { value: '250000' } });

    await waitFor(() => {
      expect(api.evaluateRebalancePlan).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_value: 250000,
        }),
        expect.any(Object),
      );
    });
  });

  it('displays initial allocation notice when is_empty_portfolio is true with plan items', async () => {
    const emptyWithPlan: SuitabilityRebalanceResponse = {
      ...mockRebalanceResponse,
      is_empty_portfolio: true,
      max_drift: 1.0,
      rebalance_plan: [
        {
          asset_class: 'EQUITY',
          current_weight: 0,
          target_weight: 0.6,
          drift: -0.6,
          adjustment_weight: 0.6,
          direction: 'INCREASE',
          indicative_amount: 60000,
          benchmark_symbol: 'VTI',
          benchmark_name: 'Vanguard Total Stock Market ETF',
          explanation: 'Portfolio is unallocated; allocate initial target.',
        },
      ],
    };
    const api = createMockApi({
      evaluateRebalancePlan: jest.fn().mockResolvedValue(emptyWithPlan),
    });

    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('EMPTY PORTFOLIO')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Initial allocation plan: establishes target distribution for unallocated portfolio capital/i),
    ).toBeInTheDocument();
  });

  it('renders explicit positive sign for positive indicative amounts and negative sign for negative amounts', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('-$12,000')).toBeInTheDocument();
    });

    expect(screen.getByText('+$10,000')).toBeInTheDocument();
    expect(screen.getByText('+$2,000')).toBeInTheDocument();
  });

  it('handles selection of Aggressive risk tier and verifies model request', async () => {
    const api = createMockApi();
    render(<SuitabilityPage api={api} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /aggressive/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /aggressive/i }));

    await waitFor(() => {
      expect(api.getTargetAllocation).toHaveBeenCalledWith('AGGRESSIVE', expect.any(Object));
    });
  });
});
