import React, { useState } from 'react';
import { ShieldCheck, Flag } from 'lucide-react';

export const OpsPage: React.FC = () => {
  const [flags, setFlags] = useState([
    {
      key: 'FEATURE_AI_ASSISTANT',
      name: 'Grounded AI Assistant',
      enabled: true,
      owner: 'AI & Knowledge Engineering',
    },
    {
      key: 'FEATURE_PAPER_TRADING',
      name: 'Simulated Order Placement',
      enabled: true,
      owner: 'Trading & Identity Core',
    },
    {
      key: 'FEATURE_SPENDING_IMPORT',
      name: 'CSV Spending Import',
      enabled: true,
      owner: 'Privacy & Data Quality',
    },
  ]);

  const toggleFlag = (key: string) => {
    setFlags((prev) => prev.map((f) => (f.key === key ? { ...f, enabled: !f.enabled } : f)));
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
          <p className="local-eyebrow">PLATFORM RELIABILITY</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Production Hardening &amp; Operations
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Release candidate preflight, observability, and circuit breaker controls
          </p>
        </div>
        <span className="badge badge-success">Candidate v1.0.0</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}
      >
        {/* Release Preflight Checklist */}
        <div className="glass-card" style={{ padding: '26px' }}>
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
            <ShieldCheck size={20} color="#16654E" /> Preflight Release Gate
          </h3>
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#16654E', fontWeight: 600 }}>
              ✓ Single-Headed Alembic Database Lineage Verified
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#16654E', fontWeight: 600 }}>
              ✓ Secret Scan Clean — Zero Credentials in Git
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#16654E', fontWeight: 600 }}>
              ✓ Deterministic AI Safety &amp; Grounded Refusals Passed
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#16654E', fontWeight: 600 }}>
              ✓ Accessibility Review 100% (WCAG AA Compliance)
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#16654E', fontWeight: 600 }}>
              ✓ Rollback Revision Tagged &amp; Rehearsed
            </li>
          </ul>
        </div>

        {/* Feature Flags Control */}
        <div className="glass-card" style={{ padding: '26px' }}>
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
            <Flag size={20} color="var(--color-accent-violet)" /> Emergency Feature Flags
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {flags.map((flag) => (
              <div
                key={flag.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  background: '#F6FAF7',
                  border: '1px solid var(--color-surface-divider)',
                  borderRadius: '14px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>{flag.name}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                    {flag.owner}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => toggleFlag(flag.key)}
                  className={flag.enabled ? 'btn-primary' : 'btn-secondary'}
                  style={{ fontSize: '0.78rem', padding: '8px 16px' }}
                >
                  {flag.enabled ? 'ACTIVE' : 'DISABLED'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
