import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Info,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  PortfolioAnalytics,
  PortfolioApi,
  PortfolioApiError,
} from '../services/portfolioApi';

export interface PortfolioAnalyticsPanelProps {
  portfolioId: string | null;
  portfolioName?: string;
  currency?: string;
  api: PortfolioApi;
  initialBenchmark?: string;
  initialConfidenceLevel?: 0.95 | 0.99;
  initialTopN?: number;
  refreshTrigger?: unknown;
  /** Set when parent owns the authoritative error alert (e.g. local valuation failure). */
  hasParentValuationError?: boolean;
}

function formatMoney(value: number | null, currency: string): string {
  if (value === null || !Number.isFinite(value)) {
    return 'Unavailable';
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency || 'USD'} ${value.toFixed(2)}`;
  }
}

function formatPercent(ratio: number | null, decimals = 2): string {
  if (ratio === null || !Number.isFinite(ratio)) {
    return 'Unavailable';
  }
  return `${(ratio * 100).toFixed(decimals)}%`;
}

function formatRatio(value: number | null, decimals = 4): string {
  if (value === null || !Number.isFinite(value)) {
    return 'Unavailable';
  }
  return value.toFixed(decimals);
}

function describeHhi(hhi: number | null): string {
  if (hhi === null || !Number.isFinite(hhi)) {
    return 'Unavailable';
  }
  if (hhi < 0.15) {
    return 'Low concentration (diversified)';
  }
  if (hhi < 0.25) {
    return 'Moderate concentration';
  }
  return 'High concentration';
}

export const PortfolioAnalyticsPanel: React.FC<PortfolioAnalyticsPanelProps> = ({
  portfolioId,
  portfolioName,
  currency = 'USD',
  api,
  initialBenchmark = 'SPY',
  initialConfidenceLevel = 0.95,
  initialTopN = 5,
  refreshTrigger,
  hasParentValuationError = false,
}) => {
  const benchmarkInputId = useId();
  const confidenceSelectId = useId();
  const topNSelectId = useId();

  const [benchmarkInput, setBenchmarkInput] = useState(initialBenchmark);
  const [appliedBenchmark, setAppliedBenchmark] = useState(initialBenchmark);
  const [confidenceLevel, setConfidenceLevel] = useState<0.95 | 0.99>(initialConfidenceLevel);
  const [topN, setTopN] = useState<number>(initialTopN);

  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const epochRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadAnalytics = useCallback(
    async (signal?: AbortSignal) => {
      if (!portfolioId) {
        setAnalytics(null);
        setError(null);
        setLoading(false);
        return;
      }

      if (hasParentValuationError && api.mode === 'local') {
        setAnalytics(null);
        setError(null);
        setLoading(false);
        return;
      }

      const epoch = ++epochRef.current;
      setLoading(true);
      setError(null);

      try {
        const result = await api.getAnalytics(
          portfolioId,
          {
            benchmark: appliedBenchmark,
            topN,
            confidenceLevel,
          },
          signal,
        );
        if (!mountedRef.current || signal?.aborted || epoch !== epochRef.current) {
          return;
        }
        setAnalytics(result);
        setError(null);
      } catch (err) {
        if (!mountedRef.current || signal?.aborted || epoch !== epochRef.current) {
          return;
        }
        if (err instanceof PortfolioApiError && err.code === 'REQUEST_CANCELLED') {
          return;
        }
        setAnalytics(null);
        setError(
          err instanceof Error ? err.message : 'Unable to load portfolio analytics right now.',
        );
      } finally {
        if (mountedRef.current && epoch === epochRef.current) {
          setLoading(false);
        }
      }
    },
    [api, appliedBenchmark, confidenceLevel, hasParentValuationError, portfolioId, topN],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadAnalytics(controller.signal);
    return () => controller.abort();
  }, [loadAnalytics, refreshTrigger]);

  const chartData = useMemo(
    () =>
      (analytics?.top_holdings ?? []).map((row) => ({
        symbol: row.symbol,
        weightPct:
          row.weight !== null && Number.isFinite(row.weight)
            ? Number((row.weight * 100).toFixed(2))
            : 0,
        hasWeight: row.weight !== null && Number.isFinite(row.weight),
        currentValue: row.current_value,
      })),
    [analytics],
  );

  const handleBenchmarkSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = benchmarkInput.trim().toUpperCase();
    if (!cleaned) {
      setError('Enter a valid benchmark symbol (e.g. SPY).');
      return;
    }
    if (cleaned === appliedBenchmark) {
      void loadAnalytics();
      return;
    }
    setAppliedBenchmark(cleaned);
  };

  if (!portfolioId) {
    return (
      <section
        className="local-s2-section"
        aria-label="Portfolio analytics"
        data-testid="portfolio-analytics-empty"
      >
        <p className="local-eyebrow">ANALYTICAL · PORTFOLIO INTELLIGENCE</p>
        <h3>Portfolio analytics</h3>
        <p className="local-help">
          Select a portfolio to inspect concentration, return, volatility, Sharpe, beta, and
          Value at Risk metrics.
        </p>
      </section>
    );
  }

  return (
    <section
      className="local-s2-section"
      aria-label="Portfolio analytics"
      data-testid="portfolio-analytics-panel"
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '16px',
        }}
      >
        <div>
          <p className="local-eyebrow">ANALYTICAL · PORTFOLIO INTELLIGENCE</p>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 size={18} aria-hidden="true" />
            Portfolio analytics{portfolioName ? ` · ${portfolioName}` : ''}
          </h3>
          <p className="local-help" style={{ marginTop: '4px' }}>
            Educational analytical metrics only — never personalized investment advice or a live
            brokerage appraisal.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span className="badge badge-info" data-testid="analytics-backend-badge">
            {api.mode === 'postgres' ? 'PostgreSQL Analytics' : 'Local SQLite Snapshot'}
          </span>
          {analytics && (
            <span
              className={
                analytics.status === 'COMPLETE' ? 'badge badge-success' : 'badge badge-warning'
              }
              data-testid="analytics-status-badge"
            >
              {analytics.status}
            </span>
          )}
        </div>
      </div>

      {api.supportsHistoricalAnalytics && (
        <form
          onSubmit={handleBenchmarkSubmit}
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'flex-end',
            gap: '12px',
            marginBottom: '18px',
          }}
        >
          <div className="local-field" style={{ marginBottom: 0, minWidth: '140px' }}>
            <label htmlFor={benchmarkInputId}>Benchmark</label>
            <input
              id={benchmarkInputId}
              type="text"
              value={benchmarkInput}
              maxLength={20}
              onChange={(e) => setBenchmarkInput(e.target.value)}
              placeholder="SPY"
            />
          </div>

          <div className="local-field" style={{ marginBottom: 0, minWidth: '140px' }}>
            <label htmlFor={confidenceSelectId}>VaR confidence</label>
            <select
              id={confidenceSelectId}
              value={String(confidenceLevel)}
              onChange={(e) => setConfidenceLevel(e.target.value === '0.99' ? 0.99 : 0.95)}
            >
              <option value="0.95">95% (1-day)</option>
              <option value="0.99">99% (1-day)</option>
            </select>
          </div>

          <div className="local-field" style={{ marginBottom: 0, minWidth: '120px' }}>
            <label htmlFor={topNSelectId}>Top holdings</label>
            <select
              id={topNSelectId}
              value={String(topN)}
              onChange={(e) => setTopN(Number(e.target.value) || 5)}
            >
              <option value="3">Top 3</option>
              <option value="5">Top 5</option>
              <option value="10">Top 10</option>
            </select>
          </div>

          <button type="submit" className="btn-secondary" disabled={loading}>
            <RefreshCw size={14} aria-hidden="true" />
            {loading ? 'Calculating…' : 'Refresh analytics'}
          </button>
        </form>
      )}

      {loading && (
        <div
          className="local-notice"
          role="status"
          aria-busy="true"
          data-testid="analytics-loading"
        >
          Loading portfolio analytics…
        </div>
      )}

      {!loading && error && (
        <div
          className="local-error"
          role={hasParentValuationError ? 'status' : 'alert'}
          data-testid="analytics-error"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} aria-hidden="true" />
            {error}
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void loadAnalytics();
            }}
          >
            <RefreshCw size={14} aria-hidden="true" /> Retry analytics
          </button>
        </div>
      )}

      {!loading && !error && hasParentValuationError && api.mode === 'local' && (
        <p className="local-help" data-testid="analytics-awaiting-valuation">
          Portfolio analytics wait for a confirmed backend valuation snapshot.
        </p>
      )}

      {!loading && !error && analytics && (
        <div data-testid="analytics-content">
          {analytics.status === 'INSUFFICIENT_DATA' && (
            <div
              className="local-notice"
              data-testid="analytics-insufficient-data"
              style={{ marginBottom: '18px' }}
            >
              <p style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700 }}>
                <Info size={16} aria-hidden="true" />
                Historical performance and VaR metrics are unavailable ({analytics.dataStatus})
              </p>
              <p className="local-help" style={{ marginTop: '6px' }}>
                Snapshot concentration (HHI and top holdings) remains available below when current
                values are confirmed. History-dependent metrics stay explicitly unavailable instead
                of being fabricated.
              </p>
            </div>
          )}

          <p className="local-help" data-testid="analytics-provenance">
            Source: {analytics.sourceLabel} · Status: {analytics.dataStatus} · Observations:{' '}
            {analytics.observation_count} · Benchmark: {analytics.benchmark_symbol}
            {analytics.dataAsOf ? ` · As of ${analytics.dataAsOf}` : ''}
          </p>

          <dl className="local-s2-grid" style={{ marginTop: '16px' }}>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Current value ({currency})</dt>
              <dd data-testid="analytics-current-value">
                {formatMoney(analytics.current_value, currency)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Concentration (HHI)</dt>
              <dd data-testid="analytics-hhi">
                {formatRatio(analytics.hhi, 6)}{' '}
                <span className="local-help" style={{ fontWeight: 500 }}>
                  ({describeHhi(analytics.hhi)})
                </span>
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Cumulative return</dt>
              <dd data-testid="analytics-cumulative-return">
                {formatPercent(analytics.returns.cumulative)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Annualized return</dt>
              <dd data-testid="analytics-annualized-return">
                {formatPercent(analytics.returns.annualized)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Daily mean return</dt>
              <dd data-testid="analytics-daily-mean">
                {formatPercent(analytics.returns.daily_mean, 4)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Annualized volatility</dt>
              <dd data-testid="analytics-volatility">
                {formatPercent(analytics.annualized_volatility)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Sharpe ratio</dt>
              <dd data-testid="analytics-sharpe">{formatRatio(analytics.sharpe_ratio, 4)}</dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>Beta vs {analytics.benchmark_symbol}</dt>
              <dd data-testid="analytics-beta">{formatRatio(analytics.beta, 4)}</dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>
                Historical VaR ({Math.round(analytics.value_at_risk.confidence_level * 100)}%,{' '}
                {analytics.value_at_risk.horizon_days}d)
              </dt>
              <dd data-testid="analytics-historical-var">
                {formatMoney(analytics.value_at_risk.historical, currency)}
              </dd>
            </div>
            <div className="local-s2-row" style={{ margin: 0 }}>
              <dt>
                Parametric VaR ({Math.round(analytics.value_at_risk.confidence_level * 100)}%,{' '}
                {analytics.value_at_risk.horizon_days}d)
              </dt>
              <dd data-testid="analytics-parametric-var">
                {formatMoney(analytics.value_at_risk.parametric, currency)}
              </dd>
            </div>
          </dl>

          <p className="local-help" data-testid="analytics-risk-free-rate">
            <ShieldCheck
              size={14}
              aria-hidden="true"
              style={{ verticalAlign: 'text-bottom', marginRight: '6px' }}
            />
            Risk-free rate:{' '}
            {analytics.risk_free_rate.annual_rate === null
              ? 'Not used in local snapshot'
              : formatPercent(analytics.risk_free_rate.annual_rate)}{' '}
            · Source: {analytics.risk_free_rate.source} · As of: {analytics.risk_free_rate.as_of}
          </p>

          <div className="local-s2-section" style={{ marginTop: '20px', paddingTop: '20px' }}>
            <h4>Top holdings concentration</h4>
            {analytics.top_holdings.length === 0 ? (
              <p className="local-help" data-testid="analytics-top-holdings-empty">
                No holdings available to rank for this portfolio.
              </p>
            ) : (
              <>
                {chartData.some((d) => d.hasWeight) && (
                  <div
                    style={{ width: '100%', height: 220, marginTop: '12px', marginBottom: '12px' }}
                    data-testid="analytics-weights-chart"
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="symbol" />
                        <YAxis unit="%" domain={[0, 100]} />
                        <Tooltip
                          formatter={(value: unknown) => [
                            `${Number(value ?? 0).toFixed(2)}%`,
                            'Portfolio weight',
                          ]}
                        />
                        <Bar dataKey="weightPct" name="Weight (%)" fill="#7564DC" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                <div style={{ overflowX: 'auto' }}>
                  <table
                    aria-label="Top holdings concentration"
                    style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}
                  >
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-surface-divider)' }}>
                        <th style={{ padding: '8px 10px' }}>Symbol</th>
                        <th style={{ padding: '8px 10px' }}>Current value ({currency})</th>
                        <th style={{ padding: '8px 10px' }}>Weight</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.top_holdings.map((row) => (
                        <tr
                          key={row.symbol}
                          style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                        >
                          <td style={{ padding: '8px 10px', fontWeight: 700 }}>{row.symbol}</td>
                          <td style={{ padding: '8px 10px' }}>
                            {formatMoney(row.current_value, currency)}
                          </td>
                          <td style={{ padding: '8px 10px' }}>{formatPercent(row.weight)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          {analytics.limitations.length > 0 && (
            <details style={{ marginTop: '14px' }}>
              <summary>Analytics assumptions and limitations</summary>
              <ul>
                {analytics.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
};

export default PortfolioAnalyticsPanel;
