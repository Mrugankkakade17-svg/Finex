import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Edit3,
  RefreshCw,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ApiClient, ApiClientError, finexApiClient } from '../services/apiClient';
import { getActiveAuthSession } from '../services/authService';

export const MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024;
const ALLOWED_CSV_MIME_TYPES = new Set([
  'text/csv',
  'application/csv',
  'application/vnd.ms-excel',
]);

export interface SpendingTransactionRecord {
  transaction_id: string;
  date: string;
  description_masked: string;
  amount: string;
  category: string;
  is_user_corrected: boolean;
}

export interface MonthlyCategoryTrendRecord {
  month: string;
  category: string;
  total_amount: string;
  transaction_count: number;
  percentage_of_month: string;
}

export interface SpendingTrendRecord {
  period_start: string;
  period_end: string;
  total_spend: string;
  monthly_trends: MonthlyCategoryTrendRecord[];
  top_categories: string[];
  privacy_disclosure: string;
}

export interface SpendingUploadSummaryRecord {
  upload_id: string;
  filename: string;
  total_rows_imported: number;
  quarantined_rows: number;
  total_spend_amount: string;
  categories_detected: string[];
  status: string;
}

export interface SpendingApi {
  listTransactions(signal?: AbortSignal): Promise<SpendingTransactionRecord[]>;
  getTrends(signal?: AbortSignal): Promise<SpendingTrendRecord>;
  importCsv(file: File, signal?: AbortSignal): Promise<SpendingUploadSummaryRecord>;
  correctCategory(
    transactionId: string,
    correctedCategory: string,
    signal?: AbortSignal,
  ): Promise<SpendingTransactionRecord>;
}

export interface SpendingApiConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

export class SpendingApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly retryable: boolean;

  constructor(
    message: string,
    code = 'API_UNAVAILABLE',
    options?: { status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = 'SpendingApiError';
    this.code = code;
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
  }
}

export interface SpendingPageProps {
  api?: SpendingApi;
}

const DEFAULT_TIMEOUT_MS = 8000;
const NON_RETRYABLE_CODES = new Set([
  'UNAUTHORIZED',
  'FORBIDDEN',
  'TRANSACTION_NOT_FOUND',
  'VALIDATION_ERROR',
  'CSV_INVALID',
  'CSV_TOO_LARGE',
  'UNSUPPORTED_MEDIA_TYPE',
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
    throw new SpendingApiError(`Invalid ${field} received from spending API.`, 'RESPONSE_INVALID');
  }
  return value.trim();
}

function asDecimalString(value: unknown, field: string): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2);
  }
  if (typeof value === 'string' && value.trim().length > 0 && Number.isFinite(Number(value))) {
    return value.trim();
  }
  throw new SpendingApiError(`Invalid ${field} received from spending API.`, 'RESPONSE_INVALID');
}

function asNumber(value: unknown, field: string): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  throw new SpendingApiError(`Invalid ${field} received from spending API.`, 'RESPONSE_INVALID');
}

function decodeTransaction(raw: unknown): SpendingTransactionRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new SpendingApiError('Invalid transaction payload from spending API.', 'RESPONSE_INVALID');
  }
  return {
    transaction_id: asRequiredString(rec.transaction_id, 'transaction_id'),
    date: asRequiredString(rec.date, 'date'),
    description_masked: asRequiredString(rec.description_masked, 'description_masked'),
    amount: asDecimalString(rec.amount, 'amount'),
    category: asRequiredString(rec.category, 'category'),
    is_user_corrected: rec.is_user_corrected === true,
  };
}

function decodeTrendItem(raw: unknown): MonthlyCategoryTrendRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new SpendingApiError('Invalid trend row from spending API.', 'RESPONSE_INVALID');
  }
  return {
    month: asRequiredString(rec.month, 'month'),
    category: asRequiredString(rec.category, 'category'),
    total_amount: asDecimalString(rec.total_amount, 'total_amount'),
    transaction_count: asNumber(rec.transaction_count, 'transaction_count'),
    percentage_of_month: asDecimalString(rec.percentage_of_month, 'percentage_of_month'),
  };
}

function decodeTrends(raw: unknown): SpendingTrendRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new SpendingApiError('Invalid spending trends payload from API.', 'RESPONSE_INVALID');
  }
  return {
    period_start: asRequiredString(rec.period_start, 'period_start'),
    period_end: asRequiredString(rec.period_end, 'period_end'),
    total_spend: asDecimalString(rec.total_spend, 'total_spend'),
    monthly_trends: Array.isArray(rec.monthly_trends)
      ? rec.monthly_trends.map(decodeTrendItem)
      : [],
    top_categories: Array.isArray(rec.top_categories)
      ? rec.top_categories.filter((c): c is string => typeof c === 'string' && c.trim().length > 0)
      : [],
    privacy_disclosure:
      typeof rec.privacy_disclosure === 'string' && rec.privacy_disclosure.trim().length > 0
        ? rec.privacy_disclosure
        : 'Raw descriptions masked before AI categorization. Calculations are deterministic.',
  };
}

function decodeUploadSummary(raw: unknown): SpendingUploadSummaryRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new SpendingApiError('Invalid CSV upload summary from API.', 'RESPONSE_INVALID');
  }
  return {
    upload_id: asRequiredString(rec.upload_id, 'upload_id'),
    filename: asRequiredString(rec.filename, 'filename'),
    total_rows_imported: asNumber(rec.total_rows_imported, 'total_rows_imported'),
    quarantined_rows: asNumber(rec.quarantined_rows, 'quarantined_rows'),
    total_spend_amount: asDecimalString(rec.total_spend_amount, 'total_spend_amount'),
    categories_detected: Array.isArray(rec.categories_detected)
      ? rec.categories_detected.filter((c): c is string => typeof c === 'string')
      : [],
    status: typeof rec.status === 'string' && rec.status.trim() ? rec.status.trim() : 'PROCESSED',
  };
}

function mapSpendingError(
  status: number,
  code: string,
  serverMessage?: string,
): SpendingApiError {
  if (status === 401 || code === 'UNAUTHORIZED') {
    return new SpendingApiError(
      serverMessage || 'Sign in with an active FinEx session to access spending insights.',
      'UNAUTHORIZED',
      { status, retryable: false },
    );
  }
  if (status === 404 || code === 'TRANSACTION_NOT_FOUND') {
    return new SpendingApiError(
      serverMessage || 'Transaction not found for this account.',
      'TRANSACTION_NOT_FOUND',
      { status, retryable: false },
    );
  }
  if (status === 413) {
    return new SpendingApiError(
      serverMessage || 'CSV exceeds the 5 MiB upload limit.',
      'CSV_TOO_LARGE',
      { status, retryable: false },
    );
  }
  if (status === 415) {
    return new SpendingApiError(
      serverMessage || 'Upload must be a CSV file.',
      'UNSUPPORTED_MEDIA_TYPE',
      { status, retryable: false },
    );
  }
  if (status === 400 || status === 422 || code === 'VALIDATION_ERROR') {
    return new SpendingApiError(
      serverMessage || 'Check the request inputs or CSV structure and try again.',
      status === 400 ? 'CSV_INVALID' : 'VALIDATION_ERROR',
      { status, retryable: false },
    );
  }
  const retryable = status >= 500 || !NON_RETRYABLE_CODES.has(code);
  return new SpendingApiError(
    serverMessage || 'Unable to complete the spending request.',
    code || 'SPENDING_REQUEST_FAILED',
    { status, retryable },
  );
}

export function createSpendingApi(config: SpendingApiConfig = {}): SpendingApi {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const getAuthToken = config.getAuthToken ?? resolveDefaultAuthToken;

  async function requestEnvelope(
    path: string,
    method: 'GET' | 'POST',
    options: { jsonBody?: unknown; formData?: FormData; signal?: AbortSignal } = {},
  ): Promise<unknown> {
    const { jsonBody, formData, signal } = options;
    if (signal?.aborted) {
      throw new SpendingApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
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
      let body: BodyInit | undefined;
      if (formData !== undefined) {
        body = formData;
      } else if (jsonBody !== undefined) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(jsonBody);
      }

      const token = getAuthToken();
      const response = await client.request(path, {
        method,
        headers,
        body,
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
            : response.status === 404
              ? 'TRANSACTION_NOT_FOUND'
              : response.status === 422
                ? 'VALIDATION_ERROR'
                : 'API_ERROR');
        const serverMessage =
          (typeof errorDetail?.message === 'string' && errorDetail.message) ||
          (typeof record?.message === 'string' && record.message) ||
          (typeof record?.detail === 'string' && record.detail) ||
          undefined;
        throw mapSpendingError(response.status, serverCode, serverMessage);
      }

      if (!record || record.success !== true || !('data' in record)) {
        throw new SpendingApiError(
          'Received an unexpected response format from the spending API.',
          'RESPONSE_INVALID',
          { status: response.status, retryable: true },
        );
      }

      return record.data;
    } catch (error) {
      if (error instanceof SpendingApiError) throw error;
      if (timedOut) {
        throw new SpendingApiError(
          'The spending request timed out. Please retry.',
          'REQUEST_TIMEOUT',
          { retryable: true },
        );
      }
      if (signal?.aborted) {
        throw new SpendingApiError('The request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (error instanceof ApiClientError) {
        throw new SpendingApiError(error.message, error.code, { retryable: true });
      }
      throw new SpendingApiError(
        'Spending service is temporarily unreachable. Check the backend and retry.',
        'API_UNAVAILABLE',
        { retryable: true },
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onCallerAbort);
    }
  }

  return {
    async listTransactions(signal?: AbortSignal): Promise<SpendingTransactionRecord[]> {
      const data = await requestEnvelope('/api/v1/spending/transactions', 'GET', { signal });
      if (!Array.isArray(data)) {
        throw new SpendingApiError(
          'Expected a list of transactions from the API.',
          'RESPONSE_INVALID',
        );
      }
      return data.map(decodeTransaction);
    },

    async getTrends(signal?: AbortSignal): Promise<SpendingTrendRecord> {
      const data = await requestEnvelope('/api/v1/spending/trends', 'GET', { signal });
      return decodeTrends(data);
    },

    async importCsv(file: File, signal?: AbortSignal): Promise<SpendingUploadSummaryRecord> {
      const normalizedType = file.type.split(';')[0].trim().toLowerCase();
      const uploadFile =
        !normalizedType && file.name.toLowerCase().endsWith('.csv')
          ? new File([file], file.name, { type: 'text/csv' })
          : file;
      const formData = new FormData();
      formData.append('file', uploadFile);
      const data = await requestEnvelope('/api/v1/spending/imports', 'POST', {
        formData,
        signal,
      });
      return decodeUploadSummary(data);
    },

    async correctCategory(
      transactionId: string,
      correctedCategory: string,
      signal?: AbortSignal,
    ): Promise<SpendingTransactionRecord> {
      const data = await requestEnvelope('/api/v1/spending/correct-category', 'POST', {
        jsonBody: {
          transaction_id: transactionId,
          corrected_category: correctedCategory,
        },
        signal,
      });
      return decodeTransaction(data);
    },
  };
}

export const defaultSpendingApi = createSpendingApi();

function toNum(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatUsd(value: string | number | null | undefined): string {
  const parsed = toNum(value);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

export function validateCsvFileSelection(file: File | null): string | null {
  if (!file) {
    return 'Select a CSV file before uploading.';
  }
  if (file.size <= 0) {
    return 'The selected CSV file is empty.';
  }
  if (file.size > MAX_CSV_UPLOAD_BYTES) {
    return 'CSV exceeds the 5 MiB upload limit.';
  }
  const normalizedType = file.type.split(';')[0].trim().toLowerCase();
  const hasCsvExtension = file.name.toLowerCase().endsWith('.csv');
  if (!hasCsvExtension && !ALLOWED_CSV_MIME_TYPES.has(normalizedType)) {
    return 'Upload must be a .csv file.';
  }
  if (normalizedType && !ALLOWED_CSV_MIME_TYPES.has(normalizedType) && !hasCsvExtension) {
    return 'Upload must be a .csv file.';
  }
  return null;
}

export const SpendingPage: React.FC<SpendingPageProps> = ({ api = defaultSpendingApi }) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [transactions, setTransactions] = useState<SpendingTransactionRecord[]>([]);
  const [trends, setTrends] = useState<SpendingTrendRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSummary, setUploadSummary] = useState<SpendingUploadSummaryRecord | null>(null);

  const [breakdownView, setBreakdownView] = useState<'chart' | 'table'>('chart');

  const [editingTxId, setEditingTxId] = useState<string | null>(null);
  const [categoryInput, setCategoryInput] = useState('');
  const [savingCategory, setSavingCategory] = useState(false);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const loadSpendingData = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [txList, trendData] = await Promise.all([
          api.listTransactions(signal),
          api.getTrends(signal),
        ]);
        if (signal?.aborted) return;
        setTransactions(txList);
        setTrends(trendData);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof SpendingApiError && err.code === 'REQUEST_CANCELLED') return;
        setError({
          message: err instanceof Error ? err.message : 'Unable to load spending data.',
          code: err instanceof SpendingApiError ? err.code : undefined,
        });
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [api],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadSpendingData(controller.signal);
    return () => controller.abort();
  }, [loadSpendingData]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    setUploadError(null);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadError(null);

    const validationError = validateCsvFileSelection(selectedFile);
    if (validationError || !selectedFile) {
      setUploadError(validationError ?? 'Select a CSV file before uploading.');
      return;
    }

    setUploading(true);
    try {
      const summary = await api.importCsv(selectedFile);
      setUploadSummary(summary);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      await loadSpendingData();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'CSV upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const startEditingCategory = (tx: SpendingTransactionRecord) => {
    setEditingTxId(tx.transaction_id);
    setCategoryInput(tx.category);
    setCategoryError(null);
  };

  const handleSaveCategory = async (e: React.FormEvent, transactionId: string) => {
    e.preventDefault();
    setCategoryError(null);
    const cleaned = categoryInput.trim();
    if (cleaned.length < 2 || cleaned.length > 50) {
      setCategoryError('Category must be between 2 and 50 characters.');
      return;
    }

    setSavingCategory(true);
    try {
      const updated = await api.correctCategory(transactionId, cleaned);
      setTransactions((prev) =>
        prev.map((tx) => (tx.transaction_id === transactionId ? updated : tx)),
      );
      setEditingTxId(null);
      const refreshedTrends = await api.getTrends();
      setTrends(refreshedTrends);
    } catch (err) {
      setCategoryError(err instanceof Error ? err.message : 'Unable to update category.');
    } finally {
      setSavingCategory(false);
    }
  };

  const sortedTrends = useMemo(() => {
    const items = trends?.monthly_trends ?? [];
    return [...items].sort((a, b) => toNum(b.total_amount) - toNum(a.total_amount));
  }, [trends]);

  const chartData = useMemo(
    () =>
      sortedTrends.map((item) => ({
        category: item.category,
        totalAmount: toNum(item.total_amount),
        percentage: toNum(item.percentage_of_month),
        count: item.transaction_count,
      })),
    [sortedTrends],
  );

  return (
    <div>
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
          <p className="local-eyebrow">SPEND WITH INTENTION</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Spending Trends &amp; Statement Import
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Principal-scoped CSV import, PII description masking, and deterministic category totals
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
          <span className="badge badge-info" data-testid="spending-capability-badge">
            <ShieldCheck size={13} aria-hidden="true" /> ANALYTICAL · Privacy Shield Active
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadSpendingData()}
            disabled={loading}
          >
            <RefreshCw size={15} aria-hidden="true" /> Refresh
          </button>
        </div>
      </div>

      <section
        aria-label="Spending privacy disclosure"
        className="glass-card"
        style={{
          padding: '14px 18px',
          marginBottom: '22px',
          borderLeft: '4px solid var(--color-accent-coral)',
          fontSize: '0.86rem',
          color: 'var(--color-text-muted)',
        }}
      >
        <strong style={{ color: 'var(--color-text)' }}>Privacy &amp; Safety Guard:</strong>{' '}
        {trends?.privacy_disclosure ??
          'Raw descriptions masked before storage and categorization. Calculations are deterministic.'}{' '}
        CSV uploads enforce a 5 MiB limit, 5,000-row cap, and formula-prefix escaping.
      </section>

      {loading ? (
        <div
          role="status"
          data-testid="spending-loading"
          className="glass-card"
          style={{ padding: '36px', textAlign: 'center', color: 'var(--color-text-muted)' }}
        >
          Loading masked spending transactions and monthly trends…
        </div>
      ) : error ? (
        <div
          role="alert"
          data-testid="spending-error"
          className="glass-card"
          style={{
            padding: '24px',
            border: '1px solid rgba(217, 72, 59, 0.45)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#B42318' }}>
            <AlertTriangle size={20} aria-hidden="true" />
            <div>
              <strong>Unable to load spending data.</strong> {error.message}
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadSpendingData()}
          >
            <RefreshCw size={14} aria-hidden="true" /> Retry
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Summary KPI strip */}
          <div
            data-testid="spending-kpi-strip"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '14px',
            }}
          >
            <div className="glass-card" style={{ padding: '18px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                Total Spend
              </div>
              <div
                data-testid="spending-total-spend"
                style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--color-text)' }}
              >
                {formatUsd(trends?.total_spend ?? '0')}
              </div>
            </div>
            <div className="glass-card" style={{ padding: '18px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                Reporting Period
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--color-text)' }}>
                {trends ? `${trends.period_start} to ${trends.period_end}` : 'Unavailable'}
              </div>
            </div>
            <div className="glass-card" style={{ padding: '18px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                Top Category
              </div>
              <div
                data-testid="spending-top-category"
                style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--color-text)' }}
              >
                {trends?.top_categories[0] ?? 'None'}
              </div>
            </div>
            <div className="glass-card" style={{ padding: '18px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                Transactions
              </div>
              <div
                data-testid="spending-tx-count"
                style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--color-text)' }}
              >
                {transactions.length}
              </div>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '24px',
            }}
          >
            {/* Real CSV Upload Card */}
            <section
              className="glass-card"
              data-testid="csv-upload-section"
              aria-label="Import bank CSV statements"
              style={{ padding: '24px' }}
            >
              <h3
                style={{
                  fontSize: '1.2rem',
                  color: 'var(--color-text)',
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <Upload size={19} color="var(--color-accent-coral)" aria-hidden="true" /> Import CSV
                Statements
              </h3>
              <p
                style={{
                  fontSize: '0.84rem',
                  color: 'var(--color-text-muted)',
                  marginBottom: '16px',
                }}
              >
                Required columns: <code>date</code> (YYYY-MM-DD), <code>description</code>,{' '}
                <code>amount</code>, <code>category</code>.
              </p>

              <form onSubmit={handleUploadSubmit}>
                <label
                  htmlFor="spending-csv-file"
                  style={{
                    display: 'block',
                    padding: '24px',
                    borderRadius: '14px',
                    border: '2px dashed var(--color-accent-violet)',
                    background: 'var(--color-surface-elevated)',
                    textAlign: 'center',
                    cursor: 'pointer',
                    marginBottom: '14px',
                  }}
                >
                  <CreditCard
                    size={30}
                    color="var(--color-accent-coral)"
                    style={{ margin: '0 auto 10px' }}
                    aria-hidden="true"
                  />
                  <div style={{ color: 'var(--color-text)', fontWeight: 700, marginBottom: '4px' }}>
                    {selectedFile ? selectedFile.name : 'Choose a CSV statement file'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                    {selectedFile
                      ? `${selectedFile.size.toLocaleString()} bytes ready for import`
                      : 'Max 5 MiB · Up to 5,000 rows · Invalid rows are quarantined safely'}
                  </div>
                </label>

                <input
                  ref={fileInputRef}
                  id="spending-csv-file"
                  type="file"
                  accept=".csv,text/csv"
                  aria-label="Select spending CSV file"
                  onChange={handleFileChange}
                  style={{ marginBottom: '14px', width: '100%' }}
                />

                {uploadError && (
                  <div
                    role="alert"
                    data-testid="csv-upload-error"
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      background: 'rgba(217, 72, 59, 0.12)',
                      border: '1px solid rgba(217, 72, 59, 0.4)',
                      color: '#B42318',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      marginBottom: '12px',
                    }}
                  >
                    {uploadError}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={uploading}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  <Upload size={16} aria-hidden="true" />{' '}
                  {uploading ? 'Importing CSV…' : 'Upload CSV Statement'}
                </button>
              </form>

              {uploadSummary && (
                <div
                  data-testid="csv-import-summary"
                  role="status"
                  style={{
                    marginTop: '16px',
                    padding: '14px 16px',
                    borderRadius: '12px',
                    background: '#ECFDF5',
                    border: '1px solid #6EE7B7',
                    color: '#065F46',
                    fontSize: '0.86rem',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontWeight: 700,
                      marginBottom: '6px',
                    }}
                  >
                    <CheckCircle2 size={16} aria-hidden="true" />
                    Import {uploadSummary.status}: {uploadSummary.filename}
                  </div>
                  <div>
                    Imported <strong>{uploadSummary.total_rows_imported}</strong>{' '}
                    {uploadSummary.total_rows_imported === 1 ? 'row' : 'rows'} (
                    {formatUsd(uploadSummary.total_spend_amount)}) · Quarantined:{' '}
                    <strong>{uploadSummary.quarantined_rows}</strong>
                  </div>
                  {uploadSummary.categories_detected.length > 0 && (
                    <div style={{ marginTop: '4px' }}>
                      Categories: {uploadSummary.categories_detected.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* Category Breakdown Chart & Table */}
            <section
              className="glass-card"
              data-testid="spending-trends-section"
              aria-label="Monthly spending breakdown by category"
              style={{ padding: '24px' }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '10px',
                  marginBottom: '16px',
                }}
              >
                <h3 style={{ fontSize: '1.2rem', color: 'var(--color-text)', margin: 0 }}>
                  Monthly Breakdown
                </h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    aria-pressed={breakdownView === 'chart'}
                    className={breakdownView === 'chart' ? 'btn-primary' : 'btn-secondary'}
                    onClick={() => setBreakdownView('chart')}
                  >
                    Chart
                  </button>
                  <button
                    type="button"
                    aria-pressed={breakdownView === 'table'}
                    className={breakdownView === 'table' ? 'btn-primary' : 'btn-secondary'}
                    onClick={() => setBreakdownView('table')}
                  >
                    Table
                  </button>
                </div>
              </div>

              {sortedTrends.length === 0 ? (
                <p style={{ color: 'var(--color-text-muted)', padding: '24px 0' }}>
                  No category spending trends available yet. Upload a CSV statement to analyze
                  spending.
                </p>
              ) : breakdownView === 'chart' ? (
                <div>
                  <div
                    data-testid="spending-trends-chart"
                    role="img"
                    aria-label="Category spending bar chart"
                    style={{ width: '100%', height: 240, marginBottom: '14px' }}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        margin={{ top: 8, right: 12, left: 4, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#E6E8E7" />
                        <XAxis dataKey="category" tick={{ fill: '#667085', fontSize: 12 }} />
                        <YAxis
                          tickFormatter={(v: number) => `$${Math.round(v).toLocaleString('en-US')}`}
                          tick={{ fill: '#667085', fontSize: 12 }}
                          width={70}
                        />
                        <Tooltip
                          formatter={(value: unknown) => [formatUsd(Number(value)), 'Total']}
                        />
                        <Bar
                          dataKey="totalAmount"
                          name="Spend"
                          fill="#6366F1"
                          radius={[4, 4, 0, 0]}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div style={{ display: 'grid', gap: '10px' }}>
                    {sortedTrends.map((c) => (
                      <div
                        key={`${c.month}-${c.category}`}
                        data-testid={`trend-row-${c.category}`}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '10px 14px',
                          borderRadius: '12px',
                          background: 'var(--color-surface-elevated)',
                          border: '1px solid var(--color-surface-divider)',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>
                            {c.category}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                            {c.percentage_of_month}% · {c.transaction_count}{' '}
                            {c.transaction_count === 1 ? 'tx' : 'txs'}
                          </div>
                        </div>
                        <div style={{ fontWeight: 800, color: 'var(--color-accent-violet)' }}>
                          {formatUsd(c.total_amount)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table
                    aria-label="Monthly spending category table"
                    style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}
                  >
                    <thead>
                      <tr
                        style={{
                          borderBottom: '1px solid var(--color-surface-divider)',
                          textAlign: 'left',
                        }}
                      >
                        <th style={{ padding: '8px' }}>Category</th>
                        <th style={{ padding: '8px', textAlign: 'right' }}>Transactions</th>
                        <th style={{ padding: '8px', textAlign: 'right' }}>Share</th>
                        <th style={{ padding: '8px', textAlign: 'right' }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedTrends.map((c) => (
                        <tr
                          key={`${c.month}-${c.category}`}
                          style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                        >
                          <td style={{ padding: '8px', fontWeight: 600 }}>{c.category}</td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            {c.transaction_count}
                          </td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            {c.percentage_of_month}%
                          </td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            {formatUsd(c.total_amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          {/* Masked Transactions Table + Category Correction */}
          <section
            className="glass-card"
            data-testid="spending-transactions-section"
            aria-label="Masked spending transactions"
            style={{ padding: '24px' }}
          >
            <h3 style={{ fontSize: '1.2rem', color: 'var(--color-text)', marginBottom: '14px' }}>
              Masked Transactions
            </h3>

            {categoryError && (
              <div role="alert" style={{ color: '#B42318', fontWeight: 600, marginBottom: '12px' }}>
                {categoryError}
              </div>
            )}

            {transactions.length === 0 ? (
              <p
                data-testid="spending-empty"
                style={{ color: 'var(--color-text-muted)', padding: '16px 0' }}
              >
                No spending transactions recorded yet. Upload a CSV statement above to get started.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table
                  aria-label="Spending transactions list"
                  style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: '1px solid var(--color-surface-divider)',
                        textAlign: 'left',
                      }}
                    >
                      <th style={{ padding: '10px 8px' }}>Date</th>
                      <th style={{ padding: '10px 8px' }}>Description (Masked)</th>
                      <th style={{ padding: '10px 8px' }}>Category</th>
                      <th style={{ padding: '10px 8px', textAlign: 'right' }}>Amount</th>
                      <th style={{ padding: '10px 8px', textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => {
                      const isEditing = editingTxId === tx.transaction_id;
                      return (
                        <tr
                          key={tx.transaction_id}
                          data-testid={`spending-tx-${tx.transaction_id}`}
                          style={{ borderBottom: '1px solid var(--color-surface-divider)' }}
                        >
                          <td style={{ padding: '10px 8px', whiteSpace: 'nowrap' }}>{tx.date}</td>
                          <td style={{ padding: '10px 8px' }}>{tx.description_masked}</td>
                          <td style={{ padding: '10px 8px' }}>
                            {isEditing ? (
                              <form
                                onSubmit={(e) => void handleSaveCategory(e, tx.transaction_id)}
                                style={{ display: 'flex', gap: '6px', alignItems: 'center' }}
                              >
                                <input
                                  type="text"
                                  aria-label={`New category for ${tx.description_masked}`}
                                  value={categoryInput}
                                  onChange={(e) => setCategoryInput(e.target.value)}
                                  maxLength={50}
                                  style={{ minWidth: '120px', padding: '6px 8px' }}
                                />
                                <button
                                  type="submit"
                                  className="btn-primary"
                                  disabled={savingCategory}
                                  style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                                >
                                  {savingCategory ? 'Saving…' : 'Save'}
                                </button>
                                <button
                                  type="button"
                                  className="btn-secondary"
                                  onClick={() => {
                                    setEditingTxId(null);
                                    setCategoryError(null);
                                  }}
                                  style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                                >
                                  Cancel
                                </button>
                              </form>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                                <span>{tx.category}</span>
                                {tx.is_user_corrected && (
                                  <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>
                                    Corrected
                                  </span>
                                )}
                              </span>
                            )}
                          </td>
                          <td
                            style={{
                              padding: '10px 8px',
                              textAlign: 'right',
                              fontWeight: 700,
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {formatUsd(tx.amount)}
                          </td>
                          <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                            {!isEditing && (
                              <button
                                type="button"
                                className="btn-secondary"
                                onClick={() => startEditingCategory(tx)}
                                style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                              >
                                <Edit3 size={13} aria-hidden="true" /> Edit category
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
