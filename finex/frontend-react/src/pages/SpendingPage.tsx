import React, { useState } from 'react';
import { CreditCard, Upload, CheckCircle2 } from 'lucide-react';

export const SpendingPage: React.FC = () => {
  const [uploaded, setUploaded] = useState(false);

  const categories = [
    { category: 'Housing & Utilities', total: '$1,850.00', pct: '45%' },
    { category: 'Groceries & Dining', total: '$620.00', pct: '15%' },
    { category: 'Investment & Savings', total: '$1,200.00', pct: '30%' },
    { category: 'Entertainment', total: '$410.00', pct: '10%' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Spending Trends & CSV Upload</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Privacy-controlled spending classification & monthly analysis
          </p>
        </div>
        <span className="badge badge-info">Privacy Shield Active</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* CSV Upload Container */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={20} color="#10b981" /> Import CSV Statements
          </h3>

          <div
            onClick={() => setUploaded(true)}
            style={{
              padding: '36px',
              borderRadius: '12px',
              border: '2px dashed var(--border-glass-hover)',
              background: 'rgba(255, 255, 255, 0.02)',
              textAlign: 'center',
              cursor: 'pointer',
              marginBottom: '20px',
              transition: 'all var(--transition-fast)',
            }}
          >
            <CreditCard size={36} color="var(--primary-emerald)" style={{ margin: '0 auto 12px auto' }} />
            <div style={{ color: '#ffffff', fontWeight: 600, marginBottom: '4px' }}>Click to Upload Bank CSV</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Supports standard bank export files (Max 5MB)</div>
          </div>

          {uploaded && (
            <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#10b981', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={16} /> Statement uploaded: 42 transactions categorized with PII masking.
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '20px' }}>Monthly Breakdown</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {categories.map((c) => (
              <div key={c.category} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-glass)' }}>
                <div>
                  <div style={{ color: '#ffffff', fontWeight: 600, fontSize: '0.9rem' }}>{c.category}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.pct} of monthly spend</div>
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>{c.total}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
