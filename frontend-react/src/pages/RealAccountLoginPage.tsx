import React, { FormEvent, useState } from 'react';
import { ApiClientError } from '../services/apiClient';
import { realAuthService } from '../services/authService';

type Mode = 'login' | 'register';

interface FieldErrors {
  name?: string;
  email?: string;
  password?: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateFields(
  mode: Mode,
  name: string,
  email: string,
  password: string,
): { errors: FieldErrors; trimmedName: string; trimmedEmail: string } {
  const errors: FieldErrors = {};
  const trimmedName = name.trim();
  const trimmedEmail = email.trim();

  if (mode === 'register') {
    if (!trimmedName) {
      errors.name = 'Full name is required.';
    } else if (trimmedName.length < 2) {
      errors.name = 'Full name must be at least 2 characters.';
    } else if (trimmedName.length > 100) {
      errors.name = 'Full name must be 100 characters or fewer.';
    }
  }

  if (!trimmedEmail) {
    errors.email = 'Email is required.';
  } else if (!EMAIL_PATTERN.test(trimmedEmail)) {
    errors.email = 'Enter a valid email address.';
  }

  if (!password) {
    errors.password = 'Password is required.';
  } else if (mode === 'register' && password.length < 8) {
    errors.password = 'Password must be at least 8 characters.';
  } else if (password.length > 64) {
    errors.password = 'Password must be 64 characters or fewer.';
  }

  return { errors, trimmedName, trimmedEmail };
}

export const RealAccountLoginPage: React.FC = () => {
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const clearFieldError = (field: keyof FieldErrors) => {
    setFieldErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setMessage('');

    const { errors, trimmedName, trimmedEmail } = validateFields(mode, name, email, password);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setError('Please fix the highlighted fields and try again.');
      return;
    }

    setFieldErrors({});
    setBusy(true);
    try {
      if (mode === 'register') {
        await realAuthService.register(trimmedName, trimmedEmail, password);
        setName(trimmedName);
        setEmail(trimmedEmail);
        setPassword('');
        setMode('login');
        setMessage('Your account was created. You can now sign in.');
      } else {
        await realAuthService.login(trimmedEmail, password);
        setEmail(trimmedEmail);
        setPassword('');
        setMessage(
          'Sign-in succeeded. Real-account sessions are not connected to the local educational application.',
        );
      }
    } catch (failure) {
      if (failure instanceof ApiClientError) {
        if (failure.fieldErrors && Object.keys(failure.fieldErrors).length > 0) {
          setFieldErrors({
            name: failure.fieldErrors.name,
            email: failure.fieldErrors.email,
            password: failure.fieldErrors.password,
          });
        }
        setError(failure.message);
      } else {
        setError('Authentication failed. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setPassword('');
    setFieldErrors({});
    setError('');
    setMessage('');
  };

  return (
    <main style={{ maxWidth: 460, margin: '48px auto', padding: 24 }}>
      <section className="glass-card" style={{ padding: 32 }}>
        <h1 style={{ color: 'var(--color-text)', marginTop: 0, marginBottom: 8 }}>
          FinEx account
        </h1>
        <p style={{ color: 'var(--color-text-muted)', marginTop: 0 }}>
          Create an account or sign in to your existing account.
        </p>

        <div
          role="tablist"
          aria-label="Account access"
          style={{ display: 'flex', gap: 8, margin: '24px 0' }}
        >
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            onClick={() => switchMode('login')}
            className={mode === 'login' ? 'btn-primary' : 'btn-secondary'}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            onClick={() => switchMode('register')}
            className={mode === 'register' ? 'btn-primary' : 'btn-secondary'}
          >
            Create account
          </button>
        </div>

        <form onSubmit={submit} noValidate>
          {mode === 'register' && (
            <div style={{ marginBottom: 16 }}>
              <label
                htmlFor="real-auth-name"
                style={{ display: 'block', color: 'var(--color-text)', fontWeight: 600 }}
              >
                Full name
              </label>
              <input
                id="real-auth-name"
                name="name"
                type="text"
                autoComplete="name"
                required
                maxLength={100}
                value={name}
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? 'real-auth-name-error' : undefined}
                onChange={(event) => {
                  setName(event.target.value);
                  clearFieldError('name');
                }}
                style={fieldStyle}
              />
              {fieldErrors.name && (
                <p id="real-auth-name-error" role="alert" style={fieldErrorStyle}>
                  {fieldErrors.name}
                </p>
              )}
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label
              htmlFor="real-auth-email"
              style={{ display: 'block', color: 'var(--color-text)', fontWeight: 600 }}
            >
              Email
            </label>
            <input
              id="real-auth-email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? 'real-auth-email-error' : undefined}
              onChange={(event) => {
                setEmail(event.target.value);
                clearFieldError('email');
              }}
              style={fieldStyle}
            />
            {fieldErrors.email && (
              <p id="real-auth-email-error" role="alert" style={fieldErrorStyle}>
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div style={{ marginBottom: 20 }}>
            <label
              htmlFor="real-auth-password"
              style={{ display: 'block', color: 'var(--color-text)', fontWeight: 600 }}
            >
              Password
            </label>
            <input
              id="real-auth-password"
              name="password"
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              required
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={64}
              value={password}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={fieldErrors.password ? 'real-auth-password-error' : undefined}
              onChange={(event) => {
                setPassword(event.target.value);
                clearFieldError('password');
              }}
              style={fieldStyle}
            />
            {fieldErrors.password && (
              <p id="real-auth-password-error" role="alert" style={fieldErrorStyle}>
                {fieldErrors.password}
              </p>
            )}
          </div>

          {error && (
            <p role="alert" style={{ color: 'var(--status-error)', marginBottom: 16 }}>
              {error}
            </p>
          )}
          {message && (
            <p role="status" style={{ color: 'var(--status-success)', marginBottom: 16 }}>
              {message}
            </p>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={busy}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <p style={{ marginTop: 20, color: 'var(--color-text-muted)', fontSize: 13 }}>
          Real account access is enabled for this deployment. Local persona sign-in remains
          available when this feature is turned off.
        </p>
      </section>
    </main>
  );
};

const fieldStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  boxSizing: 'border-box',
  marginTop: 6,
  padding: 12,
  borderRadius: 8,
  border: '1px solid var(--color-border)',
  background: 'var(--bg-input)',
  color: 'var(--color-text)',
};

const fieldErrorStyle: React.CSSProperties = {
  color: 'var(--status-error)',
  fontSize: '0.85rem',
  margin: '6px 0 0 0',
};
