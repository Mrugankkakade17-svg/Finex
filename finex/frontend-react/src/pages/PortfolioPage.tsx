import React from 'react';
import { PieChart, ArrowUpRight, ArrowDownRight, RefreshCw } from 'lucide-react';

export const PortfolioPage: React.FC = () => {
  const holdings = [
    { symbol: 'AAPL', name: 'Apple Inc.', qty: '50', price: '$185.50', value: '$9,275.00', change: '+1.2%', positive: true },
    { symbol: 'MSFT', name: 'Microsoft Corp.', qty: '30', price: '$415.20', value: '$12,456.00', change: '+2.4%', positive: true },
    { symbol: 'NVDA', name: 'NVIDIA Corp.', qty: '15', price: '$875.00', value: '$13,125.00', change: '-0.8%', positive: false },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', qty: '40', price: '$155.10', value: '$6,204.00', change: '+0.5%', positive: true },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#ffffff' }}>Portfolio Holdings & Analytics</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Deterministic portfolio tracking and allocation metrics
          </p>
        </div>
        <button className="btn-secondary" style={{ fontSize: '0.85rem' }}>
          <RefreshCw size={14} /> Refresh Quotes (Cached 15m)
        </button>
      </div>

      {/* Holdings Table */}
      <div className="glass-card" style={{ padding: '24px', overflowX: 'auto' }}>
        <h3 style={{ fontSize: '1.1rem', color: '#ffffff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <PieChart size={18} color="#10b981" /> Current Positions
        </h3>

        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '12px 16px' }}>Symbol</th>
              <th style={{ padding: '12px 16px' }}>Asset Name</th>
              <th style={{ padding: '12px 16px' }}>Quantity</th>
              <th style={{ padding: '12px 16px' }}>Market Price</th>
              <th style={{ padding: '12px 16px' }}>Total Value</th>
              <th style={{ padding: '12px 16px' }}>Day Change</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.symbol} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '14px 16px', fontWeight: 700, color: '#ffffff' }}>{h.symbol}</td>
                <td style={{ padding: '14px 16px', color: 'var(--text-secondary)' }}>{h.name}</td>
                <td style={{ padding: '14px 16px', color: '#ffffff' }}>{h.qty}</td>
                <td style={{ padding: '14px 16px', color: '#ffffff' }}>{h.price}</td>
                <td style={{ padding: '14px 16px', fontWeight: 600, color: '#ffffff' }}>{h.value}</td>
                <td style={{ padding: '14px 16px', color: h.positive ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                    {h.positive ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                    {h.change}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
