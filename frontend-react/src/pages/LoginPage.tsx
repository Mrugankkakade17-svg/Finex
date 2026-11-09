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
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await authService.login();

      login(response.user);

      navigate('/consent');
    } catch (err) {
      console.error('Login failed:', err);
      setError(
        'Unable to sign in right now. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await authService.login({
        displayName: 'Demo Investor',
      });

      login({
        ...response.user,
        displayName: 'Demo Investor',
        riskProfile: 'AGGRESSIVE',
      });

      navigate('/dashboard');
    } catch (err) {
      console.error('Demo login failed:', err);
      setError(
        'Unable to start demo login. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: '480px',
        margin: '40px auto 0 auto',
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
            borderRadius: '16px',
            background:
              'linear-gradient(135deg, #10b981, #6366f1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px auto',
            boxShadow:
              '0 0 25px rgba(16, 185, 129, 0.4)',
          }}
        >
          <Sparkles size={32} color="#ffffff" />
        </div>

        <h2
          style={{
            fontSize: '1.75rem',
            color: '#ffffff',
            marginBottom: '8px',
          }}
        >
          Welcome to FinEx
        </h2>

        <p
          style={{
            color: 'var(--text-secondary)',
            fontSize: '0.9rem',
            marginBottom: '28px',
          }}
        >
          AI-Powered Financial Intelligence & Paper-Trading
          Platform
        </p>

        {isAuthenticated && (
          <div
            style={{
              padding: '12px',
              borderRadius: '10px',
              background: 'rgba(16, 185, 129, 0.1)',
              border:
                '1px solid rgba(16, 185, 129, 0.3)',
              color: '#10b981',
              fontSize: '0.85rem',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            <CheckCircle2 size={16} />
            Currently Authenticated as{' '}
            <strong>{' '}{'Khyati'}</strong>
          </div>
        )}

        {error && (
          <div
            role="alert"
            style={{
              padding: '12px',
              marginBottom: '20px',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <button
            onClick={handleLogin}
            disabled={isLoading}
            aria-disabled={isLoading}
            className="btn-primary"
            style={{
              width: '100%',
              justifyContent: 'center',
              padding: '12px',
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            <LogIn size={18} />

            {isLoading
              ? 'Signing In...'
              : 'Sign In with Google (Mock OAuth)'}
          </button>

          <button
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

            {isLoading
              ? 'Please Wait...'
              : 'Demo Quick Login'}
          </button>
        </div>

        <div
          style={{
            marginTop: '30px',
            paddingTop: '20px',
            borderTop:
              '1px solid var(--border-glass)',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            textAlign: 'left',
          }}
        >
          <div
            style={{
              fontWeight: 600,
              color: 'var(--text-secondary)',
              marginBottom: '4px',
            }}
          >
            Prototype Note (Task W0-KHY):
          </div>

          Authentication uses the typed authentication
          service. Mock OAuth responses are used while the
          backend API is pending.
        </div>
      </div>
    </div>
  );
};