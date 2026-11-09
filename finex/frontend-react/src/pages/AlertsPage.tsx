import React from 'react';
import { Bell, ShieldAlert, Check } from 'lucide-react';

export const AlertsPage: React.FC = () => {
  const alerts = [
    { id: '1', type: 'PRICE_MOVE', title: 'NVDA Volatility Alert', body: 'NVIDIA Corp moved -0.8% in last 24h', time: '10 mins ago', read: false },
    { id: '2', type: 'PORTFOLIO_RISK', title: 'Risk Alignment Check', body: 'Portfolio concentration matches your Moderate profile.', time: '2 hours ago', read: true },
    { id: '3', type: 'GOAL_PROGRESS', title: 'Retirement Goal Off-Track', body: 'Required monthly contribution increased by $50.', time: '1 day ago', read: true },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Smart Alerts & Notification Center</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Deduplicated notifications and risk triggers
          </p>
        </div>
        <button className="btn-secondary" style={{ fontSize: '0.85rem' }}>
          <Check size={14} /> Mark All as Read
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {alerts.map((a) => (
          <div
            key={a.id}
            className="glass-card"
            style={{
              padding: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderLeft: a.read ? '1px solid var(--border-glass)' : '4px solid var(--primary-emerald)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ padding: '10px', borderRadius: '10px', background: 'rgba(255,255,255,0.05)' }}>
                {a.type === 'PRICE_MOVE' ? <Bell size={20} color="#f59e0b" /> : <ShieldAlert size={20} color="#10b981" />}
              </div>
              <div>
                <h4 style={{ color: '#ffffff', marginBottom: '4px' }}>{a.title}</h4>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{a.body}</p>
              </div>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{a.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
