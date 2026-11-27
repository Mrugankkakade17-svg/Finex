import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WatchlistPage } from './WatchlistPage';
import {
  configureMarketService,
  resetFixtureWatchlist,
  resetMarketServiceConfig,
} from '../services/marketService';

describe('WatchlistPage', () => {
  beforeEach(() => {
    resetMarketServiceConfig();
    resetFixtureWatchlist();
  });

  afterEach(() => {
    resetMarketServiceConfig();
  });

  test('shows a loading state before the watchlist resolves', () => {
    render(<WatchlistPage />);

    expect(screen.getByTestId('watchlist-loading')).toBeInTheDocument();
  });

  test('renders the seeded watchlist item and its true freshness badge once loaded', async () => {
    render(<WatchlistPage />);

    expect(await screen.findByText('AAPL')).toBeInTheDocument();
    const badge = screen.getByTestId('watchlist-freshness-badge-AAPL');
    expect(badge).toHaveAttribute('data-status', 'CACHED');
    expect(badge).toHaveTextContent('Cached');
  });

  test('removes an item from the watchlist when the remove control is used', async () => {
    render(<WatchlistPage />);

    const removeButton = await screen.findByLabelText('Remove AAPL from watchlist');
    fireEvent.click(removeButton);

    await waitFor(() => {
      expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument();
    });
  });

  test('renders true freshness badges across STALE, MARKET_CLOSED, and UNAVAILABLE items in API mode', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        success: true,
        data: {
          items: [
            {
              symbol: 'INFY.BO',
              name: 'Infosys Limited',
              added_at: '2026-11-26T10:00:00Z',
              currency: 'INR',
              price: 1842.75,
              freshness: {
                status: 'STALE',
                source: 'quotes-latest',
                as_of: '2026-11-26T09:30:00Z',
                fetched_at: '2026-11-26T09:35:00Z',
              },
            },
            {
              symbol: 'TCS.NS',
              name: 'Tata Consultancy Services Limited',
              added_at: '2026-11-26T10:01:00Z',
              currency: 'INR',
              price: 4120.0,
              freshness: {
                status: 'MARKET_CLOSED',
                source: 'market-calendar',
                as_of: '2026-11-26T10:00:00Z',
                fetched_at: '2026-11-26T10:01:00Z',
              },
            },
            {
              symbol: 'DOWN',
              name: 'Provider Outage Demo Security',
              added_at: '2026-11-26T10:02:00Z',
              currency: 'USD',
              price: null,
              freshness: {
                status: 'UNAVAILABLE',
                source: 'yfinance',
                as_of: null,
                fetched_at: '2026-11-26T10:02:00Z',
              },
            },
          ],
        },
      }),
    });

    configureMarketService({
      mode: 'api',
      apiBaseUrl: 'http://127.0.0.1:8000',
      fetchImpl: mockFetch as unknown as typeof fetch,
    });

    render(<WatchlistPage />);

    expect(await screen.findByText('INFY.BO')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-freshness-badge-INFY.BO')).toHaveAttribute('data-status', 'STALE');
    expect(screen.getByTestId('watchlist-freshness-badge-INFY.BO')).toHaveTextContent('Stale');

    expect(screen.getByTestId('watchlist-freshness-badge-TCS.NS')).toHaveAttribute('data-status', 'MARKET_CLOSED');
    expect(screen.getByTestId('watchlist-freshness-badge-TCS.NS')).toHaveTextContent('Market closed');

    expect(screen.getByTestId('watchlist-freshness-badge-DOWN')).toHaveAttribute('data-status', 'UNAVAILABLE');
    expect(screen.getByTestId('watchlist-freshness-badge-DOWN')).toHaveTextContent('Unavailable');
    expect(screen.getByText('Price unavailable')).toBeInTheDocument();
  });

  test('shows error state and retries when loading watchlist fails', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce({
        status: 503,
        ok: false,
        json: async () => ({ message: 'Watchlist service unavailable' }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({ success: true, data: { items: [] } }),
      });

    configureMarketService({
      mode: 'api',
      apiBaseUrl: 'http://127.0.0.1:8000',
      fetchImpl: mockFetch as unknown as typeof fetch,
    });

    render(<WatchlistPage />);

    expect(await screen.findByTestId('watchlist-error')).toHaveTextContent('Watchlist service unavailable');

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(await screen.findByTestId('watchlist-empty')).toBeInTheDocument();
  });
});
