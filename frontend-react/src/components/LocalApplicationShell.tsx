import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X, Sun, Sparkles } from 'lucide-react';
import { useLocalSession } from '../context/LocalSessionContext';
import { useAuth } from '../context/AuthContext';
import './LocalApplication.css';

const links = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/onboarding', label: 'Onboarding' },
  { path: '/risk', label: 'Risk profile' },
  { path: '/portfolio', label: 'Portfolio' },
  { path: '/market', label: 'Market Data' },
  { path: '/watchlist', label: 'Watchlist' },
  { path: '/paper-trading', label: 'Paper Trading' },
  { path: '/goals', label: 'Goal Planning' },
  { path: '/spending', label: 'Spending Trends' },
  { path: '/chat', label: 'AI Assistant' },
  { path: '/alerts', label: 'Smart Alerts' },
  { path: '/ops', label: 'Operations & RC' },
  { path: '/release', label: 'Release & Handover' },
];

function FinexAsterisk() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      <line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}

export function LocalApplicationShell({ children }: { children: React.ReactNode }) {
  const session = useLocalSession();
  const { user: authUser, isAuthenticated, logout: authLogout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, setTheme] = useState<'gme' | 'ledger'>(() => {
    return (localStorage.getItem('finex_theme_mode') as 'gme' | 'ledger') || 'gme';
  });

  const pilot = location.pathname.startsWith('/pilot/');

  useEffect(() => {
    setMenuOpen(false);
    document.querySelector<HTMLElement>('#local-main h1, #local-main h2')?.focus();
  }, [location.key]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('finex_theme_mode', theme);
  }, [theme]);

  const activeUserName =
    session.onboarding?.draft?.display_name?.trim() ||
    (isAuthenticated && authUser?.displayName ? authUser.displayName : null) ||
    session.user?.alias ||
    null;

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'gme' ? 'ledger' : 'gme'));
  };

  const handleSignOut = async () => {
    if (session.user) {
      await session.logout();
    }
    if (isAuthenticated) {
      authLogout();
    }
    navigate('/login');
  };

  return (
    <div className="local-app" data-theme={theme}>
      <a className="local-skip" href="#local-main">
        Skip to content
      </a>

      {/* Top Navigation Bar — Good Money Energy Header */}
      <header className="local-header">
        <Link className="local-brand" to="/login" aria-label="FinEx home">
          <div>
            <span className="local-brand__wordmark">
              finex
              <span className="local-brand__asterisk">
                <FinexAsterisk />
              </span>
            </span>
            <small>Your Money, In Your Orbit</small>
          </div>
        </Link>

        <nav className="local-top-nav" aria-label="Primary quick links">
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              isActive ? 'local-top-nav__link local-top-nav__link--active' : 'local-top-nav__link'
            }
          >
            For you
          </NavLink>
          <NavLink
            to="/goals"
            className={({ isActive }) =>
              isActive ? 'local-top-nav__link local-top-nav__link--active' : 'local-top-nav__link'
            }
          >
            For your goals
          </NavLink>
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              isActive ? 'local-top-nav__link local-top-nav__link--active' : 'local-top-nav__link'
            }
          >
            Learn
          </NavLink>
        </nav>

        <div className="local-header__status">
          <button
            type="button"
            className="local-theme-toggle"
            onClick={toggleTheme}
            title="Switch between Good Money Energy and Ledger in Orbit theme"
          >
            {theme === 'gme' ? <Sun size={14} /> : <Sparkles size={14} />}
            <span>{theme === 'gme' ? 'Good Money Energy' : 'Ledger in Orbit'}</span>
          </button>

          {session.user && (
            <span data-testid="local-persona" className="local-user-pill">
              <span className="local-user-pill__avatar" aria-hidden="true">
                {(activeUserName || session.user.alias).charAt(0).toUpperCase()}
              </span>
              <span>
                {activeUserName && activeUserName !== session.user.alias
                  ? `${activeUserName} · ${session.user.alias}`
                  : `Synthetic persona · ${session.user.alias}`}
              </span>
            </span>
          )}

          {!session.user && isAuthenticated && activeUserName && (
            <span className="local-user-pill">
              <span className="local-user-pill__avatar" aria-hidden="true">
                {activeUserName.charAt(0).toUpperCase()}
              </span>
              <span>{activeUserName}</span>
            </span>
          )}

          {session.user || isAuthenticated ? (
            <button
              className="btn-secondary"
              disabled={session.busy}
              aria-busy={session.operation === 'logout'}
              onClick={() => {
                void handleSignOut();
              }}
            >
              {session.operation === 'logout'
                ? 'Confirming sign-out…'
                : session.errorOperation === 'logout'
                  ? 'Retry sign out'
                  : 'Sign out'}
            </button>
          ) : (
            <Link className="btn-dark-pill" to="/login">
              <span>Let&apos;s go</span>
              <span className="gme-hero__cta-arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
          )}

          <button
            className="local-menu btn-secondary"
            aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={menuOpen}
            aria-controls="local-navigation"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
        </div>
      </header>

      {/* Good Money Energy Hero Banner (shown on Login & Dashboard) */}
      {(location.pathname === '/login' || location.pathname === '/dashboard') && (
        <section className="gme-hero" aria-label="FinEx highlight">
          <div className="gme-hero__inner">
            <div className="gme-hero__content">
              <p className="gme-hero__eyebrow">YOUR MONEY, IN YOUR ORBIT</p>
              <h2 className="gme-hero__title">
                Small steps.
                <br />
                Big future energy.
              </h2>
              <p className="gme-hero__subtitle">
                Make a little progress today, and feel it add up tomorrow.
                {activeUserName ? ` Welcome back, ${activeUserName}!` : ''}
              </p>
              <div className="gme-hero__cta-row">
                <Link
                  className="gme-hero__cta"
                  to={session.user || isAuthenticated ? '/goals' : '/onboarding'}
                >
                  <span>Build your money rhythm</span>
                  <span className="gme-hero__cta-arrow" aria-hidden="true">
                    ↗
                  </span>
                </Link>
              </div>
            </div>

            <div className="gme-hero__visual" aria-hidden="true">
              <div className="gme-shape-lime" />
              <div className="gme-shape-violet" />
              <div
                className="gme-savings-card"
                onClick={() => navigate('/goals')}
                role="presentation"
              >
                <div className="gme-savings-card__label">NEXT GOAL</div>
                <div className="gme-savings-card__amount">₹ 50,000</div>
                <div className="gme-savings-card__divider" />
                <div className="gme-savings-card__progress-track">
                  <div className="gme-savings-card__progress-fill" />
                </div>
                <div className="gme-savings-card__footer">
                  <span>Weekend away</span>
                  <span className="gme-savings-card__pct">68%</span>
                </div>
              </div>
            </div>
          </div>

          <div className="gme-strip">
            <div className="gme-strip__inner">
              <span className="gme-strip__item">Spend with intention</span>
              <span className="gme-strip__item">Save in your own rhythm</span>
              <span className="gme-strip__item">Grow with confidence</span>
            </div>
          </div>
        </section>
      )}

      <div className="local-layout">
        <aside id="local-navigation" className="local-sidebar" data-open={menuOpen}>
          <p className="local-eyebrow">Your money orbit</p>
          <nav aria-label="Local application">
            {links.map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                aria-label={link.label}
                className={({ isActive }) =>
                  isActive ? 'local-nav-link local-nav-link--active' : 'local-nav-link'
                }
              >
                <span>{link.label}</span>
                <span className="local-nav-dot" aria-hidden="true" />
              </NavLink>
            ))}
          </nav>
          <div className="local-sidebar__note">
            <p>Explore your personal finance rhythm, goals, portfolios, and grounded AI insights.</p>
          </div>
          <nav className="local-pilot-nav" aria-label="Compatibility pilots">
            <p className="local-eyebrow">Guided experiences</p>
            <Link to="/pilot/consent">Pilot consent</Link>
            <Link to="/pilot/onboarding">Pilot profile</Link>
            <Link to="/pilot/risk">Pilot risk</Link>
          </nav>
        </aside>

        <main id="local-main" tabIndex={-1} className="local-main">
          {session.errorOperation === 'logout' && (
            <div className="local-error" role="alert">
              <strong>Sign-out was not confirmed.</strong> Your session and unsaved input are retained.{' '}
              {session.error?.message}
            </div>
          )}
          {pilot && (
            <div className="local-pilot-banner">
              Guided interactive preview — explore at your own pace
            </div>
          )}
          {children}
          <footer className="local-footer">
            finex* · Small steps. Big future energy. · Educational financial intelligence platform.
          </footer>
        </main>
      </div>
    </div>
  );
}
