/** Versioned S2 boundary. Fixtures replay domain outputs; clients never score. */
import fixtures from '../data/s2RiskFixtures.v1.json';

export interface RiskRequest {
  questionnaire_id: string;
  questionnaire_version: string;
  answers: Array<{ question_id: string; answer_code: string }>;
}
export interface RiskQuestion {
  question_id: string;
  dimension: string;
  text: string;
  options: Array<{ code: string; label: string }>;
}
export interface RiskQuestionnaire {
  contract_version: string;
  questionnaire_id: string;
  questionnaire_version: string;
  questions: RiskQuestion[];
  limitation: { code: string; message: string };
}
export interface RiskSubmission {
  assessment: {
    contract_version: string;
    questionnaire_id: string;
    questionnaire_version: string;
    scoring_version: string;
    willingness_score: number;
    capacity_score: number;
    composite_score: number;
    risk_category: { code: string; label: string };
    calculated_at: string;
    limitation: { code: string; message: string };
    informational_tension?: { code: string; message: string };
  };
  explanation: {
    summary: string;
    dimensions: string;
    method: string;
    questionnaire_version: string;
    scoring_version: string;
    calculated_at: string;
    limitation: string;
  };
  scope: 'local_educational_pilot';
  persisted: false;
}
export interface RiskContractClient {
  loadQuestionnaire(): Promise<RiskQuestionnaire>;
  submit(request: RiskRequest, correlationId?: string): Promise<RiskSubmission>;
}
export interface RiskConfig {
  mode: 'fixture' | 'api';
  apiBaseUrl: string;
}
const messages: Record<string, string> = {
  MALFORMED_ANSWER: 'The assessment format is invalid. Restart and try again.',
  UNSUPPORTED_QUESTIONNAIRE_VERSION:
    'This questionnaire version is unsupported. Reload the questionnaire.',
  DUPLICATE_QUESTION_ANSWER: 'A question has more than one answer. Restart and try again.',
  UNKNOWN_QUESTION_ID: 'An unknown question was submitted. Reload the questionnaire.',
  MISSING_REQUIRED_QUESTION: 'Please answer every required question.',
  INVALID_ANSWER_CODE: 'An option is not recognized. Reload and choose a listed option.',
  ANSWER_NOT_PERMITTED_FOR_QUESTION:
    'An option belongs to another question. Restart and try again.',
  LOCAL_PILOT_ONLY: 'This educational pilot is available only on a local development API.',
  RISK_ASSESSMENT_UNAVAILABLE: 'The assessment service is unavailable. Please retry.',
  INVALID_RESPONSE:
    'The service returned an incompatible risk contract. Reload or contact the team.',
  FIXTURE_VECTOR_UNAVAILABLE:
    'Choose an approved synthetic profile in fixture mode, or use the local API.',
};
export class RiskClientError extends Error {
  constructor(public readonly code: string) {
    super(messages[code] || 'The assessment could not be completed. Please retry.');
    this.name = 'RiskClientError';
  }
}
export const approvedRiskProfiles = fixtures.cases
  .filter((item) => 'response' in item)
  .map((item) => ({
    case_id: item.case_id,
    title: item.title,
    request: item.request as RiskRequest,
  }));
export function getRiskConfig(): RiskConfig {
  return {
    mode: process.env.REACT_APP_RISK_MODE === 'api' ? 'api' : 'fixture',
    apiBaseUrl: process.env.REACT_APP_FINEX_API_BASE_URL || 'http://127.0.0.1:8000',
  };
}
function copy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
function requestKey(request: RiskRequest): string {
  return JSON.stringify([
    request.questionnaire_id,
    request.questionnaire_version,
    request.answers
      .map((answer) => JSON.stringify([answer.question_id, answer.answer_code]))
      .sort(),
  ]);
}
function assertVersion(value: any): void {
  if (
    !value ||
    value.contract_version !== 's2-risk-contract/v1.0' ||
    value.questionnaire_id !== 'risk_questionnaire_v1' ||
    value.questionnaire_version !== 'v1'
  )
    throw new RiskClientError('INVALID_RESPONSE');
}
function decodeQuestionnaire(value: any): RiskQuestionnaire {
  assertVersion(value);
  if (
    !Array.isArray(value.questions) ||
    value.questions.length !== 10 ||
    value.limitation?.code !== 'EDUCATIONAL_SELF_REPORTED_PROFILE' ||
    value.limitation?.message !== fixtures.questionnaire.limitation.message
  )
    throw new RiskClientError('INVALID_RESPONSE');
  for (const expected of fixtures.questionnaire.questions) {
    const question = value.questions.find((item: any) => item.question_id === expected.question_id);
    if (
      !question ||
      question.dimension !== expected.dimension ||
      typeof question.text !== 'string' ||
      !Array.isArray(question.options) ||
      question.options.length !== 5 ||
      !expected.options.every((option) =>
        question.options.some(
          (item: any) => item.code === option.code && typeof item.label === 'string',
        ),
      )
    )
      throw new RiskClientError('INVALID_RESPONSE');
  }
  return copy(value);
}
function decodeSubmission(value: any): RiskSubmission {
  const assessment = value?.assessment;
  assertVersion(assessment);
  const labels: Record<string, string> = {
    CONSERVATIVE: 'Conservative',
    MODERATE: 'Moderate',
    AGGRESSIVE: 'Aggressive',
  };
  if (
    value.scope !== 'local_educational_pilot' ||
    value.persisted !== false ||
    assessment.scoring_version !== 'deterministic_v1.0.0' ||
    labels[assessment.risk_category?.code] !== assessment.risk_category?.label ||
    !assessment.risk_category?.label ||
    ![assessment.willingness_score, assessment.capacity_score, assessment.composite_score].every(
      (score) => typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 100,
    ) ||
    typeof assessment.calculated_at !== 'string' ||
    !Number.isFinite(Date.parse(assessment.calculated_at)) ||
    !/(Z|[+-]\d{2}:\d{2})$/.test(assessment.calculated_at) ||
    assessment.limitation?.code !== 'EDUCATIONAL_SELF_REPORTED_PROFILE' ||
    assessment.limitation?.message !== fixtures.questionnaire.limitation.message
  )
    throw new RiskClientError('INVALID_RESPONSE');
  const explanation = value.explanation;
  const tension = assessment.informational_tension;
  if (
    tension !== undefined &&
    (!tension ||
      !['WILLINGNESS_BELOW_CAPACITY', 'CAPACITY_BELOW_WILLINGNESS'].includes(tension.code) ||
      typeof tension.message !== 'string' ||
      tension.message !==
        'The two self-reported dimensions are in different model bands. This is informational context, not a recommendation or suitability decision.')
  )
    throw new RiskClientError('INVALID_RESPONSE');
  if (
    !explanation ||
    !['summary', 'dimensions', 'method', 'limitation'].every(
      (field) => typeof explanation[field] === 'string' && explanation[field].length > 0,
    ) ||
    explanation.questionnaire_version !== assessment.questionnaire_version ||
    explanation.scoring_version !== assessment.scoring_version ||
    explanation.calculated_at !== assessment.calculated_at ||
    explanation.limitation !== assessment.limitation.message
  )
    throw new RiskClientError('INVALID_RESPONSE');
  return copy(value);
}
export function createRiskClient(
  config: RiskConfig = getRiskConfig(),
  fetcher?: typeof fetch,
): RiskContractClient {
  if (config.mode === 'fixture')
    return {
      loadQuestionnaire: async () => decodeQuestionnaire(fixtures.questionnaire),
      submit: async (request) => {
        const fixture = fixtures.cases.find(
          (item) => requestKey(item.request as RiskRequest) === requestKey(request),
        );
        if (!fixture) throw new RiskClientError('FIXTURE_VECTOR_UNAVAILABLE');
        if ('error_code' in fixture) throw new RiskClientError(fixture.error_code as string);
        return decodeSubmission(fixture.response);
      },
    };
  const url = new URL(config.apiBaseUrl);
  if (
    !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== '/'
  )
    throw new Error('Risk pilot API URL must be a local origin.');
  async function call(path: string, request?: RiskRequest, correlationId?: string): Promise<any> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await (fetcher || fetch)(`${url.origin}/api/v1/risk-contract/${path}`, {
        method: request ? 'POST' : 'GET',
        credentials: 'omit',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(correlationId ? { 'X-Correlation-ID': correlationId } : {}),
        },
        ...(request ? { body: JSON.stringify(request) } : {}),
      });
      const body = await response.json();
      if (!response.ok || body.success !== true)
        throw new RiskClientError(
          body.error?.code || body.error_code || 'RISK_ASSESSMENT_UNAVAILABLE',
        );
      return body.data;
    } catch (error) {
      if (error instanceof RiskClientError) throw error;
      throw new RiskClientError('RISK_ASSESSMENT_UNAVAILABLE');
    } finally {
      clearTimeout(timeout);
    }
  }
  return {
    loadQuestionnaire: async () => decodeQuestionnaire(await call('questionnaire')),
    submit: async (request, correlationId) =>
      decodeSubmission(await call('assessments', request, correlationId)),
  };
}
