import crypto from 'node:crypto';
import http from 'node:http';

const PORT = Number(process.env.FINEX_E2E_API_PORT || '8010');
const ALLOWED_ORIGIN = process.env.FINEX_E2E_ALLOWED_ORIGIN || 'http://127.0.0.1:3000';

const LOCAL_SCOPE = 'local_educational_application';
const LOCAL_CONTRACT_VERSION = 'local.v1';
const LOCAL_PROFILE_VERSION = 'profile.v1';
const LOCAL_CONSENT_VERSION = 'consent.v1';
const INITIAL_CASH_CENTS = 5_000_000; // $50,000.00
const FEE_BPS = 10;

const FIXTURE_INSTRUMENTS = [
  { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', asset_class: 'EQUITY', currency: 'USD' },
  { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NASDAQ', asset_class: 'EQUITY', currency: 'USD' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ', asset_class: 'EQUITY', currency: 'USD' },
  { symbol: 'NVDA', name: 'NVIDIA Corporation', exchange: 'NASDAQ', asset_class: 'EQUITY', currency: 'USD' },
  { symbol: 'SPY', name: 'SPDR S&P 500 ETF Trust', exchange: 'NYSE', asset_class: 'ETF', currency: 'USD' },
  { symbol: 'RELIANCE', name: 'Reliance Industries Limited', exchange: 'NSE', asset_class: 'EQUITY', currency: 'INR' },
  { symbol: 'TCS', name: 'Tata Consultancy Services Limited', exchange: 'NSE', asset_class: 'EQUITY', currency: 'INR' },
];

const FIXTURE_QUOTES = {
  AAPL: { price: 227.16, currency: 'USD', change: 1.5, change_pct: 0.0075, freshness: 'CACHED', source: 'fixture' },
  MSFT: { price: 505.12, currency: 'USD', change: 2.3, change_pct: 0.0046, freshness: 'CACHED', source: 'fixture' },
  GOOGL: { price: 178.4, currency: 'USD', change: -0.8, change_pct: -0.0045, freshness: 'CACHED', source: 'fixture' },
  NVDA: { price: 128.5, currency: 'USD', change: 3.2, change_pct: 0.0255, freshness: 'DELAYED', source: 'yfinance-fixture' },
  SPY: { price: 560.25, currency: 'USD', change: 1.1, change_pct: 0.002, freshness: 'CACHED', source: 'fixture' },
  TSLA: { price: 242.84, currency: 'USD', change: -4.2, change_pct: -0.017, freshness: 'CACHED', source: 'fixture' },
  AMZN: { price: 186.4, currency: 'USD', change: 0.9, change_pct: 0.0049, freshness: 'CACHED', source: 'fixture' },
};

const USERS = {
  'learner-a': { id: 'local-learner-a', alias: 'learner-a' },
  'learner-b': { id: 'local-learner-b', alias: 'learner-b' },
};

function createInitialOnboardingState() {
  return {
    scope: LOCAL_SCOPE,
    contract_version: LOCAL_CONTRACT_VERSION,
    profile_schema_version: LOCAL_PROFILE_VERSION,
    consent_version: LOCAL_CONSENT_VERSION,
    consent: null,
    draft: {
      display_name: null,
      experience_level: null,
      updated_at: null,
    },
    onboarding_completed: false,
    completed_at: null,
  };
}

let sessions = new Map();
let onboardingByUser = new Map();
let watchlistsByUser = new Map();
let paperByUser = new Map();

function resetState() {
  sessions = new Map();
  onboardingByUser = new Map([
    ['local-learner-a', createInitialOnboardingState()],
    ['local-learner-b', createInitialOnboardingState()],
  ]);
  watchlistsByUser = new Map();
  paperByUser = new Map();
}

resetState();

function nowIso() {
  return new Date().toISOString();
}

function generateLocalToken() {
  return crypto.randomBytes(32).toString('base64url');
}

function getOrCreatePaperState(userId) {
  let state = paperByUser.get(userId);
  if (!state) {
    state = {
      accountId: `paper-${userId}`,
      cashCents: INITIAL_CASH_CENTS,
      positions: new Map(),
      orders: [],
      ordersByKey: new Map(),
    };
    paperByUser.set(userId, state);
  }
  return state;
}

function getOrCreateUserWatchlists(userId) {
  let lists = watchlistsByUser.get(userId);
  if (!lists) {
    lists = new Map();
    watchlistsByUser.set(userId, lists);
  }
  return lists;
}

function formatCents(cents) {
  return (cents / 100).toFixed(2);
}

function buildPaperAccountPayload(userId) {
  const state = getOrCreatePaperState(userId);
  let portfolioCents = 0;
  const positions = Array.from(state.positions.values()).map((pos) => {
    const quote = FIXTURE_QUOTES[pos.instrument_id];
    const lastPrice = quote ? quote.price : Number(pos.lastPrice);
    const marketCents = Math.round(pos.quantity * lastPrice * 100);
    portfolioCents += marketCents;
    const avgCost = pos.totalCostCents / 100 / pos.quantity;
    const pnlCents = marketCents - pos.totalCostCents;
    return {
      instrument_id: pos.instrument_id,
      exchange: pos.exchange,
      quantity: pos.quantity,
      average_cost: avgCost.toFixed(6),
      last_price: lastPrice.toFixed(6),
      market_value: formatCents(marketCents),
      unrealized_pnl: formatCents(pnlCents),
    };
  });

  return {
    account_id: state.accountId,
    currency: 'USD',
    cash_balance: formatCents(state.cashCents),
    portfolio_value: formatCents(portfolioCents),
    total_equity: formatCents(state.cashCents + portfolioCents),
    positions,
    recent_orders: state.orders.slice(0, 10),
    is_simulated: true,
  };
}

function sendJson(res, statusCode, body, correlationId) {
  const origin = ALLOWED_ORIGIN;
  res.writeHead(statusCode, {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Correlation-ID',
    'X-Correlation-ID': correlationId,
  });
  res.end(JSON.stringify(body));
}

function sendSuccess(res, statusCode, message, data, correlationId, dataStatus = 'CACHED') {
  sendJson(
    res,
    statusCode,
    {
      success: true,
      message,
      data,
      meta: {
        correlationId,
        apiVersion: 'v1',
        dataAsOf: null,
        dataStatus,
      },
    },
    correlationId,
  );
}

function sendError(res, statusCode, errorCode, message, correlationId) {
  sendJson(
    res,
    statusCode,
    {
      success: false,
      error_code: errorCode,
      message,
      error: {
        code: errorCode,
        message,
        correlationId,
      },
    },
    correlationId,
  );
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
      if (raw.length > 1_000_000) {
        reject(new Error('Body too large'));
      }
    });
    req.on('end', () => {
      if (!raw.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

function resolveBearerSession(req) {
  const authHeader = req.headers.authorization || '';
  const parts = authHeader.trim().split(/\s+/);
  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') {
    return null;
  }
  const session = sessions.get(parts[1]);
  if (!session) {
    return null;
  }
  if (Date.parse(session.expires_at) <= Date.now()) {
    sessions.delete(parts[1]);
    return null;
  }
  return { token: parts[1], session };
}

const server = http.createServer(async (req, res) => {
  const correlationHeader = req.headers['x-correlation-id'];
  const correlationId =
    typeof correlationHeader === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(correlationHeader)
      ? correlationHeader
      : `e2e-${crypto.randomUUID().slice(0, 12)}`;

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
      'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Correlation-ID',
      'X-Correlation-ID': correlationId,
    });
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url || '/', `http://127.0.0.1:${PORT}`);
  const path = parsedUrl.pathname;

  try {
    if (req.method === 'GET' && path === '/api/v1/health') {
      sendSuccess(res, 200, 'Healthy', { status: 'healthy', provider: 'fixture-e2e' }, correlationId);
      return;
    }

    if (req.method === 'POST' && path === '/api/e2e/reset') {
      resetState();
      sendSuccess(res, 200, 'Fixture E2E state reset', { reset: true }, correlationId);
      return;
    }

    // --- Local Auth ---
    if (req.method === 'POST' && path === '/api/v1/local-auth/mock-login') {
      const body = await readJsonBody(req);
      const alias = body?.alias;
      const user = USERS[alias];
      if (!user) {
        sendError(res, 422, 'UNKNOWN_LOCAL_ALIAS', 'Select one of the two approved synthetic personas.', correlationId);
        return;
      }
      const token = generateLocalToken();
      const expiresAt = new Date(Date.now() + 30 * 60 * 1000).toISOString();
      sessions.set(token, { user, expires_at: expiresAt });
      sendSuccess(
        res,
        200,
        'Synthetic local sign-in',
        {
          scope: LOCAL_SCOPE,
          contract_version: LOCAL_CONTRACT_VERSION,
          user,
          access_token: token,
          token_type: 'Bearer',
          expires_at: expiresAt,
        },
        correlationId,
      );
      return;
    }

    if (req.method === 'GET' && path === '/api/v1/local-auth/me') {
      const resolved = resolveBearerSession(req);
      if (!resolved) {
        sendError(res, 401, 'SESSION_INVALID', 'Your local session has ended.', correlationId);
        return;
      }
      sendSuccess(
        res,
        200,
        'Local session validated',
        {
          scope: LOCAL_SCOPE,
          contract_version: LOCAL_CONTRACT_VERSION,
          user: resolved.session.user,
        },
        correlationId,
      );
      return;
    }

    if (req.method === 'POST' && path === '/api/v1/local-auth/logout') {
      const resolved = resolveBearerSession(req);
      if (!resolved) {
        sendError(res, 401, 'SESSION_INVALID', 'Your local session has ended.', correlationId);
        return;
      }
      sessions.delete(resolved.token);
      sendSuccess(
        res,
        200,
        'Local session revoked',
        {
          scope: LOCAL_SCOPE,
          contract_version: LOCAL_CONTRACT_VERSION,
          signed_out: true,
        },
        correlationId,
      );
      return;
    }

    // --- Local Onboarding ---
    if (path.startsWith('/api/v1/local-onboarding/')) {
      const resolved = resolveBearerSession(req);
      if (!resolved) {
        sendError(res, 401, 'SESSION_INVALID', 'Your local session has ended.', correlationId);
        return;
      }
      const userId = resolved.session.user.id;
      const state = onboardingByUser.get(userId) || createInitialOnboardingState();
      onboardingByUser.set(userId, state);

      if (req.method === 'GET' && path === '/api/v1/local-onboarding/state') {
        sendSuccess(res, 200, 'Owned onboarding state', state, correlationId);
        return;
      }

      if (req.method === 'POST' && path === '/api/v1/local-onboarding/consent') {
        const body = await readJsonBody(req);
        if (body?.consent_version !== LOCAL_CONSENT_VERSION) {
          sendError(res, 409, 'CONSENT_VERSION_MISMATCH', 'Consent version mismatch.', correlationId);
          return;
        }
        const accepted = Boolean(body?.consent_given);
        state.consent = {
          accepted,
          version: LOCAL_CONSENT_VERSION,
          recorded_at: nowIso(),
        };
        if (!accepted) {
          state.onboarding_completed = false;
          state.completed_at = null;
        }
        sendSuccess(res, 200, 'Consent decision recorded', state, correlationId);
        return;
      }

      if (req.method === 'PUT' && path === '/api/v1/local-onboarding/draft') {
        const body = await readJsonBody(req);
        if (body?.profile_schema_version !== LOCAL_PROFILE_VERSION) {
          sendError(res, 409, 'PROFILE_VERSION_MISMATCH', 'Profile version mismatch.', correlationId);
          return;
        }
        const displayName = typeof body.display_name === 'string' ? body.display_name.trim() || null : null;
        const exp = body.experience_level ?? null;
        state.draft = {
          display_name: displayName,
          experience_level: exp,
          updated_at: nowIso(),
        };
        state.onboarding_completed = false;
        state.completed_at = null;
        sendSuccess(res, 200, 'Profile draft saved', state, correlationId);
        return;
      }

      if (req.method === 'POST' && path === '/api/v1/local-onboarding/complete') {
        if (!state.consent?.accepted) {
          sendError(res, 409, 'CONSENT_REQUIRED', 'Accept educational notice first.', correlationId);
          return;
        }
        if (!state.draft.display_name || !state.draft.experience_level) {
          sendError(res, 409, 'PROFILE_INCOMPLETE', 'Save profile fields first.', correlationId);
          return;
        }
        state.onboarding_completed = true;
        state.completed_at = nowIso();
        sendSuccess(res, 200, 'Owned onboarding completed', state, correlationId);
        return;
      }
    }

    // --- Market Fixture Routes ---
    if (req.method === 'GET' && path === '/api/v1/market/instruments') {
      const needle = (parsedUrl.searchParams.get('query') || '').trim().toLowerCase();
      const exchange = (parsedUrl.searchParams.get('exchange') || '').trim().toUpperCase();
      const items = FIXTURE_INSTRUMENTS.filter(
        (item) =>
          (!needle ||
            item.symbol.toLowerCase().includes(needle) ||
            item.name.toLowerCase().includes(needle)) &&
          (!exchange || item.exchange === exchange),
      );
      sendSuccess(res, 200, 'Instrument search completed', { items, count: items.length }, correlationId);
      return;
    }

    const quoteMatch = /^\/api\/v1\/market\/quotes\/([^/]+)$/.exec(path);
    if (req.method === 'GET' && quoteMatch) {
      const sym = decodeURIComponent(quoteMatch[1]).trim().toUpperCase();
      if (sym === 'DOWN') {
        sendSuccess(
          res,
          200,
          'Quote unavailable',
          {
            symbol: 'DOWN',
            price: null,
            currency: 'USD',
            change: 0,
            change_pct: 0,
            source: 'fixture',
            as_of: null,
            fetched_at: nowIso(),
            freshness: 'UNAVAILABLE',
            reason: 'Simulated provider outage',
          },
          correlationId,
          'UNAVAILABLE',
        );
        return;
      }
      const q = FIXTURE_QUOTES[sym];
      if (!q) {
        sendError(res, 404, 'SYMBOL_NOT_SUPPORTED', `Unknown symbol ${sym}`, correlationId);
        return;
      }
      const ts = nowIso();
      sendSuccess(
        res,
        200,
        'Quote retrieved',
        {
          symbol: sym,
          price: q.price,
          currency: q.currency,
          change: q.change,
          change_pct: q.change_pct,
          source: q.source,
          as_of: ts,
          fetched_at: ts,
          freshness: q.freshness,
        },
        correlationId,
        q.freshness,
      );
      return;
    }

    // --- Watchlist Routes (Authenticated) ---
    if (path === '/api/v1/watchlists' || path.startsWith('/api/v1/watchlists/')) {
      const resolved = resolveBearerSession(req);
      if (!resolved) {
        sendError(res, 401, 'UNAUTHORIZED', 'Authorization header missing', correlationId);
        return;
      }
      const userId = resolved.session.user.id;
      const lists = getOrCreateUserWatchlists(userId);

      if (req.method === 'GET' && path === '/api/v1/watchlists') {
        const items = Array.from(lists.values()).map((wl) => ({
          watchlist_id: wl.watchlist_id,
          name: wl.name,
          created_at: wl.created_at,
          updated_at: wl.updated_at,
          item_count: wl.items.length,
        }));
        sendSuccess(res, 200, 'Watchlists retrieved successfully', { items, count: items.length }, correlationId);
        return;
      }

      if (req.method === 'POST' && path === '/api/v1/watchlists') {
        const body = await readJsonBody(req);
        const name = typeof body?.name === 'string' && body.name.trim() ? body.name.trim() : 'Default';
        const ts = nowIso();
        const watchlist = {
          watchlist_id: `wl-${crypto.randomUUID().slice(0, 8)}`,
          name,
          created_at: ts,
          updated_at: ts,
          items: [],
        };
        lists.set(watchlist.watchlist_id, watchlist);
        sendSuccess(
          res,
          201,
          'Watchlist created successfully',
          { ...watchlist, item_count: 0 },
          correlationId,
        );
        return;
      }

      const itemsMatch = /^\/api\/v1\/watchlists\/([^/]+)\/items$/.exec(path);
      if (req.method === 'GET' && itemsMatch) {
        const wl = lists.get(decodeURIComponent(itemsMatch[1]));
        if (!wl) {
          sendError(res, 404, 'NOT_FOUND', 'Watchlist not found', correlationId);
          return;
        }
        sendSuccess(
          res,
          200,
          'Watchlist items retrieved successfully',
          { items: wl.items, count: wl.items.length },
          correlationId,
        );
        return;
      }

      const itemMatch = /^\/api\/v1\/watchlists\/([^/]+)\/items\/([^/]+)$/.exec(path);
      if (itemMatch) {
        const wl = lists.get(decodeURIComponent(itemMatch[1]));
        if (!wl) {
          sendError(res, 404, 'NOT_FOUND', 'Watchlist not found', correlationId);
          return;
        }
        const instrumentId = decodeURIComponent(itemMatch[2]).trim().toUpperCase();
        if (req.method === 'PUT') {
          let existing = wl.items.find((it) => it.instrument_id === instrumentId);
          if (!existing) {
            existing = { instrument_id: instrumentId, added_at: nowIso() };
            wl.items.push(existing);
            wl.updated_at = nowIso();
          }
          sendSuccess(res, 200, 'Item saved in watchlist successfully', existing, correlationId);
          return;
        }
        if (req.method === 'DELETE') {
          wl.items = wl.items.filter((it) => it.instrument_id !== instrumentId);
          wl.updated_at = nowIso();
          sendSuccess(
            res,
            200,
            'Item removed from watchlist successfully',
            { watchlist_id: wl.watchlist_id, instrument_id: instrumentId, removed: true },
            correlationId,
          );
          return;
        }
      }
    }

    // --- Paper Trading Routes (Authenticated) ---
    if (path.startsWith('/api/v1/paper/')) {
      const resolved = resolveBearerSession(req);
      if (!resolved) {
        sendError(res, 401, 'UNAUTHORIZED', 'Authorization header missing', correlationId);
        return;
      }
      const userId = resolved.session.user.id;
      const paperState = getOrCreatePaperState(userId);

      if (req.method === 'GET' && path === '/api/v1/paper/account') {
        sendSuccess(res, 200, 'Paper account retrieved', buildPaperAccountPayload(userId), correlationId);
        return;
      }

      if (req.method === 'GET' && path === '/api/v1/paper/positions') {
        const acct = buildPaperAccountPayload(userId);
        sendSuccess(res, 200, 'Paper positions retrieved', acct.positions, correlationId);
        return;
      }

      if (req.method === 'GET' && path === '/api/v1/paper/orders') {
        const limit = Math.max(1, Math.min(100, Number(parsedUrl.searchParams.get('limit') || '20')));
        sendSuccess(res, 200, 'Paper orders retrieved', paperState.orders.slice(0, limit), correlationId);
        return;
      }

      if (req.method === 'POST' && path === '/api/v1/paper/orders') {
        const body = await readJsonBody(req);
        const symbol = String(body?.instrument_id || '').trim().toUpperCase();
        const exchange = String(body?.exchange || 'NASDAQ').trim().toUpperCase();
        const side = String(body?.side || '').trim().toUpperCase();
        const quantity = body?.quantity;
        const idempotencyKey = String(body?.idempotency_key || '').trim();

        if (!symbol || !['NYSE', 'NASDAQ'].includes(exchange) || !['BUY', 'SELL'].includes(side) ||
            !Number.isInteger(quantity) || quantity < 1 || quantity > 100_000 || idempotencyKey.length < 10) {
          sendError(res, 422, 'VALIDATION_ERROR', 'Invalid paper order request.', correlationId);
          return;
        }

        const fingerprint = `${symbol}|${exchange}|${side}|${quantity}`;
        const existing = paperState.ordersByKey.get(idempotencyKey);
        if (existing) {
          if (existing.fingerprint !== fingerprint) {
            sendError(
              res,
              409,
              'IDEMPOTENCY_KEY_REUSED',
              'The idempotency key was already used for a different order.',
              correlationId,
            );
            return;
          }
          sendSuccess(res, 200, 'Paper order replayed', existing.order, correlationId, existing.order.quote_freshness);
          return;
        }

        const quote = FIXTURE_QUOTES[symbol];
        if (!quote || quote.currency !== 'USD' || quote.freshness === 'UNAVAILABLE') {
          sendError(res, 503, 'QUOTE_UNAVAILABLE', 'An eligible market quote is unavailable.', correlationId);
          return;
        }

        const executedPrice = quote.price;
        const notionalCents = Math.round(executedPrice * quantity * 100);
        const feeCents = Math.round((notionalCents * FEE_BPS) / 10_000);
        const cashDeltaCents = side === 'BUY' ? -(notionalCents + feeCents) : notionalCents - feeCents;

        if (paperState.cashCents + cashDeltaCents < 0) {
          sendError(res, 409, 'INSUFFICIENT_CASH', 'The order would make paper cash negative.', correlationId);
          return;
        }

        const posKey = `${symbol}:${exchange}`;
        const currentPos = paperState.positions.get(posKey) || {
          instrument_id: symbol,
          exchange,
          quantity: 0,
          totalCostCents: 0,
          lastPrice: executedPrice,
        };

        if (side === 'SELL' && currentPos.quantity < quantity) {
          sendError(res, 409, 'INSUFFICIENT_POSITION', 'There are not enough shares to sell.', correlationId);
          return;
        }

        paperState.cashCents += cashDeltaCents;
        if (side === 'BUY') {
          currentPos.quantity += quantity;
          currentPos.totalCostCents += notionalCents + feeCents;
          currentPos.lastPrice = executedPrice;
          paperState.positions.set(posKey, currentPos);
        } else {
          const remaining = currentPos.quantity - quantity;
          if (remaining === 0) {
            paperState.positions.delete(posKey);
          } else {
            currentPos.totalCostCents = Math.round((currentPos.totalCostCents * remaining) / currentPos.quantity);
            currentPos.quantity = remaining;
            currentPos.lastPrice = executedPrice;
            paperState.positions.set(posKey, currentPos);
          }
        }

        const ts = nowIso();
        const order = {
          order_id: `paper-order-${crypto.randomUUID().slice(0, 12)}`,
          instrument_id: symbol,
          exchange,
          side,
          quantity,
          executed_price: executedPrice.toFixed(6),
          notional: formatCents(notionalCents),
          fee: formatCents(feeCents),
          cash_delta: formatCents(cashDeltaCents),
          status: 'FILLED',
          quote_freshness: quote.freshness === 'DELAYED' ? 'DELAYED' : 'CACHED',
          quote_as_of: ts,
          created_at: ts,
          simulation_notice: 'SIMULATION ONLY: no real money or broker execution.',
        };

        paperState.orders.unshift(order);
        paperState.ordersByKey.set(idempotencyKey, { fingerprint, order });
        sendSuccess(res, 201, 'Paper order filled', order, correlationId, order.quote_freshness);
        return;
      }
    }

    sendError(res, 404, 'NOT_FOUND', `Route not found: ${path}`, correlationId);
  } catch (err) {
    sendError(
      res,
      500,
      'INTERNAL_ERROR',
      err instanceof Error ? err.message : 'Unexpected fixture server error',
      correlationId,
    );
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`FinEx E2E fixture server listening on http://127.0.0.1:${PORT}`);
});
