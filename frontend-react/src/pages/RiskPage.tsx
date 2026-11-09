import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  approvedRiskProfiles,
  createRiskClient,
  getRiskConfig,
  RiskContractClient,
  RiskClientError,
  RiskQuestionnaire,
  RiskSubmission,
} from '../services/riskContract';
import { loadOnboardingJourney } from '../services/onboardingJourneyStorage';
import './RiskPage.css';

export const RiskPage: React.FC<{ client?: RiskContractClient; basePath?: string }> = ({ client: suppliedClient, basePath = '' }) => {
  const config = useMemo(getRiskConfig, []);
  const client = useMemo(() => {
    if (suppliedClient) return suppliedClient;
    try {
      return createRiskClient(config);
    } catch {
      return {
        loadQuestionnaire: async () => {
          throw new RiskClientError('LOCAL_PILOT_ONLY');
        },
        submit: async () => {
          throw new RiskClientError('LOCAL_PILOT_ONLY');
        },
      };
    }
  }, [suppliedClient, config]);
  const journey = loadOnboardingJourney();
  const allowed = journey?.consentRecorded === true && journey?.completed === true;
  const [questionnaire, setQuestionnaire] = useState<RiskQuestionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [result, setResult] = useState<RiskSubmission | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    if (!allowed) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    client
      .loadQuestionnaire()
      .then((data) => {
        if (active) setQuestionnaire(data);
      })
      .catch(() => {
        if (active) setError('The questionnaire is unavailable. Please retry.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, allowed, reload]);
  useEffect(() => {
    if (!loading) heading.current?.focus();
  }, [index, result, loading]);
  if (!allowed)
    return (
      <section className="s1-journey">
        <div className="glass-card s1-journey__card">
          <h2>Complete onboarding first</h2>
          <p>Educational consent and a completed local profile are required before this pilot.</p>
          <Link to={`${basePath}/onboarding`}>Return to onboarding</Link>
        </div>
      </section>
    );

  const submit = async () => {
    if (!questionnaire || loading) return;
    if (questionnaire.questions.some((question) => !answers[question.question_id])) {
      setError('Please select an option for every question.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await client.submit(
        {
          questionnaire_id: questionnaire.questionnaire_id,
          questionnaire_version: questionnaire.questionnaire_version,
          answers: questionnaire.questions.map((question) => ({
            question_id: question.question_id,
            answer_code: answers[question.question_id],
          })),
        },
        journey?.correlationId,
      );
      if (mounted.current) setResult(response);
    } catch (failure) {
      if (mounted.current)
        setError(
          failure instanceof RiskClientError
            ? failure.message
            : 'The assessment service is unavailable. Please retry.',
        );
    } finally {
      if (mounted.current) setLoading(false);
    }
  };
  const next = () => {
    if (!questionnaire || loading) return;
    if (!answers[questionnaire.questions[index].question_id]) {
      setError('Please select an option to continue.');
      return;
    }
    setError('');
    if (index === questionnaire.questions.length - 1) void submit();
    else setIndex(index + 1);
  };
  const restart = () => {
    setResult(null);
    setAnswers({});
    setIndex(0);
    setError('');
  };
  const question = questionnaire?.questions[index];
  return (
    <section className="s1-journey" aria-busy={loading} aria-labelledby="risk-heading">
      <div className="glass-card s1-journey__card">
        <p className="s1-journey__eyebrow">
          Sprint 2 · {config.mode === 'fixture' ? 'Synthetic fixture replay' : 'Local API pilot'}
        </p>
        {!questionnaire && (
          <h2 id="risk-heading" ref={heading} tabIndex={-1}>
            Educational risk questionnaire
          </h2>
        )}
        {loading && (
          <p role="status">
            {questionnaire ? 'Calculating educational profile…' : 'Loading questionnaire…'}
          </p>
        )}
        {error && (
          <div className="s1-journey__error" role="alert">
            {error}
          </div>
        )}
        {!questionnaire && !loading && (
          <button className="btn-primary" onClick={() => setReload(reload + 1)}>
            Retry questionnaire
          </button>
        )}
        {result ? (
          <>
            <h2 id="risk-heading" ref={heading} tabIndex={-1}>
              Your educational risk profile
            </h2>
            <p className="s1-journey__lede">Self-reported answers, not a suitability decision.</p>
            <h3 data-testid="risk-category">{result.assessment.risk_category.label}</h3>
            <dl className="risk-scores">
              <div>
                <dt>Composite</dt>
                <dd data-testid="risk-composite">{result.assessment.composite_score}/100</dd>
              </div>
              <div>
                <dt>Willingness</dt>
                <dd>{result.assessment.willingness_score}/100</dd>
              </div>
              <div>
                <dt>Capacity</dt>
                <dd>{result.assessment.capacity_score}/100</dd>
              </div>
            </dl>
            <p>{result.explanation.summary}</p>
            <p>{result.explanation.dimensions}</p>
            <p>{result.explanation.method}</p>
            {result.assessment.informational_tension && (
              <p>{result.assessment.informational_tension.message}</p>
            )}
            <p className="s1-journey__mode">
              Questionnaire {result.assessment.questionnaire_version} ·{' '}
              {result.assessment.scoring_version} · Calculated {result.assessment.calculated_at}
            </p>
            <p className="s1-journey__notice">{result.assessment.limitation.message}</p>
            <p>Answers and results stay in memory only. This pilot does not save an assessment.</p>
            <button className="btn-primary" onClick={restart}>
              Start a new assessment
            </button>
          </>
        ) : (
          question &&
          questionnaire && (
            <>
              <h2 id="risk-heading" ref={heading} tabIndex={-1}>
                Question {index + 1} of {questionnaire.questions.length}
              </h2>
              <p className="s1-journey__mode">
                Questionnaire {questionnaire.questionnaire_version} ·{' '}
                {questionnaire.contract_version}
              </p>
              <progress
                aria-label="Questionnaire progress"
                value={index + 1}
                max={questionnaire.questions.length}
              />
              {config.mode === 'fixture' && (
                <div className="risk-preset">
                  <label htmlFor="risk-preset">Approved synthetic profile</label>
                  <select
                    id="risk-preset"
                    disabled={loading}
                    defaultValue=""
                    onChange={(event) => {
                      const profile = approvedRiskProfiles.find(
                        (item) => item.case_id === event.target.value,
                      );
                      if (profile) {
                        setAnswers(
                          Object.fromEntries(
                            profile.request.answers.map((answer) => [
                              answer.question_id,
                              answer.answer_code,
                            ]),
                          ),
                        );
                        setError('');
                      }
                    }}
                  >
                    <option value="">Choose a golden-case profile</option>
                    {approvedRiskProfiles.map((profile) => (
                      <option key={profile.case_id} value={profile.case_id}>
                        {profile.title}
                      </option>
                    ))}
                  </select>
                  <p>
                    Offline mode replays approved vectors only. Use the local API for other answer
                    combinations.
                  </p>
                </div>
              )}
              <fieldset className="s1-journey__field" disabled={loading}>
                <legend>{question.text}</legend>
                {question.options.map((option) => (
                  <label className="s1-journey__radio" key={option.code}>
                    <input
                      type="radio"
                      name={question.question_id}
                      value={option.code}
                      checked={answers[question.question_id] === option.code}
                      onChange={() => {
                        setAnswers({ ...answers, [question.question_id]: option.code });
                        setError('');
                      }}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </fieldset>
              <p>{questionnaire.limitation.message}</p>
              <div className="s1-journey__actions">
                <button
                  className="btn-secondary"
                  disabled={loading || index === 0}
                  onClick={() => {
                    setIndex(index - 1);
                    setError('');
                  }}
                >
                  Previous question
                </button>
                <button className="btn-primary" disabled={loading} onClick={next}>
                  {index < questionnaire.questions.length - 1
                    ? 'Next question'
                    : error
                      ? 'Retry assessment'
                      : 'Calculate educational profile'}
                </button>
              </div>
            </>
          )
        )}
      </div>
    </section>
  );
};
