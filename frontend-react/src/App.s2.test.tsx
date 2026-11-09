import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import App from './App';
import { completedState, journeyClientMock } from './testHelpers/localApplication';

beforeEach(() => { window.history.replaceState({}, '', '/login'); });

test.each([
  ['Risk profile', 'Your saved risk profile'],
  ['Portfolio', 'Your manual portfolios'],
])('the full %s route is delivered, with a safe missing-capability error rather than a pilot fallback', async (link, heading) => {
  const { client } = journeyClientMock(completedState());
  render(<App client={client} />);
  fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  fireEvent.click(screen.getByRole('link', { name: link }));
  await screen.findByRole('heading', { name: heading });
  expect(await screen.findByRole('alert')).toHaveTextContent(/S2.*unavailable/i);
  expect(screen.queryByText(/Pending full-app delivery/i)).not.toBeInTheDocument();
});
