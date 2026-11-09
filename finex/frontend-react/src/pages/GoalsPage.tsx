import React from 'react';
import { Target, TrendingUp, Calendar } from 'lucide-react';

export const GoalsPage: React.FC = () => {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Financial Goal Planning MVP</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Deterministic projection scenarios and progress tracking
          </p>
        </div>
        <button className="btn-primary" style={{ fontSize: '0.85rem' }}>
          + Add New Goal
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Goal Card 1 */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Target size={22} color="#10b981" />
              <h3 style={{ fontSize: '1.1rem', color: '#ffffff' }}>Retirement Fund</h3>
            </div>
            <span className="badge badge-success">On Track</span>
          </div>

          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>$45,000 / $100,000</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>Target Date: Dec 2030</div>

          {/* Progress Bar */}
          <div style={{ height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden', marginBottom: '16px' }}>
            <div style={{ width: '45%', height: '100%', background: 'linear-gradient(90deg, #10b981, #06b6d4)' }} />
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Calendar size={14} /> Required Monthly Contribution: <strong>$650.00</strong>
          </div>
        </div>

        {/* Goal Card 2 */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <TrendingUp size={22} color="#6366f1" />
              <h3 style={{ fontSize: '1.1rem', color: '#ffffff' }}>Home Down Payment</h3>
            </div>
            <span className="badge badge-warning">Off Track</span>
          </div>

          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>$12,000 / $40,000</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>Target Date: Jun 2027</div>

          <div style={{ height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden', marginBottom: '16px' }}>
            <div style={{ width: '30%', height: '100%', background: 'linear-gradient(90deg, #f59e0b, #ef4444)' }} />
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Calendar size={14} /> Required Monthly Contribution: <strong>$800.00</strong>
          </div>
        </div>
      </div>
    </div>
  );
};
