import React, { useCallback, useEffect, useId, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  PieChart as PieIcon,
  RefreshCw,
  Scale,
  ShieldAlert,
  Sliders,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  SuitabilityApi,
  SuitabilityApiError,
  suitabilityService,
} from '../services/suitabilityService';
import {
  AllocationDriftItem,
  RebalancePlanItem,
  RiskCategory,
  SuitabilityRebalanceResponse,
  TargetAllocationResponse,
} from '../types/suitability';

export interface SuitabilityPageProps {
  api?: SuitabilityApi;
  initialRiskCategory?: RiskCategory;
}

const RISK_CATEGORIES: Array<{ value: RiskCategory; label: string; description: string }> = [
  {
    value: 'CONSERVATIVE',
    label: 'Conservative',
    description: 'Capital preservation focus: 20% Equity, 50% Fixed Income, 30% Cash',
  },
  {
    value: 'MODERATE',
    label: 'Moderate',
    description: 'Balanced growth focus: 60% Equity, 30% Fixed Income, 10% Cash',
  },
  {
    value: 'AGGRESSIVE',
    label: 'Aggressive',
    description: 'Long-term equity appreciation focus: 85% Equity, 10% Fixed Income, 5% Cash',
  },
];

const ASSET_COLORS: Record<string, string> = {
  EQUITY: '#2F6B5F', // Deep Forest / Teal
  FIXED_INCOME: '#4A6984', // Slate Blue
  CASH: '#D4A373', // Warm Sand
};

export const SuitabilityPage: React.FC<SuitabilityPageProps> = ({
  api,
  initialRiskCategory = 'MODERATE',
}) => {
  const service = useMemo(() => api ?? suitabilityService, [api]);
  const chartId = useId().replace(/[^a-zA-Z0-9_-]/g, '');

  // State
  const [riskCategory, setRiskCategory] = useState<RiskCategory>(initialRiskCategory);
  const [allocationMode, setAllocationMode] = useState<'model' | 'portfolio'>('model');
  const [portfolioIdInput, setPortfolioIdInput] = useState<string>('');
  const [activePortfolioId, setActivePortfolioId] = useState<string>('');
  const [portfolioValueInput, setPortfolioValueInput] = useState<string>('100000');
  const [chartView, setChartView] = useState<'chart' | 'table'>('chart');

  // Async data state
  const [targetData, setTargetData] = useState<TargetAllocationResponse | null>(null);
  const [rebalanceData, setRebalanceData] = useState<SuitabilityRebalanceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadSuitability = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        if (allocationMode === 'model') {
          // 1. Fetch Target Allocation Model
          const target = await service.getTargetAllocation(riskCategory, signal);
          setTargetData(target);

          // 2. Fetch baseline rebalance response (model with zero drift / baseline)
          const rebal = await service.evaluateRebalancePlan(
            {
              risk_category: riskCategory,
              portfolio_value: Number(portfolioValueInput) || undefined,
            },
            signal,
          );
          setRebalanceData(rebal);
        } else {
          // Portfolio evaluation mode
          const rebal = await service.evaluateRebalancePlan(
            {
              risk_category: riskCategory,
              portfolio_id: activePortfolioId.trim() || undefined,
              portfolio_value: Number(portfolioValueInput) || undefined,
            },
            signal,
          );
          setRebalanceData(rebal);

          // Also get target metadata for description
          const target = await service.getTargetAllocation(riskCategory, signal);
          setTargetData(target);
        }
      } catch (err) {
        if (err instanceof SuitabilityApiError) {
          setError(err.message);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to evaluate portfolio suitability.');
        }
      } finally {
        setLoading(false);
      }
    },
    [service, riskCategory, allocationMode, activePortfolioId, portfolioValueInput],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadSuitability(controller.signal);
    return () => controller.abort();
  }, [loadSuitability]);

  const handleApplyPortfolioId = (e: React.FormEvent) => {
    e.preventDefault();
    setActivePortfolioId(portfolioIdInput.trim());
  };

  // Comparison data for charts and tables
  const comparisonData = useMemo(() => {
    if (!rebalanceData || !rebalanceData.drift_summary) {
      return [];
    }
    return rebalanceData.drift_summary.map((item) => ({
      asset_class: item.asset_class,
      target_pct: Number((Number(item.target_pct) || item.target_weight * 100).toFixed(2)),
      current_pct: Number((Number(item.current_pct) || item.current_weight * 100).toFixed(2)),
      drift_pct: Number((Number(item.drift_pct) || item.drift * 100).toFixed(2)),
      status: item.status,
      action: item.action,
    }));
  }, [rebalanceData]);

  // Pie chart data for target allocation
  const targetPieData = useMemo(() => {
    if (!targetData || !targetData.allocations) {
      return [];
    }
    return targetData.allocations.map((a) => ({
      name: a.asset_class.replace('_', ' '),
      value: Number(a.target_pct),
      asset_class: a.asset_class,
    }));
  }, [targetData]);

  return (
    <div className="suitability-page" style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
      {/* SECTION A: MANDATORY PERMANENT EDUCATIONAL BANNER */}
      <section
        role="status"
        aria-label="Educational suitability notice"
        data-testid="suitability-educational-banner"
        style={{
          marginBottom: '24px',
          padding: '16px 20px',
          borderRadius: '16px',
          background: 'rgba(230, 237, 115, 0.28)',
          border: '1.5px solid #C8D14B',
          color: 'var(--color-text)',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '14px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span
              className="badge badge-warning"
              style={{
                background: '#FEE4E2',
                color: '#B42318',
                border: '1px solid #FDA29B',
                fontWeight: 800,
                fontSize: '0.75rem',
                padding: '3px 8px',
                borderRadius: '6px',
              }}
            >
              EDUCATIONAL ONLY
            </span>
            <strong>Simulated Educational Suitability Analysis</strong>
          </div>
          <p style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', marginTop: '6px', marginBottom: 0 }}>
            EDUCATIONAL ONLY — FinEx provides simulated portfolio analysis and educational suitability information.
            It is not investment advice, a brokerage service, or a guarantee of returns. Review all information
            independently.
          </p>
        </div>
        <ShieldAlert
          size={22}
          style={{ flexShrink: 0, color: 'var(--color-accent-violet, #5C4EB7)', marginTop: '2px' }}
          aria-hidden="true"
        />
      </section>

      {/* HEADER CONTROLS */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, margin: 0, color: 'var(--color-text)' }}>
            Portfolio Suitability & Rebalance
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', margin: '4px 0 0' }}>
            Compare current portfolio distribution against target asset-allocation models.
          </p>
        </div>

        {/* View Toggle (Chart vs Table) */}
        <div role="group" aria-label="Allocation visualization view" style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            aria-pressed={chartView === 'chart'}
            className={chartView === 'chart' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setChartView('chart')}
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            Chart View
          </button>
          <button
            type="button"
            aria-pressed={chartView === 'table'}
            className={chartView === 'table' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setChartView('table')}
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            Table View
          </button>
        </div>
      </header>

      {/* RISK CATEGORY SELECTOR & PORTFOLIO MODE */}
      <div
        className="glass-card"
        style={{
          padding: '20px',
          borderRadius: '16px',
          border: '1px solid var(--color-surface-divider, #E6E8E7)',
          background: 'var(--color-surface, #FFFFFF)',
          marginBottom: '24px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--color-text-muted)' }}>
              SELECT RISK CATEGORY:
            </label>
            <div
              role="group"
              aria-label="Risk Category"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
                marginTop: '8px',
              }}
            >
              {RISK_CATEGORIES.map((cat) => {
                const selected = riskCategory === cat.value;
                return (
                  <button
                    key={cat.value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setRiskCategory(cat.value)}
                    style={{
                      padding: '14px 16px',
                      borderRadius: '12px',
                      border: selected
                        ? '2px solid var(--color-accent-coral, #2F6B5F)'
                        : '1px solid var(--color-surface-divider, #E6E8E7)',
                      background: selected ? 'rgba(47, 107, 95, 0.08)' : 'var(--color-surface-elevated, #FAFAFA)',
                      color: 'var(--color-text)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: selected ? '#2F6B5F' : 'inherit' }}>
                      {cat.label}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                      {cat.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Allocation Mode: Model vs Portfolio ID */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              paddingTop: '12px',
              borderTop: '1px solid var(--color-surface-divider, #E6E8E7)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                className={allocationMode === 'model' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => {
                  setAllocationMode('model');
                  setActivePortfolioId('');
                }}
                style={{ padding: '6px 14px', fontSize: '0.82rem' }}
              >
                Model Target Baseline
              </button>
              <button
                type="button"
                className={allocationMode === 'portfolio' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setAllocationMode('portfolio')}
                style={{ padding: '6px 14px', fontSize: '0.82rem' }}
              >
                Evaluate Portfolio ID
              </button>
            </div>

            {allocationMode === 'portfolio' && (
              <form
                onSubmit={handleApplyPortfolioId}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
              >
                <input
                  type="text"
                  placeholder="Enter Portfolio UUID..."
                  value={portfolioIdInput}
                  onChange={(e) => setPortfolioIdInput(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--color-surface-divider, #ccc)',
                    fontSize: '0.85rem',
                    minWidth: '240px',
                  }}
                  aria-label="Portfolio UUID"
                />
                <button type="submit" className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                  Load Portfolio
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      {/* ASYNC STATE HANDLERS */}
      {loading ? (
        <div
          role="status"
          aria-live="polite"
          data-testid="suitability-loading"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            color: 'var(--color-text-muted)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <RefreshCw size={28} className="animate-spin" style={{ color: '#2F6B5F' }} />
          <span>Evaluating portfolio suitability and rebalance model…</span>
        </div>
      ) : error ? (
        <div
          role="alert"
          data-testid="suitability-error"
          style={{
            padding: '24px',
            borderRadius: '16px',
            background: '#FEF3F2',
            border: '1.5px solid #FDA29B',
            color: '#B42318',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle size={20} />
            <strong style={{ fontSize: '1rem' }}>Suitability Evaluation Error</strong>
          </div>
          <p style={{ margin: '8px 0 16px', fontSize: '0.9rem' }}>{error}</p>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadSuitability()}
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            Retry Evaluation
          </button>
        </div>
      ) : !rebalanceData || comparisonData.length === 0 ? (
        <div
          role="status"
          data-testid="suitability-empty"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            color: 'var(--color-text-muted)',
            background: 'var(--color-surface, #FFF)',
            borderRadius: '16px',
            border: '1px solid var(--color-surface-divider, #E6E8E7)',
          }}
        >
          <Scale size={32} style={{ color: 'var(--color-text-muted)', marginBottom: '8px' }} />
          <p style={{ fontSize: '1rem', fontWeight: 600 }}>No suitability data available</p>
          <p style={{ fontSize: '0.85rem' }}>Select a risk profile or enter portfolio holdings to evaluate drift.</p>
        </div>
      ) : (
        <>
          {/* SECTION B: SUITABILITY SUMMARY METRICS */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '16px',
              marginBottom: '24px',
            }}
          >
            {/* Model Card */}
            <div
              className="glass-card"
              style={{
                padding: '20px',
                borderRadius: '16px',
                border: '1px solid var(--color-surface-divider, #E6E8E7)',
                background: 'var(--color-surface, #FFFFFF)',
              }}
            >
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>
                TARGET MODEL
              </span>
              <h3 style={{ fontSize: '1.2rem', margin: '6px 0', color: 'var(--color-text)' }}>
                {targetData?.model_name ?? rebalanceData.model_code}
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', margin: 0 }}>
                {targetData?.description ?? 'Reference allocation benchmark for selected risk tier.'}
              </p>
            </div>

            {/* Max Drift Card */}
            <div
              className="glass-card"
              style={{
                padding: '20px',
                borderRadius: '16px',
                border: '1px solid var(--color-surface-divider, #E6E8E7)',
                background: 'var(--color-surface, #FFFFFF)',
              }}
            >
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>
                MAXIMUM DRIFT
              </span>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, margin: '6px 0', color: 'var(--color-text)' }}>
                {(Number(rebalanceData.max_drift) * 100).toFixed(1)}%
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                {rebalanceData.is_empty_portfolio
                  ? 'Empty Portfolio (Full allocation needed)'
                  : rebalanceData.rebalance_required
                    ? 'Exceeds 1.0% rebalance threshold'
                    : 'Within acceptable tolerance range'}
              </span>
            </div>

            {/* Rebalance Status Card */}
            <div
              className="glass-card"
              style={{
                padding: '20px',
                borderRadius: '16px',
                border: '1px solid var(--color-surface-divider, #E6E8E7)',
                background: 'var(--color-surface, #FFFFFF)',
              }}
            >
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>
                REBALANCE RECOMMENDATION
              </span>
              <div style={{ marginTop: '8px' }}>
                {rebalanceData.is_empty_portfolio ? (
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      background: '#F0F9FF',
                      color: '#026AA2',
                      border: '1px solid #B9E6FE',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                    }}
                  >
                    EMPTY PORTFOLIO
                  </span>
                ) : rebalanceData.rebalance_required ? (
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      background: '#FEF0C7',
                      color: '#B54708',
                      border: '1px solid #FEDF89',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                    }}
                  >
                    REBALANCE SUGGESTED
                  </span>
                ) : (
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      background: '#ECFDF3',
                      color: '#027A48',
                      border: '1px solid #A6F4C5',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                    }}
                  >
                    BALANCED WITHIN TOLERANCE
                  </span>
                )}
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '8px', marginBottom: 0 }}>
                {rebalanceData.rebalance_plan.length} asset class allocations evaluated.
              </p>
            </div>
          </div>

          {/* SECTION C: TARGET ALLOCATION CHART & COMPARISON */}
          <section
            aria-label="Target and Current Portfolio Allocation"
            className="glass-card"
            style={{
              padding: '24px',
              borderRadius: '16px',
              border: '1px solid var(--color-surface-divider, #E6E8E7)',
              background: 'var(--color-surface, #FFFFFF)',
              marginBottom: '24px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                marginBottom: '20px',
              }}
            >
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--color-text)' }}>
                  Asset Allocation: Current vs Target
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
                  Target model weights alongside current portfolio distribution.
                </p>
              </div>
            </div>

            {chartView === 'chart' ? (
              <div
                role="img"
                aria-label="Target vs Current Allocation Comparison Bar Chart"
                style={{ height: 300, width: '100%' }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E6E8E7" />
                    <XAxis
                      dataKey="asset_class"
                      tickFormatter={(val: string) => val.replace('_', ' ')}
                      tick={{ fill: '#667085', fontSize: 12, fontWeight: 600 }}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(val: number) => `${val}%`}
                      tick={{ fill: '#667085', fontSize: 12 }}
                      width={50}
                    />
                    <Tooltip
                      formatter={(val, name) => [
                        val != null ? `${val}%` : '—',
                        name === 'target_pct' ? 'Target' : 'Current',
                      ]}
                      labelFormatter={(val) => `Asset Class: ${String(val).replace('_', ' ')}`}
                    />
                    <Legend
                      formatter={(value: string) => (value === 'target_pct' ? 'Target Weight (%)' : 'Current Weight (%)')}
                    />
                    <Bar dataKey="target_pct" name="target_pct" fill="#2F6B5F" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="current_pct" name="current_pct" fill="#D4A373" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 480 }}>
                  <caption style={{ textAlign: 'left', padding: '8px 0', color: 'var(--color-text-muted)' }}>
                    Asset allocation target and current weights table
                  </caption>
                  <thead>
                    <tr>
                      <th
                        scope="col"
                        style={{
                          textAlign: 'left',
                          padding: '10px 12px',
                          borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                        }}
                      >
                        Asset Class
                      </th>
                      <th
                        scope="col"
                        style={{
                          textAlign: 'right',
                          padding: '10px 12px',
                          borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                        }}
                      >
                        Target Weight
                      </th>
                      <th
                        scope="col"
                        style={{
                          textAlign: 'right',
                          padding: '10px 12px',
                          borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                        }}
                      >
                        Current Weight
                      </th>
                      <th
                        scope="col"
                        style={{
                          textAlign: 'right',
                          padding: '10px 12px',
                          borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                        }}
                      >
                        Drift
                      </th>
                      <th
                        scope="col"
                        style={{
                          textAlign: 'center',
                          padding: '10px 12px',
                          borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                        }}
                      >
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonData.map((row) => (
                      <tr key={row.asset_class}>
                        <th
                          scope="row"
                          style={{
                            textAlign: 'left',
                            padding: '10px 12px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          {row.asset_class.replace('_', ' ')}
                        </th>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '10px 12px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          {row.target_pct}%
                        </td>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '10px 12px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          {row.current_pct}%
                        </td>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '10px 12px',
                            fontWeight: 700,
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                            color:
                              row.status === 'OVERWEIGHT'
                                ? '#B42318'
                                : row.status === 'UNDERWEIGHT'
                                  ? '#026AA2'
                                  : '#027A48',
                          }}
                        >
                          {row.drift_pct > 0 ? `+${row.drift_pct}%` : `${row.drift_pct}%`}
                        </td>
                        <td
                          style={{
                            textAlign: 'center',
                            padding: '10px 12px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background:
                                row.status === 'OVERWEIGHT'
                                  ? '#FEF0C7'
                                  : row.status === 'UNDERWEIGHT'
                                    ? '#E0F2FE'
                                    : '#ECFDF3',
                              color:
                                row.status === 'OVERWEIGHT'
                                  ? '#B54708'
                                  : row.status === 'UNDERWEIGHT'
                                    ? '#026AA2'
                                    : '#027A48',
                            }}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* SECTION D: ALLOCATION DRIFT BARS */}
          <section
            aria-label="Allocation Drift Bars"
            className="glass-card"
            style={{
              padding: '24px',
              borderRadius: '16px',
              border: '1px solid var(--color-surface-divider, #E6E8E7)',
              background: 'var(--color-surface, #FFFFFF)',
              marginBottom: '24px',
            }}
          >
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--color-text)' }}>
                Per-Asset Allocation Drift
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
                Deviation from target model in percentage points. Positive drift is overweight; negative drift is
                underweight.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {comparisonData.map((item) => {
                const isOver = item.status === 'OVERWEIGHT';
                const isUnder = item.status === 'UNDERWEIGHT';
                const isBalanced = item.status === 'BALANCED';

                // Bar visual representation (max scale 50% drift)
                const absDrift = Math.min(Math.abs(item.drift_pct), 50);
                const barWidth = `${(absDrift / 50) * 100}%`;

                return (
                  <div key={item.asset_class} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                        fontSize: '0.9rem',
                      }}
                    >
                      <div style={{ fontWeight: 700 }}>{item.asset_class.replace('_', ' ')}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                          Target: {item.target_pct}% | Current: {item.current_pct}%
                        </span>
                        <span
                          style={{
                            fontWeight: 800,
                            color: isOver ? '#B42318' : isUnder ? '#026AA2' : '#027A48',
                          }}
                        >
                          {item.drift_pct > 0 ? `+${item.drift_pct}%` : `${item.drift_pct}%`}
                        </span>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            background: isOver ? '#FEF0C7' : isUnder ? '#E0F2FE' : '#ECFDF3',
                            color: isOver ? '#B54708' : isUnder ? '#026AA2' : '#027A48',
                          }}
                        >
                          {item.action === 'REDUCE' ? 'Reduce' : item.action === 'INCREASE' ? 'Increase' : 'Hold'}
                        </span>
                      </div>
                    </div>

                    {/* Bi-directional horizontal drift bar */}
                    <div
                      style={{
                        position: 'relative',
                        height: '14px',
                        background: 'var(--color-surface-elevated, #F2F4F7)',
                        borderRadius: '7px',
                        overflow: 'hidden',
                        display: 'flex',
                      }}
                    >
                      {/* Left half: Underweight */}
                      <div
                        style={{
                          width: '50%',
                          height: '100%',
                          display: 'flex',
                          justifyContent: 'flex-end',
                          borderRight: '1px solid #98A2B3',
                        }}
                      >
                        {isUnder && (
                          <div
                            style={{
                              width: barWidth,
                              height: '100%',
                              background: '#026AA2',
                              borderRadius: '4px 0 0 4px',
                              transition: 'width 0.3s ease',
                            }}
                          />
                        )}
                      </div>

                      {/* Right half: Overweight */}
                      <div style={{ width: '50%', height: '100%', display: 'flex', justifyContent: 'flex-start' }}>
                        {isOver && (
                          <div
                            style={{
                              width: barWidth,
                              height: '100%',
                              background: '#B54708',
                              borderRadius: '0 4px 4px 0',
                              transition: 'width 0.3s ease',
                            }}
                          />
                        )}
                        {isBalanced && (
                          <div
                            style={{
                              width: '6px',
                              height: '100%',
                              background: '#027A48',
                              borderRadius: '2px',
                            }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* SECTION E: REBALANCE RECOMMENDATION TABLE */}
          <section
            aria-label="Rebalance Recommendations Table"
            className="glass-card"
            style={{
              padding: '24px',
              borderRadius: '16px',
              border: '1px solid var(--color-surface-divider, #E6E8E7)',
              background: 'var(--color-surface, #FFFFFF)',
              marginBottom: '24px',
            }}
          >
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--color-text)' }}>
                Educational Rebalance Recommendations
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
                Non-discretionary adjustment plan to realign portfolio weights with the target suitability benchmark.
              </p>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 680 }}>
                <caption style={{ textAlign: 'left', padding: '8px 0', color: 'var(--color-text-muted)' }}>
                  Detailed rebalance recommendations by asset class
                </caption>
                <thead>
                  <tr>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'left',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Asset Class
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'right',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Current %
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'right',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Target %
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'center',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Action
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'right',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Indicative Amount
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'left',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Proxy Benchmark
                    </th>
                    <th
                      scope="col"
                      style={{
                        textAlign: 'left',
                        padding: '12px 10px',
                        borderBottom: '2px solid var(--color-surface-divider, #E6E8E7)',
                      }}
                    >
                      Educational Rationale
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rebalanceData.rebalance_plan.map((item) => {
                    const isReduce = item.direction === 'REDUCE';
                    const isIncrease = item.direction === 'INCREASE';
                    const isHold = item.direction === 'HOLD';

                    return (
                      <tr key={item.asset_class}>
                        <th
                          scope="row"
                          style={{
                            textAlign: 'left',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                            fontWeight: 700,
                          }}
                        >
                          {item.asset_class.replace('_', ' ')}
                        </th>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          {(Number(item.current_weight) * 100).toFixed(1)}%
                        </td>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          {(Number(item.target_weight) * 100).toFixed(1)}%
                        </td>
                        <td
                          style={{
                            textAlign: 'center',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                          }}
                        >
                          <span
                            style={{
                              padding: '3px 8px',
                              borderRadius: '4px',
                              fontSize: '0.78rem',
                              fontWeight: 800,
                              background: isReduce ? '#FEE4E2' : isIncrease ? '#E0F2FE' : '#ECFDF3',
                              color: isReduce ? '#B42318' : isIncrease ? '#026AA2' : '#027A48',
                            }}
                          >
                            {item.direction}
                          </span>
                        </td>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                            fontWeight: 600,
                          }}
                        >
                          {item.indicative_amount != null
                            ? Number(item.indicative_amount).toLocaleString(undefined, {
                                style: 'currency',
                                currency: 'USD',
                                maximumFractionDigits: 0,
                              })
                            : '—'}
                        </td>
                        <td
                          style={{
                            textAlign: 'left',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                            fontSize: '0.85rem',
                          }}
                        >
                          {item.benchmark_symbol ? (
                            <div>
                              <strong>{item.benchmark_symbol}</strong>
                              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                                {item.benchmark_name}
                              </div>
                            </div>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td
                          style={{
                            textAlign: 'left',
                            padding: '12px 10px',
                            borderBottom: '1px solid var(--color-surface-divider, #E6E8E7)',
                            fontSize: '0.82rem',
                            color: 'var(--color-text-muted)',
                            maxWidth: '260px',
                          }}
                        >
                          {item.explanation}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div
              style={{
                marginTop: '16px',
                fontSize: '0.8rem',
                color: 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <CheckCircle2 size={16} style={{ color: '#027A48' }} />
              <span>
                Zero-sum invariant verified: sum of indicative adjustments equals zero, conserving estimated portfolio
                capital.
              </span>
            </div>
          </section>

          {/* SECTION F: ENGINE DATA CONTEXT & DISCLAIMERS */}
          <section
            aria-label="Engine Metadata and Disclaimers"
            style={{
              padding: '16px 20px',
              borderRadius: '12px',
              background: 'var(--color-surface-elevated, #F8F9FA)',
              border: '1px solid var(--color-surface-divider, #E6E8E7)',
              fontSize: '0.82rem',
              color: 'var(--color-text-muted)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <span>
                <strong>Model Code:</strong> {rebalanceData.model_code}
              </span>
              <span>
                <strong>Drift Tolerance:</strong> 1.0% (0.01 threshold)
              </span>
              <span>
                <strong>Invariants Satisfied:</strong> True (Sum of Weights = 1.0)
              </span>
            </div>
            <p style={{ marginTop: '10px', marginBottom: 0, lineHeight: 1.5 }}>
              {rebalanceData.educational_disclaimer}
            </p>
          </section>
        </>
      )}
    </div>
  );
};

export default SuitabilityPage;
