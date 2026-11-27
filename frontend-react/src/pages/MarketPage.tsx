import React, { useState } from 'react';
import { Search, TrendingUp, TrendingDown, AlertTriangle, Star, RefreshCw } from 'lucide-react';
import { getMarketConfig, marketService } from '../services/marketService';
import { MarketQuote, MarketSecurity, getFreshnessBadgeMeta } from '../types/market';

export const MarketPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MarketSecurity[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);

  const [selectedSecurity, setSelectedSecurity] = useState<MarketSecurity | null>(null);
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>([]);
  const [watchlistBusy, setWatchlistBusy] = useState(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  const mode = getMarketConfig().mode;

  const runSearch = async () => {
    setValidationError(null);
    setProviderError(null);

    if (!query.trim()) {
      setValidationError('Enter a symbol or company name to search.');
      setResults(null);
      return;
    }

    setLoading(true);
    try {
      const found = await marketService.search(query);
      setResults(found);
    } catch (err) {
      setProviderError(err instanceof Error ? err.message : 'Search is temporarily unavailable.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await runSearch();
  };

  const loadQuote = async (security: MarketSecurity) => {
    setSelectedSecurity(security);
    setQuote(null);
    setQuoteError(null);
    setWatchlistError(null);
    setQuoteLoading(true);

    try {
      const result = await marketService.getQuote(security.symbol);
      setQuote(result);
    } catch (err) {
      setQuoteError(err instanceof Error ? err.message : 'PRICE_UNAVAILABLE');
    } finally {
      setQuoteLoading(false);
    }
  };

  const handleAddToWatchlist = async (security: MarketSecurity) => {
    setWatchlistBusy(true);
    setWatchlistError(null);
    try {
      const updated = await marketService.addToWatchlist(security);
      setWatchlistSymbols(updated.map((item) => item.symbol));
    } catch (err) {
      setWatchlistError(
        err instanceof Error ? err.message : 'Unable to add security to watchlist.'
      );
    } finally {
      setWatchlistBusy(false);
    }
  };

  const isWatchlisted = (symbol: string) => watchlistSymbols.includes(symbol);
  const badgeMeta = quote
    ? getFreshnessBadgeMeta(quote.freshness?.status ?? quote.dataStatus)
    : null;
  const effectiveSource = quote?.freshness?.source ?? quote?.source;
  const effectiveAsOf = quote?.freshness?.as_of ?? quote?.dataAsOf;
  const effectiveReason = quote?.freshness?.reason ?? quote?.reason;
  const isUnavailableQuote = quote?.dataStatus === 'UNAVAILABLE' || quote?.priceAvailable === false;

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '24px',
        }}
      >
        <div>
          <p className="local-eyebrow">EXPLORE SECURITIES</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>Market Search</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Search supported securities across NSE, BSE, and US markets with honest data freshness
          </p>
        </div>
        <span
          data-testid="market-mode-badge"
          style={{
            fontSize: '0.78rem',
            fontWeight: 600,
            padding: '6px 12px',
            borderRadius: '999px',
            border: '1px solid var(--color-surface-divider)',
            background: '#FFFFFF',
            color: 'var(--color-text-muted)',
          }}
        >
          ANALYTICAL · {mode === 'api' ? 'Live API' : 'Fixture mode'}
        </span>
      </div>

      <form
        onSubmit={handleSearch}
        style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}
      >
        <div style={{ flex: '1 1 260px', position: 'relative' }}>
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: '14px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--color-text-muted)',
            }}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by symbol or name (e.g. AAPL, RELIANCE.NS, TCS.NS)"
            aria-label="Search securities"
            style={{
              width: '100%',
              padding: '12px 14px 12px 42px',
              borderRadius: '999px',
            }}
          />
        </div>
        <button type="submit" className="btn-primary">
          Search
        </button>
      </form>

      {validationError && (
        <div
          role="alert"
          style={{
            marginBottom: '16px',
            padding: '12px 16px',
            borderRadius: '12px',
            background: '#FFFAEB',
            border: '1px solid #FEC84B',
            color: '#93370D',
            fontSize: '0.88rem',
            fontWeight: 600,
          }}
        >
          {validationError}
        </div>
      )}

      {providerError && (
        <div
          role="alert"
          style={{
            marginBottom: '16px',
            padding: '12px 16px',
            borderRadius: '12px',
            background: '#FEF3F2',
            border: '1px solid #FDA29B',
            color: '#B42318',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} /> {providerError}
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void runSearch();
            }}
            style={{ fontSize: '0.78rem', padding: '6px 12px' }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {loading && (
        <div
          data-testid="market-search-loading"
          style={{ color: 'var(--color-text-muted)', padding: '20px 0' }}
        >
          Searching securities…
        </div>
      )}

      {!loading && results !== null && results.length === 0 && (
        <div
          data-testid="market-search-empty"
          className="glass-card"
          style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}
        >
          No supported securities matched &ldquo;{query}&rdquo;.
        </div>
      )}

      {!loading && results !== null && results.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
            gap: '24px',
          }}
        >
          <div className="glass-card" style={{ padding: '22px' }}>
            <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', marginBottom: '16px' }}>
              Results
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {results.map((security) => (
                <button
                  key={security.securityId}
                  type="button"
                  onClick={() => loadQuote(security)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    border:
                      selectedSecurity?.securityId === security.securityId
                        ? '2px solid var(--color-accent-coral)'
                        : '1.5px solid var(--color-surface-divider)',
                    background:
                      selectedSecurity?.securityId === security.securityId
                        ? 'rgba(255, 114, 94, 0.08)'
                        : '#F7FAF8',
                    color: 'var(--color-text)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700 }}>{security.symbol}</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                      {security.name}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--color-accent-violet)',
                      fontWeight: 700,
                    }}
                  >
                    {security.exchange} · {security.currency}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '22px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)' }}>
                Latest Available Quote
              </h3>
              {selectedSecurity && !quoteLoading && quote && !quoteError && badgeMeta && (
                <span
                  data-testid="quote-freshness-badge"
                  data-status={badgeMeta.status}
                  title={badgeMeta.description}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '4px 10px',
                    borderRadius: '999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: badgeMeta.color,
                    background: badgeMeta.background,
                    border: `1px solid ${badgeMeta.borderColor}`,
                  }}
                >
                  {badgeMeta.label}
                </span>
              )}
            </div>

            {!selectedSecurity && (
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.88rem' }}>
                Select a security from the results to view its quote.
              </p>
            )}

            {selectedSecurity && quoteLoading && (
              <div data-testid="quote-loading" style={{ color: 'var(--color-text-muted)' }}>
                Loading quote…
              </div>
            )}

            {selectedSecurity && !quoteLoading && quoteError && (
              <div
                data-testid="quote-unavailable"
                role="alert"
                style={{
                  padding: '14px',
                  borderRadius: '12px',
                  background: '#FEF3F2',
                  border: '1px solid #FDA29B',
                  color: '#B42318',
                  fontSize: '0.88rem',
                }}
              >
                Price unavailable for {selectedSecurity.symbol}. The market data provider did not
                return a usable price.
              </div>
            )}

            {selectedSecurity && !quoteLoading && quote && !quoteError && badgeMeta && (
              <div>
                {isUnavailableQuote ? (
                  <div
                    data-testid="quote-unavailable"
                    role="alert"
                    style={{
                      padding: '14px',
                      borderRadius: '12px',
                      background: '#FEF3F2',
                      border: '1px solid #FDA29B',
                      color: '#B42318',
                      fontSize: '0.88rem',
                      marginBottom: '14px',
                    }}
                  >
                    Price unavailable for {quote.symbol}.{' '}
                    {effectiveReason ? `(${effectiveReason})` : 'Try again shortly.'}
                  </div>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: '12px',
                      marginBottom: '8px',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: '2.1rem',
                        fontWeight: 700,
                        color: 'var(--color-text)',
                      }}
                    >
                      {quote.price.toFixed(2)} {quote.currency}
                    </span>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        color: quote.changeValue >= 0 ? '#16654E' : '#B42318',
                        fontSize: '0.92rem',
                        fontWeight: 700,
                      }}
                    >
                      {quote.changeValue >= 0 ? (
                        <TrendingUp size={16} />
                      ) : (
                        <TrendingDown size={16} />
                      )}
                      {(quote.changePercent * 100).toFixed(2)}%
                    </span>
                  </div>
                )}

                <div
                  data-testid="quote-freshness"
                  style={{
                    fontSize: '0.78rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: '12px',
                  }}
                >
                  Source: {effectiveSource} • Status: {badgeMeta.label}
                  {effectiveAsOf ? ` • As of ${new Date(effectiveAsOf).toLocaleTimeString()}` : ''}
                  {effectiveReason ? ` • ${effectiveReason}` : ''}
                </div>

                <p
                  style={{
                    fontSize: '0.78rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: '16px',
                  }}
                >
                  ANALYTICAL educational market data — status reflects actual provider freshness,
                  never guaranteed live.
                </p>

                {watchlistError && (
                  <div
                    role="alert"
                    style={{
                      marginBottom: '12px',
                      padding: '10px 12px',
                      borderRadius: '10px',
                      background: '#FEF3F2',
                      border: '1px solid #FDA29B',
                      color: '#B42318',
                      fontSize: '0.82rem',
                    }}
                  >
                    {watchlistError}
                  </div>
                )}

                <button
                  type="button"
                  className={
                    isWatchlisted(selectedSecurity.symbol) ? 'btn-secondary' : 'btn-primary'
                  }
                  onClick={() => handleAddToWatchlist(selectedSecurity)}
                  disabled={watchlistBusy || isWatchlisted(selectedSecurity.symbol)}
                >
                  <Star size={16} />
                  {isWatchlisted(selectedSecurity.symbol) ? 'On Watchlist' : 'Add to Watchlist'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
