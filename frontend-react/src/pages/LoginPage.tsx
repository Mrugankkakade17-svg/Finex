import React, { FormEvent, useState } from 'react';
import { realAuthService } from '../services/authService';

type Mode = 'login' | 'register';

export const LoginPage: React.FC = () => {
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    setError('');
    setMessage('');
    setBusy(true);
    try {
      if (mode === 'register') await realAuthService.register(name.trim(), email.trim(), password);
      else await realAuthService.login(email.trim(), password);
      setMessage(mode === 'register'
        ? 'Your account was created. You can now sign in.'
        : 'Sign-in succeeded. Real-account sessions are not connected to the local educational application.');
      if (mode === 'register') {
        setMode('login');
        setPassword('');
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Authentication failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setError('');
    setMessage('');
  };

  return <main style={{ maxWidth: 440, margin: '48px auto', padding: 24 }}>
    <section className="glass-card" style={{ padding: 32 }}>
      <h1 style={{ color: '#fff', marginTop: 0 }}>FinEx account</h1>
      <p style={{ color: 'var(--text-secondary)' }}>Create an account or sign in to your existing account.</p>
      <div role="tablist" aria-label="Account access" style={{ display: 'flex', gap: 8, margin: '24px 0' }}>
        <button type="button" role="tab" aria-selected={mode === 'login'} onClick={() => switchMode('login')} className="btn-primary">Sign in</button>
        <button type="button" role="tab" aria-selected={mode === 'register'} onClick={() => switchMode('register')} className="btn-primary">Create account</button>
      </div>
      <form onSubmit={submit} noValidate>
        {mode === 'register' && <label style={{ display: 'block', marginBottom: 16, color: '#fff' }}>
          Full name
          <input autoComplete="name" required minLength={2} maxLength={100} value={name} onChange={(event) => setName(event.target.value)} style={fieldStyle} />
        </label>}
        <label style={{ display: 'block', marginBottom: 16, color: '#fff' }}>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} style={fieldStyle} />
        </label>
        <label style={{ display: 'block', marginBottom: 20, color: '#fff' }}>
          Password
          <input type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} required minLength={mode === 'register' ? 8 : undefined} maxLength={64} value={password} onChange={(event) => setPassword(event.target.value)} style={fieldStyle} />
        </label>
        {error && <p role="alert" style={{ color: '#f87171' }}>{error}</p>}
        {message && <p role="status" style={{ color: '#34d399' }}>{message}</p>}
        <button type="submit" className="btn-primary" disabled={busy} style={{ width: '100%', justifyContent: 'center' }}>
          {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}
        </button>
      </form>
      <p style={{ marginTop: 20, color: 'var(--text-secondary)', fontSize: 13 }}>
        Real account access is enabled for this deployment. Local persona sign-in remains available when this feature is turned off.
      </p>
    </section>
  </main>;
};

const fieldStyle: React.CSSProperties = {
  display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 6, padding: 12,
  borderRadius: 8, border: '1px solid #475569', background: '#0f172a', color: '#fff',
};

