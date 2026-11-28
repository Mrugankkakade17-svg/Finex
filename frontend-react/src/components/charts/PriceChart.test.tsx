import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PriceChart, { buildPriceChartPoints, PriceBar } from './PriceChart';

jest.mock('recharts', () => {
  const React = require('react');
  const component = () => ({ children }: { children?: React.ReactNode }) =>
    React.createElement('div', null, children);
  return {
    Area: component(),
    AreaChart: component(),
    CartesianGrid: component(),
    ResponsiveContainer: component(),
    Tooltip: component(),
    XAxis: component(),
    YAxis: component(),
  };
}, { virtual: true });

const bars: PriceBar[] = [
  { timestamp: '2026-11-23', open: 100, high: 105, low: 99, close: 104, volume: 1200 },
  { timestamp: '2026-11-26', open: 104, high: 107, low: 102, close: 106, volume: 900 },
];

describe('buildPriceChartPoints', () => {
  it('sorts candles and creates a null weekday point for a missing session', () => {
    const points = buildPriceChartPoints([...bars].reverse());

    expect(points.map(({ date, kind, close }) => [date, kind, close])).toEqual([
      ['2026-11-23', 'price', 104],
      ['2026-11-24', 'gap', null],
      ['2026-11-25', 'gap', null],
      ['2026-11-26', 'price', 106],
    ]);
  });

  it('marks explicit exchange closures without adding prices and skips weekend markers', () => {
    const oneWeek: PriceBar[] = [
      bars[0],
      { ...bars[1], timestamp: '2026-11-30' },
    ];
    const points = buildPriceChartPoints(oneWeek, ['2026-11-26']);

    expect(points.find((point) => point.date === '2026-11-26')).toMatchObject({
      kind: 'closed', close: null, volume: null,
    });
    expect(points.some((point) => point.date === '2026-11-28' || point.date === '2026-11-29')).toBe(false);
    expect(points.find((point) => point.date === '2026-11-27')?.kind).toBe('gap');
  });

  it('does not invent prices when the only supplied dates are closures', () => {
    expect(buildPriceChartPoints([], ['2026-11-26'])).toEqual([
      expect.objectContaining({ date: '2026-11-26', kind: 'closed', close: null }),
    ]);
  });
});

describe('PriceChart', () => {
  it('offers a table alternative with OHLCV and explicit missing-session rows', () => {
    render(<PriceChart symbol="TEST" currency="USD" candles={bars} />);
    fireEvent.click(screen.getByRole('button', { name: 'Table' }));

    expect(screen.getByRole('table', { name: /TEST daily OHLCV/ })).toBeInTheDocument();
    expect(screen.getAllByText('No data for this session')).toHaveLength(2);
    expect(screen.getAllByText(/104\.00$/)).toHaveLength(2);
    expect(screen.getByText('1,200')).toBeInTheDocument();
  });

  it('renders loading, error, retry, and empty states', () => {
    const retry = jest.fn();
    const { rerender } = render(<PriceChart symbol="TEST" candles={[]} loading />);
    expect(screen.getByRole('status')).toHaveTextContent(/loading price history/i);

    rerender(<PriceChart symbol="TEST" candles={[]} error="History unavailable" onRetry={retry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('History unavailable');

    rerender(<PriceChart symbol="TEST" candles={[]} />);
    expect(screen.getByRole('status')).toHaveTextContent(/no historical prices/i);
  });
});
