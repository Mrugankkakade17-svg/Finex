import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  Briefcase,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';
import { ApiClient, ApiClientError, finexApiClient } from '../services/apiClient';
import { getActiveAuthSession } from '../services/authService';

export type PaperSide = 'BUY' | 'SELL';
export type PaperExchange = 'NASDAQ' | 'NYSE';
export type PaperQuoteFreshness = 'LIVE' | 'DELAYED' | 'CACHED';

export interface PaperPosition {
  instrument_id: string;
  exchange: PaperExchange | string;
  quantity: number;
  average_cost: string;
  last_price: string;
  market_value: string;
  unrealized_pnl: string;
}

export interface PaperOrder {
  order_id: string;
  instrument_id: string;
  exchange: PaperExchange | string;
  side: PaperSide;
  quantity: number;
  executed_price: string;
  notional: string;
  fee: string;
  cash_delta: string;
  status: 'FILLED';
  quote_freshness: PaperQuoteFreshness | string;
  quote_as_of: string | null;
  created_at: string;
  simulation_notice: string;
}

export interface PaperAccount {
  account_id: string;
  currency: 'USD' | string;
  cash_balance: string;
  portfolio_value: string;
  total_equity: string;
  positions: PaperPosition[];
  recent_orders: PaperOrder[];
  is_simulated: true;
}

export interface PaperOrderInput {
  instrument_id: string;
  exchange: PaperExchange;
  side: PaperSide;
  quantity: number;
  idempotency_key: string;
}

export interface PaperOrderSubmitResult {
  order: PaperOrder;
  replayed: boolean;
  message: string;
}

export interface PaperTradingApi {
  getAccount(signal?: AbortSignal): Promise<PaperAccount>;
  listOrders(limit?: number, signal?: AbortSignal): Promise<PaperOrder[]>;
  placeOrder(order: PaperOrderInput, signal?: AbortSignal): Promise<PaperOrderSubmitResult>;
}

export interface PaperTradingApiConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

export class PaperTradingApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly retryable: boolean;

  constructor(
    message: string,
    code = 'API_UNAVAILABLE',
    options?: { status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = 'PaperTradingApiError';
    this.code = code;
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
  }
}

export interface PaperTradingPageProps {
  api?: PaperTradingApi;
}

const SYMBOL_PATTERN = /^[A-Za-z0-9.^_-]{1,20}$/;
const MAX_ORDER_QUANTITY = 100_000;
const NON_RETRYABLE_CODES = new Set([
  'UNAUTHORIZED',
  'FORBIDDEN',
  'VALIDATION_ERROR',
  'MARKET_CLOSED',
  'INSUFFICIENT_CASH',
  'INSUFFICIENT_POSITION',
  'IDEMPOTENCY_KEY_REUSED',
  'QUOTE_CURRENCY_UNSUPPORTED',
  'ORDER_VALUE_TOO_SMALL',
]);

function readSessionStorageToken(): string | null {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage.getItem('finex_access_token');
    }
  } catch {
    return null;
  }
  return null;
}

function resolveDefaultAuthToken(): string | null {
  return getActiveAuthSession()?.access_token ?? readSessionStorageToken();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asRequiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new PaperTradingApiError(
      `Invalid ${field} received from paper trading API.`,
      'RESPONSE_INVALID',
    );
  }
  return value.trim();
}

function asMoneyString(value: unknown, field: string): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2);
  }
  if (typeof value === 'string' && value.trim().length > 0 && Number.isFinite(Number(value))) {
    return value.trim();
  }
  throw new PaperTradingApiError(
    `Invalid ${field} amount received from paper trading API.`,
    'RESPONSE_INVALID',
  );
}

function asInteger(value: unknown, field: string): number {
  if (typeof value === 'number' && Number.isInteger(value)) {
    return value;
  }
  throw new PaperTradingApiError(
    `Invalid ${field} integer received from paper trading API.`,
    'RESPONSE_INVALID',
  );
}

function decodePosition(raw: unknown): PaperPosition {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PaperTradingApiError('Invalid position entry in paper account.', 'RESPONSE_INVALID');
  }
  return {
    instrument_id: asRequiredString(rec.instrument_id, 'instrument_id'),
    exchange: asRequiredString(rec.exchange, 'exchange'),
    quantity: asInteger(rec.quantity, 'quantity'),
    average_cost: asMoneyString(rec.average_cost, 'average_cost'),
    last_price: asMoneyString(rec.last_price, 'last_price'),
    market_value: asMoneyString(rec.market_value, 'market_value'),
    unrealized_pnl: asMoneyString(rec.unrealized_pnl, 'unrealized_pnl'),
  };
}

function decodeOrder(raw: unknown): PaperOrder {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PaperTradingApiError('Invalid paper order payload.', 'RESPONSE_INVALID');
  }
  const side = asRequiredString(rec.side, 'side').toUpperCase();
  if (side !== 'BUY' && side !== 'SELL') {
    throw new PaperTradingApiError('Invalid order side in paper order.', 'RESPONSE_INVALID');
  }
  return {
    order_id: asRequiredString(rec.order_id, 'order_id'),
    instrument_id: asRequiredString(rec.instrument_id, 'instrument_id'),
    exchange: asRequiredString(rec.exchange, 'exchange'),
    side,
    quantity: asInteger(rec.quantity, 'quantity'),
    executed_price: asMoneyString(rec.executed_price, 'executed_price'),
    notional: asMoneyString(rec.notional, 'notional'),
    fee: asMoneyString(rec.fee, 'fee'),
    cash_delta: asMoneyString(rec.cash_delta, 'cash_delta'),
    status: 'FILLED',
    quote_freshness: asRequiredString(rec.quote_freshness, 'quote_freshness'),
    quote_as_of: typeof rec.quote_as_of === 'string' ? rec.quote_as_of : null,
    created_at: asRequiredString(rec.created_at, 'created_at'),
    simulation_notice:
      typeof rec.simulation_notice === 'string' && rec.simulation_notice.trim().length > 0
        ? rec.simulation_notice
        : 'SIMULATION ONLY: no real money or broker execution.',
  };
}

function decodeAccount(raw: unknown): PaperAccount {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PaperTradingApiError('Invalid paper account payload.', 'RESPONSE_INVALID');
  }
  const positions = Array.isArray(rec.positions) ? rec.positions.map(decodePosition) : [];
  const recentOrders = Array.isArray(rec.recent_orders)
    ? rec.recent_orders.map(decodeOrder)
    : [];
  return {
    account_id: asRequiredString(rec.account_id, 'account_id'),
    currency: typeof rec.currency === 'string' && rec.currency.trim() ? rec.currency.trim() : 'USD',
    cash_balance: asMoneyString(rec.cash_balance, 'cash_balance'),
    portfolio_value: asMoneyString(rec.portfolio_value, 'portfolio_value'),
    total_equity: asMoneyString(rec.total_equity, 'total_equity'),
    positions,
    recent_orders: recentOrders,
    is_simulated: true,
  };
}

function mapPaperError(status: number, code: string, serverMessage?: string): PaperTradingApiError {
  if (status === 401 || code === 'UNAUTHORIZED') {
    return new PaperTradingApiError(
      serverMessage || 'Sign in with an active FinEx session to access paper trading.',
      'UNAUTHORIZED',
      { status, retryable: false },
    );
  }
  if (code === 'IDEMPOTENCY_KEY_REUSED') {
    return new PaperTradingApiError(
      serverMessage ||
        'This order key was already used for a different order. Review your ticket and submit again.',
      code,
      { status, retryable: false },
    );
  }
  if (code === 'MARKET_CLOSED') {
    return new PaperTradingApiError(
      serverMessage || 'Paper orders are accepted only during regular NYSE/NASDAQ market hours.',
      code,
      { status, retryable: false },
    );
  }
  if (code === 'INSUFFICIENT_CASH') {
    return new PaperTradingApiError(
      serverMessage || 'Insufficient virtual cash for this order and estimated fee.',
      code,
      { status, retryable: false },
    );
  }
  if (code === 'INSUFFICIENT_POSITION') {
    return new PaperTradingApiError(
      serverMessage || 'You do not hold enough simulated shares to complete this SELL order.',
      code,
      { status, retryable: false },
    );
  }
  if (code === 'QUOTE_UNAVAILABLE' || code === 'QUOTE_INELIGIBLE') {
    return new PaperTradingApiError(
      serverMessage || 'An eligible market quote is unavailable; no simulated fill was created.',
      code,
      { status, retryable: true },
    );
  }
  if (code === 'PAPER_STORE_UNAVAILABLE' || status === 503) {
    return new PaperTradingApiError(
      serverMessage || 'Paper trading persistence is temporarily unavailable. Please retry.',
      code || 'PAPER_STORE_UNAVAILABLE',
      { status, retryable: true },
    );
  }
  const retryable = status >= 500 || !NON_RETRYABLE_CODES.has(code);
  return new PaperTradingApiError(
    serverMessage || 'The paper trading request could not be completed.',
    code || 'PAPER_REQUEST_FAILED',
    { status, retryable },
  );
}

export function createPaperTradingApi(config: PaperTradingApiConfig = {}): PaperTradingApi {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? 8000;
  const getAuthToken = config.getAuthToken ?? resolveDefaultAuthToken;

  async function requestEnvelope(
    path: string,
    method: 'GET' | 'POST',
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<{ status: number; message: string; data: unknown }> {
    if (signal?.aborted) {
      throw new PaperTradingApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
        retryable: true,
      });
    }

    const controller = new AbortController();
    let timedOut = false;
    const onCallerAbort = () => controller.abort();
    signal?.addEventListener('abort', onCallerAbort, { once: true });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    try {
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
      }
      const token = getAuthToken();
      const response = await client.request(path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        ...(token ? { accessToken: token } : {}),
      });

      const payload = await response.json().catch(() => null);
      const record = asRecord(payload);

      if (!response.ok) {
        const errorDetail = asRecord(record?.error);
        const serverCode =
          (typeof errorDetail?.code === 'string' && errorDetail.code) ||
          (typeof record?.error_code === 'string' && record.error_code) ||
          (response.status === 401
            ? 'UNAUTHORIZED'
            : response.status === 422
              ? 'VALIDATION_ERROR'
              : 'API_ERROR');
        const serverMessage =
          (typeof errorDetail?.message === 'string' && errorDetail.message) ||
          (typeof record?.message === 'string' && record.message) ||
          (typeof record?.detail === 'string' && record.detail) ||
          undefined;
        throw mapPaperError(response.status, serverCode, serverMessage);
      }

      if (!record || record.success !== true || !('data' in record)) {
        throw new PaperTradingApiError(
          'Received an unexpected response format from the paper trading API.',
          'RESPONSE_INVALID',
          { status: response.status, retryable: true },
        );
      }

      return {
        status: response.status,
        message: typeof record.message === 'string' ? record.message : 'Success',
        data: record.data,
      };
    } catch (error) {
      if (error instanceof PaperTradingApiError) {
        throw error;
      }
      if (timedOut) {
        throw new PaperTradingApiError(
          'The paper trading request timed out. You can safely retry.',
          'REQUEST_TIMEOUT',
          { retryable: true },
        );
      }
      if (signal?.aborted) {
        throw new PaperTradingApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (error instanceof ApiClientError) {
        throw new PaperTradingApiError(error.message, error.code, { retryable: true });
      }
      throw new PaperTradingApiError(
        'Paper trading is temporarily unreachable. Check the backend and retry.',
        'API_UNAVAILABLE',
        { retryable: true },
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onCallerAbort);
    }
  }

  return {
    async getAccount(signal?: AbortSignal): Promise<PaperAccount> {
      const result = await requestEnvelope('/api/v1/paper/account', 'GET', undefined, signal);
      return decodeAccount(result.data);
    },

    async listOrders(limit = 20, signal?: AbortSignal): Promise<PaperOrder[]> {
      const clampedLimit = Math.max(1, Math.min(100, Math.trunc(limit)));
      const result = await requestEnvelope(
        `/api/v1/paper/orders?limit=${clampedLimit}`,
        'GET',
        undefined,
        signal,
      );
      if (!Array.isArray(result.data)) {
        throw new PaperTradingApiError('Expected an array of paper orders.', 'RESPONSE_INVALID');
      }
      return result.data.map(decodeOrder);
    },

    async placeOrder(order: PaperOrderInput, signal?: AbortSignal): Promise<PaperOrderSubmitResult> {
      const result = await requestEnvelope('/api/v1/paper/orders', 'POST', order, signal);
      const decodedOrder = decodeOrder(result.data);
      const replayed = result.status === 200 || /replayed/i.test(result.message);
      return {
        order: decodedOrder,
        replayed,
        message: result.message,
      };
    },
  };
}

export const defaultPaperTradingApi = createPaperTradingApi();

function generateIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `paper-${globalThis.crypto.randomUUID()}`;
  }
  const randomSuffix = Math.random().toString(36).slice(2, 12);
  return `paper-${Date.now().toString(36)}-${randomSuffix}`;
}

function formatUsd(value: string | number): string {
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) {
    return '$0.00';
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function formatSignedUsd(value: string | number): string {
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) {
    return '$0.00';
  }
  const formatted = formatUsd(Math.abs(num));
  if (num > 0) return `+${formatted}`;
  if (num < 0) return `-${formatted}`;
  return formatted;
}

function formatPriceUsd(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '$0.00';
  }
  const hasSubCent = Math.abs(num * 100 - Math.round(num * 100)) > 0.0001;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: hasSubCent ? 4 : 2,
  }).format(num);
}

function formatTimestamp(iso: string): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) {
    return iso;
  }
  return new Date(parsed).toLocaleString();
}

export const PaperTradingPage: React.FC<PaperTradingPageProps> = ({
  api = defaultPaperTradingApi,
}) => {
  const [symbol, setSymbol] = useState('AAPL');
  const [exchange, setExchange] = useState<PaperExchange>('NASDAQ');
  const [quantity, setQuantity] = useState('10');
  const [orderType, setOrderType] = useState<PaperSide>('BUY');

  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshWarning, setRefreshWarning] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [lastSubmission, setLastSubmission] = useState<PaperOrderSubmitResult | null>(null);

  const mountedRef = useRef(true);
  const submittingRef = useRef(false);
  const pendingOrderKeyRef = useRef<{ signature: string; key: string } | null>(null);
  const loadEpochRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadPaperState = useCallback(
    async (options?: { silent?: boolean; signal?: AbortSignal }) => {
      const silent = options?.silent ?? false;
      const epoch = ++loadEpochRef.current;

      if (silent) {
        setRefreshing(true);
        setRefreshWarning(null);
      } else {
        setLoading(true);
        setLoadError(null);
        setRefreshWarning(null);
      }

      try {
        const [accountData, ordersData] = await Promise.all([
          api.getAccount(options?.signal),
          api.listOrders(20, options?.signal),
        ]);
        if (!mountedRef.current || options?.signal?.aborted || epoch !== loadEpochRef.current) {
          return false;
        }
        setAccount(accountData);
        setOrders(ordersData.length > 0 ? ordersData : accountData.recent_orders);
        setLoadError(null);
        setRefreshWarning(null);
        return true;
      } catch (err) {
        if (!mountedRef.current || options?.signal?.aborted || epoch !== loadEpochRef.current) {
          return false;
        }
        if (err instanceof PaperTradingApiError && err.code === 'REQUEST_CANCELLED') {
          return false;
        }
        const message =
          err instanceof Error
            ? err.message
            : 'Unable to load your simulated paper trading account.';
        if (silent) {
          setRefreshWarning(message);
        } else {
          setLoadError(message);
        }
        return false;
      } finally {
        if (mountedRef.current && epoch === loadEpochRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [api],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadPaperState({ signal: controller.signal });
    return () => controller.abort();
  }, [loadPaperState]);

  const positions = useMemo(() => account?.positions ?? [], [account]);

  const handleTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) {
      return;
    }

    setOrderError(null);

    const normalizedSymbol = symbol.trim().toUpperCase();
    if (!SYMBOL_PATTERN.test(normalizedSymbol)) {
      setOrderError(
        'Enter a valid ticker symbol (1-20 characters: letters, numbers, ".", "^", "_", "-").',
      );
      return;
    }

    const trimmedQuantity = quantity.trim();
    if (!/^\d+$/.test(trimmedQuantity)) {
      setOrderError('Quantity must be a whole positive number.');
      return;
    }

    const parsedQuantity = Number(trimmedQuantity);
    if (
      !Number.isSafeInteger(parsedQuantity) ||
      parsedQuantity < 1 ||
      parsedQuantity > MAX_ORDER_QUANTITY
    ) {
      setOrderError(
        `Quantity must be between 1 and ${MAX_ORDER_QUANTITY.toLocaleString('en-US')}.`,
      );
      return;
    }

    const signature = `${normalizedSymbol}|${exchange}|${orderType}|${parsedQuantity}`;
    if (!pendingOrderKeyRef.current || pendingOrderKeyRef.current.signature !== signature) {
      pendingOrderKeyRef.current = {
        signature,
        key: generateIdempotencyKey(),
      };
    }

    const payload: PaperOrderInput = {
      instrument_id: normalizedSymbol,
      exchange,
      side: orderType,
      quantity: parsedQuantity,
      idempotency_key: pendingOrderKeyRef.current.key,
    };

    submittingRef.current = true;
    setSubmitting(true);

    try {
      const result = await api.placeOrder(payload);
      if (!mountedRef.current) {
        return;
      }
      pendingOrderKeyRef.current = null;
      setLastSubmission(result);
      await loadPaperState({ silent: true });
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      if (err instanceof PaperTradingApiError && !err.retryable) {
        pendingOrderKeyRef.current = null;
      }
      setOrderError(
        err instanceof Error ? err.message : 'Unable to submit simulated paper order.',
      );
    } finally {
      submittingRef.current = false;
      if (mountedRef.current) {
        setSubmitting(false);
      }
    }
  };

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '20px',
        }}
      >
        <div>
          <p className="local-eyebrow">GROW WITH CONFIDENCE</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Paper Trading Simulator
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Practice market orders against eligible quotes with an append-only virtual USD ledger
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span className="badge badge-warning" data-testid="paper-simulated-badge">
            SIMULATED · Virtual USD
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void loadPaperState({ silent: account !== null });
            }}
            disabled={loading || refreshing}
          >
            <RefreshCw size={15} />
            {refreshing ? 'Refreshing…' : 'Reload account'}
          </button>
        </div>
      </div>

      {/* Mandatory SIMULATED capability banner */}
      <section
        role="status"
        aria-label="Simulated trading notice"
        data-testid="paper-simulated-banner"
        style={{
          marginBottom: '24px',
          padding: '16px 20px',
          borderRadius: '16px',
          background: 'rgba(230, 237, 115, 0.28)',
          border: '1.5px solid #C8D14B',
          color: 'var(--color-text)',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '14px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span className="badge badge-warning">SIMULATED</span>
            <strong>Paper Trading — Simulated Environment Only</strong>
          </div>
          <p style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', marginTop: '6px' }}>
            All cash balances, positions, fills, and ledger entries are simulated in virtual USD.
            No real money, brokerage routing, or licensed investment advice is involved, and
            simulated balances are kept strictly separate from manual portfolios.
          </p>
        </div>
        <ShieldAlert
          size={20}
          style={{ flexShrink: 0, color: 'var(--color-accent-violet)', marginTop: '2px' }}
          aria-hidden="true"
        />
      </section>

      {loading && (
        <div
          className="glass-card"
          data-testid="paper-loading"
          role="status"
          aria-busy="true"
          style={{ padding: '28px', marginBottom: '24px', color: 'var(--color-text-muted)' }}
        >
          Loading simulated paper trading account, positions, and ledger…
        </div>
      )}

      {!loading && loadError && (
        <div
          className="glass-card"
          data-testid="paper-load-error"
          role="alert"
          style={{
            padding: '24px',
            marginBottom: '24px',
            borderColor: '#FDA29B',
            background: '#FEF3F2',
            color: '#B42318',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle size={18} />
            <span>{loadError}</span>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void loadPaperState();
            }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {!loading && refreshWarning && (
        <div
          role="alert"
          data-testid="paper-refresh-warning"
          style={{
            marginBottom: '20px',
            padding: '12px 16px',
            borderRadius: '12px',
            background: '#FFFAEB',
            border: '1px solid #FEC84B',
            color: '#93370D',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px',
            flexWrap: 'wrap',
          }}
        >
          <span>{refreshWarning}</span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void loadPaperState({ silent: true });
            }}
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            Refresh now
          </button>
        </div>
      )}

      {!loading && account && (
        <>
          {/* Ticket & Account Summary */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
              gap: '24px',
              marginBottom: '24px',
            }}
          >
            {/* Order Entry Ticket */}
            <div className="glass-card" style={{ padding: '28px' }}>
              <h3
                style={{
                  fontSize: '1.25rem',
                  color: 'var(--color-text)',
                  marginBottom: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <TrendingUp size={20} color="var(--color-accent-coral)" /> Order Ticket
              </h3>

              <form
                onSubmit={(e) => {
                  void handleTrade(e);
                }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      color: 'var(--color-text)',
                      marginBottom: '6px',
                    }}
                  >
                    Order Side
                  </label>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                      type="button"
                      onClick={() => setOrderType('BUY')}
                      aria-pressed={orderType === 'BUY'}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: '999px',
                        border:
                          orderType === 'BUY'
                            ? '2px solid #16654E'
                            : '1.5px solid var(--color-surface-divider)',
                        background: orderType === 'BUY' ? '#ECFDF5' : 'var(--color-surface)',
                        color: orderType === 'BUY' ? '#16654E' : 'var(--color-text-muted)',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      BUY
                    </button>
                    <button
                      type="button"
                      onClick={() => setOrderType('SELL')}
                      aria-pressed={orderType === 'SELL'}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: '999px',
                        border:
                          orderType === 'SELL'
                            ? '2px solid var(--color-accent-coral)'
                            : '1.5px solid var(--color-surface-divider)',
                        background:
                          orderType === 'SELL'
                            ? 'rgba(255, 114, 94, 0.14)'
                            : 'var(--color-surface)',
                        color: orderType === 'SELL' ? '#B42318' : 'var(--color-text-muted)',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      SELL
                    </button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px' }}>
                  <div>
                    <label
                      htmlFor="paper-symbol-input"
                      style={{
                        display: 'block',
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        color: 'var(--color-text)',
                        marginBottom: '6px',
                      }}
                    >
                      Security Symbol
                    </label>
                    <input
                      id="paper-symbol-input"
                      aria-label="Security Symbol"
                      type="text"
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      placeholder="AAPL"
                      maxLength={20}
                      style={{ width: '100%' }}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="paper-exchange-select"
                      style={{
                        display: 'block',
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        color: 'var(--color-text)',
                        marginBottom: '6px',
                      }}
                    >
                      Exchange
                    </label>
                    <select
                      id="paper-exchange-select"
                      aria-label="Exchange"
                      value={exchange}
                      onChange={(e) => setExchange(e.target.value as PaperExchange)}
                      style={{ width: '100%' }}
                    >
                      <option value="NASDAQ">NASDAQ</option>
                      <option value="NYSE">NYSE</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="paper-quantity-input"
                    style={{
                      display: 'block',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      color: 'var(--color-text)',
                      marginBottom: '6px',
                    }}
                  >
                    Quantity
                  </label>
                  <input
                    id="paper-quantity-input"
                    aria-label="Quantity"
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    min="1"
                    max={MAX_ORDER_QUANTITY}
                    step="1"
                    style={{ width: '100%' }}
                  />
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submitting}
                  aria-busy={submitting}
                  style={{ marginTop: '8px', justifyContent: 'center' }}
                >
                  {submitting
                    ? `Submitting Paper ${orderType} Order…`
                    : `Submit Paper ${orderType} Order`}
                </button>
              </form>

              {orderError && (
                <div
                  role="alert"
                  data-testid="paper-order-error"
                  style={{
                    marginTop: '18px',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    background: '#FEF3F2',
                    border: '1px solid #FDA29B',
                    color: '#B42318',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px',
                  }}
                >
                  <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{orderError}</span>
                </div>
              )}

              {lastSubmission && (
                <div
                  role="status"
                  data-testid="paper-order-confirmation"
                  style={{
                    marginTop: '18px',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: '#ECFDF5',
                    border: '1px solid #6EE7B7',
                    color: '#065F46',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <CheckCircle2 size={16} />
                    <span>
                      {lastSubmission.replayed ? 'Idempotent replay:' : 'Filled:'} Paper{' '}
                      {lastSubmission.order.side} order for {lastSubmission.order.quantity} shares of{' '}
                      {lastSubmission.order.instrument_id} ({lastSubmission.order.exchange}) at{' '}
                      {formatPriceUsd(lastSubmission.order.executed_price)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.78rem', marginTop: '6px', opacity: 0.9 }}>
                    Order ID: {lastSubmission.order.order_id} · Fee:{' '}
                    {formatUsd(lastSubmission.order.fee)} · Cash Delta:{' '}
                    {formatSignedUsd(lastSubmission.order.cash_delta)} · Quote:{' '}
                    {lastSubmission.order.quote_freshness}
                  </div>
                </div>
              )}
            </div>

            {/* Simulated Cash & Equity Account */}
            <div className="glass-card" style={{ padding: '28px' }} data-testid="paper-account-card">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  marginBottom: '18px',
                }}
              >
                <h3 style={{ fontSize: '1.25rem', color: 'var(--color-text)' }}>
                  Virtual Cash Account
                </h3>
                <span
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                    fontWeight: 700,
                  }}
                >
                  {account.account_id}
                </span>
              </div>

              <div
                style={{
                  padding: '22px',
                  borderRadius: '16px',
                  background: 'var(--color-surface-elevated)',
                  border: '1px solid var(--color-surface-divider)',
                  marginBottom: '16px',
                }}
              >
                <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                  Current Virtual Cash ({account.currency})
                </div>
                <div
                  data-testid="paper-cash-balance"
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: '2.1rem',
                    fontWeight: 700,
                    color: 'var(--color-text)',
                    marginTop: '4px',
                  }}
                >
                  {formatUsd(account.cash_balance)} {account.currency}
                </div>
                <div
                  style={{
                    fontSize: '0.78rem',
                    color: 'var(--color-text-muted)',
                    marginTop: '4px',
                  }}
                >
                  Append-only simulated cash ledger — No real funds involved.
                </div>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  marginBottom: '18px',
                }}
              >
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: '14px',
                    background: 'var(--color-surface-elevated)',
                    border: '1px solid var(--color-surface-divider)',
                  }}
                >
                  <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                    Simulated Portfolio Value
                  </div>
                  <div
                    data-testid="paper-portfolio-value"
                    style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '4px' }}
                  >
                    {formatUsd(account.portfolio_value)}
                  </div>
                </div>

                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: '14px',
                    background: 'var(--color-surface-elevated)',
                    border: '1px solid var(--color-surface-divider)',
                  }}
                >
                  <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                    Simulated Total Equity
                  </div>
                  <div
                    data-testid="paper-total-equity"
                    style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text)', marginTop: '4px' }}
                  >
                    {formatUsd(account.total_equity)}
                  </div>
                </div>
              </div>

              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '14px',
                  background: 'rgba(230, 237, 115, 0.25)',
                  border: '1px solid #C8D14B',
                  color: 'var(--color-text)',
                  fontSize: '0.84rem',
                  display: 'flex',
                  gap: '10px',
                }}
              >
                <ShieldAlert
                  size={18}
                  style={{ flexShrink: 0, color: 'var(--color-accent-violet)', marginTop: '2px' }}
                />
                <div>
                  <strong>Financial Safety Rule:</strong> Paper trading is a simulated learning
                  sandbox. Order execution requires eligible non-stale quotes during regular market
                  hours and never calls real brokerages.
                </div>
              </div>
            </div>
          </div>

          {/* Open Simulated Positions */}
          <section
            className="glass-card"
            data-testid="paper-positions-section"
            style={{ padding: '26px', marginBottom: '24px' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '16px',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <h3
                style={{
                  fontSize: '1.2rem',
                  color: 'var(--color-text)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <Briefcase size={19} color="var(--color-accent-violet)" /> Simulated Positions
              </h3>
              <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                {positions.length} open {positions.length === 1 ? 'position' : 'positions'}
              </span>
            </div>

            {positions.length === 0 ? (
              <p
                data-testid="paper-positions-empty"
                style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}
              >
                No open simulated positions yet. Submit a BUY order to open a paper position.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                  <thead>
                    <tr
                      style={{
                        textAlign: 'left',
                        borderBottom: '1px solid var(--color-surface-divider)',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      <th style={{ padding: '10px 8px' }}>Symbol</th>
                      <th style={{ padding: '10px 8px' }}>Exchange</th>
                      <th style={{ padding: '10px 8px' }}>Quantity</th>
                      <th style={{ padding: '10px 8px' }}>Avg Cost</th>
                      <th style={{ padding: '10px 8px' }}>Last Price</th>
                      <th style={{ padding: '10px 8px' }}>Market Value</th>
                      <th style={{ padding: '10px 8px' }}>Unrealized P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos) => {
                      const pnl = Number(pos.unrealized_pnl);
                      const pnlPositive = Number.isFinite(pnl) && pnl >= 0;
                      return (
                        <tr
                          key={`${pos.instrument_id}-${pos.exchange}`}
                          data-testid={`paper-position-${pos.instrument_id}`}
                          style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                        >
                          <td style={{ padding: '12px 8px', fontWeight: 700 }}>
                            {pos.instrument_id}
                          </td>
                          <td style={{ padding: '12px 8px', color: 'var(--color-text-muted)' }}>
                            {pos.exchange}
                          </td>
                          <td style={{ padding: '12px 8px', fontWeight: 600 }}>{pos.quantity}</td>
                          <td style={{ padding: '12px 8px' }}>{formatPriceUsd(pos.average_cost)}</td>
                          <td style={{ padding: '12px 8px' }}>{formatPriceUsd(pos.last_price)}</td>
                          <td style={{ padding: '12px 8px', fontWeight: 700 }}>
                            {formatUsd(pos.market_value)}
                          </td>
                          <td
                            style={{
                              padding: '12px 8px',
                              fontWeight: 700,
                              color: pnlPositive ? '#16654E' : '#B42318',
                            }}
                          >
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              {pnlPositive ? (
                                <ArrowUpRight size={14} />
                              ) : (
                                <ArrowDownRight size={14} />
                              )}
                              {formatSignedUsd(pos.unrealized_pnl)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Append-only Paper Order & Cash Ledger */}
          <section
            className="glass-card"
            data-testid="paper-ledger-section"
            style={{ padding: '26px' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '16px',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <h3
                style={{
                  fontSize: '1.2rem',
                  color: 'var(--color-text)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <BookOpen size={19} color="var(--color-accent-coral)" /> Simulated Order &amp; Cash
                Ledger
              </h3>
              <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                {orders.length} recorded {orders.length === 1 ? 'entry' : 'entries'}
              </span>
            </div>

            {orders.length === 0 ? (
              <p
                data-testid="paper-ledger-empty"
                style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}
              >
                No paper orders executed yet. Opening cash allocation is recorded in your simulated
                ledger; placed orders will appear here.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}>
                  <thead>
                    <tr
                      style={{
                        textAlign: 'left',
                        borderBottom: '1px solid var(--color-surface-divider)',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      <th style={{ padding: '10px 8px' }}>Time</th>
                      <th style={{ padding: '10px 8px' }}>Order ID</th>
                      <th style={{ padding: '10px 8px' }}>Side</th>
                      <th style={{ padding: '10px 8px' }}>Symbol</th>
                      <th style={{ padding: '10px 8px' }}>Qty</th>
                      <th style={{ padding: '10px 8px' }}>Exec Price</th>
                      <th style={{ padding: '10px 8px' }}>Notional</th>
                      <th style={{ padding: '10px 8px' }}>Fee</th>
                      <th style={{ padding: '10px 8px' }}>Cash Delta</th>
                      <th style={{ padding: '10px 8px' }}>Quote</th>
                      <th style={{ padding: '10px 8px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((ord) => {
                      const deltaPositive = Number(ord.cash_delta) >= 0;
                      return (
                        <tr
                          key={ord.order_id}
                          data-testid={`paper-ledger-row-${ord.order_id}`}
                          style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                        >
                          <td style={{ padding: '12px 8px', color: 'var(--color-text-muted)' }}>
                            {formatTimestamp(ord.created_at)}
                          </td>
                          <td style={{ padding: '12px 8px', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                            {ord.order_id}
                          </td>
                          <td
                            style={{
                              padding: '12px 8px',
                              fontWeight: 700,
                              color: ord.side === 'BUY' ? '#16654E' : '#B42318',
                            }}
                          >
                            {ord.side}
                          </td>
                          <td style={{ padding: '12px 8px', fontWeight: 700 }}>
                            {ord.instrument_id} ({ord.exchange})
                          </td>
                          <td style={{ padding: '12px 8px' }}>{ord.quantity}</td>
                          <td style={{ padding: '12px 8px' }}>
                            {formatPriceUsd(ord.executed_price)}
                          </td>
                          <td style={{ padding: '12px 8px' }}>{formatUsd(ord.notional)}</td>
                          <td style={{ padding: '12px 8px' }}>{formatUsd(ord.fee)}</td>
                          <td
                            style={{
                              padding: '12px 8px',
                              fontWeight: 700,
                              color: deltaPositive ? '#16654E' : '#B42318',
                            }}
                          >
                            {formatSignedUsd(ord.cash_delta)}
                          </td>
                          <td style={{ padding: '12px 8px' }}>{ord.quote_freshness}</td>
                          <td style={{ padding: '12px 8px' }}>
                            <span className="badge badge-success">{ord.status}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};
