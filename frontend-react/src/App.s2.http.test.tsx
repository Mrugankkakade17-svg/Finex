import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
// Keep the application's actual import order; no substituted session/domain adapter.
import App from './App';
import { completedState, loginDto } from './testHelpers/localApplication';
import { catalogFixture } from './testHelpers/localS2';
import { createLocalApplicationClient } from './services/localApplicationClient';

test.each(['application-first', 'models-first'] as const)(
  'a cold %s import returns initialized scope through both S2 decoding layers', (order) => {
    jest.isolateModules(() => {
      if (order === 'application-first') require('./services/localApplicationClient');
      const models = require('./services/localS2Models') as typeof import('./services/localS2Models');
      const client = require('./services/localS2Client') as typeof import('./services/localS2Client');
      const wire = { scope: 'local_educational_application', contract_version: 'local.v1',
        portfolio_version: 'portfolio.v1', items: [], count: 0 };
      const decoded = models.decodePortfolioList(wire);
      expect(decoded.scope).toBe('local_educational_application');
      expect(decoded.contract_version).toBe('local.v1');
      expect(client.checkedS2({ data: decoded, meta: { apiVersion: 'v1', dataStatus: 'CACHED',
        dataAsOf: null, correlationId: 'cold-import-check' } }, models.decodePortfolioList,
        client.nullMeta).data).toEqual(wire);
    });
  },
);

test('the default App HTTP client signs in and renders S2 records without a mock domain capability', async () => {
  window.history.replaceState({}, '', '/login');
  const original = Object.getOwnPropertyDescriptor(globalThis, 'fetch');
  const login = loginDto(), state = completedState();
  const scope = { scope: 'local_educational_application', contract_version: 'local.v1' };
  const routes: Record<string, unknown> = {
    '/api/v1/local-auth/mock-login': login,
    '/api/v1/local-auth/me': { ...scope, user: login.user },
    '/api/v1/local-onboarding/state': state,
    '/api/v1/local-portfolios/instruments': catalogFixture(),
    '/api/v1/local-portfolios': { ...scope, portfolio_version: 'portfolio.v1', items: [], count: 0 },
  };
  const fetchWire = jest.fn(async function (this: typeof globalThis, url: RequestInfo | URL) {
    // Browser host methods may require their global receiver; arrow mocks hide this.
    if (this !== globalThis) throw new TypeError('Synthetic unbound host receiver');
    const path = new URL(String(url)).pathname;
    if (!Object.prototype.hasOwnProperty.call(routes, path)) throw new Error('Unexpected test-only route');
    const envelope = { success: true, message: 'Synthetic HTTP boundary test', data: routes[path],
      meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null, correlationId: 'default-app-http' } };
    const bytes = JSON.stringify(envelope);
    return { status: 200, ok: true, redirected: false,
      headers: { get: (key: string) => key.toLowerCase() === 'content-type' ? 'application/json' : null },
      json: async () => JSON.parse(bytes), text: async () => bytes } as unknown as Response;
  });
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: fetchWire });
  const mounted = render(<App />);
  try {
    fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
    await screen.findByRole('heading', { name: 'Your local onboarding' });
    fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
    await screen.findByText('No manual portfolios saved yet.');
    expect(screen.getByRole('textbox', { name: 'Portfolio name' })).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await waitFor(() => expect(fetchWire.mock.calls.some(([url]) =>
      new URL(String(url)).pathname === '/api/v1/local-portfolios')).toBe(true));
  } finally {
    mounted.unmount();
    if (original) Object.defineProperty(globalThis, 'fetch', original);
    else delete (globalThis as { fetch?: typeof fetch }).fetch;
  }
});

test('injected S1 and S2 fetch functions retain their original receiver without using global fetch', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'fetch');
  let globalCalls = 0, injectedCalls = 0, originalReceiver = true;
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: () => {
    globalCalls++;
    throw new Error('Global transport must not replace injected transport');
  } });
  const login = loginDto();
  const injected = async function (this: unknown, url: RequestInfo | URL): Promise<Response> {
    injectedCalls++;
    originalReceiver = originalReceiver && this === undefined;
    const path = new URL(String(url)).pathname;
    const data = path === '/api/v1/local-auth/mock-login' ? login : catalogFixture();
    const envelope = { success: true, message: 'Synthetic injected boundary', data,
      meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null, correlationId: 'injected-http' } };
    const bytes = JSON.stringify(envelope);
    return { status: 200, ok: true, redirected: false, headers: { get: () => 'application/json' },
      json: async () => JSON.parse(bytes), text: async () => bytes } as unknown as Response;
  };
  try {
    const client = createLocalApplicationClient({ baseOrigin: 'http://127.0.0.1:8082', fetchImpl: injected });
    expect((await client.login('learner-a')).user.alias).toBe('learner-a');
    expect((await client.s2!.catalog(login.access_token)).data.items.length > 0).toBe(true);
    expect(originalReceiver && injectedCalls === 2 && globalCalls === 0).toBe(true);
  } finally {
    if (original) Object.defineProperty(globalThis, 'fetch', original);
    else delete (globalThis as { fetch?: typeof fetch }).fetch;
  }
});
