/** Optional review observation. No permanent risk capture or current-client native acceptance is inferred. */
import { createHash, randomBytes } from 'crypto';
import { readFileSync } from 'fs';
import { createLocalS2Client } from './localS2Client';
import { LocalApplicationError, LOCAL_SCOPE, LOCAL_CONTRACT_VERSION } from './localApplicationClient';
import { exactS2, objectS2, riskInput, utcInstant, uuidS2 } from './localS2Models';
interface ObservationCase {
  id: string;
  method: 'GET' | 'PUT' | 'POST';
  suffix: string;
  request: Record<string, unknown> | null;
  status: number;
  content_type: 'application/json';
  body_utf8: string;
  expected_error_code: string | null;
}
function optionalObservation(path: string | undefined): ObservationCase[] {
  if (path === undefined)
    return [];
  try {
    if (!path.trim())
      throw new Error();
    const serialized = readFileSync(path, 'utf8');
    // Exact supplied historical review artifact. This is not a same-revision formal #194 corpus.
    if (createHash('sha256').update(serialized, 'utf8').digest('hex') !== '0f78d2e710d83255a72741f0d623ab0baaacbe317091afe4b97414da3a068a6d')
      throw new Error();
    const root = exactS2(JSON.parse(serialized), ['schema_version', 'scope', 'contract_version', 'observer_sha256', 'accepted_driver_sha256', 'accepted_driver_result', 'cases', 'limitations']);
    const report = objectS2(root.accepted_driver_result);
    if (root.schema_version !== 'finex.review.saved_risk_wire_observation.v1' || root.scope !== LOCAL_SCOPE || root.contract_version !== LOCAL_CONTRACT_VERSION ||
      report.success !== true || report.tested_commit !== 'abf5956a35fc5cf01afce58753bdbeb045a87851' || report.tested_tree !== '99c08f21b9f00a8877449cca824da9a70f7cca2d' ||
      report.working_tree_dirty !== false || report.tracked_dirty !== false || !Array.isArray(root.cases) || root.cases.length !== 33)
      throw new Error();
    return root.cases as ObservationCase[];
  }
  catch {
    throw new Error('Invalid optional saved-risk review observation.');
  }
}
const observed = optionalObservation(process.env.FINEX_REVIEW_S2_RISK_WIRE_PATH);
const compatible = observed.filter((entry) => entry.method !== 'GET' || !entry.suffix.startsWith('/assessments') ||
  entry.suffix.startsWith('/assessments/') || entry.expected_error_code !== null || entry.suffix.startsWith('/assessments?limit=2'));
test('optional historical risk observation is explicit and never silently truncates a different page limit', () => {
  if (!observed.length) {
    expect(compatible.length === 0).toBe(true);
    expect(() => optionalObservation('')).toThrow('Invalid optional saved-risk review observation.');
  }
  else {
    expect(compatible.length === 25).toBe(true);
    expect(observed.length - compatible.length === 8).toBe(true);
    expect(compatible.filter((entry) => entry.suffix.startsWith('/assessments?limit=2')).length === 2).toBe(true);
  }
});
// Jest rejects an empty .each table. Absence runs only the explicit configuration
// guard above; it never becomes captured-wire acceptance or a fixture fallback.
if (compatible.length > 0) {
  test.each(compatible.map((entry) => [entry.id, entry] as const))('%s original risk bytes replay publicly (historical observation only)', async (_id, entry) => {
    const memoryBearer = randomBytes(32).toString('base64url');
    const bytes = Buffer.from(entry.body_utf8, 'utf8');
    const envelope = objectS2(JSON.parse(entry.body_utf8));
    let calls = 0;
    let safe = true;
    const client = createLocalS2Client({ baseOrigin: 'http://127.0.0.1:8000', fetchImpl: (async (url, options) => {
        calls++;
        try {
          const headers = objectS2(options?.headers);
          safe = safe && String(url).startsWith('http://127.0.0.1:8000/api/v1/local-risk/') && !String(url).includes(memoryBearer) &&
            headers.Authorization === 'Bearer ' + memoryBearer && options?.credentials === 'omit' && options.cache === 'no-store' && options.redirect === 'error' &&
            !(typeof options.body === 'string' && options.body.includes(memoryBearer));
        }
        catch {
          safe = false;
        }
        return { status: entry.status, ok: entry.status >= 200 && entry.status < 300, redirected: false, headers: { get: () => entry.content_type },
          text: async () => bytes.toString('utf8') } as unknown as Response;
      }) as typeof fetch });
    let passed = false;
    let reflected = false;
    try {
      const request = entry.request;
      const promise = entry.method === 'POST' ? client.submitRisk(memoryBearer, {
        ...riskInput({ questionnaire_id: request!.questionnaire_id, questionnaire_version: request!.questionnaire_version, answers: request!.answers }, true),
        idempotency_key: uuidS2(request!.idempotency_key),
      }) : entry.method === 'PUT' ? client.saveRiskDraft(memoryBearer, riskInput(request)) :
        entry.suffix === '/questionnaire' ? client.questionnaire(memoryBearer) : entry.suffix === '/draft' ? client.riskDraft(memoryBearer) :
          entry.suffix.startsWith('/assessments/') ? client.riskDetail(memoryBearer, uuidS2(entry.suffix.slice('/assessments/'.length))) :
            client.riskHistory(memoryBearer, entry.suffix.includes('&before=') ? entry.suffix.split('&before=')[1] : null);
      const result = await promise;
      const data = objectS2(envelope.data);
      passed = entry.expected_error_code === null && JSON.stringify(result.data) === JSON.stringify(data);
      // Metadata UTC may use equivalent Z/+00:00 spelling; maintain microseconds.
      const meta = objectS2(envelope.meta);
      passed = passed && (meta.dataAsOf === null ? result.meta.dataAsOf === null : result.meta.dataAsOf !== null && utcInstant(result.meta.dataAsOf) === utcInstant(String(meta.dataAsOf)));
      reflected = JSON.stringify(result).includes(memoryBearer);
    }
    catch (failure) {
      passed = entry.expected_error_code !== null && failure instanceof LocalApplicationError && failure.code === entry.expected_error_code;
      reflected = String(failure).includes(memoryBearer);
    }
    expect(passed && safe && calls === 1).toBe(true);
    expect(reflected).toBe(false);
  });
}
