import React, { useMemo, useState } from 'react';
import { CheckCircle2, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import {
  CONSENT_VERSION,
  getJourneyConfig,
  onboardingContract,
} from '../services/onboardingContract';
import {
  ensureOnboardingJourney,
  saveOnboardingJourney,
} from '../services/onboardingJourneyStorage';

export const ConsentPage: React.FC<{ basePath?: string }> = ({ basePath = '' }) => {
  const navigate = useNavigate();
  const config = useMemo(() => getJourneyConfig(), []);
  const [consentGiven, setConsentGiven] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleContinue = async () => {
    if (!consentGiven) {
      setError('Select the consent checkbox before continuing.');
      return;
    }

    setIsLoading(true);
    setError('');
    const journey = ensureOnboardingJourney(config.mode);

    try {
      await onboardingContract.captureConsent({
        correlationId: journey.correlationId,
        consentVersion: CONSENT_VERSION,
        consentGiven: true,
      });
      saveOnboardingJourney({ ...journey, consentRecorded: true });
      navigate(`${basePath}/onboarding`);
    } catch (submissionError) {
      const message =
        submissionError instanceof Error
          ? submissionError.message
          : 'Consent could not be recorded. Please retry.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="s1-journey" aria-labelledby="consent-heading">
      <div className="glass-card s1-journey__card">
        <div className="s1-journey__icon" aria-hidden="true">
          <ShieldCheck size={32} color="#ffffff" />
        </div>
        <p className="s1-journey__eyebrow">Sprint 1 onboarding · {CONSENT_VERSION}</p>
        <h2 id="consent-heading">Educational consent</h2>
        <p className="s1-journey__lede">
          FinEx is an educational pilot. This step records your consent to use a
          minimal profile to tailor the onboarding experience; it does not collect
          financial account details or provide investment advice.
        </p>

        <p className="s1-journey__mode" data-testid="onboarding-integration-mode">
          {config.mode === 'fixture'
            ? 'Fixture mode — using local synthetic data'
            : 'API mode — using the versioned local FinEx contract'}
        </p>

        <div className="s1-journey__notice" id="consent-summary">
          <h3>What you are agreeing to</h3>
          <ul>
            <li>The current educational consent version: {CONSENT_VERSION}</li>
            <li>A display label and a self-declared experience level</li>
            <li>Local storage of the completed onboarding state on this device</li>
          </ul>
        </div>

        <label className="s1-journey__choice" htmlFor="educational-consent">
          <input
            id="educational-consent"
            type="checkbox"
            checked={consentGiven}
            disabled={isLoading}
            aria-describedby="consent-summary"
            onChange={(event) => {
              setConsentGiven(event.target.checked);
              setError('');
            }}
          />
          <span>I understand and agree to continue with the educational onboarding pilot.</span>
        </label>

        {error && (
          <div className="s1-journey__error" role="alert">
            {error}
          </div>
        )}

        <button
          type="button"
          className="btn-primary s1-journey__action"
          onClick={handleContinue}
          disabled={!consentGiven || isLoading}
          aria-disabled={!consentGiven || isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? 'Recording consent…' : error ? 'Retry consent' : 'Continue to profile'}
          {!isLoading && <CheckCircle2 size={18} aria-hidden="true" />}
        </button>
      </div>
    </section>
  );
};
