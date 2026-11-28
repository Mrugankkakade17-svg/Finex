import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createApiClient } from '../services/apiClient';
import { clearActiveAuthSession, realAuthService } from '../services/authService';
import {
  GoalContributionRecord,
  GoalCreateInput,
  GoalProgressRecord,
  GoalRecord,
  GoalsApi,
  GoalsApiError,
  GoalsPage,
  createGoalsApi,
} from './GoalsPage';

jest.mock(
  'recharts',
  () => {
    const React = require('react');
    const component = (name: string) => ({ children }: { children?: React.ReactNode }) =>
      React.createElement('div', { 'data-testid': `recharts-${name}` }, children);
    const svgComponent = (name: string) => ({ children }: { children?: React.ReactNode }) =>
      React.createElement('svg', { 'data-testid': `recharts-${name}` }, children);
    return {
      Area: component('Area'),
      AreaChart: svgComponent('AreaChart'),
      Bar: component('Bar'),
      BarChart: component('BarChart'),
      CartesianGrid: component('CartesianGrid'),
      Legend: component('Legend'),
      ResponsiveContainer: component('ResponsiveContainer'),
      Tooltip: component('Tooltip'),
      XAxis: component('XAxis'),
      YAxis: component('YAxis'),
    };
  },
  { virtual: true },
);

function makeGoal(overrides: Partial<GoalRecord> = {}): GoalRecord {
  return {
    goal_id: 'goal-101',
    title: 'Education Reserve',
    target_amount: '50000.00',
    current_amount: '15000.00',
    horizon_years: 5,
    monthly_contribution: '500.00',
    expected_annual_return_pct: '6.0',
    projected_final_amount: '55200.00',
    shortfall_or_surplus: '5200.00',
    is_on_track: true,
    assumptions_statement:
      'Deterministic model based on constant monthly compounding. No guarantee of future performance.',
    projections: [
      {
        year: 1,
        projected_balance: '22000.00',
        contributions_total: '21000.00',
        growth_total: '1000.00',
      },
      {
        year: 2,
        projected_balance: '29500.00',
        contributions_total: '27000.00',
        growth_total: '2500.00',
      },
    ],
    target_date: '2031-11-01',
    ...overrides,
  };
}

function makeProgress(overrides: Partial<GoalProgressRecord> = {}): GoalProgressRecord {
  return {
    goal_id: 'goal-101',
    title: 'Education Reserve',
    target_amount: '50000.00',
    current_amount: '15000.00',
    remaining_amount: '35000.00',
    surplus_amount: '0.00',
    progress_pct: '30.00',
    total_contributed: '15000.00',
    contributions_count: 1,
    last_contribution_date: '2026-11-01',
    as_of_date: '2026-11-28',
    target_date: '2031-11-01',
    horizon_years: 5,
    months_remaining: 59,
    is_overdue: false,
    is_completed: false,
    configured_monthly_contribution: '500.00',
    expected_annual_return_pct: '6.0',
    required_monthly_contribution: '435.25',
    monthly_contribution_gap: '0.00',
    is_on_track: true,
    formula_summary: 'Annuity-due monthly contribution formula matching projection compounding.',
    assumptions_statement:
      'Deterministic model based on constant monthly compounding. No guarantee of future performance.',
    ...overrides,
  };
}

function makeMockApi(overrides: Partial<GoalsApi> = {}): jest.Mocked<GoalsApi> {
  return {
    listGoals: jest.fn(async () => []),
    createGoal: jest.fn(async (input: GoalCreateInput) =>
      makeGoal({
        goal_id: 'goal-new',
        title: input.title,
        target_amount: input.target_amount.toFixed(2),
        current_amount: input.current_amount.toFixed(2),
        horizon_years: input.horizon_years,
        monthly_contribution: input.monthly_contribution.toFixed(2),
        expected_annual_return_pct: input.expected_annual_return_pct.toFixed(2),
        target_date: input.target_date ?? null,
      }),
    ),
    updateGoal: jest.fn(async (goalId, input) =>
      makeGoal({
        goal_id: goalId,
        title: input.title ?? 'Updated Goal',
        target_amount: (input.target_amount ?? 50000).toFixed(2),
      }),
    ),
    deleteGoal: jest.fn(async (goalId) => ({ goal_id: goalId, deleted: true })),
    getGoalProgress: jest.fn(async (goalId) => makeProgress({ goal_id: goalId })),
    listContributions: jest.fn(async () => []),
    recordContribution: jest.fn(async (goalId, input) => ({
      contribution: {
        contribution_id: 'contrib-1',
        goal_id: goalId,
        amount: input.amount.toFixed(2),
        contribution_date: input.contribution_date,
        note: input.note ?? null,
        created_at: '2026-11-28T10:00:00Z',
      },
      goal: makeGoal({
        goal_id: goalId,
        current_amount: (15000 + input.amount).toFixed(2),
      }),
      progress: makeProgress({
        goal_id: goalId,
        current_amount: (15000 + input.amount).toFixed(2),
        total_contributed: (15000 + input.amount).toFixed(2),
        contributions_count: 2,
      }),
    })),
    ...overrides,
  } as jest.Mocked<GoalsApi>;
}

describe('GoalsPage', () => {
  afterEach(() => {
    clearActiveAuthSession();
    window.sessionStorage.clear();
  });

  test('renders no hard-coded goal cards in empty state', async () => {
    const api = makeMockApi({ listGoals: jest.fn(async () => []) });
    render(<GoalsPage api={api} />);

    expect(screen.getByTestId('goals-loading')).toBeInTheDocument();
    expect(await screen.findByTestId('goals-empty')).toBeInTheDocument();

    expect(screen.queryByText('Weekend away')).not.toBeInTheDocument();
    expect(screen.queryByText('Emergency Cushion')).not.toBeInTheDocument();
    expect(screen.queryByText('Home Down Payment')).not.toBeInTheDocument();
    expect(screen.queryByText('Retirement Fund')).not.toBeInTheDocument();
  });

  test('renders error state and retries loading goals', async () => {
    const api = makeMockApi({
      listGoals: jest
        .fn()
        .mockRejectedValueOnce(new GoalsApiError('Sign in required', 'UNAUTHORIZED', { status: 401 }))
        .mockResolvedValueOnce([makeGoal()]),
    });

    render(<GoalsPage api={api} />);

    expect(await screen.findByTestId('goals-error')).toHaveTextContent('Sign in required');
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

    expect(await screen.findByTestId('goal-card-goal-101')).toBeInTheDocument();
    expect(api.listGoals).toHaveBeenCalledTimes(2);
  });

  test('renders overview progress BarChart with accessible table toggle', async () => {
    const api = makeMockApi({
      listGoals: jest.fn(async () => [
        makeGoal(),
        makeGoal({
          goal_id: 'goal-102',
          title: 'House Deposit',
          target_amount: '80000.00',
          current_amount: '20000.00',
          projected_final_amount: '72000.00',
          shortfall_or_surplus: '-8000.00',
          is_on_track: false,
        }),
      ]),
    });

    render(<GoalsPage api={api} />);

    expect(await screen.findByTestId('goals-overview-chart')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Table' }));

    const table = screen.getByRole('table', { name: 'Goal funding comparison table' });
    expect(table).toBeInTheDocument();
    expect(table).toHaveTextContent('Education Reserve');
    expect(table).toHaveTextContent('House Deposit');
    expect(table).toHaveTextContent('30%');
    expect(table).toHaveTextContent('25%');
  });

  test('validates goal creation form and creates a goal via API', async () => {
    const api = makeMockApi({ listGoals: jest.fn(async () => []) });
    render(<GoalsPage api={api} />);
    await screen.findByTestId('goals-empty');

    fireEvent.click(screen.getByRole('button', { name: /Add New Goal/i }));
    fireEvent.click(screen.getByRole('button', { name: /Save Goal/i }));

    expect(await screen.findByText('Goal title must be between 1 and 100 characters.')).toBeInTheDocument();
    expect(api.createGoal).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Goal Title'), {
      target: { value: 'Travel Reserve' },
    });
    fireEvent.change(screen.getByLabelText('Target Amount ($)'), {
      target: { value: '12000' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save Goal/i }));

    await waitFor(() => {
      expect(api.createGoal).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Travel Reserve',
          target_amount: 12000,
        }),
      );
    });
    expect(await screen.findByTestId('goal-card-goal-new')).toBeInTheDocument();
  });

  test('loads progress chart, handles null required_monthly_contribution, and records contribution', async () => {
    const existingContrib: GoalContributionRecord = {
      contribution_id: 'contrib-0',
      goal_id: 'goal-101',
      amount: '500.00',
      contribution_date: '2026-11-01',
      note: 'Initial deposit',
      created_at: '2026-11-01T08:00:00Z',
    };
    const api = makeMockApi({
      listGoals: jest.fn(async () => [makeGoal()]),
      getGoalProgress: jest.fn(async () =>
        makeProgress({
          months_remaining: 0,
          is_overdue: true,
          required_monthly_contribution: null,
          monthly_contribution_gap: null,
        }),
      ),
      listContributions: jest.fn(async () => [existingContrib]),
    });

    render(<GoalsPage api={api} />);
    await screen.findByTestId('goal-card-goal-101');

    fireEvent.click(screen.getByRole('button', { name: 'View Progress & Chart' }));

    expect(await screen.findByTestId('goal-progress-summary')).toHaveTextContent(
      'N/A (0 months left)',
    );
    expect(screen.getByTestId('goal-projection-chart-goal-101')).toBeInTheDocument();
    expect(screen.getByTestId('goal-contributions-goal-101')).toHaveTextContent('Initial deposit');

    fireEvent.click(screen.getByRole('button', { name: 'Yearly Schedule' }));
    expect(
      screen.getByRole('table', { name: 'Education Reserve yearly projection schedule' }),
    ).toHaveTextContent('$22,000.00');

    const contribForm = screen.getByTestId('goal-contribution-form-goal-101');
    fireEvent.change(contribForm.querySelector('input[type="number"]') as HTMLInputElement, {
      target: { value: '300' },
    });
    fireEvent.change(contribForm.querySelector('input[type="text"]') as HTMLInputElement, {
      target: { value: 'Bonus transfer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Record Contribution/i }));

    await waitFor(() => {
      expect(api.recordContribution).toHaveBeenCalledWith(
        'goal-101',
        expect.objectContaining({
          amount: 300,
          note: 'Bonus transfer',
        }),
      );
    });
    expect(await screen.findByTestId('goal-card-goal-101')).toHaveTextContent('$15,300.00');
  });

  test('edits and deletes a goal via API', async () => {
    const api = makeMockApi({
      listGoals: jest.fn(async () => [makeGoal()]),
    });

    render(<GoalsPage api={api} />);
    await screen.findByTestId('goal-card-goal-101');

    fireEvent.click(screen.getByRole('button', { name: /Edit/i }));
    const editForm = screen.getByTestId('goal-edit-form-goal-101');
    fireEvent.change(editForm.querySelector('input[type="text"]') as HTMLInputElement, {
      target: { value: 'College Fund' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(api.updateGoal).toHaveBeenCalledWith(
        'goal-101',
        expect.objectContaining({ title: 'College Fund' }),
      );
    });
    expect(await screen.findByTestId('goal-card-goal-101')).toHaveTextContent('College Fund');

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Delete' }));

    await waitFor(() => {
      expect(api.deleteGoal).toHaveBeenCalledWith('goal-101');
    });
    expect(await screen.findByTestId('goals-empty')).toBeInTheDocument();
  });

  test('createGoalsApi sends Authorization Bearer header from active auth session', async () => {
    const fetchMock = jest.fn<Promise<Response>, [RequestInfo | URL, RequestInit?]>(
      async (url: RequestInfo | URL) => {
        const target = String(url);
        if (target.endsWith('/api/v1/auth/login')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              success: true,
              data: {
                access_token: 'real.jwt.token',
                refresh_token: 'real.refresh.token',
                token_type: 'bearer',
              },
            }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({
            success: true,
            message: 'Goals retrieved',
            data: [makeGoal()],
          }),
        } as Response;
      },
    );

    const originalFetch = globalThis.fetch;
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    try {
      await realAuthService.login('nilisha@finex.app', 'Password123!');
      const api = createGoalsApi({
        apiClient: createApiClient({
          baseUrl: 'http://127.0.0.1:8000',
          fetchImpl: fetchMock as unknown as typeof fetch,
        }),
      });
      const result = await api.listGoals();
      expect(result).toHaveLength(1);
      const goalsCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/api/v1/goals'));
      expect(goalsCall?.[1]?.headers).toEqual(
        expect.objectContaining({ Authorization: 'Bearer real.jwt.token' }),
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
