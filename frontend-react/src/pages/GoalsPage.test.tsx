import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { GoalsPage } from './GoalsPage';
import {
  CapabilitiesSummary,
  GoalCreateInput,
  GoalRecord,
  PlatformApiClient,
  PlatformApiError,
} from '../services/platformApi';

function makeApi(overrides: Partial<PlatformApiClient> = {}): PlatformApiClient {
  return {
    getCapabilities: jest.fn(async (): Promise<CapabilitiesSummary> => ({ mounted: false, capabilities: {} })),
    listGoals: jest.fn(async () => []),
    createGoal: jest.fn(),
    getGoal: jest.fn(),
    listAlertRules: jest.fn(async () => []),
    createAlertRule: jest.fn(),
    deleteAlertRule: jest.fn(),
    listNotifications: jest.fn(async () => ({ unread_count: 0, notifications: [] })),
    markNotificationRead: jest.fn(),
    getObservability: jest.fn(),
    listFlags: jest.fn(async () => []),
    toggleFlag: jest.fn(),
    getPreflight: jest.fn(),
    ...overrides,
  };
}

describe('GoalsPage', () => {
  test('shows loading state before goals resolve and empty state when none exist', async () => {
    let resolveGoals!: (value: GoalRecord[]) => void;
    const api = makeApi({
      listGoals: jest.fn(
        () =>
          new Promise<GoalRecord[]>((resolve) => {
            resolveGoals = resolve;
          })
      ),
    });

    render(<GoalsPage api={api} />);
    expect(screen.getByTestId('goals-loading')).toBeInTheDocument();
    expect(screen.getByTestId('goals-capability-banner')).toHaveTextContent('EDUCATIONAL');

    resolveGoals([]);
    expect(await screen.findByTestId('goals-empty')).toBeInTheDocument();
  });

  test('renders error state on API failure and recovers on retry', async () => {
    const listGoals = jest
      .fn()
      .mockRejectedValueOnce(new PlatformApiError('Backend offline', 'API_UNAVAILABLE'))
      .mockResolvedValueOnce([]);
    const api = makeApi({ listGoals });

    render(<GoalsPage api={api} />);
    expect(await screen.findByTestId('goals-error')).toHaveTextContent('Backend offline');
    expect(screen.getByTestId('goals-capability-banner')).toHaveTextContent('Capability unavailable');

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByTestId('goals-empty')).toBeInTheDocument();
    expect(listGoals).toHaveBeenCalledTimes(2);
  });

  test('shows limited capability banner when capabilities.goals is false', async () => {
    const api = makeApi({
      getCapabilities: jest.fn(async () => ({
        mounted: true,
        capabilities: { goals: false },
      })),
    });

    render(<GoalsPage api={api} />);
    await screen.findByTestId('goals-empty');
    expect(screen.getByTestId('goals-capability-banner')).toHaveTextContent('Limited capability');
  });

  test('created goal persists across reload (unmount and remount against backend store)', async () => {
    const store: GoalRecord[] = [];
    const api = makeApi({
      listGoals: jest.fn(async () => [...store]),
      createGoal: jest.fn(async (input: GoalCreateInput): Promise<GoalRecord> => {
        const created: GoalRecord = {
          goal_id: `goal-${store.length + 1}`,
          title: input.title,
          target_amount: input.target_amount.toFixed(2),
          current_amount: input.current_amount.toFixed(2),
          horizon_years: input.horizon_years,
          monthly_contribution: input.monthly_contribution.toFixed(2),
          expected_annual_return_pct: input.expected_annual_return_pct.toFixed(1),
          projected_final_amount: '125000.00',
          shortfall_or_surplus: '25000.00',
          is_on_track: true,
          assumptions_statement: 'Deterministic model based on constant monthly compounding.',
          projections: [
            {
              year: 1,
              projected_balance: '16500.00',
              contributions_total: '16000.00',
              growth_total: '500.00',
            },
          ],
        };
        store.push(created);
        return created;
      }),
    });

    const { unmount } = render(<GoalsPage api={api} />);
    await screen.findByTestId('goals-empty');

    fireEvent.click(screen.getByRole('button', { name: 'Add New Goal' }));
    fireEvent.change(screen.getByLabelText('Goal Title'), { target: { value: 'Education Fund' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Goal' }));

    expect(await screen.findByText('Education Fund')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /View 1-Year Schedule/i }));
    expect(screen.getByText('$16,500.00')).toBeInTheDocument();

    unmount();
    render(<GoalsPage api={api} />);

    await waitFor(() => {
      expect(screen.getByText('Education Fund')).toBeInTheDocument();
    });
    expect(screen.getByText('On Track')).toBeInTheDocument();
  });
});
