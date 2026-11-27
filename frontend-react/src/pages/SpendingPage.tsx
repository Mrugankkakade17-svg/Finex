import React, { useState } from 'react';
import { CreditCard, Upload, CheckCircle2 } from 'lucide-react';

export const SpendingPage: React.FC = () => {
  const [uploaded, setUploaded] = useState(false);

  const categories = [
    { category: 'Housing & Utilities', total: '₹ 18,500', pct: '45%' },
    { category: 'Groceries & Dining', total: '₹ 6,200', pct: '15%' },
    { category: 'Investment & Savings', total: '₹ 12,000', pct: '30%' },
    { category: 'Weekend & Leisure', total: '₹ 4,100', pct: '10%' },
  ];

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
          <p className="local-eyebrow">SPEND WITH INTENTION</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Spending Trends &amp; Statement Import
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Privacy-controlled spending classification &amp; monthly rhythm analysis
          </p>
        </div>
        <span className="badge badge-info">Privacy Shield Active</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}
      >
        {/* CSV Upload Container */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3
            style={{
              fontSize: '1.25rem',
              color: 'var(--color-text)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Upload size={20} color="var(--color-accent-coral)" /> Import CSV Statements
          </h3>

          <div
            onClick={() => setUploaded(true)}
            style={{
              padding: '36px',
              borderRadius: '16px',
              border: '2px dashed var(--color-accent-violet)',
              background: 'var(--color-surface-elevated)',
              textAlign: 'center',
              cursor: 'pointer',
              marginBottom: '20px',
              transition: 'all var(--transition-fast)',
            }}
          >
            <CreditCard
              size={36}
              color="var(--color-accent-coral)"
              style={{ margin: '0 auto 12px auto' }}
            />
            <div style={{ color: 'var(--color-text)', fontWeight: 700, marginBottom: '4px' }}>
              Click to Upload Bank CSV
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
              Supports standard bank export files (Max 5MB)
            </div>
          </div>

          {uploaded && (
            <div
              style={{
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
              <CheckCircle2 size={16} /> Statement uploaded: 42 transactions categorized with PII
              masking.
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.25rem', color: 'var(--color-text)', marginBottom: '20px' }}>
            Monthly Breakdown
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {categories.map((c) => (
              <div
                key={c.category}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 18px',
                  borderRadius: '14px',
                  background: 'var(--color-surface-elevated)',
                  border: '1px solid var(--color-surface-divider)',
                }}
              >
                <div>
                  <div style={{ color: 'var(--color-text)', fontWeight: 700, fontSize: '0.95rem' }}>
                    {c.category}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                    {c.pct} of monthly spend
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: '1.1rem',
                    fontWeight: 700,
                    color: 'var(--color-accent-violet)',
                  }}
                >
                  {c.total}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
