// Test-only browser entry point. No injected HTTP client: conditional imports
// select the production JS transport. Controlled responses are not TCP proof.
import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';
import 'dart:math';

import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:web/web.dart' as web;

@JS('finexProbe.install')
external void _install(JSString id, JSString expectedBearer);
@JS('finexProbe.snapshot')
external JSObject _snapshot();
@JS('finexProbe.restore')
external void _restore();
@JS('finexProbe.report')
external void _report(JSString id, JSBoolean passed);
@JS('finexProbe.begin')
external void _begin();
@JS('finexProbe.finish')
external void _finish();

const _ids = [
  'options_utf8_state',
  'draft_nullable_json',
  'consent_true_json',
  'consent_false_json',
  'completion_json',
  'logout_empty_json',
  'me_typed_identity',
  'full_body_timeout_aborts',
  'current_401_skips_body',
  'failed_mutation_explicit_retry',
  'non401_cannot_claim_revocation',
  'authorization_guard_empty',
  'authorization_guard_wrong',
  'stream_cap_then_stall',
  'stream_below_cap',
  'stream_exact_cap',
];
bool _running = false;

void _check(bool condition) {
  if (!condition) throw StateError('Controlled probe condition failed.');
}

Map<String, dynamic> _observed() =>
    Map<String, dynamic>.from(_snapshot().dartify()! as Map);

bool _jsonEqual(Object? left, Object? right) {
  if (left is Map && right is Map) {
    return left.length == right.length &&
        left.keys.every(
          (key) => right.containsKey(key) && _jsonEqual(left[key], right[key]),
        );
  }
  if (left is List && right is List) {
    return left.length == right.length &&
        List.generate(
          left.length,
          (index) => index,
        ).every((index) => _jsonEqual(left[index], right[index]));
  }
  return left == right;
}

void _request(
  String method,
  String path,
  Object? body, {
  int calls = 1,
  int bodyReads = 1,
  bool authorizationMatches = true,
}) {
  final observed = _observed();
  _check(observed['calls'] == calls);
  _check(observed['method'] == method && observed['path'] == path);
  _check(observed['credentials'] == 'omit');
  _check(observed['cache'] == 'no-store');
  _check(observed['redirect'] == 'error');
  _check(observed['authorization_matches'] == authorizationMatches);
  _check(observed['accept'] == 'application/json');
  _check(observed['content_type'] == 'application/json');
  _check(_jsonEqual(observed['request_body'], body));
  _check(observed['body_reads'] == bodyReads);
}

Future<LocalApiException> _error(
  Future<Object?> operation,
  String code, {
  int? status,
}) async {
  try {
    await operation;
  } on LocalApiException catch (error) {
    _check(error.code == code && (status == null || error.status == status));
    _check(!error.message.contains('probe-raw-diagnostic'));
    _check(!error.toString().contains('probe-raw-diagnostic'));
    return error;
  }
  throw StateError('Expected a safe controlled failure.');
}

Future<void> _case(
  String id,
  HttpLocalApplicationApi api,
  String bearer,
) async {
  switch (id) {
    case 'options_utf8_state':
      final state = await api.state(bearer);
      _check(state.displayName == 'Café 学習');
      _check(!state.completed && !state.canAccessFeatures);
      _check(state.draftUpdatedAt == DateTime.utc(2030, 1, 1));
      _request('GET', '/api/v1/local-onboarding/state', null);
    case 'draft_nullable_json':
      final state = await api.saveDraft(bearer, displayName: ' Café 学習 ');
      _check(state.displayName == 'Café 学習' && state.experienceLevel == null);
      _request('PUT', '/api/v1/local-onboarding/draft', {
        'profile_schema_version': 'profile.v1',
        'display_name': 'Café 学習',
        'experience_level': null,
      });
    case 'consent_true_json':
    case 'consent_false_json':
      final accepted = id == 'consent_true_json';
      final state = await api.consent(bearer, accepted);
      _check(state.consent?.accepted == accepted && !state.completed);
      _request('POST', '/api/v1/local-onboarding/consent', {
        'consent_version': 'consent.v1',
        'consent_given': accepted,
      });
    case 'completion_json':
      final state = await api.complete(bearer);
      _check(state.canAccessFeatures);
      _check(state.completedAt == DateTime.utc(2030, 1, 1));
      _request('POST', '/api/v1/local-onboarding/complete', {
        'consent_version': 'consent.v1',
        'profile_schema_version': 'profile.v1',
      });
    case 'logout_empty_json':
      await api.logout(bearer);
      _request('POST', '/api/v1/local-auth/logout', <String, Object?>{});
    case 'me_typed_identity':
      final user = await api.me(bearer);
      _check(user.id == 'probe-synthetic-a' && user.alias == 'learner-a');
      _request('GET', '/api/v1/local-auth/me', null);
    case 'full_body_timeout_aborts':
      await _error(api.state(bearer), 'REQUEST_TIMEOUT');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      _request('GET', '/api/v1/local-onboarding/state', null);
      _check(_observed()['aborted'] == true);
    case 'current_401_skips_body':
      await _error(api.state(bearer), 'SESSION_INVALID', status: 401);
      _request('GET', '/api/v1/local-onboarding/state', null, bodyReads: 0);
      _check(_observed()['aborted'] == true);
    case 'stream_cap_then_stall':
      await _error(api.state(bearer), 'INVALID_API_RESPONSE');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      _request('GET', '/api/v1/local-onboarding/state', null);
      _check(_observed()['array_buffer_reads'] == 0);
      _check(
        _observed()['cancelled'] == true && _observed()['aborted'] == true,
      );
    case 'stream_below_cap':
    case 'stream_exact_cap':
      final state = await api.state(bearer);
      _check(state.displayName == 'Café 学習' && !state.completed);
      _request('GET', '/api/v1/local-onboarding/state', null);
      _check(_observed()['array_buffer_reads'] == 0);
      _check(_observed()['aborted'] == false);
    case 'failed_mutation_explicit_retry':
      await _error(api.consent(bearer, true), 'API_UNAVAILABLE');
      await Future<void>.delayed(const Duration(milliseconds: 180));
      _request('POST', '/api/v1/local-onboarding/consent', {
        'consent_version': 'consent.v1',
        'consent_given': true,
      }, bodyReads: 0);
      final state = await api.consent(bearer, true);
      _check(state.consent?.accepted == true && !state.completed);
      _request('POST', '/api/v1/local-onboarding/consent', {
        'consent_version': 'consent.v1',
        'consent_given': true,
      }, calls: 2);
    case 'non401_cannot_claim_revocation':
      await _error(api.logout(bearer), 'REQUEST_FAILED', status: 503);
      _request('POST', '/api/v1/local-auth/logout', <String, Object?>{});
    case 'authorization_guard_empty':
    case 'authorization_guard_wrong':
      // These controlled cases fault the checker input, not the typed API.
      // They prove that header presence cannot certify the selected bearer.
      await api.state(bearer);
      _request(
        'GET',
        '/api/v1/local-onboarding/state',
        null,
        authorizationMatches: false,
      );
    default:
      throw StateError('Unknown controlled probe case.');
  }
}

Future<void> _run() async {
  if (_running) return;
  _running = true;
  final button = web.document.querySelector('#run')! as web.HTMLButtonElement;
  button.disabled = true;
  _begin();
  try {
    for (final id in _ids) {
      HttpLocalApplicationApi? api;
      var passed = false;
      try {
        // This shape-only random input has no server authority and is never
        // captured. The wrapper never delegates to the actual network.
        final bearer = base64UrlEncode(
          List.generate(32, (_) => Random.secure().nextInt(256)),
        ).replaceAll('=', '');
        _install(id.toJS, bearer.toJS);
        api = HttpLocalApplicationApi(
          Uri.parse('http://127.0.0.1:1'),
          timeout:
              id == 'full_body_timeout_aborts' || id == 'stream_cap_then_stall'
              ? const Duration(milliseconds: 120)
              : const Duration(seconds: 2),
        );
        await _case(id, api, bearer);
        passed = true;
      } catch (_) {
        // The only visible output is a case ID and PASS/FAIL, never diagnostics.
        passed = false;
      } finally {
        api?.close();
        _restore();
      }
      _report(id.toJS, passed.toJS);
    }
  } finally {
    _restore();
    _finish();
    button.disabled = false;
    _running = false;
  }
}

void main() {
  final button = web.document.querySelector('#run')! as web.HTMLButtonElement;
  button.disabled = false;
  button.addEventListener('click', ((web.Event _) => unawaited(_run())).toJS);
}
