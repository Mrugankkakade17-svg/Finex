import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MarketPage } from './MarketPage';
import {
  configureMarketService,
  resetFixtureWatchlist,
  resetMarketServiceConfig,
} from '../services/marketService';

describe('MarketPage', () => {
  beforeEach(() => {
    resetMarketServiceConfig();
    resetFixtureWatchlist();
  });

  afterEach(() => {
    resetMarketServiceConfig();
  });

  test('shows a validation error when searching with an empty query', async () => {
    render(<MarketPage />);

    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    expect(
      await screen.findByText('Enter a symbol or company name to search.')
    ).toBeInTheDocument();
  });

  test('shows an empty state when no securities match', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'ZZZUNKNOWN' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    expect(await screen.findByTestId('market-search-empty')).toBeInTheDocument();
  });

  test('shows results and loads a quote with freshness badge on selection', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    const resultButton = await screen.findByRole('button', { name: /AAPL/i });
    fireEvent.click(resultButton);

    await waitFor(() => {
      expect(screen.getByTestId('quote-freshness')).toBeInTheDocument();
      expect(screen.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'CACHED');
      expect(screen.getByTestId('quote-freshness-badge')).toHaveTextContent('Cached');
    });
  });

  test('shows true freshness badge statuses for MARKET_CLOSED and STALE quotes', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'TCS.NS' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    fireEvent.click(await screen.findByRole('button', { name: /TCS\.NS/i }));
    await waitFor(() => {
      expect(screen.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'MARKET_CLOSED');
      expect(screen.getByTestId('quote-freshness-badge')).toHaveTextContent('Market closed');
    });

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'INFY.BO' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    fireEvent.click(await screen.findByRole('button', { name: /INFY\.BO/i }));
    await waitFor(() => {
      expect(screen.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'STALE');
      expect(screen.getByTestId('quote-freshness-badge')).toHaveTextContent('Stale');
    });
  });

  test('shows a price-unavailable state and Unavailable badge without a fake price for outage symbol', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'DOWN' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    const resultButton = await screen.findByRole('button', { name: /DOWN/i });
    fireEvent.click(resultButton);

    await waitFor(() => {
      expect(screen.getByTestId('quote-unavailable')).toBeInTheDocument();
      expect(screen.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'UNAVAILABLE');
      expect(screen.getByTestId('quote-freshness-badge')).toHaveTextContent('Unavailable');
    });
    expect(screen.queryByText(/0\.00 USD/)).not.toBeInTheDocument();
  });

  test('renders Live freshness badge when API mode returns a LIVE quote from a licensed provider', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          success: true,
          data: {
            items: [
              {
                symbol: 'AAPL',
                name: 'Apple Inc.',
                exchange: 'NASDAQ',
                asset_class: 'EQUITY',
                currency: 'USD',
              },
            ],
            count: 1,
          },
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          success: true,
          data: {
            symbol: 'AAPL',
            price: 230.15,
            currency: 'USD',
            change: 2.1,
            change_pct: 0.0092,
            source: 'licensed-exchange-feed',
            as_of: '2026-11-26T12:00:00Z',
            fetched_at: '2026-11-26T12:00:01Z',
            freshness: 'LIVE',
          },
        }),
      });

    configureMarketService({
      mode: 'api',
      apiBaseUrl: 'http://127.0.0.1:8000',
      fetchImpl: mockFetch as unknown as typeof fetch,
    });

    render(<MarketPage />);
    expect(screen.getByTestId('market-mode-badge')).toHaveTextContent('Live API');

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));
    fireEvent.click(await screen.findByRole('button', { name: /AAPL/i }));

    await waitFor(() => {
      expect(screen.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'LIVE');
      expect(screen.getByTestId('quote-freshness-badge')).toHaveTextContent('Live');
    });
  });
});
