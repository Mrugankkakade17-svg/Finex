// Replay the same safe wire corpus as React through the production typed API.
// MockClient replay is not native HTTP or browser transport evidence.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _caseIds = {
  'initial',
  'me',
  'partial_draft',
  'saved_profile',
  'consent_accepted',
  'completed',
  'repeated_complete',
  'identical_draft',
  'changed_profile',
  'withdrawn',
  'reaccepted',
  'logged_out',
  'session_invalid',
  'consent_required',
  'profile_incomplete',
  'validation_error',
  'consent_version_mismatch',
  'profile_version_mismatch',
};
const _operations = {'state', 'draft', 'consent', 'complete', 'me', 'logout'};
const _caseSpecs = <String, (String, String, int, String?)>{
  'initial': ('state', 'success', 200, null),
  'me': ('me', 'success', 200, null),
  'partial_draft': ('draft', 'success', 200, null),
  'saved_profile': ('draft', 'success', 200, null),
  'consent_accepted': ('consent', 'success', 200, null),
  'completed': ('complete', 'success', 200, null),
  'repeated_complete': ('complete', 'success', 200, null),
  'identical_draft': ('draft', 'success', 200, null),
  'changed_profile': ('draft', 'success', 200, null),
  'withdrawn': ('consent', 'success', 200, null),
  'reaccepted': ('consent', 'success', 200, null),
  'logged_out': ('logout', 'success', 200, null),
  'session_invalid': ('state', 'error', 401, 'SESSION_INVALID'),
  'consent_required': ('complete', 'error', 409, 'CONSENT_REQUIRED'),
  'profile_incomplete': ('complete', 'error', 409, 'PROFILE_INCOMPLETE'),
  'validation_error': ('draft', 'error', 422, 'VALIDATION_ERROR'),
  'consent_version_mismatch': (
    'consent',
    'error',
    409,
    'CONSENT_VERSION_MISMATCH',
  ),
  'profile_version_mismatch': (
    'draft',
    'error',
    409,
    'PROFILE_VERSION_MISMATCH',
  ),
};
const _credentialKeys = {
  'accesstoken',
  'refreshtoken',
  'token',
  'tokentype',
  'bearer',
  'authorization',
  'cookie',
  'cookies',
  'password',
  'secret',
  'headers',
  'apikey',
  'dbpath',
};

Never _invalidCorpus() =>
    throw const FormatException('The safe local S1 corpus is invalid.');

Map<String, dynamic> _object(Object? value) {
  if (value is! Map<String, dynamic>) _invalidCorpus();
  return value;
}

void _exactKeys(Map<String, dynamic> object, Set<String> keys) {
  if (object.length != keys.length || !keys.every(object.containsKey)) {
    _invalidCorpus();
  }
}

void _noCredentials(Object? value) {
  if (value is Map) {
    for (final entry in value.entries) {
      if (entry.key is! String ||
          _credentialKeys.contains(
            (entry.key as String).toLowerCase().replaceAll(
              RegExp(r'[^a-z0-9]'),
              '',
            ),
          )) {
        _invalidCorpus();
      }
      _noCredentials(entry.value);
    }
  } else if (value is List) {
    for (final item in value) {
      _noCredentials(item);
    }
  }
}

Map<String, dynamic> _parseCorpus(
  String source, {
  bool requireNative = false,
  Map<String, String>? expectedRevision,
}) {
  Object? decoded;
  try {
    decoded = jsonDecode(source);
  } on FormatException {
    _invalidCorpus();
  }
  final corpus = _object(decoded);
  _exactKeys(corpus, {
    'schema_version',
    'scope',
    'contract_version',
    'provenance',
    'cases',
  });
  if (corpus['schema_version'] != 'finex.local_s1.corpus.v1' ||
      corpus['scope'] != localApplicationScope ||
      corpus['contract_version'] != localContractVersion) {
    _invalidCorpus();
  }
  final provenance = _object(corpus['provenance']);
  final native = provenance['kind'] == 'native_tcp_capture';
  if (native) {
    _exactKeys(provenance, {
      'kind',
      'source',
      'command',
      'tested_commit',
      'tested_tree',
    });
    if (provenance['source'] != 'owned_loopback_uvicorn' ||
        provenance['command'] != 'python verify_s1_application.py' ||
        !['tested_commit', 'tested_tree'].every(
          (key) =>
              provenance[key] is String &&
              RegExp(r'^[0-9a-f]{40}$').hasMatch(provenance[key] as String),
        )) {
      _invalidCorpus();
    }
    final revision = expectedRevision ?? _gitRevision();
    if (provenance['tested_commit'] != revision['tested_commit'] ||
        provenance['tested_tree'] != revision['tested_tree']) {
      _invalidCorpus();
    }
  } else {
    _exactKeys(provenance, {'kind', 'source', 'command'});
    if (requireNative ||
        provenance['kind'] != 'synthetic_fixture' ||
        provenance['source'] != 'handcrafted' ||
        provenance['command'] != 'handcrafted local S1 contract fixture') {
      _invalidCorpus();
    }
  }
  final cases = corpus['cases'];
  if (cases is! List || cases.length != _caseIds.length) _invalidCorpus();
  final seen = <String>{};
  for (final raw in cases) {
    final item = _object(raw);
    _exactKeys(item, {
      'id',
      'operation',
      'request',
      'status',
      'content_type',
      'body_utf8',
      'expected',
    });
    final id = item['id'];
    final operation = item['operation'];
    final status = item['status'];
    if (id is! String ||
        !_caseIds.contains(id) ||
        !seen.add(id) ||
        !_operations.contains(operation) ||
        status is! int ||
        status < 100 ||
        status > 599 ||
        item['content_type'] != 'application/json' ||
        item['body_utf8'] is! String ||
        utf8.encode(item['body_utf8'] as String).length > 262144) {
      _invalidCorpus();
    }
    final request = item['request'];
    if (['state', 'me', 'logout'].contains(operation)) {
      if (request != null) _invalidCorpus();
    } else if (request is! Map<String, dynamic>) {
      _invalidCorpus();
    }
    _noCredentials(request);
    Object? body;
    try {
      body = jsonDecode(item['body_utf8'] as String);
    } on FormatException {
      _invalidCorpus();
    }
    _noCredentials(body);
    final envelope = _object(body);
    final expected = _object(item['expected']);
    final (expectedOperation, expectedOutcome, expectedStatus, expectedCode) =
        _caseSpecs[id]!;
    if (operation != expectedOperation ||
        expected['outcome'] != expectedOutcome ||
        status != expectedStatus ||
        expected['error_code'] != expectedCode) {
      _invalidCorpus();
    }
    if (expected['outcome'] == 'success') {
      _exactKeys(expected, {'outcome'});
      if (status < 200 || status >= 300 || envelope['success'] != true) {
        _invalidCorpus();
      }
      if (operation == 'draft') {
        final dto = _object(request);
        _exactKeys(dto, {
          'profile_schema_version',
          'display_name',
          'experience_level',
        });
        if (dto['profile_schema_version'] != localProfileVersion ||
            (dto['display_name'] != null && dto['display_name'] is! String) ||
            ![
              null,
              'beginner',
              'intermediate',
              'advanced',
            ].contains(dto['experience_level'])) {
          _invalidCorpus();
        }
      } else if (operation == 'consent') {
        final dto = _object(request);
        _exactKeys(dto, {'consent_version', 'consent_given'});
        if (dto['consent_version'] != localConsentVersion ||
            dto['consent_given'] is! bool) {
          _invalidCorpus();
        }
      } else if (operation == 'complete') {
        final dto = _object(request);
        _exactKeys(dto, {'consent_version', 'profile_schema_version'});
        if (dto['consent_version'] != localConsentVersion ||
            dto['profile_schema_version'] != localProfileVersion) {
          _invalidCorpus();
        }
      }
    } else if (expected['outcome'] == 'error') {
      _exactKeys(expected, {'outcome', 'error_code'});
      if (status < 400 ||
          envelope['success'] != false ||
          expected['error_code'] is! String ||
          expected['error_code'] != envelope['error_code']) {
        _invalidCorpus();
      }
    } else {
      _invalidCorpus();
    }
  }
  if (!seen.containsAll(_caseIds)) _invalidCorpus();
  return corpus;
}

typedef _GitRevisionRunner = ProcessResult Function(
  String executable,
  List<String> arguments, {
  required String workingDirectory,
  required bool runInShell,
  required Map<String, String> environment,
  required bool includeParentEnvironment,
});

Map<String, String> _gitRevision({
  _GitRevisionRunner? runProcess,
  Map<String, String>? inheritedEnvironment,
}) {
  ProcessResult result;
  try {
    // Read-only metadata, no credential helper, fetch, mutation or clean-tree
    // claim. Root separately records the actual dirty-source manifest.
    final runner = runProcess ?? Process.runSync;
    final environment = Map<String, String>.from(
      inheritedEnvironment ?? Platform.environment,
    );
    environment.removeWhere((key, _) {
      final name = key.toUpperCase();
      return name.startsWith('GIT_') ||
          RegExp(r'(^|_)(?:TOKEN|PAT|PASSWORD|SECRET|AUTHORIZATION)(?:_|$)')
              .hasMatch(name) ||
          const {'GITHUBTOKEN', 'GHTOKEN', 'GITHUBPAT'}.contains(name);
    });
    environment['GIT_OPTIONAL_LOCKS'] = '0';
    environment['GIT_TERMINAL_PROMPT'] = '0';
    result = runner(
      'git',
      [
        '--no-replace-objects',
        '--no-lazy-fetch',
        '-c',
        'core.fsmonitor=false',
        'rev-parse',
        'HEAD',
        'HEAD^{tree}',
      ],
      workingDirectory: Directory.current.path,
      runInShell: false,
      environment: environment,
      includeParentEnvironment: false,
    );
  } on ProcessException {
    _invalidCorpus();
  }
  if (result.exitCode != 0 || result.stdout is! String) _invalidCorpus();
  final rows = (result.stdout as String).trim().split(RegExp(r'\r?\n'));
  if (rows.length != 2 ||
      !rows.every((row) => RegExp(r'^[0-9a-f]{40}$').hasMatch(row))) {
    _invalidCorpus();
  }
  return {'tested_commit': rows[0], 'tested_tree': rows[1]};
}

Map<String, dynamic> _loadCorpus(Map<String, String> environment) {
  final required = environment['FINEX_REQUIRE_LOCAL_S1_CORPUS'];
  if (required != null && !['0', '1'].contains(required)) _invalidCorpus();
  final supplied = environment['FINEX_LOCAL_S1_CORPUS'];
  if ((supplied != null && supplied.trim().isEmpty) ||
      (required == '1' && supplied == null)) {
    throw const FormatException(
      'Required native local S1 corpus was not supplied.',
    );
  }
  final path = supplied ?? '../data/fixtures/local_s1/contract_cases.v1.json';
  String source;
  try {
    final file = File(path);
    if (!file.existsSync() || file.lengthSync() > 1048576) _invalidCorpus();
    source = file.readAsStringSync(encoding: utf8);
  } on FileSystemException {
    _invalidCorpus();
  } on FormatException {
    _invalidCorpus();
  }
  // An explicitly supplied file never falls back to the synthetic fixture.
  return _parseCorpus(source, requireNative: required == '1');
}

Map<String, dynamic> _caseById(Map<String, dynamic> corpus, String id) =>
    _object(
      (corpus['cases'] as List).singleWhere(
        (item) => _object(item)['id'] == id,
      ),
    );

Map<String, dynamic> _copy(Map<String, dynamic> source) =>
    _object(jsonDecode(jsonEncode(source)));

DateTime? _time(Object? value) =>
    value == null ? null : DateTime.parse(value as String);

void _expectState(LocalOnboardingState state, Map<String, dynamic> data) {
  final draft = _object(data['draft']);
  expect(state.displayName, draft['display_name']);
  expect(state.experienceLevel, draft['experience_level']);
  expect(state.draftUpdatedAt, _time(draft['updated_at']));
  expect(state.completed, data['onboarding_completed']);
  expect(state.completedAt, _time(data['completed_at']));
  final consent = data['consent'];
  if (consent == null) {
    expect(state.consent, isNull);
  } else {
    final decision = _object(consent);
    expect(state.consent?.accepted, decision['accepted']);
    expect(state.consent?.version, decision['version']);
    expect(state.consent?.recordedAt, _time(decision['recorded_at']));
  }
  final current =
      consent is Map &&
      consent['accepted'] == true &&
      consent['version'] == localConsentVersion;
  expect(state.hasCurrentConsent, current);
  expect(
    state.canAccessFeatures,
    data['onboarding_completed'] == true && current,
  );
}

Future<Object?> _invoke(
  HttpLocalApplicationApi api,
  Map<String, dynamic> item,
  String bearer,
) {
  final success = _object(item['expected'])['outcome'] == 'success';
  final request = item['request'] as Map<String, dynamic>?;
  return switch (item['operation']) {
    'state' => api.state(bearer),
    'me' => api.me(bearer),
    'logout' => api.logout(bearer),
    'draft' => api.saveDraft(
      bearer,
      displayName: success
          ? request!['display_name'] as String?
          : 'Corpus safe probe',
      experienceLevel: success
          ? request!['experience_level'] as String?
          : 'beginner',
    ),
    'consent' => api.consent(
      bearer,
      success ? request!['consent_given'] as bool : true,
    ),
    'complete' => api.complete(bearer),
    _ => throw const FormatException('Unsupported safe corpus operation.'),
  };
}

void _expectSafeRequestBody(String body, Object? expected) {
  var matches = false;
  try {
    matches = expected == null
        ? body.isEmpty
        : equals(expected).matches(jsonDecode(body), <Object?, Object?>{});
  } on FormatException {
    // JSON diagnostics can reflect their source. Reject without propagating it.
    matches = false;
  }
  expect(
    matches,
    isTrue,
    reason: 'The canonical safe request body must match.',
  );
}

void main() {
  test('S1 metadata Git disables lazy fetch before the revision command', () {
    var calls = 0;
    final value = _gitRevision(
      inheritedEnvironment: const {},
      runProcess:
          (
            executable,
            arguments, {
            required workingDirectory,
            required runInShell,
            required environment,
            required includeParentEnvironment,
          }) {
            calls++;
            expect(executable == 'git', isTrue);
            expect(
              equals([
                '--no-replace-objects',
                '--no-lazy-fetch',
                '-c',
                'core.fsmonitor=false',
                'rev-parse',
                'HEAD',
                'HEAD^{tree}',
              ]).matches(arguments, <Object?, Object?>{}),
              isTrue,
              reason: 'Global no-network controls must precede the command.',
            );
            expect(workingDirectory.isNotEmpty, isTrue);
            expect(runInShell, isFalse);
            return ProcessResult(0, 0, '${'1' * 40}\n${'2' * 40}\n', '');
          },
    );
    expect(value['tested_commit'] == '1' * 40, isTrue);
    expect(value['tested_tree'] == '2' * 40, isTrue);
    expect(calls, 1);
  });
  test('S1 metadata Git scrubs mixed-case overrides but preserves PATH', () {
    _gitRevision(
      inheritedEnvironment: const {
        'PATH': 'synthetic-search-path',
        'PATHEXT': '.EXE',
        'SystemRoot': 'synthetic-system-root',
        'safe_marker': 'kept',
        'git_dir': 'synthetic-override',
        'gIt_Config_Count': '1',
        'GIT_NO_LAZY_FETCH': '0',
        'Gh_ToKeN': 'synthetic-private-marker',
        'FiNeX_GITHUB_PaT': 'synthetic-private-marker',
        'pat': 'synthetic-private-marker',
      },
      runProcess:
          (
            executable,
            arguments, {
            required workingDirectory,
            required runInShell,
            required environment,
            required includeParentEnvironment,
          }) {
            expect(includeParentEnvironment, isFalse);
            expect(
              equals({
                'PATH': 'synthetic-search-path',
                'PATHEXT': '.EXE',
                'SystemRoot': 'synthetic-system-root',
                'safe_marker': 'kept',
                'GIT_OPTIONAL_LOCKS': '0',
                'GIT_TERMINAL_PROMPT': '0',
              }).matches(environment, <Object?, Object?>{}),
              isTrue,
              reason: 'Only sanitized values may reach the child process.',
            );
            return ProcessResult(0, 0, '${'1' * 40}\n${'2' * 40}\n', '');
          },
    );
  });
  test(
    'S1 metadata Git unsupported flag fails without diagnostic reflection',
    () {
      Object? failure;
      try {
        _gitRevision(
          inheritedEnvironment: const {},
          runProcess: (
            executable,
            arguments, {
            required workingDirectory,
            required runInShell,
            required environment,
            required includeParentEnvironment,
          }) => ProcessResult(0, 129, '', 'synthetic-private-diagnostic'),
        );
      } catch (error) {
        failure = error;
      }
      expect(failure is FormatException, isTrue);
      expect(
        failure.toString().contains('synthetic-private-diagnostic'),
        isFalse,
      );
    },
  );
  late Map<String, dynamic> corpus;
  setUpAll(() => corpus = _loadCorpus(Platform.environment));

  for (final kind in [
    'mismatched JSON',
    'malformed JSON',
    'unexpected GET body',
  ]) {
    test('request diagnostic guard rejects $kind without input reflection', () {
      final marker = base64UrlEncode(
        List.generate(32, (_) => Random.secure().nextInt(256)),
      ).replaceAll('=', '');
      final body = switch (kind) {
        'mismatched JSON' => jsonEncode({'access_token': marker}),
        'malformed JSON' => '{"access_token":"$marker",}',
        _ => marker,
      };
      Object? failure;
      try {
        _expectSafeRequestBody(
          body,
          kind == 'unexpected GET body' ? null : <String, Object?>{},
        );
      } catch (error) {
        failure = error;
      }
      // Only booleans enter these matchers, even when the guarded input leaks.
      expect(failure != null, isTrue);
      expect(failure.toString().contains(marker), isFalse);
      expect(failure is FormatException, isFalse);
    });
  }
  test(
    'request diagnostic guard accepts only matching safe request bodies',
    () {
      _expectSafeRequestBody('', null);
      _expectSafeRequestBody('{}', <String, Object?>{});
      _expectSafeRequestBody(
        '{"experience_level":null,"display_name":"Safe synthetic label"}',
        {'display_name': 'Safe synthetic label', 'experience_level': null},
      );
    },
  );

  test(
    'required native corpus cannot be missing or fall back to a fixture',
    () {
      expect(
        () => _loadCorpus({'FINEX_REQUIRE_LOCAL_S1_CORPUS': '1'}),
        throwsFormatException,
      );
      expect(
        () => _loadCorpus({'FINEX_LOCAL_S1_CORPUS': ''}),
        throwsFormatException,
      );
      expect(
        () => _loadCorpus({
          'FINEX_LOCAL_S1_CORPUS': 'missing-local-s1-corpus-file.json',
        }),
        throwsFormatException,
      );
    },
  );
  test('malformed or incomplete supplied corpus is rejected', () {
    expect(() => _parseCorpus('{'), throwsFormatException);
    final incomplete = _copy(corpus);
    (incomplete['cases'] as List).removeLast();
    expect(() => _parseCorpus(jsonEncode(incomplete)), throwsFormatException);
    final duplicate = _copy(corpus);
    final cases = duplicate['cases'] as List;
    cases[cases.length - 1] = cases.first;
    expect(() => _parseCorpus(jsonEncode(duplicate)), throwsFormatException);
  });
  test(
    'wrong scope/schema and credential-bearing bodies are rejected safely',
    () {
      for (final entry in {
        'schema_version': 'obsolete',
        'scope': 'pilot',
        'contract_version': 'local.v0',
      }.entries) {
        final invalid = _copy(corpus)..[entry.key] = entry.value;
        expect(() => _parseCorpus(jsonEncode(invalid)), throwsFormatException);
      }
      for (final key in ['access_token', 'accessToken', 'Cookie']) {
        final credential = _copy(corpus);
        final item = _caseById(credential, 'initial');
        final body = _object(jsonDecode(item['body_utf8'] as String));
        _object(body['data'])[key] = 'synthetic-marker-not-a-credential';
        item['body_utf8'] = jsonEncode(body);
        expect(
          () => _parseCorpus(jsonEncode(credential)),
          throwsFormatException,
        );
      }
    },
  );
  test(
    'native mode rejects handcrafted provenance and malformed SHA metadata',
    () {
      final synthetic = _copy(corpus)
        ..['provenance'] = {
          'kind': 'synthetic_fixture',
          'source': 'handcrafted',
          'command': 'handcrafted local S1 contract fixture',
        };
      expect(
        () => _parseCorpus(jsonEncode(synthetic), requireNative: true),
        throwsFormatException,
      );
      final invalid = _copy(corpus)
        ..['provenance'] = {
          'kind': 'native_tcp_capture',
          'source': 'owned_loopback_uvicorn',
          'command': 'python verify_s1_application.py',
          'tested_commit': 'not-a-verified-sha',
          'tested_tree': 'not-a-verified-tree',
        };
      expect(
        () => _parseCorpus(jsonEncode(invalid), requireNative: true),
        throwsFormatException,
      );
    },
  );

  test('case semantics cannot disguise incomplete operation coverage', () {
    final wrongOperation = _copy(corpus);
    _caseById(wrongOperation, 'initial')['operation'] = 'logout';
    expect(
      () => _parseCorpus(jsonEncode(wrongOperation)),
      throwsFormatException,
    );
    final wrongStatus = _copy(corpus);
    _caseById(wrongStatus, 'session_invalid')['status'] = 503;
    expect(() => _parseCorpus(jsonEncode(wrongStatus)), throwsFormatException);
    final wrongCode = _copy(corpus);
    _object(
      _caseById(wrongCode, 'validation_error')['expected'],
    )['error_code'] = 'PROFILE_INCOMPLETE';
    expect(() => _parseCorpus(jsonEncode(wrongCode)), throwsFormatException);
  });
  test('native corpus revision must match the consumer checkout', () {
    // These fake revisions prove only the loader comparison seam. They are
    // never written or labelled as native capture or accepted API evidence.
    final expected = {
      'tested_commit': List.filled(40, 'a').join(),
      'tested_tree': List.filled(40, 'b').join(),
    };
    final native = _copy(corpus)
      ..['provenance'] = {
        'kind': 'native_tcp_capture',
        'source': 'owned_loopback_uvicorn',
        'command': 'python verify_s1_application.py',
        ...expected,
      };
    expect(
      _parseCorpus(
        jsonEncode(native),
        requireNative: true,
        expectedRevision: expected,
      )['provenance'],
      native['provenance'],
    );
    for (final field in ['tested_commit', 'tested_tree']) {
      final mismatch = {...expected, field: List.filled(40, 'c').join()};
      expect(
        () => _parseCorpus(
          jsonEncode(native),
          requireNative: true,
          expectedRevision: mismatch,
        ),
        throwsFormatException,
      );
    }
  });
  test('mutation success cases require the exact safe canonical DTO', () {
    final extraField = _copy(corpus);
    _object(_caseById(extraField, 'saved_profile')['request'])['owner_id'] =
        'synthetic-other-owner';
    expect(() => _parseCorpus(jsonEncode(extraField)), throwsFormatException);
    final wrongConsent = _copy(corpus);
    _object(
      _caseById(wrongConsent, 'consent_accepted')['request'],
    )['consent_given'] = 'true';
    expect(() => _parseCorpus(jsonEncode(wrongConsent)), throwsFormatException);
  });

  for (final id in _caseIds) {
    test('shared UTF8 corpus public typed transport: $id', () async {
      final item = _caseById(corpus, id);
      final outcome = _object(item['expected']);
      final operation = item['operation'] as String;
      final bearer = base64UrlEncode(
        List.generate(32, (_) => Random.secure().nextInt(256)),
      ).replaceAll('=', '');
      var calls = 0;
      final api = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:1'),
        client: MockClient((request) async {
          calls++;
          final (method, path) = switch (operation) {
            'state' => ('GET', '/api/v1/local-onboarding/state'),
            'me' => ('GET', '/api/v1/local-auth/me'),
            'logout' => ('POST', '/api/v1/local-auth/logout'),
            'draft' => ('PUT', '/api/v1/local-onboarding/draft'),
            'consent' => ('POST', '/api/v1/local-onboarding/consent'),
            'complete' => ('POST', '/api/v1/local-onboarding/complete'),
            _ => throw const FormatException(
              'Unsupported safe corpus operation.',
            ),
          };
          expect(request.method == method, isTrue);
          expect(request.url.path == path, isTrue);
          expect(request.url.query.isEmpty, isTrue);
          expect(request.followRedirects == false, isTrue);
          // Boolean comparison avoids printing even the shape-only input.
          expect(request.headers['Authorization'] == 'Bearer $bearer', isTrue);
          if (outcome['outcome'] == 'success') {
            if (operation == 'logout') {
              _expectSafeRequestBody(request.body, <String, Object?>{});
            } else if (item['request'] == null) {
              _expectSafeRequestBody(request.body, null);
            } else {
              _expectSafeRequestBody(request.body, item['request']);
            }
          }
          // Illegal captured server requests are NOT emitted by this strict
          // client. Error cases replay their safe response mapping only.
          return http.Response.bytes(
            utf8.encode(item['body_utf8'] as String),
            item['status'] as int,
            headers: {'content-type': item['content_type'] as String},
          );
        }),
      );
      addTearDown(api.close);
      if (outcome['outcome'] == 'error') {
        await expectLater(
          _invoke(api, item, bearer),
          throwsA(
            isA<LocalApiException>()
                .having(
                  (error) => error.code,
                  'safe API code',
                  outcome['error_code'],
                )
                .having(
                  (error) => error.status,
                  'actual status',
                  item['status'],
                ),
          ),
        );
      } else {
        final actual = await _invoke(api, item, bearer);
        final data = _object(
          _object(jsonDecode(item['body_utf8'] as String))['data'],
        );
        if (actual is LocalOnboardingState) {
          _expectState(actual, data);
          if ([
            'completed',
            'repeated_complete',
            'identical_draft',
          ].contains(id)) {
            expect(actual.canAccessFeatures, isTrue);
            final first = _caseById(corpus, 'completed');
            final firstData = _object(
              _object(jsonDecode(first['body_utf8'] as String))['data'],
            );
            expect(actual.completedAt, _time(firstData['completed_at']));
          } else {
            expect(actual.canAccessFeatures, isFalse);
          }
          if (id == 'initial') {
            expect(actual.consent, isNull);
            expect(actual.displayName, isNull);
            expect(actual.experienceLevel, isNull);
            expect(actual.draftUpdatedAt, isNull);
          }
          if (id == 'withdrawn') expect(actual.hasCurrentConsent, isFalse);
          if (id == 'reaccepted') expect(actual.hasCurrentConsent, isTrue);
        } else if (actual is LocalUser) {
          final user = _object(data['user']);
          expect(actual.id, user['id']);
          expect(actual.alias, user['alias']);
        } else {
          expect(operation, 'logout');
          expect(data['signed_out'], isTrue);
        }
      }
      expect(calls, 1);
    });
  }
}
