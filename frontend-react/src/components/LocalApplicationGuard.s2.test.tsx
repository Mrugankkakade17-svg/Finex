import React, { useLayoutEffect } from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocalApplicationGuard } from './LocalApplicationGuard';
import { LocalSession, LocalSessionProvider, useLocalSession } from '../context/LocalSessionContext';
import { LocalRiskPage } from '../pages/LocalRiskPage';
import { LocalPortfolioPage } from '../pages/LocalPortfolioPage';
import { LocalAlias, LocalApplicationError } from '../services/localApplicationClient';
import { LocalS2Api } from '../services/localS2Client';
import { completedState, deferred, journeyClientMock } from '../testHelpers/localApplication';
import { s2Mock } from '../testHelpers/localS2';
test.each(['learner-b', 'learner-a'] as const)('coalesced confirmed logout and %s login cannot retain the prior risk form or a late401', async (nextAlias: LocalAlias) => {
  const { client, setState } = journeyClientMock(completedState());
  setState(completedState(), 'learner-b');
  const api = s2Mock();
  client.s2 = api;
  let session!: LocalSession;
  const renderedAliases: Array<LocalAlias | null> = [];
  function Capture() {
    session = useLocalSession();
    useLayoutEffect(() => {
      renderedAliases.push(session.user?.alias ?? null);
    });
    return null;
  }
  render(<LocalSessionProvider client={client}>
    <MemoryRouter initialEntries={['/risk']}>
     <Capture />
     <LocalApplicationGuard><LocalRiskPage /></LocalApplicationGuard>
    </MemoryRouter>
   </LocalSessionProvider>);
  await act(async () => {
    await session.login('learner-a');
  });
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  const selected = within(screen.getByRole('group', { name: 'Synthetic server question W1' }))
    .getByRole('radio', { name: 'Synthetic option C' });
  fireEvent.click(selected);
  const oldSave = deferred<Awaited<ReturnType<LocalS2Api['saveRiskDraft']>>>();
  api.saveRiskDraft.mockReturnValueOnce(oldSave.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Save answers draft' }));
  renderedAliases.length = 0;
  // One React batch: no intermediate signed-out render is available to dispose a child.
  await act(async () => {
    await session.logout();
    await session.login(nextAlias);
  });
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  expect(renderedAliases.includes(null)).toBe(false);
  expect(session.user?.alias).toBe(nextAlias);
  expect(within(screen.getByRole('group', { name: 'Synthetic server question W1' }))
    .getByRole('radio', { name: 'Synthetic option C' })).not.toBeChecked();
  await act(async () => {
    oldSave.reject(new LocalApplicationError('SESSION_INVALID'));
  });
  expect(session.user?.alias).toBe(nextAlias);
  expect(screen.queryByText(/signed-out|session expired/i)).not.toBeInTheDocument();
});
test('coalesced owner replacement resets a dirty portfolio controller without an intervening signed-out render', async () => {
  const { client, setState } = journeyClientMock(completedState());
  setState(completedState(), 'learner-b');
  client.s2 = s2Mock();
  let session!: LocalSession;
  const renderedAliases: Array<LocalAlias | null> = [];
  function Capture() {
    session = useLocalSession();
    useLayoutEffect(() => {
      renderedAliases.push(session.user?.alias ?? null);
    });
    return null;
  }
  render(<LocalSessionProvider client={client}>
   <MemoryRouter initialEntries={['/portfolio']}>
    <Capture />
    <LocalApplicationGuard><LocalPortfolioPage /></LocalApplicationGuard>
   </MemoryRouter>
  </LocalSessionProvider>);
  await act(async () => {
    await session.login('learner-a');
  });
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), {
    target: { value: 'Old owner unsaved label' },
  });
  renderedAliases.length = 0;
  await act(async () => {
    await session.logout();
    await session.login('learner-b');
  });
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  expect(renderedAliases.includes(null)).toBe(false);
  expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('');
  expect(screen.queryByDisplayValue('Old owner unsaved label')).not.toBeInTheDocument();
});
