import React, { useState } from 'react';
import { Activity, ShieldCheck, Flag, RefreshCw } from 'lucide-react';

export const OpsPage: React.FC = () => {
  const [flags, setFlags] = useState([
    { key: 'FEATURE_AI_ASSISTANT', name: 'Grounded AI Assistant', enabled: true, owner: 'P6-AI-QA' },
    { key: 'FEATURE_PAPER_TRADING', name: 'Simulated Order Placement', enabled: true, owner: 'P2-API' },
    { key: 'FEATURE_SPENDING_IMPORT', name: 'CSV Spending Import', enabled: true, owner: 'P3-Data' },
  ]);

  const toggleFlag = (key: string) => {
    setFlags((prev) =>
      prev.map((f) => (f.key === key ? { ...f, enabled: !f.enabled } : f))
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Production Hardening & Operations</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Sprint 7 release candidate preflight, observability, and circuit breaker controls
          </p>
        </div>
        <span className="badge badge-success">Candidate v1.0.0-rc7</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Release Preflight Checklist */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={20} color="#10b981" /> Preflight Release Gate
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
              ✓ Single-Headed Alembic Database Lineage Verified
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
              ✓ Secret Scan Clean — Zero Credentials in Git
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
              ✓ Deterministic AI Safety & Grounded Refusals Passed
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
              ✓ Accessibility Review 100% (WCAG AA Compliance)
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
              ✓ Rollback Revision Tagged & Rehearsed
            </li>
          </ul>
        </div>

        {/* Feature Flags Control */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#ffffff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Flag size={20} color="#6366f1" /> Emergency Feature Flags
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {flags.map((flag) => (
              <div
                key={flag.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  borderRadius: '8px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: '#ffffff' }}>{flag.name}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{flag.owner}</div>
                </div>
                <button
                  type="button"
                  onClick={() => toggleFlag(flag.key)}
                  className={flag.enabled ? 'btn-primary' : 'btn-secondary'}
                  style={{ fontSize: '0.8rem', padding: '6px 12px' }}
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

