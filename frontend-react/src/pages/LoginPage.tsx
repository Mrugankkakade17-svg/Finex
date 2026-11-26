import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  ShieldCheck,
  LogIn,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { authService } from '../services/authService';

export const LoginPage: React.FC = () => {
  const { user, login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState(
    user?.displayName && user.displayName !== 'Investor' ? user.displayName : ''
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setError('');

    const chosenName = displayName.trim() || user?.displayName || 'Investor';

    try {
      const response = await authService.login({
        displayName: chosenName,
      });

      login({
        ...response.user,
        displayName: chosenName,
      });

      navigate('/dashboard');
    } catch (err) {
      console.error('Login failed:', err);
      setError('Unable to sign in right now. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setIsLoading(true);
    setError('');

    const chosenName = displayName.trim() || 'Demo Investor';

    try {
      const response = await authService.login({
        displayName: chosenName,
      });

      login({
        ...response.user,
        displayName: chosenName,
        riskProfile: 'MODERATE',
      });

      navigate('/dashboard');
    } catch (err) {
      console.error('Demo login failed:', err);
      setError('Unable to start demo login. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: '500px',
        margin: '32px auto',
      }}
    >
      <div
        className="glass-card"
        style={{
          padding: '40px',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '18px',
            background: 'var(--color-accent-coral)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px auto',
            boxShadow: '0 10px 25px rgba(255, 114, 94, 0.32)',
          }}
        >
          <Sparkles size={32} color="#ffffff" />
        </div>

        <h2
          style={{
            fontSize: '1.9rem',
            color: 'var(--color-text)',
            marginBottom: '8px',
          }}
        >
          Welcome to finex*
        </h2>

        <p
          style={{
            color: 'var(--color-text-muted)',
            fontSize: '0.95rem',
            marginBottom: '24px',
          }}
        >
          Small steps. Big future energy. Personalize your financial space below.
        </p>

        {isAuthenticated && user && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: '12px',
              background: '#ECFDF5',
              border: '1px solid #6EE7B7',
              color: '#065F46',
              fontSize: '0.88rem',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            <CheckCircle2 size={16} />
            Currently Authenticated as <strong>{user.displayName}</strong>
          </div>
        )}

        {error && (
          <div
            role="alert"
            style={{
              padding: '12px',
              marginBottom: '20px',
              borderRadius: '10px',
              background: '#FEF3F2',
              border: '1px solid #FDA29B',
              color: '#B42318',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        <form
          onSubmit={handleLogin}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            textAlign: 'left',
          }}
        >
          <div>
            <label
              htmlFor="login-user-name"
              style={{
                display: 'block',
                fontSize: '0.85rem',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginBottom: '6px',
              }}
            >
              Your Name
            </label>
            <input
              id="login-user-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Enter your name"
              style={{ width: '100%' }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            aria-disabled={isLoading}
            className="btn-primary"
            style={{
              width: '100%',
              justifyContent: 'center',
              padding: '13px',
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            <LogIn size={18} />
            {isLoading ? 'Signing In...' : 'Sign In & Build Your Rhythm'}
          </button>

          <button
            type="button"
            onClick={handleDemoLogin}
            disabled={isLoading}
            aria-disabled={isLoading}
            className="btn-secondary"
            style={{
              width: '100%',
              justifyContent: 'center',
              padding: '12px',
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            <ShieldCheck size={18} />
            {isLoading ? 'Please Wait...' : 'Quick Demo Login'}
          </button>
        </form>

        <div
          style={{
            marginTop: '28px',
            paddingTop: '18px',
            borderTop: '1px solid var(--color-surface-divider)',
            fontSize: '0.78rem',
            color: 'var(--color-text-muted)',
            textAlign: 'left',
          }}
        >
          <div
            style={{
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: '4px',
            }}
          >
            Your Money, In Your Orbit:
          </div>
          Your chosen display name personalizes your dashboard, onboarding profile, and AI assistant
          session locally on your device.
        </div>
      </div>
    </div>
  );
};
