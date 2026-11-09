/** Pure shared contract/error boundary. Never import a wire client or session here. */
export const LOCAL_SCOPE = 'local_educational_application';
export const LOCAL_CONTRACT_VERSION = 'local.v1';
export const LOCAL_PROFILE_VERSION = 'profile.v1';
export const LOCAL_CONSENT_VERSION = 'consent.v1';

const messages: Record<string, string> = {
  LOCAL_ORIGIN_INVALID: 'Configure an HTTP(S) loopback API origin without credentials or a path.',
  API_UNAVAILABLE: 'The local API is unavailable. Check the backend and retry.',
  REQUEST_TIMEOUT: 'The local API did not respond in time. Please retry.',
  REQUEST_CANCELLED: 'The request was cancelled.',
  RESPONSE_INVALID: 'The local API returned an incompatible response. Please retry.',
  SESSION_INVALID: 'Your local session has ended. Please sign in again.',
  LOCAL_APPLICATION_ONLY: 'Enable the local application on the loopback backend before continuing.',
  LOCAL_STORE_UNAVAILABLE: 'The local application could not confirm the operation. Please retry.',
  VALIDATION_ERROR: 'Check the profile fields and try again.',
  UNKNOWN_LOCAL_ALIAS: 'Select one of the two approved synthetic personas.',
  CONSENT_REQUIRED: 'Accept the current educational notice before completing onboarding.',
  PROFILE_INCOMPLETE: 'Save a display label and experience level before completing onboarding.',
  PROFILE_VERSION_MISMATCH: 'The profile version changed. Reload onboarding before continuing.',
  CONSENT_VERSION_MISMATCH: 'The consent version changed. Reload and review the current notice.',
  ONBOARDING_REQUIRED: 'Complete your current onboarding before using this feature.',
  S2_UNAVAILABLE: 'The S2 capability is unavailable on this API adapter. Check the accepted local backend and retry.',
  RISK_ASSESSMENT_UNAVAILABLE: 'The saved risk operation could not be confirmed. Your answers are retained.',
  RISK_ASSESSMENT_NOT_FOUND: 'That saved assessment is not available to this persona. Refresh history.',
  IDEMPOTENCY_CONFLICT: 'This retry key already belongs to different answers. Start a deliberate new assessment.',
  MALFORMED_ANSWER: 'Check the questionnaire answers before retrying.',
  UNSUPPORTED_QUESTIONNAIRE_VERSION: 'Reload the current server questionnaire before continuing.',
  DUPLICATE_QUESTION_ANSWER: 'Choose one answer per question.',
  UNKNOWN_QUESTION_ID: 'Reload the current questionnaire.',
  MISSING_REQUIRED_QUESTION: 'Answer all ten questions before submitting.',
  INVALID_ANSWER_CODE: 'Choose an approved answer for each question.',
  ANSWER_NOT_PERMITTED_FOR_QUESTION: 'Choose an answer belonging to its question.',
  LOCAL_PORTFOLIO_NOT_FOUND: 'That portfolio is not available. Refresh your owned list.',
  LOCAL_HOLDING_NOT_FOUND: 'That holding is not available. Refresh the portfolio.',
  UNSUPPORTED_INSTRUMENT: 'Choose an instrument from the supported synthetic catalogue.',
  HOLDING_ALREADY_EXISTS: 'That instrument already has a holding. Refresh or edit it instead.',
  PORTFOLIO_LIMIT_REACHED: 'This persona has reached the twenty-portfolio limit.',
  HOLDING_LIMIT_REACHED: 'This portfolio has reached the one-hundred-holding limit.',
  LOCAL_CATALOG_UNAVAILABLE: 'The synthetic catalogue could not be confirmed. Please retry.',
  LOCAL_QUOTE_UNAVAILABLE: 'The synthetic valuation could not be confirmed. Holdings remain saved.',
};

export class LocalApplicationError extends Error {
  readonly code: string;
  constructor(code: string) {
    super(messages[code] || 'The local request could not be confirmed. Please retry.');
    this.name = 'LocalApplicationError';
    this.code = Object.prototype.hasOwnProperty.call(messages, code) ? code : 'API_UNAVAILABLE';
  }
}

export function isKnownLocalErrorCode(code: string): boolean {
  return Object.prototype.hasOwnProperty.call(messages, code);
}

export function validateLocalBaseOrigin(value: string): string {
  // Reject alternate IPv4 spellings, empty credentials/query/hash and URL normalization tricks.
  const origin = value.trim();
  if (!/^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?\/?$/i.test(origin)) {
    throw new LocalApplicationError('LOCAL_ORIGIN_INVALID');
  }
  try {
    const parsed = new URL(origin);
    if (parsed.username || parsed.password || parsed.search || parsed.hash ||
        parsed.pathname !== '/' || (parsed.port && Number(parsed.port) < 1)) {
      throw new LocalApplicationError('LOCAL_ORIGIN_INVALID');
    }
    return parsed.origin;
  } catch {
    throw new LocalApplicationError('LOCAL_ORIGIN_INVALID');
  }
}
