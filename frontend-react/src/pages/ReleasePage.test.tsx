import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ReleasePage } from './ReleasePage';
import { finexApiClient } from '../services/apiClient';

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
});

test('loads release handover through the shared client and shows a useful error on failure', async () => {
  const fetchMock = jest.fn().mockResolvedValue({ ok: false, status: 503 });
  global.fetch = fetchMock as typeof global.fetch;
  render(<ReleasePage />);

  expect(await screen.findByRole('alert')).toHaveTextContent('Release information could not be loaded. Please retry.');
  expect(fetchMock).toHaveBeenCalledWith(
    `${finexApiClient.baseUrl}/api/v1/release/handover`,
    expect.objectContaining({ credentials: 'omit', redirect: 'error' }),
  );
  await waitFor(() => expect(screen.getByRole('button', { name: /refresh live status/i })).toBeEnabled());
});
