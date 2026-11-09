import React, { useEffect, useState } from 'react';
import { Star, Trash2, RefreshCw, AlertTriangle } from 'lucide-react';
import { marketService } from '../services/marketService';
import { WatchlistItem } from '../types/market';

export const WatchlistPage: React.FC = () => {
  const [items, setItems] = useState<WatchlistItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWatchlist = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await marketService.getWatchlist();
      setItems(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load your watchlist right now.');
      setItems(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Loaded once on mount; the mock service holds state module-side.
    loadWatchlist();
  }, []);

  const handleRemove = async (symbol: string) => {
    const updated = await marketService.removeFromWatchlist(symbol);
    setItems(updated);
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Watchlist</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Securities you're tracking, with the latest available freshness status
          </p>
        </div>
        <button type="button" className="btn-secondary" onClick={loadWatchlist} style={{ fontSize: '0.85rem' }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading && (
        <div data-testid="watchlist-loading" style={{ color: 'var(--text-secondary)', padding: '20px 0' }}>
          Loading your watchlist…
        </div>
      )}

      {!loading && error && (
        <div
          role="alert"
          data-testid="watchlist-error"
          style={{
            padding: '16px',
            borderRadius: '8px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} /> {error}
          </span>
          <button type="button" className="btn-secondary" onClick={loadWatchlist} style={{ fontSize: '0.75rem' }}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && items && items.length === 0 && (
        <div
          data-testid="watchlist-empty"
          className="glass-card"
          style={{ padding: '32px', textAlign: 'center', color: 'var(--text-secondary)' }}
        >
          <Star size={28} style={{ marginBottom: '10px', opacity: 0.6 }} />
          <p>Your watchlist is empty. Search for a security to add one.</p>
        </div>
      )}

      {!loading && !error && items && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {items.map((item) => (
            <div
              key={item.symbol}
              className="glass-card"
              style={{
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, color: '#ffffff' }}>{item.symbol}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{item.name}</div>
              </div>
              <button
                type="button"
                onClick={() => handleRemove(item.symbol)}
                aria-label={`Remove ${item.symbol} from watchlist`}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '6px',
                }}
              >
                <Trash2 size={18} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
