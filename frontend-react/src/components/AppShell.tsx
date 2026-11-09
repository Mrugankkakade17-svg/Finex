import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './AppShell.css';
import {
  LayoutDashboard,
  PieChart,
  Bot,
  TrendingUp,
  Bell,
  Target,
  CreditCard,
  UserCheck,
  LogOut,
  LogIn,
  ShieldCheck,
  Menu,
  X,
  Sparkles,
  Search,
  Star,
} from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { user, isAuthenticated, toggleAuth, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isPilot = ['/consent', '/onboarding', '/risk'].includes(location.pathname);

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/portfolio', label: 'Portfolio', icon: PieChart },
    { path: '/market', label: 'Market', icon: Search },
    { path: '/watchlist', label: 'Watchlist', icon: Star },
    { path: '/chat', label: 'AI Assistant', icon: Bot },
    { path: '/paper-trading', label: 'Paper Trading', icon: TrendingUp },
    { path: '/alerts', label: 'Smart Alerts', icon: Bell },
    { path: '/goals', label: 'Goals', icon: Target },
    { path: '/spending', label: 'Spending', icon: CreditCard },
    { path: '/onboarding', label: 'Onboarding', icon: UserCheck },
    { path: '/risk', label: 'Educational Risk', icon: ShieldCheck },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-dark)' }}>
      {/* Sidebar Navigation for Desktop */}
      <aside
        id="platform-navigation"
        className={`app-sidebar${mobileMenuOpen ? ' app-sidebar--open' : ''}`}
        style={{
          backgroundColor: 'var(--bg-sidebar)',
          borderRight: '1px solid var(--border-glass)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 40,
          backdropFilter: 'blur(16px)',
          transition: 'transform var(--transition-normal)',
        }}
      >
        {/* Logo & Task Header */}
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-glass)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #10b981, #6366f1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 15px rgba(16, 185, 129, 0.4)',
              }}
            >
              <Sparkles size={20} color="#ffffff" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.25rem', color: '#ffffff', lineHeight: 1.2 }}>FinEx</h1>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Financial Excellence
              </span>
            </div>
          </div>
          <div
            style={{
              marginTop: '12px',
              padding: '4px 8px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--border-glass)',
              fontSize: '0.7rem',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>{location.pathname === '/risk' ? 'Sprint 2' : 'Sprint 1'}</span>
            <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>
              Local pilot
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
          <div
            style={{
              fontSize: '0.7rem',
              textTransform: 'uppercase',
              color: 'var(--text-muted)',
              fontWeight: 700,
              padding: '0 12px 8px 12px',
              letterSpacing: '0.05em',
            }}
          >
            Platform Modules
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  marginBottom: '4px',
                  color: isActive ? '#ffffff' : 'var(--text-secondary)',
                  backgroundColor: isActive ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                  border: isActive ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid transparent',
                  textDecoration: 'none',
                  fontSize: '0.9rem',
                  fontWeight: isActive ? 600 : 500,
                  transition: 'all var(--transition-fast)',
                }}
              >
                <Icon size={18} color={isActive ? '#10b981' : '#94a3b8'} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer User Info */}
        <div
          style={{
            padding: '16px',
            borderTop: '1px solid var(--border-glass)',
            backgroundColor: 'rgba(0,0,0,0.2)',
          }}
        >
          {isPilot ? (
            <div>
              <div style={{ fontWeight: 600 }}>Educational pilot</div>
              <div style={{ fontSize: '0.8rem' }}>No saved assessment</div>
            </div>
          ) : isAuthenticated && user ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <img
                  src={user.avatarUrl}
                  alt={user.displayName}
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    border: '2px solid var(--primary-emerald)',
                  }}
                />
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ffffff' }}>
                    {user.displayName}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {user.riskProfile} Risk
                  </div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                title="Sign Out"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '6px',
                }}
              >
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <LogIn size={16} /> Sign In
            </button>
          )}
        </div>
      </aside>
      {mobileMenuOpen && (
        <button
          className="app-nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Main Content Area */}
      <div
        className="app-content"
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}
      >
        {/* Top App Header */}
        <header
          className="app-header"
          style={{
            backgroundColor: 'rgba(15, 23, 42, 0.8)',
            backdropFilter: 'blur(12px)',
            borderBottom: '1px solid var(--border-glass)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            position: 'sticky',
            top: 0,
            zIndex: 30,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              className="app-nav-toggle"
              aria-label="Toggle navigation"
              aria-expanded={mobileMenuOpen}
              aria-controls="platform-navigation"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Route:{' '}
              <strong style={{ color: 'var(--primary-emerald)' }}>{location.pathname}</strong>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Quick Mock Auth Toggle Button */}
            {!isPilot && (
              <button
                onClick={toggleAuth}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '20px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: isAuthenticated
                    ? 'rgba(16, 185, 129, 0.15)'
                    : 'rgba(239, 68, 68, 0.15)',
                  color: isAuthenticated ? '#10b981' : '#ef4444',
                  border: isAuthenticated
                    ? '1px solid rgba(16, 185, 129, 0.3)'
                    : '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                <ShieldCheck size={14} />
                <span>Mock Auth: {isAuthenticated ? 'Authenticated' : 'Unauthenticated'}</span>
              </button>
            )}

            <span className="badge badge-info">React client</span>
          </div>
        </header>

        {/* Page Component Body */}
        <main
          className="app-main"
          style={{ flex: 1, maxWidth: '1400px', width: '100%', margin: '0 auto' }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};
