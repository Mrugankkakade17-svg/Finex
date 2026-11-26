import React, { useCallback, useEffect, useState } from 'react';
import { Calendar, Plus, RefreshCw, Sparkles, Target, TrendingUp } from 'lucide-react';
import {
  CapabilityBanner,
  CapabilityStatus,
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components';
import {
  CapabilitiesSummary,
  GoalCreateInput,
  GoalRecord,
  PlatformApiClient,
  PlatformApiError,
  platformApi,
} from '../services/platformApi';

export interface GoalsPageProps {
  api?: PlatformApiClient;
}

function toNumber(value: string | number): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatUsd(value: string | number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(toNumber(value));
}

const DEFAULT_FORM = {
  title: '',
  target_amount: '100000',
  current_amount: '10000',
  horizon_years: '10',
  monthly_contribution: '500',
  expected_annual_return_pct: '6.0',
};

export const GoalsPage: React.FC<GoalsPageProps> = ({ api = platformApi }) => {
  const [goals, setGoals] = useState<GoalRecord[] | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilitiesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<{ message: string; code?: string } | null>(null);
  const [expandedGoalId, setExpandedGoalId] = useState<string | null>(null);

  const loadGoals = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [caps, list] = await Promise.all([
          api.getCapabilities(signal),
          api.listGoals(signal),
        ]);
        if (signal?.aborted) return;
        setCapabilities(caps);
        setGoals(list);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof PlatformApiError && err.code === 'REQUEST_CANCELLED') return;
        setError({
          message: err instanceof Error ? err.message : 'Unable to load financial goals.',
          code: err instanceof PlatformApiError ? err.code : undefined,
        });
        setGoals(null);
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
    void loadGoals(controller.signal);
    return () => controller.abort();
  }, [loadGoals]);

  const capabilityLimited =
    capabilities?.mounted === true && capabilities.capabilities.goals === false;
  const bannerStatus: CapabilityStatus = error
    ? 'UNAVAILABLE'
    : capabilityLimited
      ? 'LIMITED'
      : 'AVAILABLE';

  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    const title = form.title.trim();
    const targetAmount = Number(form.target_amount);
    const currentAmount = Number(form.current_amount);
    const horizonYears = Number(form.horizon_years);
    const monthlyContribution = Number(form.monthly_contribution);
    const annualReturn = Number(form.expected_annual_return_pct);

    if (!title) {
      setSubmitError({ message: 'Enter a goal title.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isFinite(targetAmount) || targetAmount <= 0) {
      setSubmitError({ message: 'Target amount must be greater than zero.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isFinite(currentAmount) || currentAmount < 0) {
      setSubmitError({ message: 'Current amount cannot be negative.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isInteger(horizonYears) || horizonYears < 1 || horizonYears > 50) {
      setSubmitError({
        message: 'Horizon must be a whole number between 1 and 50 years.',
        code: 'VALIDATION_ERROR',
      });
      return;
    }
    if (!Number.isFinite(monthlyContribution) || monthlyContribution < 0) {
      setSubmitError({ message: 'Monthly contribution cannot be negative.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isFinite(annualReturn) || annualReturn < 0 || annualReturn > 30) {
      setSubmitError({
        message: 'Expected annual return must be between 0% and 30%.',
        code: 'VALIDATION_ERROR',
      });
      return;
    }

    const payload: GoalCreateInput = {
      title,
      target_amount: targetAmount,
      current_amount: currentAmount,
      horizon_years: horizonYears,
      monthly_contribution: monthlyContribution,
      expected_annual_return_pct: annualReturn,
    };

    setSubmitting(true);
    try {
      const created = await api.createGoal(payload);
      setGoals((prev) => (prev ? [...prev, created] : [created]));
      setForm(DEFAULT_FORM);
      setShowCreateForm(false);
    } catch (err) {
      setSubmitError({
        message: err instanceof Error ? err.message : 'Unable to save goal right now.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="fx-page-header" style={{ marginBottom: '24px' }}>
        <div>
          <p className="local-eyebrow">FOR YOUR GOALS</p>
          <h2 style={{ fontSize: '2rem', color: 'var(--color-text)' }}>
            Save in your own rhythm
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Deterministic projection scenarios and milestone tracking persisted on the backend
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadGoals()}
            disabled={loading}
            style={{ fontSize: '0.88rem' }}
          >
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setSubmitError(null);
              setShowCreateForm((prev) => !prev);
            }}
            style={{ fontSize: '0.92rem' }}
          >
            <Plus size={16} aria-hidden="true" />
            {showCreateForm ? 'Cancel' : 'Add New Goal'}
          </button>
        </div>
      </div>

      <CapabilityBanner
        kind="EDUCATIONAL"
        featureName="Goal Planning & Deterministic Projections"
        status={bannerStatus}
        summary={
          error
            ? 'Goal endpoints could not confirm saved data. Retry to reconnect.'
            : capabilityLimited
              ? 'Uses deterministic monthly compounding with no guaranteed returns. Full-sprint capability flag is pending acceptance.'
              : 'Uses deterministic monthly compounding based on your inputs. Educational projections do not guarantee future returns.'
        }
        sourceNote={capabilities?.mounted ? 'Capabilities checked' : undefined}
        testId="goals-capability-banner"
      />

      {showCreateForm && (
        <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', marginBottom: '16px' }}>
            Create Financial Goal
          </h3>
          {submitError && (
            <div style={{ marginBottom: '16px' }}>
              <ErrorState
                title="Could not save goal"
                message={submitError.message}
                errorCode={submitError.code}
                testId="goals-submit-error"
              />
            </div>
          )}
          <form onSubmit={handleCreateGoal} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="fx-form-grid">
              <div>
                <label htmlFor="goal-title" className="fx-label">
                  Goal Title
                </label>
                <input
                  id="goal-title"
                  type="text"
                  className="fx-input"
                  placeholder="e.g. Retirement Fund"
                  maxLength={100}
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label htmlFor="goal-target" className="fx-label">
                  Target Amount (USD)
                </label>
                <input
                  id="goal-target"
                  type="number"
                  step="0.01"
                  min="1"
                  className="fx-input"
                  value={form.target_amount}
                  onChange={(e) => setForm((f) => ({ ...f, target_amount: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label htmlFor="goal-current" className="fx-label">
                  Current Amount (USD)
                </label>
                <input
                  id="goal-current"
                  type="number"
                  step="0.01"
                  min="0"
                  className="fx-input"
                  value={form.current_amount}
                  onChange={(e) => setForm((f) => ({ ...f, current_amount: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label htmlFor="goal-horizon" className="fx-label">
                  Horizon (Years)
                </label>
                <input
                  id="goal-horizon"
                  type="number"
                  min="1"
                  max="50"
                  step="1"
                  className="fx-input"
                  value={form.horizon_years}
                  onChange={(e) => setForm((f) => ({ ...f, horizon_years: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label htmlFor="goal-monthly" className="fx-label">
                  Monthly Contribution (USD)
                </label>
                <input
                  id="goal-monthly"
                  type="number"
                  step="0.01"
                  min="0"
                  className="fx-input"
                  value={form.monthly_contribution}
                  onChange={(e) => setForm((f) => ({ ...f, monthly_contribution: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label htmlFor="goal-return" className="fx-label">
                  Expected Annual Return (%)
                </label>
                <input
                  id="goal-return"
                  type="number"
                  step="0.1"
                  min="0"
                  max="30"
                  className="fx-input"
                  value={form.expected_annual_return_pct}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, expected_annual_return_pct: e.target.value }))
                  }
                  required
                />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowCreateForm(false)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={submitting}>
                <Sparkles size={15} aria-hidden="true" />
                {submitting ? 'Saving Goal…' : 'Save Goal'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <LoadingState
          title="Loading your financial goals…"
          message="Retrieving saved goals and deterministic projections from the backend."
          testId="goals-loading"
        />
      )}

      {!loading && error && (
        <ErrorState
          title="Failed to load financial goals"
          message={error.message}
          errorCode={error.code}
          onRetry={() => void loadGoals()}
          testId="goals-error"
        />
      )}

      {!loading && !error && goals && goals.length === 0 && (
        <EmptyState
          icon={<Target size={30} />}
          title="No financial goals saved yet"
          message="Create a financial goal to compute deterministic compounding projections and track your progress."
          actionLabel="+ Add New Goal"
          onAction={() => setShowCreateForm(true)}
          testId="goals-empty"
        />
      )}

      {!loading && !error && goals && goals.length > 0 && (
        <div
          data-testid="goals-list"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: '24px',
          }}
        >
          {goals.map((goal) => {
            const target = toNumber(goal.target_amount);
            const current = toNumber(goal.current_amount);
            const progressPct =
              target > 0 ? Math.min(100, Math.max(0, Math.round((current / target) * 100))) : 0;
            const surplus = toNumber(goal.shortfall_or_surplus);
            const isExpanded = expandedGoalId === goal.goal_id;

            return (
              <article
                key={goal.goal_id}
                className="glass-card"
                style={{ padding: '26px', borderRadius: '24px' }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '16px',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {goal.is_on_track ? (
                      <Target size={22} color="var(--status-success)" aria-hidden="true" />
                    ) : (
                      <TrendingUp size={22} color="var(--color-accent-violet)" aria-hidden="true" />
                    )}
                    <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)' }}>{goal.title}</h3>
                  </div>
                  <span className={`badge ${goal.is_on_track ? 'badge-success' : 'badge-warning'}`}>
                    {goal.is_on_track ? 'On Track' : 'Off Track'}
                  </span>
                </div>

                <div
                  style={{
                    fontSize: '1.55rem',
                    fontWeight: 700,
                    color: 'var(--color-text)',
                    marginBottom: '4px',
                  }}
                >
                  {formatUsd(goal.current_amount)} / {formatUsd(goal.target_amount)}
                </div>
                <div style={{ fontSize: '0.84rem', color: 'var(--color-text-muted)', marginBottom: '14px' }}>
                  Horizon: {goal.horizon_years} {goal.horizon_years === 1 ? 'year' : 'years'} · Expected return:{' '}
                  {toNumber(goal.expected_annual_return_pct).toFixed(1)}%
                </div>

                <div
                  role="progressbar"
                  aria-valuenow={progressPct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${goal.title} current funding progress`}
                  style={{
                    height: '10px',
                    background: '#E6EFEA',
                    borderRadius: '999px',
                    overflow: 'hidden',
                    marginBottom: '14px',
                  }}
                >
                  <div
                    style={{
                      width: `${progressPct}%`,
                      height: '100%',
                      borderRadius: '999px',
                      background: goal.is_on_track
                        ? 'linear-gradient(90deg, var(--color-accent-coral), #FF967D)'
                        : 'linear-gradient(90deg, var(--color-accent-violet), #9A8CF2)',
                    }}
                  />
                </div>

                <div
                  style={{
                    fontSize: '0.85rem',
                    color: 'var(--color-text-muted)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Calendar size={14} aria-hidden="true" />
                    Monthly Contribution: <strong>{formatUsd(goal.monthly_contribution)}</strong>
                  </div>
                  <div>
                    Projected Final Value: <strong>{formatUsd(goal.projected_final_amount)}</strong> (
                    {surplus >= 0
                      ? `Surplus ${formatUsd(surplus)}`
                      : `Shortfall ${formatUsd(Math.abs(surplus))}`}
                    )
                  </div>
                </div>

                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '12px' }}>
                  {goal.assumptions_statement}
                </p>

                {goal.projections.length > 0 && (
                  <div style={{ marginTop: '14px' }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                      onClick={() => setExpandedGoalId(isExpanded ? null : goal.goal_id)}
                    >
                      {isExpanded
                        ? 'Hide Yearly Projections'
                        : `View ${goal.projections.length}-Year Schedule`}
                    </button>
                    {isExpanded && (
                      <div style={{ marginTop: '12px', overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                          <thead>
                            <tr
                              style={{
                                color: 'var(--color-text-muted)',
                                textAlign: 'left',
                                borderBottom: '1px solid var(--color-surface-divider)',
                              }}
                            >
                              <th style={{ padding: '6px' }}>Year</th>
                              <th style={{ padding: '6px' }}>Balance</th>
                              <th style={{ padding: '6px' }}>Contributions</th>
                              <th style={{ padding: '6px' }}>Growth</th>
                            </tr>
                          </thead>
                          <tbody>
                            {goal.projections.map((row) => (
                              <tr
                                key={row.year}
                                style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                              >
                                <td style={{ padding: '6px' }}>{row.year}</td>
                                <td style={{ padding: '6px' }}>{formatUsd(row.projected_balance)}</td>
                                <td style={{ padding: '6px' }}>{formatUsd(row.contributions_total)}</td>
                                <td style={{ padding: '6px' }}>{formatUsd(row.growth_total)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};
