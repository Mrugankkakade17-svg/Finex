import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { OpsPage } from './OpsPage';
import {
  FeatureFlagStatus,
  PlatformApiClient,
  PlatformApiError,
  ReleasePreflightCheck,
  SystemObservabilityReport,
} from '../services/platformApi';

function makeObservability(flags: FeatureFlagStatus[] = []): SystemObservabilityReport {
  return {
    environment: 'dev-local',
    app_version: 'v1.0.0-rc7',
    uptime_seconds: 120.5,
    healthy: true,
    active_feature_flags: flags,
    dependencies: [{ name: 'LakebasePostgres', status: 'HEALTHY', latency_ms: 4.2 }],
    error_rate_p95_ms: 18.4,
    rollback_target_sha: 'd1f821a8_w40_release',
  };
}

const PREFLIGHT: ReleasePreflightCheck = {
  release_tag: 'v1.0.0-rc7',
  commit_sha: '27ade62',
  migrations_single_headed: true,
  security_scan_clean: true,
  ai_safety_eval_passed: true,
  accessibility_pass_rate_pct: 100,
  anand_uat_approved: true,
  ready_for_promotion: true,
};

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
    getObservability: jest.fn(async () => makeObservability()),
    listFlags: jest.fn(async () => []),
    toggleFlag: jest.fn(),
    getPreflight: jest.fn(async () => PREFLIGHT),
    ...overrides,
  };
}

describe('OpsPage', () => {
  test('renders loading state then empty flags state when backend returns no flags', async () => {
    let resolveObs!: (v: SystemObservabilityReport) => void;
    const api = makeApi({
      getObservability: jest.fn(
        () =>
          new Promise<SystemObservabilityReport>((resolve) => {
            resolveObs = resolve;
          })
      ),
    });

    render(<OpsPage api={api} />);
    expect(screen.getByTestId('ops-loading')).toBeInTheDocument();
    expect(screen.getByTestId('ops-capability-banner')).toHaveTextContent('OPERATIONS');

    resolveObs(makeObservability([]));
    expect(await screen.findByTestId('ops-flags-empty')).toBeInTheDocument();
    expect(screen.getByText('LakebasePostgres')).toBeInTheDocument();
  });

  test('renders error state on failure and retries cleanly', async () => {
    const getObservability = jest
      .fn()
      .mockRejectedValueOnce(new PlatformApiError('Ops unavailable', 'API_UNAVAILABLE'))
      .mockResolvedValueOnce(makeObservability([]));
    const api = makeApi({ getObservability });

    render(<OpsPage api={api} />);
    expect(await screen.findByTestId('ops-error')).toHaveTextContent('Ops unavailable');

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByTestId('ops-flags-empty')).toBeInTheDocument();
  });

  test('flag toggle persists across reload and rejects 403 non-admin cleanly', async () => {
    let flags: FeatureFlagStatus[] = [
      {
        flag_key: 'FEATURE_AI_ASSISTANT',
        description: 'Enable Grounded AI Assistant',
        enabled: true,
        owner: 'P6-AI-QA',
        safe_fallback: 'Show static curriculum directory if disabled',
      },
    ];

    const api = makeApi({
      getObservability: jest.fn(async () => makeObservability(flags)),
      listFlags: jest.fn(async () => flags.map((f) => ({ ...f }))),
      toggleFlag: jest.fn(async (key: string, enabled: boolean) => {
        flags = flags.map((f) => (f.flag_key === key ? { ...f, enabled } : f));
        return flags.find((f) => f.flag_key === key)!;
      }),
    });

    const first = render(<OpsPage api={api} />);
    const toggleBtn = await screen.findByRole('button', { name: 'Toggle FEATURE_AI_ASSISTANT' });
    expect(toggleBtn).toHaveTextContent('ACTIVE');

    fireEvent.click(toggleBtn);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Toggle FEATURE_AI_ASSISTANT' })).toHaveTextContent(
        'DISABLED'
      );
    });

    first.unmount();
    const second = render(<OpsPage api={api} />);
    expect(
      await screen.findByRole('button', { name: 'Toggle FEATURE_AI_ASSISTANT' })
    ).toHaveTextContent('DISABLED');

    const forbiddenApi = makeApi({
      getObservability: jest.fn(async () => makeObservability(flags)),
      listFlags: jest.fn(async () => flags.map((f) => ({ ...f }))),
      toggleFlag: jest.fn(async () => {
        throw new PlatformApiError('Admin role required', 'FORBIDDEN', 403);
      }),
    });

    second.unmount();
    render(<OpsPage api={forbiddenApi} />);
    const btn = await screen.findByRole('button', { name: 'Toggle FEATURE_AI_ASSISTANT' });
    fireEvent.click(btn);
    expect(await screen.findByTestId('ops-toggle-error')).toHaveTextContent('Admin role required');
    expect(screen.getByRole('button', { name: 'Toggle FEATURE_AI_ASSISTANT' })).toHaveTextContent(
      'DISABLED'
    );
  });
});
