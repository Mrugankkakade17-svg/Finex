import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';
import { completedState, deferred, journeyClientMock } from './testHelpers/localApplication';
import { LocalApplicationError } from './services/localApplicationClient';
import { draftFixture, inputFixture, savedFixture, s2Mock, s2Response, s2Scope, s2Time } from './testHelpers/localS2';
import { LocalS2Api } from './services/localS2Client';
import { webcrypto } from 'crypto';
beforeEach(() => {
  window.history.replaceState({}, '', '/login');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: webcrypto });
});
async function enter(path: 'Risk profile' | 'Portfolio') {
  const mock = journeyClientMock(completedState());
  const api = s2Mock();
  mock.client.s2 = api;
  render(<App client={mock.client}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  fireEvent.click(screen.getByRole('link', { name: path }));
  return { ...mock, api };
}
function allAnswers() {
  for (const question of screen.getAllByRole('group', { name: /Synthetic server question/ }))
    fireEvent.click(within(question).getByRole('radio', { name: 'Synthetic option C' }));
}
test('actual ten server questions load, partial replacement is saved and explicit clear persists empty answers', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  expect(screen.getAllByRole('group', { name: /Synthetic server question/ })).toHaveLength(10);
  fireEvent.click(within(screen.getByRole('group', { name: 'Synthetic server question W1' })).getByRole('radio', { name: 'Synthetic option C' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save answers draft' }));
  await screen.findByText(/Answers draft saved/i);
  expect(api.saveRiskDraft.mock.calls[0][1].answers).toEqual(inputFixture().answers.slice(0, 1));
  fireEvent.click(screen.getByRole('button', { name: 'Clear saved answers draft' }));
  await waitFor(() => expect(api.saveRiskDraft.mock.calls.length).toBe(2));
  expect(api.saveRiskDraft.mock.calls[1][1].answers).toEqual([]);
  expect(api.submitRisk).not.toHaveBeenCalled();
});
test('viewing immutable history still permits deliberate new assessment without losing draft answers', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  api.riskHistory.mockResolvedValueOnce(s2Response({ scope: 'local_educational_application', contract_version: 'local.v1', items: [savedFixture()], next_cursor: null }));
  fireEvent.click(screen.getByRole('button', { name: 'Reload assessment history' }));
  fireEvent.click(await screen.findByRole('button', { name: /View Moderate assessment/ }));
  await screen.findByRole('heading', { name: 'Saved assessment · Moderate' });
  fireEvent.click(screen.getByRole('button', { name: 'Start a new assessment' }));
  expect(screen.getByRole('button', { name: 'Save immutable assessment' })).toBeEnabled();
});
test('uncertain assessment retry freezes full answers and the same UUID, double click never creates another request', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  allAnswers();
  api.submitRisk.mockRejectedValueOnce(new LocalApplicationError('REQUEST_TIMEOUT'));
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable assessment' }));
  await screen.findByRole('alert');
  const input = api.submitRisk.mock.calls[0][1];
  expect(input.answers).toHaveLength(10);
  expect(screen.getByRole('button', { name: 'Retry same assessment' })).toBeEnabled();
  const gate = deferred<Awaited<ReturnType<LocalS2Api['submitRisk']>>>();
  api.submitRisk.mockReturnValueOnce(gate.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Retry same assessment' }));
  fireEvent.click(screen.getByRole('button', { name: 'Retry same assessment' }));
  expect(api.submitRisk.mock.calls.length).toBe(2);
  expect(api.submitRisk.mock.calls[1][1]).toEqual(input);
  await act(async () => {
    gate.resolve(s2Response({ ...savedFixture(), input: { questionnaire_id: input.questionnaire_id, questionnaire_version: input.questionnaire_version, answers: input.answers.slice().reverse() } }, s2Time));
  });
  await screen.findByRole('heading', { name: 'Saved assessment · Moderate' });
  expect(screen.getByText('Synthetic server explanation')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start a new assessment' })).toBeEnabled();
});
test('failed logout hides, but does not dispose, an unsaved risk form; stale401 cannot erase it', async () => {
  const { api, client } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  const option = within(screen.getByRole('group', { name: 'Synthetic server question W1' })).getByRole('radio', { name: 'Synthetic option C' });
  fireEvent.click(option);
  const draft = deferred<Awaited<ReturnType<LocalS2Api['saveRiskDraft']>>>();
  api.saveRiskDraft.mockReturnValueOnce(draft.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Save answers draft' }));
  const logout = deferred<Awaited<ReturnType<typeof client.logout>>>();
  client.logout.mockReturnValueOnce(logout.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.queryAllByRole('radio')).toHaveLength(0);
  expect(screen.getByRole('status')).toHaveTextContent(/Checking|sign-out/i);
  await act(async () => {
    logout.reject(new LocalApplicationError('API_UNAVAILABLE'));
    draft.reject(new LocalApplicationError('SESSION_INVALID'));
  });
  expect(await screen.findByRole('button', { name: 'Retry sign out' })).toBeEnabled();
  expect(within(screen.getByRole('group', { name: 'Synthetic server question W1' })).getByRole('radio', { name: 'Synthetic option C' })).toBeChecked();
  expect(screen.getByTestId('local-persona')).toHaveTextContent('learner-a');
});
test('portfolio creation, exact string holdings, update and confirmed deletion use named API operations', async () => {
  const { api } = await enter('Portfolio');
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), { target: { value: 'Manual learning' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'Manual learning' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), { target: { value: '1.2300' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
  await screen.findByText(/Holding saved/i);
  const input = api.createHolding.mock.calls[0][2];
  expect(input.quantity).toBe('1.230000');
  expect(input.average_cost).toBe('10.0000');
  expect(api.metrics.mock.calls.length).toBeGreaterThanOrEqual(2);
  fireEvent.click(screen.getByRole('button', { name: /Edit Synthetic Apple/ }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Update holding' }));
  await waitFor(() => expect(api.updateHolding.mock.calls.length).toBe(1));
  await waitFor(() => expect(screen.getByRole('button', { name: /Delete Synthetic Apple/ })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: /Delete Synthetic Apple/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete holding' }));
  await waitFor(() => expect(api.deleteHolding.mock.calls.length).toBe(1));
});
test('uncertain portfolio POST reconciles list without replay and retains name until deliberate retry', async () => {
  const { api } = await enter('Portfolio');
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  api.createPortfolio.mockRejectedValueOnce(new LocalApplicationError('REQUEST_TIMEOUT'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), { target: { value: 'Retain this manual name' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Retain this manual name');
  expect(api.createPortfolio.mock.calls.length).toBe(1);
  expect(screen.getByRole('button', { name: 'Refresh owned portfolios before retry' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh owned portfolios before retry' }));
  await screen.findByText(/List refreshed.*no POST repeated/i);
  expect(api.createPortfolio.mock.calls.length).toBe(1);
});
test('a whitespace-only name never dispatches a POST or locks out local correction', async () => {
  const { api } = await enter('Portfolio');
  const name = await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(name, { target: { value: '   ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  expect(await screen.findByRole('alert')).toHaveFocus();
  expect(api.createPortfolio).not.toHaveBeenCalled();
  expect(name).toHaveValue('   ');
  expect(name).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Create portfolio' })).toBeEnabled();
  expect(screen.queryByText(/It may have committed/i)).not.toBeInTheDocument();
  fireEvent.change(name, { target: { value: 'Corrected local name' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'Corrected local name' });
  expect(api.createPortfolio).toHaveBeenCalledTimes(1);
  expect(api.createPortfolio.mock.calls[0][1].name).toBe('Corrected local name');
});
test('a catalogue fault retains confirmed portfolio-only records and CRUD without inventing holdings or values', async () => {
  const mock = journeyClientMock(completedState()), api = s2Mock();
  await api.createPortfolio('synthetic-test-only', { portfolio_version: 'portfolio.v1', name: 'Catalogue independent record', description: null, currency: 'USD' });
  api.createPortfolio.mockClear();
  api.catalog.mockRejectedValue(new LocalApplicationError('LOCAL_CATALOG_UNAVAILABLE'));
  api.holdings.mockRejectedValue(new LocalApplicationError('LOCAL_CATALOG_UNAVAILABLE'));
  api.metrics.mockRejectedValue(new LocalApplicationError('LOCAL_CATALOG_UNAVAILABLE'));
  mock.client.s2 = api;
  render(<App client={mock.client}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Open Catalogue independent record' }));
  await screen.findByRole('heading', { name: 'Catalogue independent record' });
  expect(screen.getByRole('button', { name: 'Edit portfolio' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Delete portfolio' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: 'Add holding' })).not.toBeInTheDocument();
  expect(screen.queryByText('No manual holdings saved.')).not.toBeInTheDocument();
  expect(screen.getByText(/No current valuation has been confirmed/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Edit portfolio' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), { target: { value: 'Edited without catalogue' } });
  fireEvent.click(screen.getByRole('button', { name: 'Update portfolio' }));
  await screen.findByRole('heading', { name: 'Edited without catalogue' });
  expect(api.updatePortfolio).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Delete portfolio' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete portfolio' }));
  await screen.findByText('Portfolio and its manual holdings deletion confirmed.');
  expect(api.deletePortfolio).toHaveBeenCalledTimes(1);
  expect(api.createHolding).not.toHaveBeenCalled();
  expect(screen.queryByRole('heading', { name: 'Edited without catalogue' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), { target: { value: 'New portfolio without catalogue' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'New portfolio without catalogue' });
  expect(api.createPortfolio).toHaveBeenCalledTimes(1);
});
test.each([false, true])('a failed catalogue reload disables holding mutations and an existing confirmation (%s)', async (pendingConfirmation) => {
  const { api } = await enter('Portfolio');
  const name = await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(name, { target: { value: 'Catalogue reload example' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'Catalogue reload example' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), { target: { value: '1' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
  await screen.findByText(/Holding saved on the backend/);
  if (pendingConfirmation)
    fireEvent.click(screen.getByRole('button', { name: 'Delete Synthetic Apple example' }));
  api.catalog.mockRejectedValueOnce(new LocalApplicationError('LOCAL_CATALOG_UNAVAILABLE'));
  fireEvent.click(screen.getByRole('button', { name: 'Reload catalogue and portfolios' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Edit portfolio' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Delete portfolio' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Edit Synthetic Apple example' })).toBeDisabled();
  const remove = screen.getByRole('button', { name: 'Delete Synthetic Apple example' });
  expect(remove).toBeDisabled();
  fireEvent.click(remove);
  const confirm = screen.queryByRole('button', { name: 'Confirm delete holding' });
  if (pendingConfirmation) {
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm!);
  }
  else
    expect(confirm).not.toBeInTheDocument();
  expect(api.deleteHolding).not.toHaveBeenCalled();
  expect(api.updateHolding).not.toHaveBeenCalled();
});

test('an uncertain holding creation cannot be reconciled by reading another portfolio', async () => {
  const mock = journeyClientMock(completedState()), api = s2Mock();
  for (const name of ['Original parent', 'Another parent'])
    await api.createPortfolio('synthetic-test-only', { portfolio_version: 'portfolio.v1', name, description: null, currency: 'USD' });
  api.createHolding.mockRejectedValueOnce(new LocalApplicationError('REQUEST_TIMEOUT'));
  mock.client.s2 = api;
  render(<App client={mock.client}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Open Original parent' }));
  await screen.findByRole('heading', { name: 'Original parent' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), { target: { value: '1' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Add holding' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Open Another parent' }));
  await screen.findByRole('heading', { name: 'Another parent' });
  fireEvent.click(screen.getByRole('button', { name: /Refresh (?:owned holdings before retry|holdings and valuation)/ }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Open Original parent' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Open Original parent' }));
  await screen.findByRole('heading', { name: 'Original parent' });
  expect(screen.getByRole('button', { name: 'Add holding' })).toBeDisabled();
  expect(api.createHolding).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh owned holdings before retry' }));
  await screen.findByText(/Holdings refreshed; no POST repeated/);
  expect(screen.getByRole('button', { name: 'Add holding' })).toBeEnabled();
  expect(api.createHolding).toHaveBeenCalledTimes(1);
});
test('a confirmed portfolio deletion is not left visible when its follow-up list read fails', async () => {
  const { api } = await enter('Portfolio');
  const name = await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(name, { target: { value: 'Confirmed deletion example' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'Confirmed deletion example' });
  api.portfolios.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
  fireEvent.click(screen.getByRole('button', { name: 'Delete portfolio' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete portfolio' }));
  await screen.findByRole('alert');
  expect(api.deletePortfolio).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: 'Open Confirmed deletion example' })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Confirmed deletion example' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Confirm delete portfolio' })).not.toBeInTheDocument();
  expect(screen.getByText('Portfolio and its manual holdings deletion confirmed.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh owned portfolios' }));
  await screen.findByText(/List refreshed; no POST repeated/);
  expect(api.deletePortfolio).toHaveBeenCalledTimes(1);
});
test('a confirmed portfolio creation remains saved when its follow-up detail read fails', async () => {
  const { api } = await enter('Portfolio');
  const name = await screen.findByRole('textbox', { name: 'Portfolio name' });
  api.portfolio.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
  fireEvent.change(name, { target: { value: 'Confirmed creation example' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('alert');
  expect(api.createPortfolio).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('heading', { name: 'Confirmed creation example' })).toBeInTheDocument();
  expect(screen.getByText('Portfolio saved on the backend.')).toBeInTheDocument();
  expect(screen.queryByText(/It may have committed/)).not.toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('');
  expect(screen.getByText(/No current valuation has been confirmed/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh holdings and valuation' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add holding' })).toBeEnabled());
  expect(api.createPortfolio).toHaveBeenCalledTimes(1);
});
test('an unsaved portfolio controller survives failed logout while inaccessible during the attempt', async () => {
  const { api, client } = await enter('Portfolio');
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), { target: { value: 'Keep unsaved portfolio input' } });
  const list = deferred<Awaited<ReturnType<LocalS2Api['portfolios']>>>();
  api.portfolios.mockReturnValueOnce(list.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh owned portfolios' }));
  const logout = deferred<Awaited<ReturnType<typeof client.logout>>>();
  client.logout.mockReturnValueOnce(logout.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.queryAllByRole('textbox')).toHaveLength(0);
  await act(async () => {
    logout.reject(new LocalApplicationError('API_UNAVAILABLE'));
    list.reject(new LocalApplicationError('SESSION_INVALID'));
  });
  expect(await screen.findByRole('button', { name: 'Retry sign out' })).toBeEnabled();
  expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Keep unsaved portfolio input');
  expect(screen.getByTestId('local-persona')).toHaveTextContent('learner-a');
});
test('route departure permanently ignores a late401 from an old save even if the adapter ignores abort', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  const save = deferred<Awaited<ReturnType<LocalS2Api['saveRiskDraft']>>>();
  api.saveRiskDraft.mockReturnValueOnce(save.promise);
  fireEvent.click(screen.getByRole('button', { name: 'Save answers draft' }));
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  await screen.findByRole('textbox', { name: 'Portfolio name' });
  await act(async () => {
    save.reject(new LocalApplicationError('SESSION_INVALID'));
  });
  expect(screen.getByRole('heading', { name: 'Your manual portfolios' })).toBeInTheDocument();
  expect(screen.getByTestId('local-persona')).toHaveTextContent('learner-a');
  expect(screen.queryByRole('heading', { name: 'Choose a local persona' })).not.toBeInTheDocument();
});
test('current onboarding-required immediately removes the private risk form and re-gates', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  api.questionnaire.mockRejectedValueOnce(new LocalApplicationError('ONBOARDING_REQUIRED'));
  fireEvent.click(screen.getByRole('button', { name: 'Reload saved risk state' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  expect(screen.queryByRole('heading', { name: 'Your saved risk profile' })).not.toBeInTheDocument();
  expect(screen.queryAllByRole('radio', { name: 'Synthetic option C' })).toHaveLength(0);
});
test('failed answer save retains dirty answers and focuses a sanitized visible error', async () => {
  const { api } = await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  const option = within(screen.getByRole('group', { name: 'Synthetic server question W1' })).getByRole('radio', { name: 'Synthetic option C' });
  fireEvent.click(option);
  api.saveRiskDraft.mockRejectedValueOnce(new Error('Do not render substituted transport diagnostics'));
  fireEvent.click(screen.getByRole('button', { name: 'Save answers draft' }));
  const error = await screen.findByRole('alert');
  expect(error).toHaveFocus();
  expect(option).toBeChecked();
  expect(screen.queryByText('Do not render substituted transport diagnostics')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save answers draft' })).toBeEnabled();
});
test('the dashboard points to active S2 practice and keeps S3/S4 explicitly pending', async () => {
  await enter('Risk profile');
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));
  await screen.findByRole('heading', { name: 'Your learning space' });
  expect(screen.getByRole('link', { name: 'Open your saved risk profile' })).toHaveAttribute('href', '/risk');
  expect(screen.getByRole('link', { name: 'Open your manual portfolios' })).toHaveAttribute('href', '/portfolio');
  expect(screen.getAllByText('Pending full-app delivery.')).toHaveLength(2);
});

const reconciliationButtons = [
  'Refresh owned portfolios',
  'Reload catalogue and portfolios',
] as const;

function portfolioMutationCounts(api: jest.Mocked<LocalS2Api>) {
  return [
    api.createPortfolio.mock.calls.length,
    api.updatePortfolio.mock.calls.length,
    api.deletePortfolio.mock.calls.length,
    api.createHolding.mock.calls.length,
    api.updateHolding.mock.calls.length,
    api.deleteHolding.mock.calls.length,
  ];
}

async function reconciliationSelection() {
  const context = await enter('Portfolio');
  const name = await screen.findByRole('textbox', { name: 'Portfolio name' });
  fireEvent.change(name, { target: { value: 'Selected peer-change example' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portfolio' }));
  await screen.findByRole('heading', { name: 'Selected peer-change example' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), {
    target: { value: '1' },
  });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), {
    target: { value: '10' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
  await screen.findByText(/Holding saved on the backend/);
  await waitFor(() => expect(screen.getByRole('button', {
    name: reconciliationButtons[0],
  })).toBeEnabled());
  expect(screen.getByRole('heading', { name: 'Saved manual holdings' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Backend valuation snapshot' })).toBeInTheDocument();
  // This is the existing unit API simulation, not an actual server or bearer.
  const saved = await context.api.portfolios('synthetic-peer-unit-only');
  return { ...context, portfolio: saved.data.items[0] };
}

function dirtyPortfolioIntent(editSelected: boolean) {
  if (editSelected) {
    fireEvent.click(screen.getByRole('button', { name: 'Edit portfolio' }));
  }
  fireEvent.change(screen.getByRole('textbox', { name: 'Portfolio name' }), {
    target: { value: editSelected ? 'Unsaved selected edit' : 'Unrelated unsaved creation' },
  });
  fireEvent.click(screen.getByRole('checkbox', { name: 'No description (save null)' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Description' }), {
    target: { value: editSelected ? 'Selected edit details' : 'Keep independent creation details' },
  });
}

function dirtySelectedHolding() {
  fireEvent.click(screen.getByRole('button', { name: 'Edit Synthetic Apple example' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), {
    target: { value: '7.5' },
  });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), {
    target: { value: '42' },
  });
}

test.each(reconciliationButtons.flatMap((button) => [false, true].map((edit) => [button, edit] as const)))(
  'portfolio list reconciliation clears externally deleted selection and only its dependent intent: %s / edit %s',
  async (button, editSelected) => {
    const { api, portfolio } = await reconciliationSelection();
    dirtyPortfolioIntent(editSelected);
    dirtySelectedHolding();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Synthetic Apple example' }));
    expect(screen.getByRole('button', { name: 'Confirm delete holding' })).toBeEnabled();
    await api.deletePortfolio('synthetic-peer-unit-only', portfolio.portfolio_id);
    const mutations = portfolioMutationCounts(api);

    fireEvent.click(screen.getByRole('button', { name: button }));
    await waitFor(() => expect(screen.getByRole('button', { name: button })).toBeEnabled());
    expect(screen.getByText('No manual portfolios saved yet.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: portfolio.name })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Saved manual holdings' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Backend valuation snapshot' })).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Quantity' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Update holding' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm delete holding' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Create a manual portfolio' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue(
      editSelected ? '' : 'Unrelated unsaved creation',
    );
    if (editSelected) {
      expect(screen.queryByRole('textbox', { name: 'Description' })).not.toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: 'No description (save null)' })).toBeChecked();
    } else {
      expect(screen.getByRole('textbox', { name: 'Description' })).toHaveValue('Keep independent creation details');
    }
    expect(portfolioMutationCounts(api)).toEqual(mutations);
    expect(screen.queryByText('Portfolio and its manual holdings deletion confirmed.')).not.toBeInTheDocument();
  },
);

test.each(reconciliationButtons)(
  'portfolio list reconciliation keeps other records and independent creation after selected peer deletion: %s',
  async (button) => {
    const { api, portfolio } = await reconciliationSelection();
    dirtyPortfolioIntent(false);
    const survivor = await api.createPortfolio('synthetic-peer-unit-only', {
      portfolio_version: 'portfolio.v1', name: 'Other surviving manual record',
      description: null, currency: 'USD',
    });
    await api.deletePortfolio('synthetic-peer-unit-only', portfolio.portfolio_id);
    const mutations = portfolioMutationCounts(api);
    fireEvent.click(screen.getByRole('button', { name: button }));
    await waitFor(() => expect(screen.getByRole('button', { name: button })).toBeEnabled());
    expect(screen.getByRole('button', { name: `Open ${survivor.data.name}` })).toBeEnabled();
    expect(screen.queryByRole('heading', { name: portfolio.name })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Backend valuation snapshot' })).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Unrelated unsaved creation');
    expect(screen.getByRole('textbox', { name: 'Description' })).toHaveValue('Keep independent creation details');
    expect(portfolioMutationCounts(api)).toEqual(mutations);
  },
);

test.each(reconciliationButtons)(
  'portfolio list reconciliation updates surviving metadata without resaving or overwriting dirty edit controllers: %s',
  async (button) => {
    const { api, portfolio } = await reconciliationSelection();
    dirtyPortfolioIntent(true);
    dirtySelectedHolding();
    const changed = await api.updatePortfolio('synthetic-peer-unit-only', portfolio.portfolio_id, {
      portfolio_version: 'portfolio.v1', name: 'Peer-renamed selected record',
      description: 'Peer saved description', currency: 'USD',
    });
    const updatedAt = '2026-10-11T12:05:00.123456+00:00';
    api.portfolios.mockResolvedValueOnce(s2Response({
      ...s2Scope, portfolio_version: 'portfolio.v1',
      items: [{ ...changed.data, updated_at: updatedAt }], count: 1,
    }));
    const mutations = portfolioMutationCounts(api);
    fireEvent.click(screen.getByRole('button', { name: button }));
    await waitFor(() => expect(screen.getByRole('button', { name: button })).toBeEnabled());
    expect(screen.getByRole('button', { name: 'Open Peer-renamed selected record' })).toBeEnabled();
    expect(screen.queryByRole('heading', { name: 'Peer-renamed selected record' })).toBeInTheDocument();
    expect(screen.getByText('Peer saved description')).toBeInTheDocument();
    expect(screen.getByText(`Portfolio details last saved: ${updatedAt}. Holding changes do not change this timestamp.`)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Unsaved selected edit');
    expect(screen.getByRole('textbox', { name: 'Description' })).toHaveValue('Selected edit details');
    expect(screen.getByRole('textbox', { name: 'Quantity' })).toHaveValue('7.5');
    expect(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' })).toHaveValue('42');
    expect(screen.getByRole('heading', { name: 'Saved manual holdings' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Backend valuation snapshot' })).toBeInTheDocument();
    expect(portfolioMutationCounts(api)).toEqual(mutations);
  },
);

test('portfolio list reconciliation removes only the vanished parent uncertain-holding intent', async () => {
  const { api, portfolio } = await reconciliationSelection();
  api.createHolding.mockRejectedValueOnce(new LocalApplicationError('REQUEST_TIMEOUT'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Quantity' }), { target: { value: '4' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' }), { target: { value: '6' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add holding' }));
  await screen.findByRole('alert');
  expect(screen.getByText(/A holding creation has not been fully confirmed/)).toBeInTheDocument();
  await api.deletePortfolio('synthetic-peer-unit-only', portfolio.portfolio_id);
  const mutations = portfolioMutationCounts(api);
  fireEvent.click(screen.getByRole('button', { name: reconciliationButtons[0] }));
  await screen.findByText(/List refreshed; no POST repeated/);
  expect(screen.queryByText(/A holding creation has not been fully confirmed/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: portfolio.name })).not.toBeInTheDocument();
  expect(portfolioMutationCounts(api)).toEqual(mutations);
});

test.each(reconciliationButtons.flatMap((button) => [
  'LOCAL_STORE_UNAVAILABLE', 'REQUEST_TIMEOUT',
].map((code) => [button, code] as const)))(
  'portfolio list reconciliation preserves confirmed data and dirty input when no authoritative list succeeds: %s / %s',
  async (button, code) => {
    const { api, portfolio } = await reconciliationSelection();
    dirtyPortfolioIntent(false);
    dirtySelectedHolding();
    api.portfolios.mockRejectedValueOnce(new LocalApplicationError(code));
    const mutations = portfolioMutationCounts(api);
    fireEvent.click(screen.getByRole('button', { name: button }));
    expect(await screen.findByRole('alert')).toHaveFocus();
    expect(screen.getByRole('heading', { name: portfolio.name })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Backend valuation snapshot' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Unrelated unsaved creation');
    expect(screen.getByRole('textbox', { name: 'Description' })).toHaveValue('Keep independent creation details');
    expect(screen.queryByText(/List refreshed; no POST repeated/)).not.toBeInTheDocument();
    expect(screen.queryByText('No manual portfolios saved yet.')).not.toBeInTheDocument();
    // A full reload deliberately hides holding mutation controls until its
    // catalogue is reconfirmed; that must not dispose their dirty controllers.
    fireEvent.click(screen.getByRole('button', { name: button }));
    await waitFor(() => expect(screen.getByRole('button', { name: button })).toBeEnabled());
    expect(screen.getByRole('textbox', { name: 'Quantity' })).toHaveValue('7.5');
    expect(screen.getByRole('textbox', { name: 'Average cost (USD per unit)' })).toHaveValue('42');
    expect(portfolioMutationCounts(api)).toEqual(mutations);
  },
);

test.each(['empty-success', 'late401'] as const)(
  'portfolio list reconciliation ignores cancelled old reads after failed logout: %s',
  async (late) => {
    const { api, client, portfolio } = await reconciliationSelection();
    dirtyPortfolioIntent(false);
    dirtySelectedHolding();
    const read = deferred<Awaited<ReturnType<LocalS2Api['portfolios']>>>();
    api.portfolios.mockReturnValueOnce(read.promise);
    fireEvent.click(screen.getByRole('button', { name: reconciliationButtons[0] }));
    client.logout.mockRejectedValueOnce(new LocalApplicationError('API_UNAVAILABLE'));
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('button', { name: 'Retry sign out' })).toBeEnabled();
    await act(async () => {
      if (late === 'late401') read.reject(new LocalApplicationError('SESSION_INVALID'));
      else read.resolve(s2Response({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [], count: 0 }));
    });
    expect(screen.getByTestId('local-persona')).toHaveTextContent('learner-a');
    expect(screen.getByRole('heading', { name: portfolio.name })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toHaveValue('Unrelated unsaved creation');
    expect(screen.getByRole('textbox', { name: 'Quantity' })).toHaveValue('7.5');
    expect(screen.queryByText(/List refreshed; no POST repeated/)).not.toBeInTheDocument();
  },
);

test.each(['learner-a', 'learner-b'] as const)(
  'portfolio list reconciliation ignores an old empty read after a new owner epoch: %s',
  async (alias) => {
    const { api, setState, portfolio } = await reconciliationSelection();
    setState(completedState(), alias);
    const read = deferred<Awaited<ReturnType<LocalS2Api['portfolios']>>>();
    api.portfolios.mockReturnValueOnce(read.promise);
    fireEvent.click(screen.getByRole('button', { name: reconciliationButtons[0] }));
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await screen.findByRole('heading', { name: 'Choose a local persona' });
    const current = await api.createPortfolio('synthetic-new-owner-unit-only', {
      portfolio_version: 'portfolio.v1', name: 'New epoch selected example',
      description: null, currency: 'USD',
    });
    api.portfolios.mockResolvedValue(s2Response({
      ...s2Scope, portfolio_version: 'portfolio.v1', items: [current.data], count: 1,
    }));
    api.portfolio.mockResolvedValue(current);
    fireEvent.click(screen.getByRole('button', { name: `Sign in as ${alias}` }));
    await screen.findByRole('heading', { name: 'Your local onboarding' });
    fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open New epoch selected example' }));
    await screen.findByRole('heading', { name: current.data.name });
    await act(async () => {
      read.resolve(s2Response({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [], count: 0 }));
    });
    expect(screen.getByTestId('local-persona')).toHaveTextContent(alias);
    expect(screen.getByRole('heading', { name: current.data.name })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: `Open ${current.data.name}` })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: portfolio.name })).not.toBeInTheDocument();
    expect(screen.queryByText('No manual portfolios saved yet.')).not.toBeInTheDocument();
    expect(screen.queryByText(/List refreshed; no POST repeated/)).not.toBeInTheDocument();
  },
);

test('portfolio list reconciliation cannot update a departed route or its replacement selection', async () => {
  const { api, portfolio } = await reconciliationSelection();
  const read = deferred<Awaited<ReturnType<LocalS2Api['portfolios']>>>();
  api.portfolios.mockReturnValueOnce(read.promise);
  fireEvent.click(screen.getByRole('button', { name: reconciliationButtons[0] }));
  fireEvent.click(screen.getByRole('link', { name: 'Risk profile' }));
  await screen.findByRole('group', { name: 'Synthetic server question W1' });
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  fireEvent.click(await screen.findByRole('button', { name: `Open ${portfolio.name}` }));
  await screen.findByRole('heading', { name: portfolio.name });
  await act(async () => {
    read.resolve(s2Response({ ...s2Scope, portfolio_version: 'portfolio.v1', items: [], count: 0 }));
  });
  expect(screen.getByRole('heading', { name: portfolio.name })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: `Open ${portfolio.name}` })).toBeInTheDocument();
  expect(screen.queryByText('No manual portfolios saved yet.')).not.toBeInTheDocument();
  expect(screen.queryByText(/List refreshed; no POST repeated/)).not.toBeInTheDocument();
});
