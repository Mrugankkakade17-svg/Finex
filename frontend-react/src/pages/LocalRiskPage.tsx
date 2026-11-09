import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocalSession } from '../context/LocalSessionContext';
import { useLocalS2Tasks } from '../hooks/useLocalS2Tasks';
import { LocalApplicationError } from '../services/localApplicationClient';
import { LocalQuestionnaire, LocalRiskDraft, RiskHistory, RiskInput, RiskSubmission, SavedRisk, riskInput } from '../services/localS2Models';
import './LocalS2.css';
function newAssessmentKey(): string {
  // A retry key is generated once, in memory, not an auth token or an owner identity.
  if (!globalThis.crypto?.getRandomValues)
    throw new LocalApplicationError('API_UNAVAILABLE');
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-');
}
export function LocalRiskPage() {
  const { domain } = useLocalSession();
  const tasks = useLocalS2Tasks();
  const [questionnaire, setQuestionnaire] = useState<LocalQuestionnaire | null>(null), [draft, setDraft] = useState<LocalRiskDraft | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({}), dirty = useRef(false);
  const [history, setHistory] = useState<RiskHistory | null>(null), [pages, setPages] = useState<(string | null)[]>([null]);
  const [result, setResult] = useState<SavedRisk | null>(null), [notice, setNotice] = useState('');
  const pending = useRef<RiskSubmission | null>(null), [locked, setLocked] = useState(false);
  const load = useCallback(() => {
    setNotice('');
    void tasks.run(async (signal) => {
      const q = await domain.questionnaire({ signal });
      if (q.status !== 'success')
        return q;
      const d = await domain.riskDraft({ signal });
      if (d.status !== 'success')
        return d;
      const h = await domain.riskHistory(null, { signal });
      if (h.status !== 'success')
        return h;
      return { status: 'success' as const, value: { q: q.value.data, d: d.value.data, h: h.value.data } };
    }, ({ q, d, h }) => {
      setQuestionnaire(q);
      setDraft(d);
      setHistory(h);
      setPages([null]);
      if (!dirty.current && pending.current === null)
        setAnswers(Object.fromEntries(d.answers.map((a) => [a.question_id, a.answer_code])));
    });
  }, [domain, tasks.run]);
  useEffect(load, [load]);
  const input = (): RiskInput => riskInput({ questionnaire_id: 'risk_questionnaire_v1', questionnaire_version: 'v1',
    answers: questionnaire!.questions.filter((q) => answers[q.question_id]).map((q) => ({ question_id: q.question_id, answer_code: answers[q.question_id] })) });
  const save = (clear: boolean) => {
    const requested = clear ? { questionnaire_id: 'risk_questionnaire_v1' as const, questionnaire_version: 'v1' as const, answers: [] } : input();
    setNotice('');
    void tasks.run((signal) => domain.saveRiskDraft(requested, { signal }), (r) => {
      setDraft(r.data);
      dirty.current = false;
      setAnswers(Object.fromEntries(r.data.answers.map((a) => [a.question_id, a.answer_code])));
      setNotice(clear ? 'Saved answers draft cleared on the backend. Existing assessments are unchanged.' : 'Answers draft saved on the local backend.');
    });
  };
  const submit = () => {
    if (tasks.busy || result !== null)
      return;
    try {
      if (pending.current === null) {
        const complete = riskInput(input(), true);
        const frozenAnswers = complete.answers.map((a) => Object.freeze({ ...a }));
        Object.freeze(frozenAnswers);
        pending.current = Object.freeze({ ...complete, answers: frozenAnswers, idempotency_key: newAssessmentKey() });
      }
      const requested = pending.current;
      setLocked(true);
      setNotice('');
      void tasks.run((signal) => domain.submitRisk(requested, { signal }), (r) => {
        setResult(r.data);
        setNotice('Immutable assessment saved on the backend. Retrying uses this same original assessment, not a new calculation.');
      });
    }
    catch (failure) {
      tasks.fail(failure instanceof LocalApplicationError && failure.code === 'RESPONSE_INVALID' ? new LocalApplicationError('MISSING_REQUIRED_QUESTION') : failure);
    }
  };
  const historyPage = (before: string | null, stack: (string | null)[]) => {
    setNotice('');
    void tasks.run((signal) => domain.riskHistory(before, { signal }), (r) => {
      setHistory(r.data);
      setPages(stack);
    });
  };
  const detail = (id: string) => {
    setNotice('');
    void tasks.run((signal) => domain.riskDetail(id, { signal }), (r) => setResult(r.data));
  };
  return <section className="local-card local-s2">
 <p className="local-eyebrow">Sprint 2 · Owned, saved educational answers</p><h1 tabIndex={-1}>Your saved risk profile</h1>
 <p className="local-lede">Ten server-supplied questions, a resumable draft and immutable assessments. This is self-reported education, not advice or a suitability decision.</p>
 {tasks.busy && <p role="status">Confirming the risk operation on the local backend…</p>}
 {tasks.error && <div className="local-error" role="alert" tabIndex={-1} ref={tasks.errorRef}>{tasks.error.message}</div>}
 {notice && <p className="local-status" role="status">{notice}</p>}
 <div className="local-actions"><button className="btn-secondary" disabled={tasks.busy} onClick={load}>Reload saved risk state</button></div>
 {questionnaire && <>
 <p className="local-help">Questionnaire {questionnaire.questionnaire_version} · scoring {questionnaire.scoring_version} · explanation {questionnaire.explanation_version}</p>
 <p className="local-help local-s2-digest">Current rules SHA-256: {questionnaire.rules_sha256}</p>
 <p className="local-help">{questionnaire.limitation.message}</p>
 <p className="local-help">{draft?.updated_at ? 'Last confirmed draft save: ' + draft.updated_at : 'No answers draft has been saved.'} {dirty.current ? 'Unsaved changes are retained locally in this mounted form.' : ''}</p>
 {locked && <p className="local-warning">These complete answers and their retry key are frozen. Retry the same assessment, or deliberately start a new one. A timeout does not prove whether the backend committed.</p>}
 <form onSubmit={(event) => {
      event.preventDefault();
      submit();
    }}>
  <fieldset disabled={tasks.busy || locked} className="local-s2-fieldset">
  {questionnaire.questions.map((q, i) => <fieldset key={q.question_id} className="local-field local-s2-question">
   <legend>{q.text}</legend><p className="local-help">Question {i + 1} of 10 · {q.dimension}</p>
   {q.options.map((o) => <label className="local-radio" key={o.code}><input type="radio" name={'risk-' + q.question_id} checked={answers[q.question_id] === o.code} onChange={() => {
        dirty.current = true;
        setAnswers((old) => ({ ...old, [q.question_id]: o.code }));
      }}/>{o.label}</label>)}
  </fieldset>)}
  </fieldset>
  <div className="local-actions">
  <button type="button" className="btn-secondary" disabled={tasks.busy || locked} onClick={() => save(false)}>Save answers draft</button>
  <button type="button" className="btn-secondary" disabled={tasks.busy || locked} onClick={() => save(true)}>Clear saved answers draft</button>
  <button type="submit" className="btn-primary" disabled={tasks.busy || result !== null}>{locked ? 'Retry same assessment' : 'Save immutable assessment'}</button>
  {(locked || result !== null) && <button type="button" className="btn-secondary" disabled={tasks.busy} onClick={() => {
      pending.current = null;
      setLocked(false);
      setResult(null);
      tasks.clearError();
      setNotice('New assessment started. Your chosen answers are retained; the next submit creates a new retry key.');
    }}>Start a new assessment</button>}
  </div>
 </form>
 </>}
 {result && <section className="local-notice local-s2-result"><h2 tabIndex={-1}>Saved assessment · {result.assessment.risk_category.label}</h2>
 <dl><dt>Willingness</dt><dd>{result.assessment.willingness_score}/100</dd><dt>Capacity</dt><dd>{result.assessment.capacity_score}/100</dd><dt>Composite</dt><dd>{result.assessment.composite_score}/100</dd></dl>
 <p>{result.explanation.summary}</p><p>{result.explanation.dimensions}</p><p>{result.explanation.method}</p>
 {result.assessment.informational_tension && <p className="local-warning">{result.assessment.informational_tension.message}</p>}
 <p>{result.assessment.limitation.message}</p><p className="local-help">Original server calculation: {result.created_at}. Reading history never recalculates it.</p>
 <p className="local-help">Questionnaire {result.input.questionnaire_version} · {result.assessment.scoring_version} · {result.explanation_version}</p>
 <p className="local-help local-s2-digest">Saved rules SHA-256: {result.rules_sha256}</p>
 <details><summary>Original answers and stored rules snapshot</summary><ul>{result.input.answers.map((a) => <li key={a.question_id}>{a.question_id}: {a.answer_code}</li>)}</ul>
  <pre className="local-s2-rules">{JSON.stringify(result.rules_snapshot, null, 2)}</pre></details>
 </section>}
 <section className="local-s2-history"><h2>Immutable assessment history</h2><p className="local-help">Two records per page, in the server's insertion order.</p>
 <button className="btn-secondary" disabled={tasks.busy} onClick={() => historyPage(null, [null])}>Reload assessment history</button>
 {history && (!history.items.length ? <p>No saved assessments on this page.</p> : <ol>{history.items.map((item) => <li key={item.assessment_id}><button className="btn-secondary" disabled={tasks.busy} onClick={() => detail(item.assessment_id)}>View {item.assessment.risk_category.label} assessment · {item.created_at}</button></li>)}</ol>)}
 <div className="local-actions">{pages.length > 1 && <button className="btn-secondary" disabled={tasks.busy} onClick={() => historyPage(pages[pages.length - 2], pages.slice(0, -1))}>Previous history page</button>}
  {history?.next_cursor && <button className="btn-secondary" disabled={tasks.busy} onClick={() => historyPage(history.next_cursor, [...pages, history.next_cursor])}>Next history page</button>}</div>
 </section>
</section>;
}
