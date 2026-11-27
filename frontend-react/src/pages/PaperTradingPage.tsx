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
          <p className="local-eyebrow">GROW WITH CONFIDENCE</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Paper Trading Simulator
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Simulate buy/sell orders with zero real-money risk
          </p>
        </div>
        <span className="badge badge-warning">Simulated Environment</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}
      >
        {/* Order Entry Form */}
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
            onSubmit={handleTrade}
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
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '999px',
                    border:
                      orderType === 'SELL'
                        ? '2px solid var(--color-accent-coral)'
                        : '1.5px solid var(--color-surface-divider)',
                    background:
                      orderType === 'SELL' ? 'rgba(255, 114, 94, 0.14)' : 'var(--color-surface)',
                    color:
                      orderType === 'SELL' ? '#B42318' : 'var(--color-text-muted)',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  SELL
                </button>
              </div>
            </div>

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
                Security Symbol
              </label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                style={{ width: '100%' }}
              />
            </div>

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
                Quantity
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                min="1"
                style={{ width: '100%' }}
              />
            </div>

            <button
              type="submit"
              className="btn-primary"
              style={{ marginTop: '8px', justifyContent: 'center' }}
            >
              Submit Paper {orderType} Order
            </button>
          </form>

          {executed && (
            <div
              style={{
                marginTop: '20px',
                padding: '12px 16px',
                borderRadius: '12px',
                background: '#ECFDF5',
                border: '1px solid #6EE7B7',
                color: '#065F46',
                fontSize: '0.88rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <CheckCircle2 size={16} /> Paper {orderType} order for {quantity} shares of {symbol}{' '}
              executed atomically.
            </div>
          )}
        </div>

        {/* Account Cash Ledger */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.25rem', color: 'var(--color-text)', marginBottom: '20px' }}>
            Virtual Cash Account
          </h3>

          <div
            style={{
              padding: '22px',
              borderRadius: '16px',
              background: 'var(--color-surface-elevated)',
              border: '1px solid var(--color-surface-divider)',
              marginBottom: '20px',
            }}
          >
            <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Current Virtual Cash
            </div>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '2.1rem',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginTop: '4px',
              }}
            >
              $10,000.00 USD
            </div>
            <div
              style={{
                fontSize: '0.78rem',
                color: 'var(--color-text-muted)',
                marginTop: '4px',
              }}
            >
              Append-only cash ledger — No real funds involved.
            </div>
          </div>

          <div
            style={{
              padding: '16px',
              borderRadius: '14px',
              background: 'rgba(230, 237, 115, 0.35)',
              border: '1px solid #C8D14B',
              color: 'var(--color-text)',
              fontSize: '0.85rem',
              display: 'flex',
              gap: '10px',
            }}
          >
            <ShieldAlert size={20} style={{ flexShrink: 0, color: 'var(--color-accent-violet)' }} />
            <div>
              <strong>Financial Safety Rule:</strong> Paper trading is an educational simulation.
              Order execution never calls real brokerages.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
