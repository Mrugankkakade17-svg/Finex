import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, ShieldCheck } from 'lucide-react';
import { consentService } from '../services/consentService';

export const ConsentPage: React.FC = () => {
  const navigate = useNavigate();

  const [consentGiven, setConsentGiven] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleContinue = async () => {
    if (!consentGiven) {
      setError(
        'You must provide the required consent before continuing.'
      );
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await consentService.saveConsent({
        consentGiven: true,
      });

      if (!response.saved || !response.consentGiven) {
        setError(
          'Consent could not be saved. Please try again.'
        );
        return;
      }

      navigate('/onboarding');
    } catch (err) {
      console.error('Consent submission failed:', err);

      setError(
        'Unable to save your consent right now. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: '720px',
        margin: '40px auto',
      }}
    >
      <div
        className="glass-card"
        style={{
          padding: '40px',
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
            marginBottom: '20px',
          }}
        >
          <ShieldCheck
            size={32}
            color="#ffffff"
          />
        </div>

        <h2
          style={{
            fontSize: '1.75rem',
            color: '#ffffff',
            marginBottom: '8px',
          }}
        >
          Financial Data Consent
        </h2>

        <p
          style={{
            color: 'var(--text-secondary)',
            marginBottom: '28px',
            lineHeight: 1.6,
          }}
        >
          Before continuing, please review and provide the
          required consent for using the FinEx financial
          intelligence platform.
        </p>

        <div
          style={{
            padding: '20px',
            borderRadius: '12px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border-glass)',
            marginBottom: '24px',
          }}
        >
          <h3
            style={{
              color: '#ffffff',
              fontSize: '1rem',
              marginBottom: '12px',
            }}
          >
            Required Consent
          </h3>

          <p
            style={{
              color: 'var(--text-secondary)',
              fontSize: '0.9rem',
              lineHeight: 1.6,
              margin: 0,
            }}
          >
            I understand and agree that FinEx may use the
            information I provide for onboarding, risk
            profiling, personalization, and platform
            functionality.
          </p>
        </div>

        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            marginBottom: '20px',
          }}
        >
          <input
            type="checkbox"
            checked={consentGiven}
            disabled={isLoading}
            onChange={(event) => {
              setConsentGiven(event.target.checked);
              setError('');
            }}
            aria-describedby="consent-description"
            style={{
              width: '18px',
              height: '18px',
              marginTop: '2px',
            }}
          />

          <span
            id="consent-description"
            style={{
              color: '#ffffff',
              fontSize: '0.9rem',
              lineHeight: 1.5,
            }}
          >
            I provide the required consent and agree to
            continue with onboarding.
          </span>
        </label>

        {error && (
          <div
            role="alert"
            style={{
              padding: '12px',
              borderRadius: '10px',
              marginBottom: '20px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={handleContinue}
          disabled={!consentGiven || isLoading}
          aria-disabled={!consentGiven || isLoading}
          className="btn-primary"
          style={{
            width: '100%',
            justifyContent: 'center',
            padding: '12px',
            opacity:
              !consentGiven || isLoading ? 0.6 : 1,
            cursor:
              !consentGiven || isLoading
                ? 'not-allowed'
                : 'pointer',
          }}
        >
          {isLoading ? (
            'Saving Consent...'
          ) : (
            <>
              <CheckCircle2 size={18} />
              Continue to Onboarding
            </>
          )}
        </button>
      </div>
    </div>
  );
};