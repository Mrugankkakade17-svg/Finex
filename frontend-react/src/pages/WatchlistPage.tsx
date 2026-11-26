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
    loadWatchlist();
  }, []);

  const handleRemove = async (symbol: string) => {
    const updated = await marketService.removeFromWatchlist(symbol);
    setItems(updated);
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
            Securities you&apos;re tracking, with the latest available freshness status
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={loadWatchlist}
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
          {items.map((item) => (
            <div
              key={item.symbol}
              className="glass-card"
              style={{
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: '1.05rem' }}>
                  {item.symbol}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                  {item.name}
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleRemove(item.symbol)}
                aria-label={`Remove ${item.symbol} from watchlist`}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-text-muted)',
                  cursor: 'pointer',
                  padding: '8px',
                  borderRadius: '8px',
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
