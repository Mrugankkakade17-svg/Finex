import React from 'react';
import { useAuth } from '../context/AuthContext';
import { TrendingUp, PieChart, Bell, Shield } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const displayName = user?.displayName || 'Investor';

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
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>Financial Dashboard</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Welcome back, {displayName}! Here is your current platform snapshot.
          </p>
        </div>
        <span className="badge badge-success">Live Status: Connected</span>
      </div>

      {/* Overview Stat Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '20px',
          marginBottom: '28px',
        }}
      >
        <div className="glass-card" style={{ padding: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <span style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Total Portfolio Valuation
            </span>
            <PieChart size={20} color="var(--color-accent-coral)" />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.9rem',
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: '4px',
            }}
          >
            ₹ 1,24,850
          </div>
          <div
            style={{
              fontSize: '0.82rem',
              color: '#16654E',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <TrendingUp size={14} /> +4.2% overall progress
          </div>
        </div>

        <div className="glass-card" style={{ padding: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <span style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Paper Account Balance
            </span>
            <TrendingUp size={20} color="var(--color-accent-violet)" />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.9rem',
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: '4px',
            }}
          >
            ₹ 50,000
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
            Virtual Cash Available
          </div>
        </div>

        <div className="glass-card" style={{ padding: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <span style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Active Smart Alerts
            </span>
            <Bell size={20} color="var(--color-accent-coral)" />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.9rem',
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: '4px',
            }}
          >
            3 Active
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--color-accent-violet)', fontWeight: 600 }}>
            All thresholds on track
          </div>
        </div>

        <div className="glass-card" style={{ padding: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <span style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Risk Classification
            </span>
            <Shield size={20} color="var(--color-accent-violet)" />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.9rem',
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: '4px',
            }}
          >
            {user?.riskProfile || 'MODERATE'}
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--color-accent-violet)', fontWeight: 600 }}>
            Verified Rhythm
          </div>
        </div>
      </div>
    </div>
  );
};
