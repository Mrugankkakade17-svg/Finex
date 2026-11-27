import React, { useState } from 'react';
import { Bell, ShieldAlert, Check } from 'lucide-react';

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState([
    {
      id: '1',
      type: 'PRICE_MOVE',
      title: 'NVDA Volatility Alert',
      body: 'NVIDIA Corp moved -0.8% in last 24h',
      time: '10 mins ago',
      read: false,
    },
    {
      id: '2',
      type: 'PORTFOLIO_RISK',
      title: 'Risk Alignment Check',
      body: 'Portfolio concentration matches your Moderate profile.',
      time: '2 hours ago',
      read: true,
    },
    {
      id: '3',
      type: 'GOAL_PROGRESS',
      title: 'Weekend Away Goal Milestone',
      body: 'You have reached 68% of your ₹ 50,000 target!',
      time: '1 day ago',
      read: false,
    },
  ]);

  const markAllRead = () => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
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
          <p className="local-eyebrow">STAY IN ORBIT</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Smart Alerts &amp; Notification Center
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Deduplicated notifications and milestone triggers
          </p>
        </div>
        <button className="btn-secondary" onClick={markAllRead} style={{ fontSize: '0.88rem' }}>
          <Check size={14} /> Mark All as Read
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {alerts.map((a) => (
          <div
            key={a.id}
            className="glass-card"
            style={{
              padding: '20px 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              borderLeft: a.read
                ? '1px solid var(--color-surface-divider)'
                : '5px solid var(--color-accent-coral)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                style={{
                  padding: '12px',
                  borderRadius: '14px',
                  background: a.read ? 'var(--color-surface-elevated)' : 'rgba(237, 121, 93, 0.16)',
                }}
              >
                {a.type === 'PRICE_MOVE' ? (
                  <Bell size={20} color="var(--color-accent-coral)" />
                ) : (
                  <ShieldAlert size={20} color="var(--color-accent-violet)" />
                )}
              </div>
              <div>
                <h4 style={{ color: 'var(--color-text)', marginBottom: '4px', fontSize: '1.05rem' }}>
                  {a.title}
                </h4>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>{a.body}</p>
              </div>
            </div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              {a.time}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
