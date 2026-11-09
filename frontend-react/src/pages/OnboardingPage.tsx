import React, { useMemo, useRef, useState } from 'react';
import { ArrowLeft, CheckCircle2, RotateCcw, ShieldCheck } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import {
  CONSENT_VERSION,
  ExperienceLevel,
  getJourneyConfig,
  onboardingContract,
  PROFILE_SCHEMA_VERSION,
} from '../services/onboardingContract';
import {
  clearOnboardingJourney,
  ensureOnboardingJourney,
  loadOnboardingJourney,
  saveOnboardingJourney,
} from '../services/onboardingJourneyStorage';

const experienceOptions: Array<{ value: ExperienceLevel; label: string }> = [
  { value: 'beginner', label: 'Beginner — I am new to investing concepts' },
  { value: 'intermediate', label: 'Intermediate — I know the fundamentals' },
  { value: 'advanced', label: 'Advanced — I am comfortable with the terminology' },
];

export const OnboardingPage: React.FC<{ basePath?: string }> = ({ basePath = '' }) => {
  const navigate = useNavigate();
  const config = useMemo(() => getJourneyConfig(), []);
  const [journey, setJourney] = useState(() => loadOnboardingJourney());
  const [displayName, setDisplayName] = useState('');
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | ''>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [invalidField, setInvalidField] = useState<'displayName' | 'experienceLevel' | null>(null);
  const displayNameRef = useRef<HTMLInputElement>(null);
  const experienceLevelRef = useRef<HTMLInputElement>(null);

  const beginAgain = () => {
    clearOnboardingJourney();
    navigate(`${basePath}/consent`);
  };

  if (!journey || !journey.consentRecorded || journey.integrationMode !== config.mode) {
    return (
      <section className="s1-journey" aria-labelledby="profile-heading">
        <div className="glass-card s1-journey__card">
          <p className="s1-journey__eyebrow">Sprint 1 onboarding</p>
          <h2 id="profile-heading">Consent is required first</h2>
          <p className="s1-journey__lede">
            The profile step is intentionally unavailable until you make an explicit
            educational-consent choice for the active integration mode.
          </p>
          <Link className="btn-primary s1-journey__action" to={`${basePath}/consent`}>
            <ArrowLeft size={18} aria-hidden="true" /> Review consent
          </Link>
        </div>
      </section>
    );
  }

  if (journey.completed) {
    return (
      <section className="s1-journey" aria-labelledby="complete-heading">
        <div className="glass-card s1-journey__card s1-journey__confirmation">
          <CheckCircle2 size={52} className="s1-journey__success-icon" aria-hidden="true" />
          <p className="s1-journey__eyebrow">Onboarding complete</p>
          <h2 id="complete-heading">Your local completion state is saved</h2>
          <p className="s1-journey__lede">
            This browser remembers that the Sprint 1 onboarding journey completed. No
            financial-account data or credentials were stored by this journey.
          </p>
          {journey.completedAt && (
            <p className="s1-journey__mode">
              Completed locally: {new Date(journey.completedAt).toLocaleString()}
            </p>
          )}
          <button type="button" className="btn-secondary" onClick={beginAgain}>
            <RotateCcw size={18} aria-hidden="true" /> Start another local journey
          </button>
          <Link className="btn-primary" to={`${basePath}/risk`}>
            Continue to educational risk profile
          </Link>
        </div>
      </section>
    );
  }

  const submitProfile = async () => {
    const trimmedDisplayName = displayName.trim();
    if (!trimmedDisplayName) {
      setInvalidField('displayName');
      setError('Enter a display label before completing onboarding.');
      displayNameRef.current?.focus();
      return;
    }
    if (!experienceLevel) {
      setInvalidField('experienceLevel');
      setError('Select an experience level before completing onboarding.');
      experienceLevelRef.current?.focus();
      return;
    }

    setIsLoading(true);
    setInvalidField(null);
    setError('');
    const currentJourney = ensureOnboardingJourney(config.mode);

    try {
      await onboardingContract.submitProfile({
        correlationId: currentJourney.correlationId,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
        displayName: trimmedDisplayName,
        experienceLevel,
      });
      const completion = await onboardingContract.completeOnboarding({
        correlationId: currentJourney.correlationId,
        consentVersion: CONSENT_VERSION,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      });
      const completedJourney = {
        ...currentJourney,
        consentRecorded: true,
        completed: true,
        completedAt: completion.recordedAt,
      };
      saveOnboardingJourney(completedJourney);
      setJourney(completedJourney);
    } catch (submissionError) {
      const message =
        submissionError instanceof Error
          ? submissionError.message
          : 'The profile could not be submitted. Please retry.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="s1-journey" aria-labelledby="profile-heading">
      <div className="glass-card s1-journey__card">
        <div className="s1-journey__icon" aria-hidden="true">
          <ShieldCheck size={32} color="#ffffff" />
        </div>
        <p className="s1-journey__eyebrow">Profile step · {PROFILE_SCHEMA_VERSION}</p>
        <h2 id="profile-heading">A small, useful profile</h2>
        <p className="s1-journey__lede">
          Use a non-sensitive display label and your self-declared experience level. This is not a
          risk questionnaire and does not produce a recommendation.
        </p>

        <p className="s1-journey__mode" data-testid="profile-integration-mode">
          {config.mode === 'fixture'
            ? 'Fixture mode — local synthetic contract adapter'
            : 'API mode — versioned local FinEx API'}
        </p>

        <div className="s1-journey__field">
          <label htmlFor="display-name">Display label</label>
          <input
            id="display-name"
            ref={displayNameRef}
            type="text"
            maxLength={80}
            required
            placeholder="For example, Local Tester"
            autoComplete="nickname"
            value={displayName}
            disabled={isLoading}
            aria-invalid={invalidField === 'displayName'}
            aria-describedby={
              invalidField === 'displayName'
                ? 'display-name-help profile-error'
                : 'display-name-help'
            }
            onChange={(event) => {
              setDisplayName(event.target.value);
              setInvalidField(null);
              setError('');
            }}
          />
          <span id="display-name-help">Use a non-sensitive label, not a legal name.</span>
        </div>

        <fieldset
          className="s1-journey__field"
          disabled={isLoading}
          aria-invalid={invalidField === 'experienceLevel'}
          aria-describedby={invalidField === 'experienceLevel' ? 'profile-error' : undefined}
        >
          <legend>Experience level</legend>
          {experienceOptions.map((option) => (
            <label className="s1-journey__radio" key={option.value}>
              <input
                type="radio"
                ref={option.value === 'beginner' ? experienceLevelRef : undefined}
                required
                name="experience-level"
                value={option.value}
                checked={experienceLevel === option.value}
                onChange={() => {
                  setExperienceLevel(option.value);
                  setInvalidField(null);
                  setError('');
                }}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </fieldset>

        {error && (
          <div id="profile-error" className="s1-journey__error" role="alert">
            {error}
          </div>
        )}

        <p id="profile-requirements" className="s1-journey__mode">
          Both fields are required. Enter a display label and choose your experience level.
        </p>
        <div className="s1-journey__actions">
          <Link className="btn-secondary" to={`${basePath}/consent`}>
            <ArrowLeft size={18} aria-hidden="true" /> Back to consent
          </Link>
          <button
            type="button"
            className="btn-primary"
            onClick={submitProfile}
            disabled={isLoading}
            aria-disabled={isLoading}
            aria-describedby="profile-requirements"
            aria-busy={isLoading}
          >
            {isLoading
              ? 'Saving profile…'
              : error && !invalidField
                ? 'Retry submission'
                : 'Complete onboarding'}
            {!isLoading && <CheckCircle2 size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>
    </section>
  );
};
