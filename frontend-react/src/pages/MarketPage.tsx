import React, { useState } from 'react';
import { Search, TrendingUp, TrendingDown, AlertTriangle, Star, RefreshCw } from 'lucide-react';
import { marketService } from '../services/marketService';
import { MarketQuote, MarketSecurity } from '../types/market';

const STATUS_LABEL: Record<string, string> = {
  LIVE: 'Live',
  DELAYED: 'Delayed',
  END_OF_DAY: 'End of day',
  CACHED: 'Cached',
  UNAVAILABLE: 'Unavailable',
};

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

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
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

  const loadQuote = async (security: MarketSecurity) => {
    setSelectedSecurity(security);
    setQuote(null);
    setQuoteError(null);
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
    const updated = await marketService.addToWatchlist(security);
    setWatchlistSymbols(updated.map((item) => item.symbol));
  };

  const isWatchlisted = (symbol: string) => watchlistSymbols.includes(symbol);

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Market Search</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Search supported securities and view the latest available quote
        </p>
      </div>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search
            size={18}
            style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by symbol or name (e.g. AAPL)"
            aria-label="Search securities"
            style={{
              width: '100%',
              padding: '12px 14px 12px 40px',
              borderRadius: '8px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-glass)',
              color: '#ffffff',
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
            borderRadius: '8px',
            background: 'rgba(245, 158, 11, 0.1)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            color: '#f59e0b',
            fontSize: '0.85rem',
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
            borderRadius: '8px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            fontSize: '0.85rem',
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
            onClick={handleSearch as unknown as () => void}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {loading && (
        <div data-testid="market-search-loading" style={{ color: 'var(--text-secondary)', padding: '20px 0' }}>
          Searching securities…
        </div>
      )}

      {!loading && results !== null && results.length === 0 && (
        <div
          data-testid="market-search-empty"
          className="glass-card"
          style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)' }}
        >
          No supported securities matched "{query}".
        </div>
      )}

      {!loading && results !== null && results.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div className="glass-card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '1rem', color: '#ffffff', marginBottom: '16px' }}>Results</h3>
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
                    padding: '12px 14px',
                    borderRadius: '8px',
                    border:
                      selectedSecurity?.securityId === security.securityId
                        ? '1px solid var(--primary-emerald)'
                        : '1px solid var(--border-glass)',
                    background:
                      selectedSecurity?.securityId === security.securityId
                        ? 'rgba(16, 185, 129, 0.1)'
                        : 'transparent',
                    color: '#ffffff',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{security.symbol}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{security.name}</div>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{security.exchange}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '1rem', color: '#ffffff', marginBottom: '16px' }}>Latest Available Quote</h3>

            {!selectedSecurity && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Select a security from the results to view its quote.
              </p>
            )}

            {selectedSecurity && quoteLoading && (
              <div data-testid="quote-loading" style={{ color: 'var(--text-secondary)' }}>
                Loading quote…
              </div>
            )}

            {selectedSecurity && !quoteLoading && quoteError && (
              <div
                data-testid="quote-unavailable"
                role="alert"
                style={{
                  padding: '14px',
                  borderRadius: '8px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#ef4444',
                  fontSize: '0.85rem',
                }}
              >
                Price unavailable for {selectedSecurity.symbol}. The market data provider did not return a usable
                price.
              </div>
            )}

            {selectedSecurity && !quoteLoading && quote && !quoteError && (
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '2rem', fontWeight: 700, color: '#ffffff' }}>
                    {quote.price.toFixed(2)} {quote.currency}
                  </span>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: quote.changeValue >= 0 ? '#10b981' : '#ef4444',
                      fontSize: '0.9rem',
                      fontWeight: 600,
                    }}
                  >
                    {quote.changeValue >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                    {(quote.changePercent * 100).toFixed(2)}%
                  </span>
                </div>

                {quote.dataStatus === 'UNAVAILABLE' ? (
                  <div
                    data-testid="quote-unavailable"
                    style={{
                      padding: '14px',
                      borderRadius: '8px',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      color: '#ef4444',
                      fontSize: '0.85rem',
                      marginTop: '8px',
                    }}
                  >
                    Price unavailable. Try again shortly.
                  </div>
                ) : (
                  <div
                    data-testid="quote-freshness"
                    style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '16px' }}
                  >
                    Source: {quote.source} • Status: {STATUS_LABEL[quote.dataStatus]} • As of{' '}
                    {new Date(quote.dataAsOf).toLocaleTimeString()}
                  </div>
                )}

                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  This is prototype educational data, not a guaranteed live feed.
                </p>

                <button
                  type="button"
                  className={isWatchlisted(selectedSecurity.symbol) ? 'btn-secondary' : 'btn-primary'}
                  onClick={() => handleAddToWatchlist(selectedSecurity)}
                  disabled={isWatchlisted(selectedSecurity.symbol)}
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
