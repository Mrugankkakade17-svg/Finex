import React, { useId, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface PriceBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceChartPoint {
  date: string;
  close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  kind: 'price' | 'gap' | 'closed';
}

export interface PriceChartProps {
  symbol: string;
  candles: PriceBar[];
  currency?: string;
  /** Exchange-calendar dates, formatted as YYYY-MM-DD. */
  closedDays?: string[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

function dateKey(value: string): string | null {
  const dateOnly = value.match(/^(\d{4}-\d{2}-\d{2})/);
  if (dateOnly) {
    const parsed = new Date(`${dateOnly[1]}T00:00:00.000Z`);
    return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== dateOnly[1]
      ? null
      : dateOnly[1];
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10);
}

function utcDate(date: string): Date {
  return new Date(`${date}T00:00:00.000Z`);
}

function nextDate(date: string): string {
  const value = utcDate(date);
  value.setUTCDate(value.getUTCDate() + 1);
  return value.toISOString().slice(0, 10);
}

function isWeekday(date: string): boolean {
  const weekday = utcDate(date).getUTCDay();
  return weekday !== 0 && weekday !== 6;
}

/**
 * Adds null chart points for missing weekdays and exchange-calendar closures.
 * These are display markers only: no candle or price is inferred for them.
 */
export function buildPriceChartPoints(
  candles: PriceBar[],
  closedDays: string[] = []
): PriceChartPoint[] {
  const byDate = new Map<string, PriceBar>();
  candles.forEach((candle) => {
    const date = dateKey(candle.timestamp);
    if (date && Number.isFinite(candle.close)) byDate.set(date, candle);
  });
  const closed = new Set(closedDays.map(dateKey).filter((date): date is string => date !== null));
  const observedDates = Array.from(byDate.keys()).sort();
  if (observedDates.length === 0) {
    return Array.from(closed)
      .sort()
      .map((date) => ({
        date,
        close: null,
        open: null,
        high: null,
        low: null,
        volume: null,
        kind: 'closed' as const,
      }));
  }

  const first = observedDates[0];
  const last = observedDates[observedDates.length - 1];
  const points: PriceChartPoint[] = [];
  for (let date = first; date <= last; date = nextDate(date)) {
    const candle = byDate.get(date);
    if (candle) {
      points.push({
        date,
        close: candle.close,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        volume: candle.volume,
        kind: 'price',
      });
    } else if (closed.has(date)) {
      points.push({
        date,
        close: null,
        open: null,
        high: null,
        low: null,
        volume: null,
        kind: 'closed',
      });
    } else if (isWeekday(date)) {
      points.push({
        date,
        close: null,
        open: null,
        high: null,
        low: null,
        volume: null,
        kind: 'gap',
      });
    }
  }
  return points;
}

function formatDate(date: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(
    utcDate(date)
  );
}

export const PriceChart: React.FC<PriceChartProps> = ({
  symbol,
  candles,
  currency = 'USD',
  closedDays = [],
  loading = false,
  error = null,
  onRetry,
}) => {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const points = useMemo(() => buildPriceChartPoints(candles, closedDays), [candles, closedDays]);
  const chartId = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const formatter = useMemo(
    () =>
      new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency,
        maximumFractionDigits: currency === 'INR' ? 2 : 4,
      }),
    [currency]
  );

  return (
    <section aria-label={`${symbol} price history`} className="glass-card" style={{ padding: 20 }}>
      <header
        style={{
          alignItems: 'center',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <div>
          <h3 style={{ color: 'var(--color-text)', fontSize: '1.1rem', margin: 0 }}>
            {symbol} price history
          </h3>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
            Historical prices are informational. Missing sessions are shown without an estimated price.
          </p>
        </div>
        <div aria-label="Price history display" role="group" style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            aria-pressed={view === 'chart'}
            onClick={() => setView('chart')}
            className={view === 'chart' ? 'btn-primary' : 'btn-secondary'}
          >
            Chart
          </button>
          <button
            type="button"
            aria-pressed={view === 'table'}
            onClick={() => setView('table')}
            className={view === 'table' ? 'btn-primary' : 'btn-secondary'}
          >
            Table
          </button>
        </div>
      </header>

      {loading ? (
        <p role="status" style={{ color: 'var(--color-text-muted)', padding: '32px 12px' }}>
          Loading price history…
        </p>
      ) : error ? (
        <div role="alert" style={{ color: '#B42318', padding: '20px 12px' }}>
          <p>{error}</p>
          {onRetry && (
            <button type="button" className="btn-secondary" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      ) : candles.length === 0 ? (
        <p role="status" style={{ color: 'var(--color-text-muted)', padding: '32px 12px' }}>
          No historical prices are available for {symbol}.
        </p>
      ) : view === 'chart' ? (
        <div aria-label={`${symbol} closing prices chart`} role="img" style={{ height: 300, width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
              <defs>
                <linearGradient id={`priceChartFill-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2F6B5F" stopOpacity={0.24} />
                  <stop offset="95%" stopColor="#2F6B5F" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E6E8E7" />
              <XAxis
                dataKey="date"
                minTickGap={28}
                tickFormatter={(value: string) =>
                  new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(
                    utcDate(value)
                  )
                }
                tick={{ fill: '#667085', fontSize: 12 }}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(value: number) => formatter.format(value)}
                tick={{ fill: '#667085', fontSize: 12 }}
                width={78}
              />
              <Tooltip
                labelFormatter={(value) => formatDate(String(value))}
                formatter={(value) => (value == null ? ['No observation', 'Price'] : [formatter.format(Number(value)), 'Close'])}
              />
              <Area
                type="monotone"
                dataKey="close"
                name="Close"
                stroke="#2F6B5F"
                strokeWidth={2}
                fill={`url(#priceChartFill-${chartId})`}
                connectNulls={false}
                isAnimationActive={false}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', minWidth: 560, width: '100%' }}>
            <caption style={{ color: 'var(--color-text-muted)', padding: 8, textAlign: 'left' }}>
              {symbol} daily OHLCV price history
            </caption>
            <thead>
              <tr>
                {['Date', 'Open', 'High', 'Low', 'Close', 'Volume'].map((heading) => (
                  <th
                    key={heading}
                    scope="col"
                    style={{ borderBottom: '1px solid var(--color-surface-divider)', padding: 10, textAlign: 'right' }}
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points.map((point) =>
                point.kind === 'price' ? (
                  <tr key={point.date}>
                    <th scope="row" style={{ padding: 10, textAlign: 'left' }}>{formatDate(point.date)}</th>
                    {[point.open, point.high, point.low, point.close].map((value, index) => (
                      <td key={index} style={{ padding: 10, textAlign: 'right' }}>{formatter.format(value as number)}</td>
                    ))}
                    <td style={{ padding: 10, textAlign: 'right' }}>{(point.volume as number).toLocaleString()}</td>
                  </tr>
                ) : (
                  <tr key={point.date}>
                    <th scope="row" style={{ padding: 10, textAlign: 'left' }}>{formatDate(point.date)}</th>
                    <td colSpan={5} style={{ color: 'var(--color-text-muted)', padding: 10, textAlign: 'center' }}>
                      {point.kind === 'closed' ? 'Market closed — no price' : 'No data for this session'}
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default PriceChart;

