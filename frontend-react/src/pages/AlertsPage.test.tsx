import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AlertsPage } from './AlertsPage';
import { clearActiveAuthSession, realAuthService } from '../services/authService';
import {
  AlertRule,
  AlertRuleCreateInput,
  NotificationItem,
  PlatformApiClient,
  PlatformApiError,
  setActiveLocalSessionToken,
} from '../services/platformApi';

function makeApi(overrides: Partial<PlatformApiClient> = {}): PlatformApiClient {
  return {
    getCapabilities: jest.fn(async () => ({ mounted: false, capabilities: {} })),
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

describe('AlertsPage', () => {
  test('shows loading then empty states when no notifications or rules exist', async () => {
    let resolveNotifs!: (v: { unread_count: number; notifications: NotificationItem[] }) => void;
    const api = makeApi({
      listNotifications: jest.fn(
        () =>
          new Promise((resolve) => {
            resolveNotifs = resolve;
          })
      ),
    });

    render(<AlertsPage api={api} />);
    expect(screen.getByTestId('alerts-loading')).toBeInTheDocument();
    expect(screen.getByTestId('alerts-capability-banner')).toHaveTextContent('ANALYTICAL');

    resolveNotifs({ unread_count: 0, notifications: [] });
    expect(await screen.findByTestId('alerts-notifications-empty')).toBeInTheDocument();
    expect(screen.getByTestId('alerts-rules-empty')).toBeInTheDocument();
  });

  test('shows error state and retries cleanly', async () => {
    const listNotifications = jest
      .fn()
      .mockRejectedValueOnce(new PlatformApiError('Auth required', 'AUTHENTICATION_REQUIRED', 401))
      .mockResolvedValueOnce({ unread_count: 0, notifications: [] });
    const api = makeApi({ listNotifications });

    render(<AlertsPage api={api} />);
    expect(await screen.findByTestId('alerts-error')).toHaveTextContent('Auth required');

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByTestId('alerts-notifications-empty')).toBeInTheDocument();
  });

  test('mark read and rule creation/deletion persist across reload', async () => {
    let notifications: NotificationItem[] = [
      {
        notification_id: 'n-1',
        rule_id: 'r-1',
        title: 'AAPL Threshold Hit',
        body: 'AAPL moved above 200',
        severity: 'INFO',
        created_at: '2026-11-26T10:00:00Z',
        is_read: false,
      },
    ];
    let rules: AlertRule[] = [
      {
        rule_id: 'r-1',
        rule_name: 'AAPL > 200',
        condition_type: 'PRICE_THRESHOLD',
        target_symbol_or_goal: 'AAPL',
        comparison_operator: 'GT',
        threshold_value: 200,
        cooldown_minutes: 60,
        is_active: true,
        created_at: '2026-11-26T09:00:00Z',
      },
    ];

    const api = makeApi({
      listNotifications: jest.fn(async () => ({
        unread_count: notifications.filter((n) => !n.is_read).length,
        notifications: notifications.map((n) => ({ ...n })),
      })),
      markNotificationRead: jest.fn(async (id: string) => {
        notifications = notifications.map((n) =>
          n.notification_id === id ? { ...n, is_read: true } : n
        );
        return notifications.find((n) => n.notification_id === id)!;
      }),
      listAlertRules: jest.fn(async () => rules.map((r) => ({ ...r }))),
      createAlertRule: jest.fn(async (input: AlertRuleCreateInput) => {
        const created: AlertRule = {
          rule_id: `r-${rules.length + 1}`,
          ...input,
          is_active: true,
          created_at: '2026-11-26T10:05:00Z',
        };
        rules = [...rules, created];
        return created;
      }),
      deleteAlertRule: jest.fn(async (id: string) => {
        rules = rules.filter((r) => r.rule_id !== id);
        return { rule_id: id, deleted: true };
      }),
    });

    const { unmount } = render(<AlertsPage api={api} />);
    await screen.findByText('AAPL Threshold Hit');
    expect(screen.getByTestId('alerts-unread-count')).toHaveTextContent('1 unread');

    fireEvent.click(screen.getByRole('button', { name: 'Mark All as Read' }));
    await waitFor(() => {
      expect(screen.getByTestId('alerts-unread-count')).toHaveTextContent('0 unread');
    });

    fireEvent.click(screen.getByRole('button', { name: /New Alert Rule/i }));
    fireEvent.change(screen.getByLabelText('Rule Name'), { target: { value: 'NVDA Drop' } });
    fireEvent.change(screen.getByLabelText('Target Symbol or Goal'), { target: { value: 'NVDA' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Alert Rule' }));

    expect(await screen.findByText('NVDA Drop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete rule AAPL > 200' }));
    await waitFor(() => {
      expect(screen.queryByText('AAPL > 200')).not.toBeInTheDocument();
    });

    unmount();
    render(<AlertsPage api={api} />);

    expect(await screen.findByText('NVDA Drop')).toBeInTheDocument();
    expect(screen.getByTestId('alerts-unread-count')).toHaveTextContent('0 unread');
    expect(screen.queryByText('AAPL > 200')).not.toBeInTheDocument();
  });

  describe('default platformApi path with authenticated session', () => {
    const originalFetch = globalThis.fetch;

    afterEach(() => {
      globalThis.fetch = originalFetch;
      clearActiveAuthSession();
      setActiveLocalSessionToken(null);
    });

    test('default AlertsPage sends Authorization Bearer header on notifications and rules requests', async () => {
      const fetchMock = jest.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
        const target = String(url);
        if (target.endsWith('/api/v1/auth/login')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              success: true,
              data: { access_token: 'alerts.jwt.token', refresh_token: 'alerts.refresh.token', token_type: 'bearer' },
            }),
          } as Response;
        }
        if (target.endsWith('/api/v1/capabilities')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ success: true, data: { capabilities: { alerts: true } } }),
          } as Response;
        }
        if (target.endsWith('/api/v1/alerts/notifications')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ success: true, data: { unread_count: 0, notifications: [] } }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ success: true, data: [] }),
        } as Response;
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      await realAuthService.login('nilisha@finex.app', 'Password123!');
      render(<AlertsPage />);

      expect(await screen.findByTestId('alerts-notifications-empty')).toBeInTheDocument();
      const notifCall = fetchMock.mock.calls.find(([url]) =>
        String(url).endsWith('/api/v1/alerts/notifications')
      );
      const rulesCall = fetchMock.mock.calls.find(([url]) =>
        String(url).endsWith('/api/v1/alerts/rules')
      );
      expect((notifCall?.[1] as RequestInit).headers).toEqual(
        expect.objectContaining({ Authorization: 'Bearer alerts.jwt.token' })
      );
      expect((rulesCall?.[1] as RequestInit).headers).toEqual(
        expect.objectContaining({ Authorization: 'Bearer alerts.jwt.token' })
      );
    });
  });
});
