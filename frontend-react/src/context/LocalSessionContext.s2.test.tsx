import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { LocalSessionProvider, useLocalSession } from './LocalSessionContext';
import { LocalApplicationError } from '../services/localApplicationClient';
import { LocalS2Api, nullMeta } from '../services/localS2Client';
import { clientMock, completedState, deferred } from '../testHelpers/localApplication';
import { inputFixture, portfolioId, questionnaireFixture, s2Mock, s2Response, savedFixture, s2Time } from '../testHelpers/localS2';
function setup() {
  const client = clientMock();
  client.state.mockResolvedValue(completedState());
  const api = s2Mock();
  api.questionnaire.mockResolvedValue({ data: questionnaireFixture(), meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null, correlationId: 's2-test' } });
  client.s2 = api;
  const wrapper = ({ children }: {
    children: React.ReactNode;
  }) => <LocalSessionProvider client={client}>{children}</LocalSessionProvider>;
  return { ...renderHook(useLocalSession, { wrapper }), client, api };
}
test('named capabilities return typed S2 data without exposing an authenticated adapter/getter', async () => {
  const { result } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  let success = false;
  await act(async () => {
    const outcome = await result.current.domain.questionnaire();
    success = outcome.status === 'success' && outcome.value.data.questions.length === 10;
  });
  expect(success).toBe(true);
  expect(['getToken', 'getBearer', 'adapter', 'requestWithBearer'].some((key) => key in result.current || key in result.current.domain)).toBe(false);
});
test.each(['success', '401', 'failure'] as const)('pre-logout domain %s is permanently ignored after a failed logout', async (kind) => {
  const { result, client, api } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  const waiting = deferred<Awaited<ReturnType<LocalS2Api['questionnaire']>>>();
  api.questionnaire.mockReturnValue(waiting.promise);
  let pending!: ReturnType<typeof result.current.domain.questionnaire>;
  act(() => {
    pending = result.current.domain.questionnaire();
  });
  const epoch = result.current.sessionEpoch;
  client.logout.mockRejectedValueOnce(new LocalApplicationError('API_UNAVAILABLE'));
  await act(async () => {
    await result.current.logout();
  });
  let status = '';
  await act(async () => {
    if (kind === 'success')
      waiting.resolve({ data: questionnaireFixture(), meta: { apiVersion: 'v1', dataStatus: nullMeta().status, dataAsOf: null, correlationId: 'old' } });
    else
      waiting.reject(new LocalApplicationError(kind === '401' ? 'SESSION_INVALID' : 'LOCAL_STORE_UNAVAILABLE'));
    status = (await pending).status;
  });
  expect(status).toBe('cancelled');
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.sessionEpoch).toBe(epoch);
  expect(result.current.errorOperation).toBe('logout');
  expect(result.current.error?.code).toBe('API_UNAVAILABLE');
});
test('page abort ignores a late401 from an adapter that ignores abort', async () => {
  const { result, api } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  const waiting = deferred<Awaited<ReturnType<LocalS2Api['questionnaire']>>>();
  api.questionnaire.mockReturnValue(waiting.promise);
  const controller = new AbortController();
  let pending!: ReturnType<typeof result.current.domain.questionnaire>;
  act(() => {
    pending = result.current.domain.questionnaire({ signal: controller.signal });
  });
  controller.abort();
  let status = '';
  await act(async () => {
    waiting.reject(new LocalApplicationError('SESSION_INVALID'));
    status = (await pending).status;
  });
  expect(status).toBe('cancelled');
  expect(result.current.user?.alias).toBe('learner-a');
});
test('current401 clears owner, and current onboarding-required removes completion rather than presenting stale data', async () => {
  const { result, api } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  api.questionnaire.mockRejectedValueOnce(new LocalApplicationError('ONBOARDING_REQUIRED'));
  await act(async () => {
    await result.current.domain.questionnaire();
  });
  expect(result.current.onboarding?.onboarding_completed).toBe(false);
  await act(async () => {
    await result.current.login('learner-a');
  });
  api.questionnaire.mockRejectedValueOnce(new LocalApplicationError('SESSION_INVALID'));
  await act(async () => {
    await result.current.domain.questionnaire();
  });
  expect(result.current.user).toBeNull();
});
test('current abort-ignoring adapter timeout is a visible failure, not a silent cancelled outcome', async () => {
  jest.useFakeTimers();
  try {
    const { result, api, unmount } = setup();
    await act(async () => {
      await result.current.login('learner-a');
    });
    api.questionnaire.mockReturnValue(new Promise(() => undefined));
    let pending!: ReturnType<typeof result.current.domain.questionnaire>;
    act(() => {
      pending = result.current.domain.questionnaire();
    });
    let visible = false;
    await act(async () => {
      jest.advanceTimersByTime(30000);
      const outcome = await pending;
      visible = outcome.status === 'error' && outcome.error.code === 'REQUEST_TIMEOUT';
    });
    expect(visible).toBe(true);
    expect(result.current.user?.alias === 'learner-a').toBe(true);
    unmount();
  }
  finally {
    jest.useRealTimers();
  }
});
test('a substituted adapter cannot mutate the copied complete request or confirmation identity', async () => {
  const { result, api } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  let deeplyFrozen = false;
  api.submitRisk.mockImplementationOnce(async (_credential, request) => {
    deeplyFrozen = Object.isFrozen(request) && Object.isFrozen(request.answers) && request.answers.every(Object.isFrozen);
    try {
      request.answers[0].answer_code = 'W1_A';
    }
    catch { /* immutable request */
    }
    return s2Response(savedFixture(), s2Time);
  });
  let success = false;
  await act(async () => {
    const response = await result.current.domain.submitRisk({ ...inputFixture(), idempotency_key: portfolioId });
    success = response.status === 'success';
  });
  expect(deeplyFrozen).toBe(true);
  expect(success).toBe(true);
});
test.each(['success', '401', 'failure'] as const)('learner A domain %s cannot replace or clear learner B', async (kind) => {
  const { result, api } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  const waiting = deferred<Awaited<ReturnType<LocalS2Api['questionnaire']>>>();
  api.questionnaire.mockReturnValueOnce(waiting.promise);
  let pending!: ReturnType<typeof result.current.domain.questionnaire>;
  act(() => {
    pending = result.current.domain.questionnaire();
  });
  await act(async () => {
    await result.current.login('learner-b');
  });
  let status = '';
  await act(async () => {
    if (kind === 'success')
      waiting.resolve(s2Response(questionnaireFixture()));
    else
      waiting.reject(new LocalApplicationError(kind === '401' ? 'SESSION_INVALID' : 'LOCAL_STORE_UNAVAILABLE'));
    status = (await pending).status;
  });
  expect(status).toBe('cancelled');
  expect(result.current.user?.alias === 'learner-b').toBe(true);
  expect(result.current.error === null).toBe(true);
});
test('unmount invalidates an adapter that ignores abort without a late401 authority', async () => {
  const { result, api, unmount } = setup();
  await act(async () => {
    await result.current.login('learner-a');
  });
  const waiting = deferred<Awaited<ReturnType<LocalS2Api['questionnaire']>>>();
  api.questionnaire.mockReturnValueOnce(waiting.promise);
  const pending = result.current.domain.questionnaire();
  unmount();
  waiting.reject(new LocalApplicationError('SESSION_INVALID'));
  expect((await pending).status).toBe('cancelled');
});
