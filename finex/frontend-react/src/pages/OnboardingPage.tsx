import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Shield,
} from 'lucide-react';
import { onboardingService } from '../services/onboardingService';

interface OnboardingAnswers {
  timeHorizon: string;
  lossReaction: string;
  investmentGoal: string;
  riskComfort: string;
  experience: string;
}

interface SavedOnboardingProgress {
  step: number;
  currency: string;
  answers: OnboardingAnswers;
}

const defaultAnswers: OnboardingAnswers = {
  timeHorizon: '',
  lossReaction: '',
  investmentGoal: '',
  riskComfort: '',
  experience: '',
};

export const OnboardingPage: React.FC = () => {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();

  const onboardingStorageKey = `finex_onboarding_progress_${
    user?.userId || 'guest'
  }`;

  const [savedProgress] =
    useState<SavedOnboardingProgress | null>(() => {
      const saved = localStorage.getItem(
        onboardingStorageKey
      );

      if (!saved) {
        return null;
      }

      try {
        return JSON.parse(saved) as SavedOnboardingProgress;
      } catch (error) {
        console.error(
          'Failed to restore onboarding progress:',
          error
        );

        localStorage.removeItem(onboardingStorageKey);
        return null;
      }
    });

  const [step, setStep] = useState<number>(() => {
    if (
      savedProgress &&
      savedProgress.step >= 1 &&
      savedProgress.step <= 3
    ) {
      return savedProgress.step;
    }

    return 1;
  });

  const [currency, setCurrency] = useState<string>(
    savedProgress?.currency ||
      user?.preferredCurrency ||
      'INR'
  );

  const [answers, setAnswers] =
    useState<OnboardingAnswers>(
      savedProgress?.answers || defaultAnswers
    );

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (step === 4) {
      return;
    }

    const progress: SavedOnboardingProgress = {
      step,
      currency,
      answers,
    };

    localStorage.setItem(
      onboardingStorageKey,
      JSON.stringify(progress)
    );
  }, [
    step,
    currency,
    answers,
    onboardingStorageKey,
  ]);

  const updateAnswer = (
    question: keyof OnboardingAnswers,
    answer: string
  ) => {
    setAnswers((previous) => ({
      ...previous,
      [question]: answer,
    }));

    setError('');
  };

  const allQuestionsAnswered =
    Object.values(answers).every(
      (answer) => answer.trim() !== ''
    );

  const goToQuestionnaire = () => {
    setError('');
    setStep(2);
  };

  const goToReview = () => {
    if (!allQuestionsAnswered) {
      setError(
        'Please answer all questions before continuing.'
      );
      return;
    }

    setError('');
    setStep(3);
  };

  const completeOnboarding = async () => {
    if (!allQuestionsAnswered) {
      setError(
        'Please answer all questions before completing onboarding.'
      );
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response =
        await onboardingService.submitOnboarding({
          preferredCurrency: currency,
          answers,
        });

      if (!response.saved) {
        setError(
          'Unable to save onboarding. Please try again.'
        );
        return;
      }

      updateUser({
        preferredCurrency: response.preferredCurrency,
        riskProfile: response.riskProfile,
        onboardingStatus: 'COMPLETED',
      });

      localStorage.removeItem(
        onboardingStorageKey
      );

      setStep(4);
    } catch (err) {
      console.error(
        'Onboarding submission failed:',
        err
      );

      setError(
        'Unable to save your onboarding details right now. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const questionStyle: React.CSSProperties = {
    marginBottom: '24px',
    padding: '20px',
    borderRadius: '12px',
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid var(--border-glass)',
  };

  const optionStyle = (
    selected: boolean
  ): React.CSSProperties => ({
    display: 'block',
    padding: '12px 14px',
    marginBottom: '8px',
    borderRadius: '8px',
    cursor: isLoading
      ? 'not-allowed'
      : 'pointer',
    background: selected
      ? 'rgba(16, 185, 129, 0.15)'
      : 'rgba(255, 255, 255, 0.02)',
    border: selected
      ? '1px solid var(--primary-emerald)'
      : '1px solid var(--border-glass)',
    color: '#ffffff',
    opacity: isLoading ? 0.6 : 1,
  });

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          gap: '20px',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '1.75rem',
              color: '#ffffff',
              marginBottom: '6px',
            }}
          >
            User Onboarding & Risk Profiling
          </h2>

          <p
            style={{
              color: 'var(--text-secondary)',
              fontSize: '0.9rem',
            }}
          >
            Complete your financial goals profile & risk
            appetite questionnaire
          </p>
        </div>

        <span className="badge badge-info">
          Task ID: W0-KHY / S1-PRD-01
        </span>
      </div>

      <div
        className="glass-card"
        style={{
          padding: '32px',
        }}
      >
        {/* Progress */}
        <div
          aria-label={`Onboarding step ${step} of 4`}
          style={{
            display: 'flex',
            gap: '12px',
            marginBottom: '32px',
          }}
        >
          {[1, 2, 3, 4].map((currentStep) => (
            <div
              key={currentStep}
              style={{
                flex: 1,
                height: '6px',
                borderRadius: '3px',
                backgroundColor:
                  currentStep <= step
                    ? 'var(--primary-emerald)'
                    : 'rgba(255, 255, 255, 0.1)',
              }}
            />
          ))}
        </div>

        {/* STEP 1 */}
        {step === 1 && (
          <div>
            <h3
              style={{
                fontSize: '1.25rem',
                color: '#ffffff',
                marginBottom: '12px',
              }}
            >
              Step 1: Profile & Preferences
            </h3>

            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '20px',
              }}
            >
              Confirm your profile and preferred currency.
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns:
                  'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '16px',
                marginBottom: '24px',
              }}
            >
              <div>
                <label
                  htmlFor="full-name"
                  style={{
                    display: 'block',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                    marginBottom: '6px',
                  }}
                >
                  Full Name
                </label>

                <input
                  id="full-name"
                  type="text"
                  readOnly
                  value={user?.displayName || 'Khyati'}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'var(--bg-input)',
                    border:
                      '1px solid var(--border-glass)',
                    color: '#ffffff',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="preferred-currency"
                  style={{
                    display: 'block',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                    marginBottom: '6px',
                  }}
                >
                  Preferred Currency
                </label>

                <select
                  id="preferred-currency"
                  value={currency}
                  disabled={isLoading}
                  onChange={(event) => {
                    setCurrency(event.target.value);
                    setError('');
                  }}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'var(--bg-input)',
                    border:
                      '1px solid var(--border-glass)',
                    color: '#ffffff',
                  }}
                >
                  <option value="USD">
                    USD ($) - US Dollar
                  </option>
                  <option value="EUR">
                    EUR (€) - Euro
                  </option>
                  <option value="INR">
                    INR (₹) - Indian Rupee
                  </option>
                </select>
              </div>
            </div>

            <button
              type="button"
              onClick={goToQuestionnaire}
              disabled={isLoading}
              aria-disabled={isLoading}
              className="btn-primary"
            >
              Continue to Risk Assessment
              <ArrowRight size={16} />
            </button>
          </div>
        )}

        {/* STEP 2 */}
        {step === 2 && (
          <div>
            <h3
              style={{
                fontSize: '1.25rem',
                color: '#ffffff',
                marginBottom: '12px',
              }}
            >
              Step 2: Risk Questionnaire
            </h3>

            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
              }}
            >
              Answer all five questions to continue.
            </p>

            {/* Q1 */}
            <div style={questionStyle}>
              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '12px',
                }}
              >
                1. What is your investment time horizon?
              </h4>

              {[
                ['LESS_THAN_1', 'Less than 1 year'],
                ['1_TO_3', '1–3 years'],
                ['3_TO_5', '3–5 years'],
                ['MORE_THAN_5', 'More than 5 years'],
              ].map(([value, label]) => (
                <div
                  key={value}
                  role="radio"
                  aria-checked={
                    answers.timeHorizon === value
                  }
                  tabIndex={isLoading ? -1 : 0}
                  onClick={() =>
                    !isLoading &&
                    updateAnswer(
                      'timeHorizon',
                      value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      !isLoading &&
                      (event.key === 'Enter' ||
                        event.key === ' ')
                    ) {
                      updateAnswer(
                        'timeHorizon',
                        value
                      );
                    }
                  }}
                  style={optionStyle(
                    answers.timeHorizon === value
                  )}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Q2 */}
            <div style={questionStyle}>
              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '12px',
                }}
              >
                2. What would you do if your investments
                temporarily lost 20%?
              </h4>

              {[
                ['SELL_ALL', 'Sell all my investments'],
                ['SELL_SOME', 'Sell some investments'],
                ['HOLD', 'Hold my investments'],
                ['INVEST_MORE', 'Invest more'],
              ].map(([value, label]) => (
                <div
                  key={value}
                  role="radio"
                  aria-checked={
                    answers.lossReaction === value
                  }
                  tabIndex={isLoading ? -1 : 0}
                  onClick={() =>
                    !isLoading &&
                    updateAnswer(
                      'lossReaction',
                      value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      !isLoading &&
                      (event.key === 'Enter' ||
                        event.key === ' ')
                    ) {
                      updateAnswer(
                        'lossReaction',
                        value
                      );
                    }
                  }}
                  style={optionStyle(
                    answers.lossReaction === value
                  )}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Q3 */}
            <div style={questionStyle}>
              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '12px',
                }}
              >
                3. What is your primary investment goal?
              </h4>

              {[
                ['PRESERVATION', 'Protect my money'],
                ['INCOME', 'Generate income'],
                ['BALANCED', 'Balanced growth'],
                ['MAX_GROWTH', 'Maximum long-term growth'],
              ].map(([value, label]) => (
                <div
                  key={value}
                  role="radio"
                  aria-checked={
                    answers.investmentGoal === value
                  }
                  tabIndex={isLoading ? -1 : 0}
                  onClick={() =>
                    !isLoading &&
                    updateAnswer(
                      'investmentGoal',
                      value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      !isLoading &&
                      (event.key === 'Enter' ||
                        event.key === ' ')
                    ) {
                      updateAnswer(
                        'investmentGoal',
                        value
                      );
                    }
                  }}
                  style={optionStyle(
                    answers.investmentGoal === value
                  )}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Q4 */}
            <div style={questionStyle}>
              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '12px',
                }}
              >
                4. How comfortable are you with investment
                risk?
              </h4>

              {[
                ['NOT_COMFORTABLE', 'Not comfortable'],
                ['SLIGHTLY', 'Slightly comfortable'],
                ['COMFORTABLE', 'Comfortable'],
                ['VERY_COMFORTABLE', 'Very comfortable'],
              ].map(([value, label]) => (
                <div
                  key={value}
                  role="radio"
                  aria-checked={
                    answers.riskComfort === value
                  }
                  tabIndex={isLoading ? -1 : 0}
                  onClick={() =>
                    !isLoading &&
                    updateAnswer(
                      'riskComfort',
                      value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      !isLoading &&
                      (event.key === 'Enter' ||
                        event.key === ' ')
                    ) {
                      updateAnswer(
                        'riskComfort',
                        value
                      );
                    }
                  }}
                  style={optionStyle(
                    answers.riskComfort === value
                  )}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Q5 */}
            <div style={questionStyle}>
              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '12px',
                }}
              >
                5. How much investment experience do you
                have?
              </h4>

              {[
                ['NONE', 'No experience'],
                ['BEGINNER', 'Beginner'],
                ['INTERMEDIATE', 'Intermediate'],
                ['EXPERIENCED', 'Experienced'],
              ].map(([value, label]) => (
                <div
                  key={value}
                  role="radio"
                  aria-checked={
                    answers.experience === value
                  }
                  tabIndex={isLoading ? -1 : 0}
                  onClick={() =>
                    !isLoading &&
                    updateAnswer(
                      'experience',
                      value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      !isLoading &&
                      (event.key === 'Enter' ||
                        event.key === ' ')
                    ) {
                      updateAnswer(
                        'experience',
                        value
                      );
                    }
                  }}
                  style={optionStyle(
                    answers.experience === value
                  )}
                >
                  {label}
                </div>
              ))}
            </div>

            {error && (
              <div
                role="alert"
                style={{
                  color: '#ef4444',
                  marginBottom: '16px',
                  padding: '12px',
                  borderRadius: '10px',
                  background:
                    'rgba(239, 68, 68, 0.1)',
                  border:
                    '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                {error}
              </div>
            )}

            <div
              style={{
                display: 'flex',
                gap: '12px',
                flexWrap: 'wrap',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setError('');
                  setStep(1);
                }}
                disabled={isLoading}
                aria-disabled={isLoading}
                className="btn-secondary"
              >
                <ArrowLeft size={16} />
                Back
              </button>

              <button
                type="button"
                onClick={goToReview}
                disabled={
                  !allQuestionsAnswered ||
                  isLoading
                }
                aria-disabled={
                  !allQuestionsAnswered ||
                  isLoading
                }
                className="btn-primary"
                style={{
                  opacity:
                    !allQuestionsAnswered ||
                    isLoading
                      ? 0.6
                      : 1,
                }}
              >
                Review Answers
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3 */}
        {step === 3 && (
          <div>
            <h3
              style={{
                fontSize: '1.25rem',
                color: '#ffffff',
                marginBottom: '12px',
              }}
            >
              Step 3: Review Your Answers
            </h3>

            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
              }}
            >
              Review your answers before completing
              onboarding.
            </p>

            {[
              [
                'Investment time horizon',
                answers.timeHorizon,
              ],
              [
                'Reaction to a 20% loss',
                answers.lossReaction,
              ],
              [
                'Investment goal',
                answers.investmentGoal,
              ],
              [
                'Risk comfort',
                answers.riskComfort,
              ],
              [
                'Investment experience',
                answers.experience,
              ],
            ].map(([title, value]) => (
              <div
                key={title}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: '20px',
                  padding: '16px',
                  marginBottom: '10px',
                  borderRadius: '8px',
                  background:
                    'rgba(255, 255, 255, 0.03)',
                  border:
                    '1px solid var(--border-glass)',
                  flexWrap: 'wrap',
                }}
              >
                <span
                  style={{
                    color: 'var(--text-secondary)',
                  }}
                >
                  {title}
                </span>

                <strong
                  style={{
                    color: '#ffffff',
                    textTransform: 'capitalize',
                  }}
                >
                  {value.replaceAll('_', ' ')}
                </strong>
              </div>
            ))}

            {error && (
              <div
                role="alert"
                style={{
                  color: '#ef4444',
                  marginTop: '16px',
                  padding: '12px',
                  borderRadius: '10px',
                  background:
                    'rgba(239, 68, 68, 0.1)',
                  border:
                    '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                {error}
              </div>
            )}

            <div
              style={{
                marginTop: '24px',
                padding: '20px',
                borderRadius: '12px',
                background:
                  'rgba(16, 185, 129, 0.1)',
                border:
                  '1px solid var(--primary-emerald)',
              }}
            >
              <Shield
                size={24}
                color="#10b981"
                style={{
                  marginBottom: '8px',
                }}
              />

              <h4
                style={{
                  color: '#ffffff',
                  marginBottom: '6px',
                }}
              >
                Risk Questionnaire Complete
              </h4>

              <p
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: '0.9rem',
                  margin: 0,
                }}
              >
                Your answers are ready to be submitted.
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                gap: '12px',
                marginTop: '24px',
                flexWrap: 'wrap',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setError('');
                  setStep(2);
                }}
                disabled={isLoading}
                aria-disabled={isLoading}
                className="btn-secondary"
              >
                <ArrowLeft size={16} />
                Change Answers
              </button>

              <button
                type="button"
                onClick={completeOnboarding}
                disabled={
                  isLoading ||
                  !allQuestionsAnswered
                }
                aria-disabled={
                  isLoading ||
                  !allQuestionsAnswered
                }
                className="btn-primary"
                style={{
                  opacity:
                    isLoading ||
                    !allQuestionsAnswered
                      ? 0.6
                      : 1,
                }}
              >
                {isLoading
                  ? 'Saving Onboarding...'
                  : 'Complete Onboarding'}
                {!isLoading && (
                  <ArrowRight size={16} />
                )}
              </button>
            </div>
          </div>
        )}

        {/* STEP 4 */}
        {step === 4 && (
          <div
            style={{
              textAlign: 'center',
              padding: '20px 0',
            }}
          >
            <CheckCircle2
              size={48}
              color="#10b981"
              style={{
                marginBottom: '16px',
              }}
            />

            <h3
              style={{
                fontSize: '1.5rem',
                color: '#ffffff',
                marginBottom: '8px',
              }}
            >
              Onboarding Complete!
            </h3>

            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
              }}
            >
              Your profile, preferences, and risk
              questionnaire have been completed
              successfully.
            </p>

            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="btn-primary"
            >
              Go to Dashboard
              <ArrowRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};