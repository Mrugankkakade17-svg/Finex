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
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-page)' }}>
      {/* Sidebar Navigation for Desktop */}
      <aside
        id="platform-navigation"
        className={`app-sidebar${mobileMenuOpen ? ' app-sidebar--open' : ''}`}
        style={{
          backgroundColor: 'var(--color-surface)',
          borderRight: '1px solid var(--color-surface-divider)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 40,
          transition: 'transform var(--transition-normal)',
        }}
      >
        {/* Logo Header */}
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--color-surface-divider)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'var(--color-accent-coral)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 6px 16px rgba(255, 114, 94, 0.3)',
              }}
            >
              <Sparkles size={20} color="#ffffff" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.35rem', color: 'var(--color-text)', lineHeight: 1.2 }}>
                finex*
              </h1>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                Your Money, In Your Orbit
              </span>
            </div>
          </div>
          <div
            style={{
              marginTop: '12px',
              padding: '6px 10px',
              borderRadius: '8px',
              background: '#F4F9F6',
              border: '1px solid var(--color-surface-divider)',
              fontSize: '0.72rem',
              color: 'var(--color-text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>Good Money Energy</span>
            <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>
              Active
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
          <div
            style={{
              fontSize: '0.7rem',
              textTransform: 'uppercase',
              color: 'var(--color-text-muted)',
              fontWeight: 800,
              padding: '0 12px 8px 12px',
              letterSpacing: '0.08em',
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
                  borderRadius: '12px',
                  marginBottom: '4px',
                  color: isActive ? '#ffffff' : 'var(--color-text-muted)',
                  backgroundColor: isActive ? 'var(--color-text)' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '0.9rem',
                  fontWeight: isActive ? 700 : 600,
                  transition: 'all var(--transition-fast)',
                }}
              >
                <Icon size={18} color={isActive ? '#E6ED73' : '#496368'} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer User Info */}
        <div
          style={{
            padding: '16px',
            borderTop: '1px solid var(--color-surface-divider)',
            backgroundColor: '#F7FAF8',
          }}
        >
          {isPilot ? (
            <div>
              <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>Educational pilot</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                No saved assessment
              </div>
            </div>
          ) : isAuthenticated && user ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    background: 'var(--color-accent-violet)',
                    color: '#FFFFFF',
                    display: 'grid',
                    placeItems: 'center',
                    fontWeight: 800,
                  }}
                >
                  {user.displayName.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text)' }}>
                    {user.displayName}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                    {user.riskProfile} Profile
                  </div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                title="Sign Out"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-text-muted)',
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
            <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              Route:{' '}
              <strong style={{ color: 'var(--color-accent-violet)' }}>{location.pathname}</strong>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {!isPilot && (
              <button
                onClick={toggleAuth}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 14px',
                  borderRadius: '999px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  background: isAuthenticated
                    ? 'rgba(29, 122, 95, 0.12)'
                    : 'rgba(217, 72, 59, 0.12)',
                  color: isAuthenticated ? '#16654E' : '#B42318',
                  border: isAuthenticated
                    ? '1px solid rgba(29, 122, 95, 0.3)'
                    : '1px solid rgba(217, 72, 59, 0.3)',
                }}
              >
                <ShieldCheck size={14} />
                <span>
                  {isAuthenticated
                    ? `Signed in: ${user?.displayName || 'Investor'}`
                    : 'Unauthenticated'}
                </span>
              </button>
            )}

            <span className="badge badge-info">finex* Web</span>
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
