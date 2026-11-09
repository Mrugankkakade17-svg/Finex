import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLocalSession } from '../context/LocalSessionContext';
import { hasCompletedOnboarding, LOCAL_CONSENT_VERSION, LOCAL_PROFILE_VERSION, LocalExperience } from '../services/localApplicationClient';

const experiences: { value: LocalExperience; label: string }[] = [
  { value: 'beginner', label: 'Beginner — I am new to investing concepts' },
  { value: 'intermediate', label: 'Intermediate — I know the fundamentals' },
  { value: 'advanced', label: 'Advanced — I am comfortable with the terminology' },
];
export function LocalOnboardingPage() {
  const session = useLocalSession();
  const state = session.onboarding;
  const navigate = useNavigate();
  const [label, setLabel] = useState(state?.draft.display_name || '');
  const [experience, setExperience] = useState<LocalExperience | null>(state?.draft.experience_level || null);
  const [consentChoice, setConsentChoice] = useState(state?.consent?.accepted === true && state.consent.version === LOCAL_CONSENT_VERSION);
  const [localError, setLocalError] = useState('');
  const [invalidField, setInvalidField] = useState<'label' | 'experience' | 'consent' | null>(null);
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const mounted = useRef(true);
  const labelRef = useRef<HTMLInputElement>(null);
  const experienceRef = useRef<HTMLInputElement>(null);
  const consentRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const surfacedError = useRef<typeof session.error>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const busy = session.busy || submitting;
  const confirmedConsent = state?.consent?.accepted === true && state.consent.version === LOCAL_CONSENT_VERSION;
  const complete = hasCompletedOnboarding(state);
  const error = localError || (session.errorOperation !== 'logout' ? session.error?.message : '') || '';
  const editableChanged = label.trim() !== (state?.draft.display_name || '') || experience !== state?.draft.experience_level;

  useEffect(() => {
    if (session.error === null) { surfacedError.current = null; return; }
    if (surfacedError.current === session.error) return;
    surfacedError.current = session.error;
    // Only new async form failures move focus. Local validation keeps focus on its field,
    // and editing retained input must not repeatedly jump back to an old server error.
    if (localError || !['consent', 'save', 'complete'].includes(session.errorOperation || '')) return;
    const alert = errorRef.current;
    alert?.focus({ preventScroll: true });
    alert?.scrollIntoView?.({ block: 'center', behavior: 'auto' });
  }, [session.error, session.errorOperation, localError]);

  function validate(forCompletion: boolean): boolean {
    const trimmed = label.trim();
    if (Array.from(trimmed).length > 80 || (forCompletion && !trimmed)) {
      setLocalError(!trimmed ? 'Enter a non-sensitive display label to complete onboarding.' : 'Use at most 80 characters for the display label.');
      setInvalidField('label'); labelRef.current?.focus(); return false;
    }
    if (forCompletion && experience === null) {
      setLocalError('Choose an experience level to complete onboarding.');
      setInvalidField('experience'); experienceRef.current?.focus(); return false;
    }
    if (forCompletion && !confirmedConsent) {
      setLocalError('Review and save acceptance of the current educational notice first.');
      setInvalidField('consent'); consentRef.current?.focus(); return false;
    }
    return true;
  }
  async function run(action: (epoch: number) => Promise<void>) {
    if (submittingRef.current || session.busy) return;
    const epoch = session.sessionEpoch;
    submittingRef.current = true; setSubmitting(true); setLocalError(''); setInvalidField(null); setMessage('');
    try { await action(epoch); }
    finally {
      submittingRef.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }
  const save = (finish: boolean) => {
    if (submittingRef.current || session.busy || !validate(finish)) return;
    void run(async (epoch) => {
      const draft = { display_name: label.trim() || null, experience_level: experience };
      if (!(await session.saveDraft(draft)) || !session.isCurrentSession(epoch) || !mounted.current) return;
      setLabel(draft.display_name || ''); setMessage('Draft saved on the local backend.');
      if (finish && await session.complete() && session.isCurrentSession(epoch) && mounted.current) navigate('/dashboard');
    });
  };
  const recordConsent = (accepted: boolean) => {
    void run(async (epoch) => {
      if (await session.setConsent(accepted) && session.isCurrentSession(epoch) && mounted.current) {
        setConsentChoice(accepted);
        setMessage(accepted ? 'Consent choice saved on the local backend.' : 'Consent withdrawn. Complete onboarding again after reaccepting.');
      }
    });
  };
  return <section className="local-card" aria-labelledby="local-onboarding-heading" aria-busy={busy}>
    <p className="local-eyebrow">Your profile, your progress</p>
    <h1 id="local-onboarding-heading" tabIndex={-1}>Your local onboarding</h1>
    <p className="local-lede">Save a draft now and resume it later by selecting the same synthetic persona.
      Completion is confirmed by the backend, not a browser flag.</p>
    <ol className="local-steps" aria-label="Onboarding sequence">
      <li><span>1</span>Persona selected</li><li><span>2</span>Review consent</li>
      <li><span>3</span>Save profile</li><li><span>4</span>Confirm completion</li>
    </ol>
    <section id="consent" className="local-notice" aria-labelledby="local-consent-heading">
      <p className="local-eyebrow">Version {LOCAL_CONSENT_VERSION}</p>
      <h2 id="local-consent-heading">Educational consent</h2>
      <ul><li>FinEx is educational. It does not provide personalised investment advice or suitability decisions.</li>
        <li>Use synthetic data only. There is no real brokerage account, trade execution or money movement.</li>
        <li>Only a display label, experience level and versioned consent are needed here. Do not enter sensitive personal or account information.</li>
        <li>You can withdraw consent. Saved data remains, but later features stay gated until you reaccept and explicitly complete onboarding again.</li></ul>
      <p className="local-status">{confirmedConsent ? 'Current notice accepted' : 'Current notice not accepted'}
        {state?.consent && <> · Recorded <time dateTime={state.consent.recorded_at}>{state.consent.recorded_at}</time></>}</p>
      <label className="local-checkbox"><input ref={consentRef} type="checkbox" checked={consentChoice}
        disabled={busy} aria-invalid={invalidField === 'consent'} aria-describedby="local-consent-help"
        onChange={(event) => { setConsentChoice(event.target.checked); setLocalError(''); setInvalidField(null); }} />
        <span>I accept the educational notice ({LOCAL_CONSENT_VERSION}).</span></label>
      <p id="local-consent-help" className="local-help">Selecting the checkbox alone does not save a decision.</p>
      <div className="local-actions">
        <button className="btn-primary" disabled={busy} onClick={() => recordConsent(consentChoice)}>Save consent choice</button>
        {confirmedConsent && <button className="btn-secondary" disabled={busy} onClick={() => recordConsent(false)}>Withdraw consent</button>}
      </div>
    </section>
    <section className="local-profile" aria-labelledby="local-profile-heading">
      <p className="local-eyebrow">Version {LOCAL_PROFILE_VERSION}</p>
      <h2 id="local-profile-heading">A small, useful profile</h2>
      <div className="local-field"><label htmlFor="local-display-label">Display label</label>
        <input id="local-display-label" ref={labelRef} type="text" maxLength={160} autoComplete="off"
          value={label} disabled={busy} aria-invalid={invalidField === 'label'}
          aria-describedby={invalidField === 'label' ? 'local-label-help local-onboarding-error' : 'local-label-help'}
          onChange={(event) => { setLabel(event.target.value); setLocalError(''); setInvalidField(null); setMessage(''); }} />
        <p id="local-label-help" className="local-help">Use a non-sensitive label, not a legal name. At most 80 characters; {Array.from(label.trim()).length}/80.</p>
      </div>
      <fieldset className="local-field" disabled={busy} aria-invalid={invalidField === 'experience'}
        aria-describedby={invalidField === 'experience' ? 'local-onboarding-error' : 'local-experience-help'}>
        <legend>Experience level</legend><p id="local-experience-help" className="local-help">This is self-declared experience, not a risk score.</p>
        {experiences.map((option) => <label className="local-radio" key={option.value}>
          <input type="radio" ref={option.value === 'beginner' ? experienceRef : undefined} name="local-experience"
            checked={experience === option.value} value={option.value}
            onChange={() => { setExperience(option.value); setLocalError(''); setInvalidField(null); setMessage(''); }} />
          <span>{option.label}</span></label>)}
      </fieldset>
      {state?.draft.updated_at && <p className="local-help">Last server draft: <time dateTime={state.draft.updated_at}>{state.draft.updated_at}</time></p>}
      {complete && <p className="local-status">Onboarding confirmed at <time dateTime={state!.completed_at!}>{state!.completed_at}</time>.</p>}
      {complete && editableChanged && <p className="local-warning">Saving these changes will clear completion. Reconfirm onboarding afterwards.</p>}
      {error && <div id="local-onboarding-error" ref={errorRef} tabIndex={-1}
        className="local-error" role="alert">{error}</div>}
      {message && <p role="status" className="local-status">{message}</p>}
      {busy && <p role="status">Confirming the operation on the local backend…</p>}
      <div className="local-actions">
        <button className="btn-secondary" disabled={busy} onClick={() => save(false)}>Save draft</button>
        <button className="btn-primary" disabled={busy} onClick={() => save(true)}>Complete onboarding</button>
        {complete && <Link className="btn-secondary" to="/dashboard">Open dashboard</Link>}
      </div>
      <p className="local-help">Partial drafts are allowed. Completion needs both profile fields and saved current consent.
        A failed request preserves your input and does not claim a save.</p>
    </section>
  </section>;
}
