import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Flag, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  CapabilityBanner,
  CapabilityStatus,
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components';
import {
  CapabilitiesSummary,
  FeatureFlagStatus,
  PlatformApiClient,
  PlatformApiError,
  ReleasePreflightCheck,
  SystemObservabilityReport,
  platformApi,
} from '../services/platformApi';

export interface OpsPageProps {
  api?: PlatformApiClient;
}

export const OpsPage: React.FC<OpsPageProps> = ({ api = platformApi }) => {
  const [capabilities, setCapabilities] = useState<CapabilitiesSummary | null>(null);
  const [observability, setObservability] = useState<SystemObservabilityReport | null>(null);
  const [flags, setFlags] = useState<FeatureFlagStatus[] | null>(null);
  const [preflight, setPreflight] = useState<ReleasePreflightCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [toggleError, setToggleError] = useState<{ message: string; code?: string } | null>(null);
  const [togglingKey, setTogglingKey] = useState<string | null>(null);

  const loadOps = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      setToggleError(null);
      try {
        const [caps, obs, flagList, preflightCheck] = await Promise.all([
          api.getCapabilities(signal),
          api.getObservability(signal),
          api.listFlags(signal),
          api.getPreflight(signal),
        ]);
        if (signal?.aborted) return;
        setCapabilities(caps);
        setObservability(obs);
        setFlags(flagList);
        setPreflight(preflightCheck);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof PlatformApiError && err.code === 'REQUEST_CANCELLED') return;
        setError({
          message: err instanceof Error ? err.message : 'Unable to load operations telemetry.',
          code: err instanceof PlatformApiError ? err.code : undefined,
        });
        setObservability(null);
        setFlags(null);
        setPreflight(null);
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [api]
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadOps(controller.signal);
    return () => controller.abort();
  }, [loadOps]);

  const capabilityLimited =
    capabilities?.mounted === true &&
    (capabilities.capabilities.operations === false || capabilities.capabilities.ops === false);
  const bannerStatus: CapabilityStatus = error
    ? 'UNAVAILABLE'
    : capabilityLimited
      ? 'LIMITED'
      : 'AVAILABLE';

  const handleToggleFlag = async (flag: FeatureFlagStatus) => {
    setToggleError(null);
    setTogglingKey(flag.flag_key);
    try {
      const updated = await api.toggleFlag(flag.flag_key, !flag.enabled);
      setFlags((prev) =>
        prev ? prev.map((item) => (item.flag_key === flag.flag_key ? updated : item)) : prev
      );
    } catch (err) {
      setToggleError({
        message: err instanceof Error ? err.message : 'Failed to toggle feature flag.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setTogglingKey(null);
    }
  };

  const preflightItems = preflight
    ? [
        {
          label: 'Single-Headed Alembic Database Lineage',
          passed: preflight.migrations_single_headed,
        },
        {
          label: 'Secret Scan Clean — Zero Credentials in Git',
          passed: preflight.security_scan_clean,
        },
        {
          label: 'Deterministic AI Safety & Grounded Refusals',
          passed: preflight.ai_safety_eval_passed,
        },
        {
          label: `Accessibility Review (${preflight.accessibility_pass_rate_pct}%)`,
          passed: preflight.accessibility_pass_rate_pct >= 100,
        },
        {
          label: 'Stakeholder UAT Sign-off Confirmed',
          passed: preflight.anand_uat_approved,
        },
      ]
    : [];

  return (
    <div>
      <div className="fx-page-header" style={{ marginBottom: '24px' }}>
        <div>
          <p className="local-eyebrow">PLATFORM RELIABILITY</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Production Hardening &amp; Operations
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Release candidate preflight, observability, and circuit breaker controls
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {preflight && (
            <span className={`badge ${preflight.ready_for_promotion ? 'badge-success' : 'badge-warning'}`}>
              {preflight.release_tag}
            </span>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadOps()}
            disabled={loading}
            style={{ fontSize: '0.88rem' }}
          >
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </button>
        </div>
      </div>

      <CapabilityBanner
        kind="OPERATIONS"
        featureName="Operations & Emergency Kill Switches"
        status={bannerStatus}
        summary={
          error
            ? 'Operations telemetry could not be confirmed from the backend. Retry to reconnect.'
            : capabilityLimited
              ? 'Displays backend observability, preflight checks, and admin-gated emergency feature flags. Full-sprint capability flag is pending acceptance.'
              : 'Shows backend observability, preflight status, and emergency feature flags. Flag toggles require admin authorization.'
        }
        sourceNote={
          observability
            ? `Env: ${observability.environment} · P95: ${observability.error_rate_p95_ms} ms`
            : undefined
        }
        testId="ops-capability-banner"
      />

      {toggleError && (
        <div style={{ marginBottom: '20px' }}>
          <ErrorState
            title="Feature flag update rejected"
            message={toggleError.message}
            errorCode={toggleError.code}
            testId="ops-toggle-error"
          />
        </div>
      )}

      {loading && (
        <LoadingState
          title="Loading operations telemetry…"
          message="Fetching observability report, preflight status, and emergency feature flags."
          testId="ops-loading"
        />
      )}

      {!loading && error && (
        <ErrorState
          title="Failed to load operations telemetry"
          message={error.message}
          errorCode={error.code}
          onRetry={() => void loadOps()}
          testId="ops-error"
        />
      )}

      {!loading && !error && observability && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '24px',
            }}
          >
            <section className="glass-card" style={{ padding: '26px' }}>
              <h3
                style={{
                  fontSize: '1.25rem',
                  color: 'var(--color-text)',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
          gap: '8px',
          justifyContent: 'space-between',
          padding: '14px 16px',
          background: 'var(--color-surface-elevated)',
          border: '1px solid var(--color-surface-divider)',
          borderRadius: '14px',
                }}
              >
                <ShieldCheck size={20} color="var(--status-success)" aria-hidden="true" /> Preflight Release Gate
              </h3>
              {preflight ? (
                <>
                  <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {preflightItems.map((item) => (
                      <li
                        key={item.label}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          color: item.passed ? '#16654E' : 'var(--status-warning)',
                          fontWeight: 600,
                        }}
                      >
                        <span>{item.passed ? '✓' : '✗'}</span>
                        <span>{item.label}</span>
                      </li>
                    ))}
                  </ul>
                  <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '14px' }}>
                    Commit: {preflight.commit_sha} · Rollback SHA: {observability.rollback_target_sha}
                  </p>
                </>
              ) : (
                <EmptyState
                  title="No preflight report"
                  message="Preflight verification details are not available."
                  testId="ops-preflight-empty"
                />
              )}
            </section>

            <section className="glass-card" style={{ padding: '26px' }}>
              <h3
                style={{
                  fontSize: '1.25rem',
                  color: 'var(--color-text)',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <Flag size={20} color="var(--color-accent-violet)" aria-hidden="true" /> Emergency Feature Flags
              </h3>
              {!flags || flags.length === 0 ? (
                <EmptyState
                  icon={<Flag size={28} />}
                  title="No feature flags configured"
                  message="No emergency kill switches were returned by the backend."
                  testId="ops-flags-empty"
                />
              ) : (
                <div data-testid="ops-flags-list" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {flags.map((flag) => (
                    <div
                      key={flag.flag_key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '12px',
                        padding: '14px 16px',
                        background: '#F6FAF7',
                        border: '1px solid var(--color-surface-divider)',
                        borderRadius: '14px',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>{flag.flag_key}</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                          {flag.description}
                        </div>
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                          Owner: {flag.owner} · Fallback: {flag.safe_fallback}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleToggleFlag(flag)}
                        disabled={togglingKey === flag.flag_key}
                        aria-label={`Toggle ${flag.flag_key}`}
                        className={flag.enabled ? 'btn-primary' : 'btn-secondary'}
                        style={{ fontSize: '0.78rem', padding: '8px 16px', flexShrink: 0 }}
                      >
                        {togglingKey === flag.flag_key
                          ? 'Updating…'
                          : flag.enabled
                            ? 'ACTIVE'
                            : 'DISABLED'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="glass-card" style={{ padding: '26px' }}>
            <h3
              style={{
                fontSize: '1.25rem',
                color: 'var(--color-text)',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Activity size={20} color="var(--color-accent-violet)" aria-hidden="true" /> Dependency Health &amp; Telemetry
            </h3>
            {observability.dependencies.length === 0 ? (
              <EmptyState
                icon={<Activity size={28} />}
                title="No dependencies reported"
                message="The observability endpoint returned no dependency health entries."
                testId="ops-dependencies-empty"
              />
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '14px',
                }}
              >
                {observability.dependencies.map((dep) => (
                  <div
                    key={dep.name}
                    style={{
                      padding: '14px',
                      borderRadius: '14px',
                      background: '#F6FAF7',
                      border: '1px solid var(--color-surface-divider)',
                    }}
                  >
                    <div style={{ fontWeight: 700, color: 'var(--color-text)', marginBottom: '6px' }}>
                      {dep.name}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                      <span className={`badge ${dep.status === 'HEALTHY' ? 'badge-success' : 'badge-warning'}`}>
                        {dep.status}
                      </span>
                      <span style={{ color: 'var(--color-text-muted)' }}>{dep.latency_ms} ms</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
