import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MarketPage } from './MarketPage';

describe('MarketPage', () => {
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

  test('shows results and loads a quote with freshness info on selection', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    const resultButton = await screen.findByRole('button', { name: /AAPL/i });
    fireEvent.click(resultButton);

    await waitFor(() => {
      expect(screen.getByTestId('quote-freshness')).toBeInTheDocument();
    });
  });

  test('shows a price-unavailable state for the provider-outage symbol', async () => {
    render(<MarketPage />);

    fireEvent.change(screen.getByLabelText('Search securities'), {
      target: { value: 'DOWN' },
    });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    const resultButton = await screen.findByRole('button', { name: /DOWN/i });
    fireEvent.click(resultButton);

    await waitFor(() => {
      expect(screen.getByTestId('quote-unavailable')).toBeInTheDocument();
    });
  });
});
