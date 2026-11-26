import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatPage } from './ChatPage';
import { finexApiClient } from '../services/apiClient';

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
});

test('sends chat through the shared client and renders the API answer', async () => {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ data: { answer_text: 'A grounded answer.', citations: [], intent: 'EDUCATIONAL' } }),
  });
  global.fetch = fetchMock as typeof global.fetch;
  render(<ChatPage />);

  fireEvent.change(screen.getByPlaceholderText(/ask ai about asset allocation/i), {
    target: { value: 'Explain diversification.' },
  });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));

  expect(await screen.findByText('A grounded answer.')).toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(fetchMock).toHaveBeenCalledWith(
    `${finexApiClient.baseUrl}/api/v1/ai/chat`,
    expect.objectContaining({ method: 'POST', credentials: 'omit', redirect: 'error' }),
  );
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ message: 'Explain diversification.' });
});
