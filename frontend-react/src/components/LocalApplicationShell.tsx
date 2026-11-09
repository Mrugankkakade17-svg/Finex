import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { BookOpen, Menu, X } from 'lucide-react';
import { useLocalSession } from '../context/LocalSessionContext';
import './LocalApplication.css';

const links = [
  { path: '/dashboard', label: 'Dashboard', sprint: 'S1' },
  { path: '/onboarding', label: 'Onboarding', sprint: 'S1' },
  { path: '/risk', label: 'Risk Profile', sprint: 'S2' },
  { path: '/portfolio', label: 'Portfolio', sprint: 'S2' },
  { path: '/market', label: 'Market Data', sprint: 'S3' },
  { path: '/watchlist', label: 'Watchlist', sprint: 'S3' },
  { path: '/paper-trading', label: 'Paper Trading', sprint: 'S4' },
  { path: '/goals', label: 'Goal Planning', sprint: 'S4' },
  { path: '/spending', label: 'Spending Trends', sprint: 'S5' },
  { path: '/chat', label: 'AI Assistant', sprint: 'S6' },
  { path: '/alerts', label: 'Smart Alerts', sprint: 'S6' },
  { path: '/ops', label: 'Operations & RC', sprint: 'S7' },
  { path: '/release', label: 'Release & Handover', sprint: 'S8' },
];
export function LocalApplicationShell({ children }: { children: React.ReactNode }) {
  const session = useLocalSession();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const pilot = location.pathname.startsWith('/pilot/');
  useEffect(() => {
    setMenuOpen(false);
    document.querySelector<HTMLElement>('#local-main h1, #local-main h2')?.focus();
  }, [location.key]);
  return <div className="local-app">
    <a className="local-skip" href="#local-main">Skip to content</a>
    <header className="local-header">
      <Link className="local-brand" to="/login" aria-label="FinEx home">
        <span className="local-brand__mark" aria-hidden="true"><BookOpen size={22} /></span>
        <span><strong>FinEx</strong><small>Learn. Explore. Build.</small></span>
      </Link>
      <div className="local-header__status">
        <span className="local-badge">Local educational application</span>
        {session.user && <span data-testid="local-persona">Synthetic persona · {session.user.alias}</span>}
        {session.user ? <button className="btn-secondary" disabled={session.busy}
          aria-busy={session.operation === 'logout'} onClick={() => { void session.logout(); }}>
          {session.operation === 'logout' ? 'Confirming sign-out…' : session.errorOperation === 'logout' ? 'Retry sign out' : 'Sign out'}
        </button> : <Link className="btn-secondary" to="/login">Persona sign-in</Link>}
        <button className="local-menu btn-secondary" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={menuOpen} aria-controls="local-navigation" onClick={() => setMenuOpen((open) => !open)}>
          {menuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
        </button>
      </div>
    </header>
    <div className="local-layout">
      <aside id="local-navigation" className="local-sidebar" data-open={menuOpen}>
        <p className="local-eyebrow">Your learning journey</p>
        <nav aria-label="Local application">
          {links.map((link) => <NavLink key={link.path} to={link.path} aria-label={link.label}
            className={({ isActive }) => isActive ? 'local-nav-link local-nav-link--active' : 'local-nav-link'}>
            <span>{link.label}</span><span className="local-nav-sprint" aria-hidden="true">{link.sprint}</span>
          </NavLink>)}
        </nav>
        <div className="local-sidebar__note">
          <p>Only delivered features are active. Later sprints show an explicit pending state.</p>
        </div>
        <nav className="local-pilot-nav" aria-label="Compatibility pilots">
          <p className="local-eyebrow">Separate contract pilots</p>
          <Link to="/pilot/consent">Pilot consent</Link>
          <Link to="/pilot/onboarding">Pilot profile</Link>
          <Link to="/pilot/risk">Pilot risk</Link>
        </nav>
      </aside>
      <main id="local-main" tabIndex={-1} className="local-main">
        {session.errorOperation === 'logout' && <div className="local-error" role="alert">
          <strong>Sign-out was not confirmed.</strong> Your session and unsaved input are retained. {session.error?.message}
        </div>}
        {pilot && <div className="local-pilot-banner">Compatibility pilot — not saved to a persona</div>}
        {children}
        <footer className="local-footer">Synthetic local learning only · No real account, money or investment advice.</footer>
      </main>
    </div>
  </div>;
}
