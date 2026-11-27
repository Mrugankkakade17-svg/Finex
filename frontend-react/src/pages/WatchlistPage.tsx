import React, { useCallback, useEffect, useState } from 'react';
import { Star, Trash2, RefreshCw, AlertTriangle } from 'lucide-react';
import { marketService } from '../services/marketService';
import { WatchlistItem, getFreshnessBadgeMeta } from '../types/market';

async function enrichItemsWithFreshness(
  rawItems: WatchlistItem[]
): Promise<WatchlistItem[]> {
  return Promise.all(
    rawItems.map(async (item) => {
      if (item.freshness || item.dataStatus) {
        return item;
      }
      try {
        const quote = await marketService.getQuote(item.symbol);
        return {
          ...item,
          currency: item.currency ?? quote.currency,
          price:
            quote.priceAvailable === false || quote.dataStatus === 'UNAVAILABLE'
              ? null
              : quote.price,
          changeValue: quote.changeValue,
          changePercent: quote.changePercent,
          source: quote.source,
          dataAsOf: quote.dataAsOf,
          dataStatus: quote.dataStatus,
          freshness: quote.freshness,
        };
      } catch {
        return {
          ...item,
          dataStatus: 'UNAVAILABLE',
          freshness: {
            status: 'UNAVAILABLE',
            source: 'market-api',
            as_of: null,
            fetched_at: new Date().toISOString(),
            reason: 'Quote freshness unavailable',
          },
        };
      }
    })
  );
}

export const WatchlistPage: React.FC = () => {
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingSymbol, setRemovingSymbol] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    setActionError(null);
    try {
      const result = await marketService.getWatchlist();
      const enriched = await enrichItemsWithFreshness(result);
      setItems(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load your watchlist right now.');
      setItems(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWatchlist();
  }, [loadWatchlist]);

  const handleRemove = async (symbol: string) => {
    setRemovingSymbol(symbol);
    setActionError(null);
    try {
      const updated = await marketService.removeFromWatchlist(symbol);
      const enriched = await enrichItemsWithFreshness(updated);
      setItems(enriched);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : `Unable to remove ${symbol} from watchlist.`
      );
    } finally {
      setRemovingSymbol(null);
    }
  };

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
          <p className="local-eyebrow">TRACK YOUR FAVORITES</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>Watchlist</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            ANALYTICAL · Securities you&apos;re tracking, with the latest available freshness status
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={loadWatchlist}
          disabled={loading}
          style={{ fontSize: '0.88rem' }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading && (
        <div
          data-testid="watchlist-loading"
          style={{ color: 'var(--color-text-muted)', padding: '20px 0' }}
        >
          Loading your watchlist…
        </div>
      )}

      {!loading && error && (
        <div
          role="alert"
          data-testid="watchlist-error"
          style={{
            padding: '16px',
            borderRadius: '12px',
            background: '#FEF3F2',
            border: '1px solid #FDA29B',
            color: '#B42318',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} /> {error}
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={loadWatchlist}
            style={{ fontSize: '0.78rem' }}
          >
            Retry
          </button>
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          data-testid="watchlist-action-error"
          style={{
            marginBottom: '16px',
            padding: '12px 16px',
            borderRadius: '12px',
            background: '#FEF3F2',
            border: '1px solid #FDA29B',
            color: '#B42318',
            fontSize: '0.88rem',
          }}
        >
          {actionError}
        </div>
      )}

      {!loading && !error && items && items.length === 0 && (
        <div
          data-testid="watchlist-empty"
          className="glass-card"
          style={{ padding: '36px', textAlign: 'center', color: 'var(--color-text-muted)' }}
        >
          <Star size={32} color="var(--color-accent-coral)" style={{ marginBottom: '10px' }} />
          <p>Your watchlist is empty. Search for a security to add one.</p>
        </div>
      )}

      {!loading && !error && items && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {items.map((item) => {
            const status = item.freshness?.status ?? item.dataStatus ?? 'UNAVAILABLE';
            const badgeMeta = getFreshnessBadgeMeta(status);
            const source = item.freshness?.source ?? item.source;
            const asOf = item.freshness?.as_of ?? item.dataAsOf;
            const hasPrice =
              status !== 'UNAVAILABLE' &&
              typeof item.price === 'number' &&
              Number.isFinite(item.price);

            return (
              <div
                key={item.symbol}
                className="glass-card"
                style={{
                  padding: '18px 22px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '16px',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: '1.05rem' }}>
                      {item.symbol}
                    </span>
                    <span
                      data-testid={`watchlist-freshness-badge-${item.symbol}`}
                      data-status={badgeMeta.status}
                      title={badgeMeta.description}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        padding: '3px 9px',
                        borderRadius: '999px',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        color: badgeMeta.color,
                        background: badgeMeta.background,
                        border: `1px solid ${badgeMeta.borderColor}`,
                      }}
                    >
                      {badgeMeta.label}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    {item.name}
                  </div>
                  {(source || asOf) && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                      {source ? `Source: ${source}` : ''}
                      {source && asOf ? ' • ' : ''}
                      {asOf ? `As of ${new Date(asOf).toLocaleTimeString()}` : ''}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    {hasPrice ? (
                      <span style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: '0.98rem' }}>
                        {item.price!.toFixed(2)} {item.currency ?? 'USD'}
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                        Price unavailable
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemove(item.symbol)}
                    disabled={removingSymbol === item.symbol}
                    aria-label={`Remove ${item.symbol} from watchlist`}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--color-text-muted)',
                      cursor: removingSymbol === item.symbol ? 'wait' : 'pointer',
                      padding: '8px',
                      borderRadius: '8px',
                    }}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
