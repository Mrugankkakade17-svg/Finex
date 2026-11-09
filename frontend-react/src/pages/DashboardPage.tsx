import React from 'react';
import { useAuth } from '../context/AuthContext';
import { TrendingUp, PieChart, Bell, Shield } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Financial Dashboard</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Welcome back, {user?.displayName}! Here is your current platform snapshot.
          </p>
        </div>
        <span className="badge badge-success">Live Status: Connected</span>
      </div>

      {/* Overview Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '28px' }}>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Total Portfolio Valuation</span>
            <PieChart size={20} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>$124,850.00</div>
          <div style={{ fontSize: '0.8rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <TrendingUp size={14} /> +4.2% overall gain
          </div>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Paper Account Balance</span>
            <TrendingUp size={20} color="#6366f1" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>$10,000.00</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Virtual Cash Available</div>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Active Smart Alerts</span>
            <Bell size={20} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>3 Active</div>
          <div style={{ fontSize: '0.8rem', color: '#f59e0b' }}>0 Triggers today</div>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Risk Classification</span>
            <Shield size={20} color="#06b6d4" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>{user?.riskProfile || 'MODERATE'}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>Verified Score</div>
        </div>
      </div>
    </div>
  );
};
