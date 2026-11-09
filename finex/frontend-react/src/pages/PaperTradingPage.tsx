import React, { useState } from 'react';
import { TrendingUp, ShieldAlert, CheckCircle2 } from 'lucide-react';

export const PaperTradingPage: React.FC = () => {
  const [symbol, setSymbol] = useState('AAPL');
  const [quantity, setQuantity] = useState('10');
  const [orderType, setOrderType] = useState('BUY');
  const [executed, setExecuted] = useState(false);

  const handleTrade = (e: React.FormEvent) => {
    e.preventDefault();
    setExecuted(true);
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Paper Trading Simulator</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Simulate buy/sell orders with zero real-money risk
          </p>
        </div>
        <span className="badge badge-warning">Simulated Environment</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Order Entry Form */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={20} color="#10b981" /> Order Ticket
          </h3>

          <form onSubmit={handleTrade} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Order Side</label>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setOrderType('BUY')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '8px',
                    border: orderType === 'BUY' ? '1px solid #10b981' : '1px solid var(--border-glass)',
                    background: orderType === 'BUY' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
                    color: orderType === 'BUY' ? '#10b981' : 'var(--text-secondary)',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  BUY
                </button>
                <button
                  type="button"
                  onClick={() => setOrderType('SELL')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '8px',
                    border: orderType === 'SELL' ? '1px solid #ef4444' : '1px solid var(--border-glass)',
                    background: orderType === 'SELL' ? 'rgba(239, 68, 68, 0.2)' : 'transparent',
                    color: orderType === 'SELL' ? '#ef4444' : 'var(--text-secondary)',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  SELL
                </button>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Security Symbol</label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'var(--bg-input)', border: '1px solid var(--border-glass)', color: '#ffffff' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Quantity</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                min="1"
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'var(--bg-input)', border: '1px solid var(--border-glass)', color: '#ffffff' }}
              />
            </div>

            <button type="submit" className="btn-primary" style={{ marginTop: '8px', justifyContent: 'center' }}>
              Submit Paper {orderType} Order
            </button>
          </form>

          {executed && (
            <div style={{ marginTop: '20px', padding: '12px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#10b981', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={16} /> Paper {orderType} order for {quantity} shares of {symbol} executed atomically.
            </div>
          )}
        </div>

        {/* Account Cash Ledger */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '20px' }}>Virtual Cash Account</h3>

          <div style={{ padding: '20px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-glass)', marginBottom: '20px' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Current Virtual Cash</div>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: '#ffffff' }}>$10,000.00 USD</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Append-only cash ledger — No real funds involved.
            </div>
          </div>

          <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#f59e0b', fontSize: '0.8rem', display: 'flex', gap: '10px' }}>
            <ShieldAlert size={20} style={{ flexShrink: 0 }} />
            <div>
              <strong>Financial Safety Rule:</strong> Paper trading is an educational simulation. Order execution never calls real brokerages.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
