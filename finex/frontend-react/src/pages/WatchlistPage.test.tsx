import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WatchlistPage } from './WatchlistPage';

describe('WatchlistPage', () => {
  test('shows a loading state before the watchlist resolves', () => {
    render(<WatchlistPage />);

    expect(screen.getByTestId('watchlist-loading')).toBeInTheDocument();
  });

  test('renders the seeded watchlist item once loaded', async () => {
    render(<WatchlistPage />);

    expect(await screen.findByText('AAPL')).toBeInTheDocument();
  });

  test('removes an item from the watchlist when the remove control is used', async () => {
    render(<WatchlistPage />);

    const removeButton = await screen.findByLabelText('Remove AAPL from watchlist');
    fireEvent.click(removeButton);

    await waitFor(() => {
      expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument();
    });
  });
});
