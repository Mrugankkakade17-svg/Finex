import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createApiClient } from '../services/apiClient';
import {
  PaperAccount,
  PaperOrder,
  PaperOrderInput,
  PaperTradingApi,
  PaperTradingApiError,
  PaperTradingPage,
  createPaperTradingApi,
} from './PaperTradingPage';

function makeOrder(overrides: Partial<PaperOrder> = {}): PaperOrder {
  return {
    order_id: 'paper-order-001',
    instrument_id: 'AAPL',
    exchange: 'NASDAQ',
    side: 'BUY',
    quantity: 10,
    executed_price: '200.000000',
    notional: '2000.00',
    fee: '2.00',
    cash_delta: '-2002.00',
    status: 'FILLED',
    quote_freshness: 'DELAYED',
    quote_as_of: '2026-11-27T15:00:00Z',
    created_at: '2026-11-27T15:00:01Z',
    simulation_notice: 'SIMULATION ONLY: no real money or broker execution.',
    ...overrides,
  };
}

function makeAccount(overrides: Partial<PaperAccount> = {}): PaperAccount {
  return {
    account_id: 'paper-acct-001',
    currency: 'USD',
    cash_balance: '10000.00',
    portfolio_value: '0.00',
    total_equity: '10000.00',
    positions: [],
    recent_orders: [],
    is_simulated: true,
    ...overrides,
  };
}

function createStatefulMockApi(initialCash = 10000): {
  api: jest.Mocked<PaperTradingApi>;
  submittedKeys: string[];
} {
  let cashCents = Math.round(initialCash * 100);
  const positions = new Map<
    string,
    { instrument_id: string; exchange: string; quantity: number; totalCostCents: number; lastPrice: number }
  >();
  const ordersByKey = new Map<string, { order: PaperOrder; fingerprint: string }>();
  const orders: PaperOrder[] = [];
  const submittedKeys: string[] = [];

  const snapshot = (): PaperAccount => {
    let portfolioValueCents = 0;
    const positionList = Array.from(positions.values()).map((pos) => {
      const marketCents = Math.round(pos.quantity * pos.lastPrice * 100);
      portfolioValueCents += marketCents;
      const avgCost = pos.totalCostCents / 100 / pos.quantity;
      const pnlCents = marketCents - pos.totalCostCents;
      return {
        instrument_id: pos.instrument_id,
        exchange: pos.exchange,
        quantity: pos.quantity,
        average_cost: avgCost.toFixed(6),
        last_price: pos.lastPrice.toFixed(6),
        market_value: (marketCents / 100).toFixed(2),
        unrealized_pnl: (pnlCents / 100).toFixed(2),
      };
    });

    return {
      account_id: 'paper-acct-001',
      currency: 'USD',
      cash_balance: (cashCents / 100).toFixed(2),
      portfolio_value: (portfolioValueCents / 100).toFixed(2),
      total_equity: ((cashCents + portfolioValueCents) / 100).toFixed(2),
      positions: positionList,
      recent_orders: orders.slice(0, 10),
      is_simulated: true,
    };
  };

  const api: jest.Mocked<PaperTradingApi> = {
    getAccount: jest.fn(async () => snapshot()),
    listOrders: jest.fn(async () => [...orders]),
    placeOrder: jest.fn(async (input: PaperOrderInput) => {
      submittedKeys.push(input.idempotency_key);
      const fingerprint = `${input.instrument_id}|${input.exchange}|${input.side}|${input.quantity}`;
      const existing = ordersByKey.get(input.idempotency_key);
      if (existing) {
        if (existing.fingerprint !== fingerprint) {
          throw new PaperTradingApiError(
            'The idempotency key was already used for a different order.',
            'IDEMPOTENCY_KEY_REUSED',
            { status: 409, retryable: false },
          );
        }
        return {
          order: existing.order,
          replayed: true,
          message: 'Paper order replayed',
        };
      }

      const price = 150.0;
      const notionalCents = Math.round(price * input.quantity * 100);
      const feeCents = Math.round(notionalCents * 0.001);
      const cashDeltaCents =
        input.side === 'BUY' ? -(notionalCents + feeCents) : notionalCents - feeCents;
      if (cashCents + cashDeltaCents < 0) {
        throw new PaperTradingApiError(
          'The order would make paper cash negative.',
          'INSUFFICIENT_CASH',
          { status: 409, retryable: false },
        );
      }

      const key = `${input.instrument_id}:${input.exchange}`;
      const current = positions.get(key) ?? {
        instrument_id: input.instrument_id,
        exchange: input.exchange,
        quantity: 0,
        totalCostCents: 0,
        lastPrice: price,
      };
      if (input.side === 'SELL' && current.quantity < input.quantity) {
        throw new PaperTradingApiError(
          'There are not enough shares to sell.',
          'INSUFFICIENT_POSITION',
          { status: 409, retryable: false },
        );
      }

      cashCents += cashDeltaCents;
      if (input.side === 'BUY') {
        current.quantity += input.quantity;
        current.totalCostCents += notionalCents + feeCents;
        current.lastPrice = price;
        positions.set(key, current);
      } else {
        const remaining = current.quantity - input.quantity;
        if (remaining === 0) {
          positions.delete(key);
        } else {
          current.totalCostCents = Math.round((current.totalCostCents * remaining) / current.quantity);
          current.quantity = remaining;
          current.lastPrice = price;
          positions.set(key, current);
        }
      }

      const order = makeOrder({
        order_id: `paper-order-${orders.length + 1}`,
        instrument_id: input.instrument_id,
        exchange: input.exchange,
        side: input.side,
        quantity: input.quantity,
        executed_price: price.toFixed(6),
        notional: (notionalCents / 100).toFixed(2),
        fee: (feeCents / 100).toFixed(2),
        cash_delta: (cashDeltaCents / 100).toFixed(2),
      });
      orders.unshift(order);
      ordersByKey.set(input.idempotency_key, { order, fingerprint });
      return {
        order,
        replayed: false,
        message: 'Paper order filled',
      };
    }),
  };

  return { api, submittedKeys };
}

describe('PaperTradingPage', () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  test('renders SIMULATED banner across loading, error, and loaded states', async () => {
    let rejectAccount!: (err: Error) => void;
    const api: PaperTradingApi = {
      getAccount: jest.fn(
        () =>
          new Promise<PaperAccount>((_resolve, reject) => {
            rejectAccount = reject;
          }),
      ),
      listOrders: jest.fn(async () => []),
      placeOrder: jest.fn(),
    };

    render(<PaperTradingPage api={api} />);
    expect(screen.getByTestId('paper-simulated-banner')).toHaveTextContent('SIMULATED');
    expect(screen.getByTestId('paper-loading')).toBeInTheDocument();

    await act(async () => {
      rejectAccount(new PaperTradingApiError('Paper trading persistence is unavailable.', 'PAPER_STORE_UNAVAILABLE', { status: 503, retryable: true }));
    });

    expect(await screen.findByTestId('paper-load-error')).toHaveTextContent(
      'Paper trading persistence is unavailable.',
    );
    expect(screen.getByTestId('paper-simulated-banner')).toHaveTextContent('SIMULATED');
    // Must not fabricate a fake $10,000.00 balance on error
    expect(screen.queryByTestId('paper-cash-balance')).not.toBeInTheDocument();
  });

  test('renders empty positions and empty ledger states before any trade is placed', async () => {
    const { api } = createStatefulMockApi(10000);

    render(<PaperTradingPage api={api} />);

    expect(await screen.findByTestId('paper-cash-balance')).toHaveTextContent('$10,000.00 USD');
    expect(screen.getByTestId('paper-portfolio-value')).toHaveTextContent('$0.00');
    expect(screen.getByTestId('paper-total-equity')).toHaveTextContent('$10,000.00');
    expect(screen.getByTestId('paper-positions-empty')).toBeInTheDocument();
    expect(screen.getByTestId('paper-ledger-empty')).toBeInTheDocument();
  });

  test('executes BUY order and persists account, positions, and ledger across page reload', async () => {
    const { api } = createStatefulMockApi(10000);

    const firstMount = render(<PaperTradingPage api={api} />);
    expect(await screen.findByTestId('paper-cash-balance')).toHaveTextContent('$10,000.00 USD');

    fireEvent.change(screen.getByLabelText('Security Symbol'), { target: { value: 'msft' } });
    fireEvent.change(screen.getByLabelText('Exchange'), { target: { value: 'NASDAQ' } });
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));

    expect(await screen.findByTestId('paper-order-confirmation')).toHaveTextContent(
      'Filled: Paper BUY order for 4 shares of MSFT (NASDAQ)',
    );
    expect(screen.getByTestId('paper-cash-balance')).toHaveTextContent('$9,399.40 USD');
    expect(screen.getByTestId('paper-position-MSFT')).toHaveTextContent('4');
    expect(screen.getByTestId('paper-ledger-row-paper-order-1')).toHaveTextContent('MSFT (NASDAQ)');

    // Simulate browser reload by unmounting and remounting against the same backend state.
    firstMount.unmount();

    render(<PaperTradingPage api={api} />);
    expect(await screen.findByTestId('paper-cash-balance')).toHaveTextContent('$9,399.40 USD');
    expect(screen.getByTestId('paper-portfolio-value')).toHaveTextContent('$600.00');
    expect(screen.getByTestId('paper-position-MSFT')).toHaveTextContent('4');
    expect(screen.getByTestId('paper-ledger-row-paper-order-1')).toHaveTextContent('-$600.60');
  });

  test('double-clicking Submit dispatches only one order while in flight', async () => {
    let resolveOrder!: (value: { order: PaperOrder; replayed: boolean; message: string }) => void;
    const order = makeOrder({ order_id: 'paper-order-double-1', quantity: 5 });
    const api: jest.Mocked<PaperTradingApi> = {
      getAccount: jest
        .fn()
        .mockResolvedValueOnce(makeAccount())
        .mockResolvedValueOnce(
          makeAccount({
            cash_balance: '8999.00',
            portfolio_value: '1000.00',
            total_equity: '9999.00',
            positions: [
              {
                instrument_id: 'AAPL',
                exchange: 'NASDAQ',
                quantity: 5,
                average_cost: '200.200000',
                last_price: '200.000000',
                market_value: '1000.00',
                unrealized_pnl: '-1.00',
              },
            ],
            recent_orders: [order],
          }),
        ),
      listOrders: jest.fn().mockResolvedValueOnce([]).mockResolvedValueOnce([order]),
      placeOrder: jest.fn(
        (_order: PaperOrderInput, _signal?: AbortSignal) =>
          new Promise((resolve) => {
            resolveOrder = resolve;
          }),
      ),
    };

    render(<PaperTradingPage api={api} />);
    await screen.findByTestId('paper-cash-balance');

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '5' } });
    const submitButton = screen.getByRole('button', { name: 'Submit Paper BUY Order' });

    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    expect(api.placeOrder).toHaveBeenCalledTimes(1);
    expect(submitButton).toBeDisabled();

    await act(async () => {
      resolveOrder({ order, replayed: false, message: 'Paper order filled' });
    });

    expect(await screen.findByTestId('paper-order-confirmation')).toHaveTextContent(
      'paper-order-double-1',
    );
    expect(api.placeOrder).toHaveBeenCalledTimes(1);
  });

  test('reuses the same idempotency_key on retry after transient failure and rotates after fill', async () => {
    const { api, submittedKeys } = createStatefulMockApi(10000);
    api.placeOrder.mockRejectedValueOnce(
      new PaperTradingApiError('The paper trading request timed out.', 'REQUEST_TIMEOUT', {
        retryable: true,
      }),
    );

    render(<PaperTradingPage api={api} />);
    await screen.findByTestId('paper-cash-balance');

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));

    expect(await screen.findByTestId('paper-order-error')).toHaveTextContent('timed out');

    // Retry same unconfirmed order -> must reuse exact same idempotency_key
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));
    expect(await screen.findByTestId('paper-order-confirmation')).toBeInTheDocument();

    const firstKey = (api.placeOrder.mock.calls[0][0] as PaperOrderInput).idempotency_key;
    const retryKey = (api.placeOrder.mock.calls[1][0] as PaperOrderInput).idempotency_key;
    expect(retryKey).toBe(firstKey);
    expect(firstKey.length).toBeGreaterThanOrEqual(10);

    // Subsequent intentional order -> must generate a new idempotency_key
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));
    await waitFor(() => expect(api.placeOrder).toHaveBeenCalledTimes(3));
    const nextOrderKey = (api.placeOrder.mock.calls[2][0] as PaperOrderInput).idempotency_key;
    expect(nextOrderKey).not.toBe(firstKey);
    expect(submittedKeys).toHaveLength(2);
  });

  test('validates symbol and positive integer quantity before sending API requests', async () => {
    const { api } = createStatefulMockApi(10000);
    render(<PaperTradingPage api={api} />);
    await screen.findByTestId('paper-cash-balance');

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));

    expect(await screen.findByTestId('paper-order-error')).toHaveTextContent(
      'Quantity must be between 1 and 100,000.',
    );
    expect(api.placeOrder).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Security Symbol'), { target: { value: 'BAD SYMBOL!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));

    expect(await screen.findByTestId('paper-order-error')).toHaveTextContent(
      'Enter a valid ticker symbol',
    );
    expect(api.placeOrder).not.toHaveBeenCalled();
  });

  test('executes SELL order and displays INSUFFICIENT_POSITION error when selling more than held', async () => {
    const { api } = createStatefulMockApi(10000);
    render(<PaperTradingPage api={api} />);
    expect(await screen.findByTestId('paper-cash-balance')).toHaveTextContent('$10,000.00 USD');

    fireEvent.change(screen.getByLabelText('Security Symbol'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper BUY Order' }));
    expect(await screen.findByTestId('paper-position-AAPL')).toHaveTextContent('5');

    fireEvent.click(screen.getByRole('button', { name: 'SELL' }));
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper SELL Order' }));
    expect(await screen.findByTestId('paper-order-error')).toHaveTextContent(
      'not enough shares',
    );

    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Paper SELL Order' }));
    expect(await screen.findByTestId('paper-order-confirmation')).toHaveTextContent(
      'Filled: Paper SELL order for 2 shares of AAPL (NASDAQ)',
    );
    expect(screen.getByTestId('paper-position-AAPL')).toHaveTextContent('3');
  });
});

describe('createPaperTradingApi HTTP contract', () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  test('sends Bearer token, decodes envelopes, and handles 201 fill + 200 replay + 409 market closed', async () => {
    window.sessionStorage.setItem('finex_access_token', 'test-bearer-token-001');
    const filledOrder = makeOrder({ order_id: 'paper-order-http-1' });
    const accountPayload = makeAccount({
      cash_balance: '7998.00',
      portfolio_value: '2000.00',
      total_equity: '9998.00',
      recent_orders: [filledOrder],
    });

    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce({
        status: 201,
        ok: true,
        json: async () => ({
          success: true,
          message: 'Paper order filled',
          data: filledOrder,
          meta: { apiVersion: 'v1', dataStatus: 'DELAYED', dataAsOf: null, correlationId: 'c1' },
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          success: true,
          message: 'Paper order replayed',
          data: filledOrder,
          meta: { apiVersion: 'v1', dataStatus: 'DELAYED', dataAsOf: null, correlationId: 'c2' },
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          success: true,
          message: 'Paper account retrieved',
          data: accountPayload,
          meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null, correlationId: 'c3' },
        }),
      })
      .mockResolvedValueOnce({
        status: 409,
        ok: false,
        json: async () => ({
          success: false,
          error_code: 'MARKET_CLOSED',
          message: 'Paper orders are accepted only during regular market hours.',
          error: {
            code: 'MARKET_CLOSED',
            message: 'Paper orders are accepted only during regular market hours.',
            fieldErrors: [],
            correlationId: 'c4',
          },
        }),
      });

    const api = createPaperTradingApi({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      }),
    });

    const orderRequest: PaperOrderInput = {
      instrument_id: 'AAPL',
      exchange: 'NASDAQ',
      side: 'BUY',
      quantity: 10,
      idempotency_key: 'idemp-http-0001',
    };

    const first = await api.placeOrder(orderRequest);
    expect(first.replayed).toBe(false);
    expect(first.order.order_id).toBe('paper-order-http-1');

    const replay = await api.placeOrder(orderRequest);
    expect(replay.replayed).toBe(true);
    expect(replay.order.order_id).toBe('paper-order-http-1');

    const account = await api.getAccount();
    expect(account.cash_balance).toBe('7998.00');

    const [, firstInit] = mockFetch.mock.calls[0];
    expect((firstInit.headers as Record<string, string>).Authorization).toBe(
      'Bearer test-bearer-token-001',
    );
    expect(JSON.parse(firstInit.body as string)).toEqual(orderRequest);

    await expect(
      api.placeOrder({ ...orderRequest, idempotency_key: 'idemp-http-0002' }),
    ).rejects.toMatchObject({
      code: 'MARKET_CLOSED',
      status: 409,
      retryable: false,
    });
  });
});
