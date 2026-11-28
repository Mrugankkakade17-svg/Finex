import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createApiClient } from '../services/apiClient';
import {
  MAX_CSV_UPLOAD_BYTES,
  SpendingApi,
  SpendingApiError,
  SpendingPage,
  SpendingTransactionRecord,
  SpendingTrendRecord,
  createSpendingApi,
  validateCsvFileSelection,
} from './SpendingPage';

jest.mock(
  'recharts',
  () => {
    const React = require('react');
    const component = (name: string) => ({ children }: { children?: React.ReactNode }) =>
      React.createElement('div', { 'data-testid': `recharts-${name}` }, children);
    return {
      Bar: component('Bar'),
      BarChart: component('BarChart'),
      CartesianGrid: component('CartesianGrid'),
      ResponsiveContainer: component('ResponsiveContainer'),
      Tooltip: component('Tooltip'),
      XAxis: component('XAxis'),
      YAxis: component('YAxis'),
    };
  },
  { virtual: true },
);

function makeTransactions(): SpendingTransactionRecord[] {
  return [
    {
      transaction_id: 'tx-001',
      date: '2026-10-05',
      description_masked: 'GROCERY STORE #***12',
      amount: '84.50',
      category: 'Groceries',
      is_user_corrected: false,
    },
    {
      transaction_id: 'tx-002',
      date: '2026-10-12',
      description_masked: 'ELECTRIC UTILITY CO #***99',
      amount: '115.00',
      category: 'Utilities',
      is_user_corrected: false,
    },
  ];
}

function makeTrends(overrides: Partial<SpendingTrendRecord> = {}): SpendingTrendRecord {
  return {
    period_start: '2026-10-01',
    period_end: '2026-10-31',
    total_spend: '199.50',
    monthly_trends: [
      {
        month: '2026-10',
        category: 'Utilities',
        total_amount: '115.00',
        transaction_count: 1,
        percentage_of_month: '57.6',
      },
      {
        month: '2026-10',
        category: 'Groceries',
        total_amount: '84.50',
        transaction_count: 1,
        percentage_of_month: '42.4',
      },
    ],
    top_categories: ['Utilities', 'Groceries'],
    privacy_disclosure:
      'Raw descriptions masked before AI categorization. Calculations are deterministic.',
    ...overrides,
  };
}

function makeMockApi(overrides: Partial<SpendingApi> = {}): jest.Mocked<SpendingApi> {
  return {
    listTransactions: jest.fn(async () => makeTransactions()),
    getTrends: jest.fn(async () => makeTrends()),
    importCsv: jest.fn(async (file) => ({
      upload_id: 'up-1',
      filename: file.name,
      total_rows_imported: 1,
      quarantined_rows: 0,
      total_spend_amount: '24.00',
      categories_detected: ['Dining'],
      status: 'PROCESSED',
    })),
    correctCategory: jest.fn(async (transactionId, correctedCategory) => ({
      transaction_id: transactionId,
      date: '2026-10-05',
      description_masked: 'GROCERY STORE #***12',
      amount: '84.50',
      category: correctedCategory,
      is_user_corrected: true,
    })),
    ...overrides,
  } as jest.Mocked<SpendingApi>;
}

describe('validateCsvFileSelection', () => {
  test('rejects missing, empty, oversized, and non-CSV files', () => {
    expect(validateCsvFileSelection(null)).toBe('Select a CSV file before uploading.');

    const empty = new File([], 'empty.csv', { type: 'text/csv' });
    expect(validateCsvFileSelection(empty)).toBe('The selected CSV file is empty.');

    const oversized = new File(['a'], 'big.csv', { type: 'text/csv' });
    Object.defineProperty(oversized, 'size', { value: MAX_CSV_UPLOAD_BYTES + 1 });
    expect(validateCsvFileSelection(oversized)).toBe('CSV exceeds the 5 MiB upload limit.');

    const wrongType = new File(['hello'], 'notes.txt', { type: 'text/plain' });
    expect(validateCsvFileSelection(wrongType)).toBe('Upload must be a .csv file.');

    const valid = new File(['date,description,amount,category\n'], 'bank.csv', {
      type: 'text/csv',
    });
    expect(validateCsvFileSelection(valid)).toBeNull();
  });
});

describe('SpendingPage', () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  test('renders real spending data without any hard-coded categories or fake upload numbers', async () => {
    const api = makeMockApi();
    render(<SpendingPage api={api} />);

    expect(screen.getByTestId('spending-loading')).toBeInTheDocument();
    expect(await screen.findByTestId('spending-total-spend')).toHaveTextContent('$199.50');
    expect(screen.getByTestId('spending-top-category')).toHaveTextContent('Utilities');
    expect(screen.getByTestId('spending-tx-count')).toHaveTextContent('2');
    expect(screen.getByTestId('spending-trends-chart')).toBeInTheDocument();

    expect(screen.queryByText('Housing & Utilities')).not.toBeInTheDocument();
    expect(screen.queryByText(/42 transactions categorized/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('table', { name: 'Monthly spending category table' })).toHaveTextContent(
      '57.6%',
    );
  });

  test('renders error state and retries loading spending endpoints', async () => {
    const api = makeMockApi({
      listTransactions: jest
        .fn()
        .mockRejectedValueOnce(
          new SpendingApiError('Authentication required', 'UNAUTHORIZED', { status: 401 }),
        )
        .mockResolvedValueOnce([]),
      getTrends: jest
        .fn()
        .mockRejectedValueOnce(
          new SpendingApiError('Authentication required', 'UNAUTHORIZED', { status: 401 }),
        )
        .mockResolvedValueOnce(
          makeTrends({
            total_spend: '0.00',
            monthly_trends: [],
            top_categories: [],
          }),
        ),
    });

    render(<SpendingPage api={api} />);

    expect(await screen.findByTestId('spending-error')).toHaveTextContent('Authentication required');
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

    expect(await screen.findByTestId('spending-empty')).toBeInTheDocument();
  });

  test('uploads real CSV file to import endpoint and refreshes transactions and trends', async () => {
    const transactionsAfterUpload: SpendingTransactionRecord[] = [
      ...makeTransactions(),
      {
        transaction_id: 'tx-003',
        date: '2026-10-25',
        description_masked: 'CAFE #***',
        amount: '24.00',
        category: 'Dining',
        is_user_corrected: false,
      },
    ];
    const trendsAfterUpload = makeTrends({
      total_spend: '223.50',
      top_categories: ['Utilities', 'Groceries', 'Dining'],
      monthly_trends: [
        ...makeTrends().monthly_trends,
        {
          month: '2026-10',
          category: 'Dining',
          total_amount: '24.00',
          transaction_count: 1,
          percentage_of_month: '10.7',
        },
      ],
    });

    const api = makeMockApi({
      listTransactions: jest
        .fn()
        .mockResolvedValueOnce(makeTransactions())
        .mockResolvedValueOnce(transactionsAfterUpload),
      getTrends: jest
        .fn()
        .mockResolvedValueOnce(makeTrends())
        .mockResolvedValueOnce(trendsAfterUpload),
    });

    render(<SpendingPage api={api} />);
    await screen.findByTestId('spending-total-spend');

    fireEvent.click(screen.getByRole('button', { name: /Upload CSV Statement/i }));
    expect(await screen.findByTestId('csv-upload-error')).toHaveTextContent(
      'Select a CSV file before uploading.',
    );

    const file = new File(
      ['date,description,amount,category\n2026-10-25,CAFE 1234,24.00,Dining\n'],
      'october.csv',
      { type: 'text/csv' },
    );
    fireEvent.change(screen.getByLabelText('Select spending CSV file'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: /Upload CSV Statement/i }));

    await waitFor(() => {
      expect(api.importCsv).toHaveBeenCalledWith(file);
    });
    expect(await screen.findByTestId('csv-import-summary')).toHaveTextContent('october.csv');
    expect(screen.getByTestId('csv-import-summary')).toHaveTextContent('Dining');
    expect(await screen.findByTestId('spending-total-spend')).toHaveTextContent('$223.50');
    expect(screen.getByTestId('spending-tx-tx-003')).toHaveTextContent('CAFE #***');
  });

  test('corrects transaction category and updates trends', async () => {
    const updatedTrends = makeTrends({
      monthly_trends: [
        {
          month: '2026-10',
          category: 'Utilities',
          total_amount: '115.00',
          transaction_count: 1,
          percentage_of_month: '57.6',
        },
        {
          month: '2026-10',
          category: 'Food & Market',
          total_amount: '84.50',
          transaction_count: 1,
          percentage_of_month: '42.4',
        },
      ],
    });
    const api = makeMockApi({
      getTrends: jest.fn().mockResolvedValueOnce(makeTrends()).mockResolvedValueOnce(updatedTrends),
    });

    render(<SpendingPage api={api} />);
    await screen.findByTestId('spending-tx-tx-001');

    const txRow = screen.getByTestId('spending-tx-tx-001');
    fireEvent.click(txRow.querySelector('button') as HTMLButtonElement);

    const input = screen.getByLabelText('New category for GROCERY STORE #***12');
    fireEvent.change(input, { target: { value: 'Food & Market' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.correctCategory).toHaveBeenCalledWith('tx-001', 'Food & Market');
    });
    expect(await screen.findByTestId('spending-tx-tx-001')).toHaveTextContent('Corrected');
    expect(screen.getByTestId('trend-row-Food & Market')).toBeInTheDocument();
  });

  test('createSpendingApi sends multipart FormData and Bearer token to /api/v1/spending/imports', async () => {
    window.sessionStorage.setItem('finex_access_token', 'spending-bearer-token');
    const fetchMock = jest.fn<Promise<Response>, [RequestInfo | URL, RequestInit?]>(
      async (_url: RequestInfo | URL, _init?: RequestInit) => {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            success: true,
            message: 'Spending CSV imported',
            data: {
              upload_id: 'up-99',
              filename: 'statement.csv',
              total_rows_imported: 2,
              quarantined_rows: 1,
              total_spend_amount: '45.50',
              categories_detected: ['Food'],
              status: 'PROCESSED',
            },
          }),
        } as Response;
      },
    );

    const api = createSpendingApi({
      apiClient: createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
    });

    const csvFile = new File(['date,description,amount,category\n'], 'statement.csv', {
      type: 'text/csv',
    });
    const summary = await api.importCsv(csvFile);

    expect(summary.total_rows_imported).toBe(2);
    expect(summary.quarantined_rows).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8000/api/v1/spending/imports');
    expect(init?.method).toBe('POST');
    expect(init?.body).toBeInstanceOf(FormData);
    expect(init?.headers).toEqual(
      expect.objectContaining({
        Accept: 'application/json',
        Authorization: 'Bearer spending-bearer-token',
      }),
    );
    expect((init?.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });
});
