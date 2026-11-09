// Test-only current-native evidence boundary. It calculates no financial
// results, supplies no fallback fixtures, and changes no application authority.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';

enum LocalS2CorpusKind { risk, portfolio }

typedef LocalS2ArtifactReader = Uint8List Function(String path);
typedef LocalS2RuntimeReader = LocalS2CorpusRuntime Function();

class LocalS2CorpusRuntime {
  final String testedCommit;
  final String testedTree;
  final bool workingTreeDirty;
  final bool trackedDirty;
  final Map<String, Uint8List> sourceBytesByPath;
  final Set<String> riskSourcePaths;
  final Set<String> portfolioSourcePaths;

  const LocalS2CorpusRuntime({
    required this.testedCommit,
    required this.testedTree,
    required this.workingTreeDirty,
    required this.trackedDirty,
    required this.sourceBytesByPath,
    required this.riskSourcePaths,
    required this.portfolioSourcePaths,
  });
}

class LocalS2CorpusCase {
  final String id;
  final String operation;
  final Map<String, dynamic>? target;
  final Map<String, dynamic>? request;
  final int status;
  final String contentType;
  final String bodyUtf8;
  final String outcome;
  final String? errorCode;

  const LocalS2CorpusCase({
    required this.id,
    required this.operation,
    required this.target,
    required this.request,
    required this.status,
    required this.contentType,
    required this.bodyUtf8,
    required this.outcome,
    required this.errorCode,
  });
}

class LocalS2Corpus {
  final LocalS2CorpusKind kind;
  final Uint8List originalBytes;
  final Map<String, dynamic> document;
  final Map<String, dynamic> report;
  final List<LocalS2CorpusCase> cases;

  const LocalS2Corpus({
    required this.kind,
    required this.originalBytes,
    required this.document,
    required this.report,
    required this.cases,
  });

  LocalS2CorpusCase caseById(String id) =>
      cases.singleWhere((item) => item.id == id);
}

class LocalS2CorpusPair {
  final LocalS2Corpus risk;
  final LocalS2Corpus portfolio;

  const LocalS2CorpusPair({required this.risk, required this.portfolio});
}

LocalS2CorpusPair? loadLocalS2Corpora(
  Map<String, String> environment, {
  LocalS2ArtifactReader? readArtifactBytes,
  LocalS2RuntimeReader? readRuntime,
}) {
  try {
    final flag = environment['FINEX_REQUIRE_LOCAL_S2_CORPUS'];
    _require(flag == null || flag == '0' || flag == '1');
    final paths = _environmentKeys.map((key) => environment[key]).toList();
    if (paths.every((path) => path == null)) {
      _require(flag != '1');
      return null;
    }
    _require(paths.every((path) => path != null && path.trim().isNotEmpty));
    _require(paths.toSet().length == paths.length);
    final reader = readArtifactBytes ?? _readArtifact;
    final originals = [for (final path in paths) reader(path!)];
    final documents = [for (final bytes in originals) _parseBytes(bytes)];
    final runtime = (readRuntime ?? _currentRuntime)();
    _require(
      _sha40.hasMatch(runtime.testedCommit) &&
          _sha40.hasMatch(runtime.testedTree),
    );
    _require(!runtime.workingTreeDirty && !runtime.trackedDirty);
    return LocalS2CorpusPair(
      risk: _validateCorpus(
        LocalS2CorpusKind.risk,
        documents[0],
        documents[1],
        originals[0],
        runtime,
      ),
      portfolio: _validateCorpus(
        LocalS2CorpusKind.portfolio,
        documents[2],
        documents[3],
        originals[2],
        runtime,
      ),
    );
  } catch (_) {
    // No raw parser/process/file/body diagnostic is interpolated or propagated.
    throw const FormatException(
      'Current native local S2 evidence is missing or invalid.',
    );
  }
}

const _environmentKeys = [
  'FINEX_LOCAL_S2_RISK_CORPUS',
  'FINEX_LOCAL_S2_RISK_REPORT',
  'FINEX_LOCAL_S2_PORTFOLIO_CORPUS',
  'FINEX_LOCAL_S2_PORTFOLIO_REPORT',
];
const _corpusKeys = {
  'schema_version',
  'scope',
  'contract_version',
  'provenance',
  'source_hashes',
  'source_manifest_sha256',
  'cases',
};
const _reportKeys = {
  'schema_version',
  'scope',
  'contract_version',
  'success',
  'mode',
  'tested_commit',
  'tested_tree',
  'working_tree_dirty',
  'tracked_dirty',
  'source_hashes',
  'source_manifest_sha256',
  'checks',
  'required_checks',
  'failures',
  'responses_checked',
  'corpus_sha256',
  'corpus_case_ids',
  'native_process',
  'python_version',
  'limitations',
};
const _processKeys = {
  'starts',
  'application_restarts',
  'owned_pids',
  'child_reaped',
  'temporary_directory_removed',
  'session_ttl_minutes',
  'real_expiry_elapsed_seconds',
  'shutdown',
};
const _riskSpecs = <(String, String, int, String?)>[
  ('questionnaire', 'questionnaire', 200, null),
  ('draft_initial', 'draft_get', 200, null),
  ('draft_partial_saved', 'draft_put', 200, null),
  ('draft_partial_resumed', 'draft_get', 200, null),
  ('history_initial', 'history', 200, null),
  ('assessment_created', 'assessment_create', 200, null),
  ('assessment_equivalent_replay', 'assessment_create', 200, null),
  ('assessment_detail', 'assessment_detail', 200, null),
  ('history_single', 'history', 200, null),
  ('other_owner_history_empty', 'history', 200, null),
  ('draft_cleared', 'draft_put', 200, null),
  ('draft_after_restart', 'draft_get', 200, null),
  ('assessment_after_restart', 'assessment_detail', 200, null),
  ('assessment_aggressive', 'assessment_create', 200, null),
  ('assessment_conservative', 'assessment_create', 200, null),
  ('history_page_first', 'history', 200, null),
  ('assessment_inserted_between_pages', 'assessment_create', 200, null),
  ('history_page_next', 'history', 200, null),
  ('history_after_relogin', 'history', 200, null),
  ('idempotency_conflict', 'assessment_create', 409, 'IDEMPOTENCY_CONFLICT'),
  (
    'assessment_other_owner',
    'assessment_detail',
    404,
    'RISK_ASSESSMENT_NOT_FOUND',
  ),
  ('assessment_missing', 'assessment_detail', 404, 'RISK_ASSESSMENT_NOT_FOUND'),
  ('onboarding_withdrawn', 'history', 409, 'ONBOARDING_REQUIRED'),
  ('onboarding_reaccepted', 'history', 409, 'ONBOARDING_REQUIRED'),
  ('session_invalid', 'draft_get', 401, 'SESSION_INVALID'),
  ('session_restart_invalid', 'history', 401, 'SESSION_INVALID'),
  (
    'unsupported_version',
    'draft_put',
    400,
    'UNSUPPORTED_QUESTIONNAIRE_VERSION',
  ),
  (
    'missing_required_question',
    'assessment_create',
    400,
    'MISSING_REQUIRED_QUESTION',
  ),
  ('validation_error', 'assessment_create', 422, 'VALIDATION_ERROR'),
];
const _portfolioSpecs = <(String, String, int, String?)>[
  ('catalogue', 'catalogue', 200, null),
  ('portfolio_created', 'portfolio_create', 201, null),
  ('portfolio_list', 'portfolio_list', 200, null),
  ('portfolio_detail', 'portfolio_detail', 200, null),
  ('portfolio_updated', 'portfolio_update', 200, null),
  ('portfolio_unchanged', 'portfolio_update', 200, null),
  ('portfolio_deleted', 'portfolio_delete', 200, null),
  ('holding_created', 'holding_create', 201, null),
  ('holding_list', 'holding_list', 200, null),
  ('holding_detail', 'holding_detail', 200, null),
  ('holding_updated', 'holding_update', 200, null),
  ('holding_unchanged', 'holding_update', 200, null),
  ('holding_deleted', 'holding_delete', 200, null),
  ('golden_1', 'metrics', 200, null),
  ('golden_2', 'metrics', 200, null),
  ('golden_3', 'metrics', 200, null),
  ('golden_4', 'metrics', 200, null),
  ('golden_5', 'metrics', 200, null),
  ('golden_6', 'metrics', 200, null),
  ('empty', 'metrics', 200, null),
  ('zero_cost', 'metrics', 200, null),
  ('partial', 'metrics', 200, null),
  ('unavailable', 'metrics', 200, null),
  ('session_invalid', 'portfolio_list', 401, 'SESSION_INVALID'),
  ('onboarding_required', 'portfolio_list', 409, 'ONBOARDING_REQUIRED'),
  ('portfolio_not_found', 'portfolio_detail', 404, 'LOCAL_PORTFOLIO_NOT_FOUND'),
  ('holding_not_found', 'holding_detail', 404, 'LOCAL_HOLDING_NOT_FOUND'),
  ('validation_error', 'holding_create', 422, 'VALIDATION_ERROR'),
  ('unsupported_instrument', 'holding_create', 422, 'UNSUPPORTED_INSTRUMENT'),
  ('holding_duplicate', 'holding_create', 409, 'HOLDING_ALREADY_EXISTS'),
  ('portfolio_limit', 'portfolio_create', 409, 'PORTFOLIO_LIMIT_REACHED'),
];
const _riskChecks = [
  'disabled_prebody_no_database',
  'missing_bearer_no_database',
  'current_s1_prerequisites',
  'ordered_ten_question_contract',
  'owned_partial_draft',
  'saved_numeric_rules_snapshot',
  'original_equivalent_replay',
  'conflict_unchanged_history',
  'owner_scoped_history_detail',
  'empty_draft_preserves_history',
  'first_native_restart',
  'bounded_stable_cursor',
  'withdrawal_reacceptance_gate',
  'durable_session_logout',
  'second_native_restart',
  'safe_wire_without_credentials',
  'complete_safe_wire_corpus',
  'owned_cleanup',
];
const _portfolioChecks = [
  'disabled_prebody_no_database',
  'remote_configuration_no_database',
  'missing_bearer_no_database',
  'current_s1_prerequisites',
  'schema3_preserves_s1_and_risk',
  'versioned_synthetic_catalog',
  'owned_portfolio_crud_noop',
  'owned_holding_crud_noop',
  'canonical_input_rejections_unchanged',
  'cross_owner_and_parent_isolation',
  'duplicate_and_portfolio_capacity',
  'six_decimal_golden_cases',
  'zero_cost_and_rounded_zero',
  'honest_empty_partial_unavailable',
  'first_native_restart',
  'persisted_portfolios_holdings_and_risk',
  'withdrawal_reacceptance_gates',
  'no_implicit_record_erasure',
  'durable_per_session_logout',
  'second_native_restart',
  'real_one_minute_expiry',
  'records_preserved_after_expiry',
  'digest_only_storage_no_reflection',
  'safe_wire_and_diagnostics',
  'complete_safe_wire_corpus',
  'owned_cleanup',
];
const _privateKeys = {
  'user',
  'userid',
  'owner',
  'ownerid',
  'alias',
  'session',
  'sessionid',
  'token',
  'bearer',
  'digest',
  'dbpath',
  'database',
  'headers',
  'path',
  'logs',
  'diagnostics',
  'nonce',
  'password',
  'secret',
  'authorization',
  'accesstoken',
  'refreshtoken',
  'cookie',
  'cookies',
  'setcookie',
  'expiresat',
  'apikey',
  'credentials',
};
final _sha40 = RegExp(r'^[0-9a-f]{40}$');
final _sha64 = RegExp(r'^[0-9a-f]{64}$');
final _correlation = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$');

void _require(bool value) {
  if (!value) {
    throw const FormatException('Invalid bounded local S2 evidence.');
  }
}

Map<String, dynamic> _object(Object? value, [Set<String>? keys]) {
  _require(value is Map<String, dynamic>);
  final result = value as Map<String, dynamic>;
  if (keys != null) {
    _require(result.length == keys.length && keys.every(result.containsKey));
  }
  return result;
}

List<dynamic> _array(Object? value, int maximum) {
  _require(value is List && value.length <= maximum);
  return value as List<dynamic>;
}

String _text(Object? value, {int maximum = 4096}) {
  _require(value is String && value.length <= maximum);
  return value as String;
}

String _hash(List<int> bytes) => sha256.convert(bytes).toString();

bool _same(Object? left, Object? right) {
  if (left is Map && right is Map) {
    return left.length == right.length &&
        left.keys.every(
          (key) => right.containsKey(key) && _same(left[key], right[key]),
        );
  }
  if (left is List && right is List) {
    return left.length == right.length &&
        List.generate(
          left.length,
          (index) => _same(left[index], right[index]),
        ).every((value) => value);
  }
  return left == right;
}

Object? _instantComparable(Object? value) {
  if (value is Map<String, dynamic>) {
    return {
      for (final entry in value.entries)
        entry.key: entry.key == 'rules_snapshot'
            ? entry
                  .value // Immutable rule bytes are not normalized/rehashed.
            : [
                    'created_at',
                    'updated_at',
                    'calculated_at',
                  ].contains(entry.key) &&
                  entry.value != null
            ? localUtcTimestamp(entry.value).toIso8601String()
            : _instantComparable(entry.value),
    };
  }
  if (value is List) {
    return value.map(_instantComparable).toList();
  }
  return value;
}

bool _sameRecords(Object? left, Object? right) =>
    _same(_instantComparable(left), _instantComparable(right));

Object? _freeze(Object? value) {
  if (value is Map<String, dynamic>) {
    return Map<String, dynamic>.unmodifiable(
      value.map((key, item) => MapEntry(key, _freeze(item))),
    );
  }
  if (value is List) {
    return List<dynamic>.unmodifiable(value.map(_freeze));
  }
  return value;
}

void _privateFree(Object? value, [int depth = 0]) {
  _require(depth <= 24);
  if (value is Map) {
    for (final entry in value.entries) {
      _require(entry.key is String);
      final key = (entry.key as String).toLowerCase().replaceAll(
        RegExp(r'[^a-z0-9]'),
        '',
      );
      _require(!_privateKeys.contains(key));
      _privateFree(entry.value, depth + 1);
    }
  } else if (value is List) {
    for (final item in value) {
      _privateFree(item, depth + 1);
    }
  } else if (value is String) {
    _require(!value.contains('Bearer ') && !value.contains('github_pat_'));
  } else if (value is num) {
    _require(value.isFinite);
  }
}

Uint8List _readArtifact(String path) {
  final file = File(path);
  _require(
    FileSystemEntity.typeSync(path, followLinks: false) ==
        FileSystemEntityType.file,
  );
  _require(file.lengthSync() > 0 && file.lengthSync() <= 2097152);
  final bytes = file.readAsBytesSync();
  _require(bytes.length <= 2097152);
  return bytes;
}

Map<String, dynamic> _parseBytes(Uint8List bytes) {
  _require(bytes.isNotEmpty && bytes.length <= 2097152);
  final source = utf8.decode(bytes, allowMalformed: false);
  // jsonDecode keeps the last duplicate member. Check the original text first
  // so a later safe value cannot erase an earlier credential/private value.
  // This validates object-member identity without rewriting captured bytes.
  _JsonMemberGuard(source).validate();
  return _object(jsonDecode(source));
}

class _JsonMemberGuard {
  final String _source;
  int _offset = 0;

  _JsonMemberGuard(this._source);

  void validate() {
    _value(0);
    _whitespace();
    _require(_offset == _source.length);
  }

  void _value(int depth) {
    _require(depth <= 64);
    _whitespace();
    _require(_offset < _source.length);
    switch (_source.codeUnitAt(_offset)) {
      case 0x7b:
        _objectMembers(depth);
        break;
      case 0x5b:
        _arrayItems(depth);
        break;
      case 0x22:
        _stringToken();
        break;
      default:
        final start = _offset;
        while (_offset < _source.length &&
            !const {
              0x20,
              0x09,
              0x0a,
              0x0d,
              0x2c,
              0x5d,
              0x7d,
            }.contains(_source.codeUnitAt(_offset))) {
          _offset++;
        }
        _require(_offset > start);
      // The standard decoder subsequently validates scalar grammar. No
      // scalar, input fragment or parser diagnostic is surfaced to callers.
    }
  }

  void _objectMembers(int depth) {
    _offset++;
    _whitespace();
    if (_take(0x7d)) {
      return;
    }
    final names = <String>{};
    while (true) {
      _whitespace();
      _require(_offset < _source.length && _source.codeUnitAt(_offset) == 0x22);
      final token = _stringToken();
      final name = jsonDecode(token);
      _require(name is String && names.add(name));
      _whitespace();
      _require(_take(0x3a));
      _value(depth + 1);
      _whitespace();
      if (_take(0x7d)) {
        return;
      }
      _require(_take(0x2c));
    }
  }

  void _arrayItems(int depth) {
    _offset++;
    _whitespace();
    if (_take(0x5d)) {
      return;
    }
    while (true) {
      _value(depth + 1);
      _whitespace();
      if (_take(0x5d)) {
        return;
      }
      _require(_take(0x2c));
    }
  }

  String _stringToken() {
    final start = _offset;
    _require(_take(0x22));
    while (_offset < _source.length) {
      final code = _source.codeUnitAt(_offset++);
      if (code == 0x22) {
        return _source.substring(start, _offset);
      }
      _require(code >= 0x20);
      if (code != 0x5c) {
        continue;
      }
      _require(_offset < _source.length);
      final escaped = _source.codeUnitAt(_offset++);
      if (escaped == 0x75) {
        _require(_offset + 4 <= _source.length);
        for (var index = 0; index < 4; index++) {
          final digit = _source.codeUnitAt(_offset++);
          _require(
            (digit >= 0x30 && digit <= 0x39) ||
                (digit >= 0x41 && digit <= 0x46) ||
                (digit >= 0x61 && digit <= 0x66),
          );
        }
      } else {
        _require(
          const {
            0x22,
            0x5c,
            0x2f,
            0x62,
            0x66,
            0x6e,
            0x72,
            0x74,
          }.contains(escaped),
        );
      }
    }
    throw const FormatException('Invalid bounded local S2 evidence.');
  }

  bool _take(int code) {
    if (_offset < _source.length && _source.codeUnitAt(_offset) == code) {
      _offset++;
      return true;
    }
    return false;
  }

  void _whitespace() {
    while (_offset < _source.length &&
        const {0x20, 0x09, 0x0a, 0x0d}.contains(_source.codeUnitAt(_offset))) {
      _offset++;
    }
  }
}

LocalS2Corpus _validateCorpus(
  LocalS2CorpusKind kind,
  Map<String, dynamic> rawCorpus,
  Map<String, dynamic> rawReport,
  Uint8List originalBytes,
  LocalS2CorpusRuntime runtime,
) {
  final isRisk = kind == LocalS2CorpusKind.risk;
  final corpus = _object(rawCorpus, _corpusKeys);
  final report = _object(rawReport, _reportKeys);
  final name = isRisk ? 'saved_risk' : 'portfolio';
  final command = isRisk
      ? 'python verify_s2_saved_risk.py'
      : 'python verify_s2_manual_portfolio.py';
  _require(corpus['schema_version'] == 'finex.local_s2.${name}_corpus.v1');
  _require(
    report['schema_version'] ==
        (isRisk
            ? 'finex.local_s2.saved_risk.acceptance.v1'
            : 'finex.local_s2.manual_portfolio.acceptance.v1'),
  );
  for (final value in [corpus, report]) {
    _require(
      value['scope'] == localApplicationScope &&
          value['contract_version'] == localContractVersion,
    );
  }
  final provenance = _object(corpus['provenance'], {
    'kind',
    'source',
    'command',
    'tested_commit',
    'tested_tree',
  });
  _require(
    provenance['kind'] == 'native_tcp_capture' &&
        provenance['source'] == 'owned_loopback_uvicorn',
  );
  _require(provenance['command'] == command);
  for (final value in [provenance, report]) {
    _require(
      value['tested_commit'] == runtime.testedCommit &&
          value['tested_tree'] == runtime.testedTree,
    );
  }
  _require(report['success'] == true && report['mode'] == 'owned_native_tcp');
  _require(
    report['working_tree_dirty'] == false && report['tracked_dirty'] == false,
  );
  _require(_array(report['failures'], 0).isEmpty);
  _require(
    report['corpus_sha256'] is String &&
        _sha64.hasMatch(report['corpus_sha256'] as String),
  );
  _require(report['corpus_sha256'] == _hash(originalBytes));
  _validateSources(corpus, report, runtime, kind);
  final checks = isRisk ? _riskChecks : _portfolioChecks;
  _require(_same(report['required_checks'], checks));
  final actualChecks = _array(report['checks'], checks.length);
  _require(actualChecks.length == checks.length);
  for (var index = 0; index < checks.length; index++) {
    final item = _object(actualChecks[index], {'id', 'passed'});
    _require(item['id'] == checks[index] && item['passed'] == true);
  }
  _validateLifecycle(report, isRisk);
  _require(
    RegExp(r'^3\.[0-9]{1,2}\.[0-9]{1,3}$')
        .hasMatch(_text(report['python_version'], maximum: 20)),
  );
  final limitations = _array(report['limitations'], 16);
  _require(limitations.isNotEmpty);
  for (final limitation in limitations) {
    _text(limitation);
  }
  final specs = isRisk ? _riskSpecs : _portfolioSpecs;
  final items = _array(corpus['cases'], specs.length);
  _require(items.length == specs.length);
  _require(
    report['responses_checked'] is int &&
        (report['responses_checked'] as int) >= items.length,
  );
  _require(
    _same(report['corpus_case_ids'], specs.map((spec) => spec.$1).toList()),
  );
  final cases = <LocalS2CorpusCase>[];
  final successData = <String, Map<String, dynamic>>{};
  for (var index = 0; index < items.length; index++) {
    final item = _object(items[index], {
      'id',
      'operation',
      if (isRisk) 'target',
      'request',
      'status',
      'content_type',
      'body_utf8',
      'expected',
    });
    final (id, operation, status, code) = specs[index];
    _require(
      item['id'] == id &&
          item['operation'] == operation &&
          item['status'] is int &&
          item['status'] == status,
    );
    _require(item['content_type'] == 'application/json');
    final expected = _object(
      item['expected'],
      code == null ? {'outcome'} : {'outcome', 'error_code'},
    );
    _require(
      expected['outcome'] == (code == null ? 'success' : 'error') &&
          expected['error_code'] == code,
    );
    final bodyString = _text(item['body_utf8'], maximum: 262144);
    final bodyBytes = Uint8List.fromList(utf8.encode(bodyString));
    _require(bodyBytes.length <= 262144);
    final body = _parseBytes(bodyBytes);
    _privateFree(body);
    _privateFree(item['request']);
    final target = isRisk ? _riskTarget(operation, item['target']) : null;
    if (code == null) {
      final data = _successBody(body, kind, operation);
      _validateRequest(item['request'], data, operation, target);
      successData[id] = data;
    } else {
      _require(item['request'] == null);
      _errorBody(body, code);
    }
    cases.add(
      LocalS2CorpusCase(
        id: id,
        operation: operation,
        target: target == null ? null : _object(_freeze(target)),
        request: item['request'] == null
            ? null
            : _object(_freeze(item['request'])),
        status: status,
        contentType: 'application/json',
        bodyUtf8: bodyString,
        outcome: code == null ? 'success' : 'error',
        errorCode: code,
      ),
    );
  }
  if (isRisk) {
    _riskRelationships(cases, successData);
  } else {
    _portfolioRelationships(successData);
  }
  return LocalS2Corpus(
    kind: kind,
    originalBytes: Uint8List.fromList(originalBytes),
    document: _object(_freeze(corpus)),
    report: _object(_freeze(report)),
    cases: List.unmodifiable(cases),
  );
}

void _validateSources(
  Map<String, dynamic> corpus,
  Map<String, dynamic> report,
  LocalS2CorpusRuntime runtime,
  LocalS2CorpusKind kind,
) {
  final expectedPaths = kind == LocalS2CorpusKind.risk
      ? runtime.riskSourcePaths
      : runtime.portfolioSourcePaths;
  _require(expectedPaths.contains('backend/local_s2_evidence.py'));
  _require(
    expectedPaths.contains(
      kind == LocalS2CorpusKind.risk
          ? 'backend/verify_s2_saved_risk.py'
          : 'backend/verify_s2_manual_portfolio.py',
    ),
  );
  final rows = _array(corpus['source_hashes'], 512);
  _require(rows.isNotEmpty && rows.length == expectedPaths.length);
  _require(_same(rows, report['source_hashes']));
  String? previous;
  final manifest = StringBuffer();
  for (final raw in rows) {
    final row = _object(raw, {'path', 'sha256'});
    final path = _text(row['path'], maximum: 300);
    final digest = _text(row['sha256'], maximum: 64);
    _require(
      RegExp(r'^[A-Za-z0-9_./-]+$').hasMatch(path) && !path.startsWith('/'),
    );
    _require(
      path
          .split('/')
          .every((part) => part.isNotEmpty && part != '.' && part != '..'),
    );
    _require(previous == null || previous.compareTo(path) < 0);
    _require(expectedPaths.contains(path) && _sha64.hasMatch(digest));
    final actual = runtime.sourceBytesByPath[path];
    _require(
      actual != null && actual.length <= 2097152 && _hash(actual) == digest,
    );
    manifest.writeln('$path ${digest.toUpperCase()}');
    previous = path;
  }
  final digest = _hash(utf8.encode(manifest.toString()));
  _require(
    corpus['source_manifest_sha256'] == digest &&
        report['source_manifest_sha256'] == digest,
  );
}

void _validateLifecycle(Map<String, dynamic> report, bool isRisk) {
  final process = _object(report['native_process'], _processKeys);
  final starts = isRisk ? 4 : 5;
  _require(process['starts'] is int && process['starts'] == starts);
  _require(
    process['application_restarts'] is int &&
        process['application_restarts'] == 2,
  );
  _require(
    process['session_ttl_minutes'] is int &&
        process['session_ttl_minutes'] == 1,
  );
  _require(
    process['child_reaped'] == true &&
        process['temporary_directory_removed'] == true,
  );
  _require(process['shutdown'] == 'owned_terminate_and_reap');
  final pids = _array(process['owned_pids'], starts);
  _require(pids.length == starts && pids.every((pid) => pid is int && pid > 0));
  _require(pids.toSet().length == pids.length);
  final expiry = process['real_expiry_elapsed_seconds'];
  if (isRisk) {
    _require(expiry == null);
  } else {
    _require(expiry is num && expiry.isFinite && expiry >= 59 && expiry <= 75);
  }
}

Map<String, dynamic>? _riskTarget(String operation, Object? raw) {
  if (operation == 'history') {
    final target = _object(raw, {'limit', 'before'});
    _require(target['limit'] is int && target['limit'] == 2);
    if (target['before'] != null) {
      localRiskCursor(target['before']);
    }
    return target;
  }
  if (operation == 'assessment_detail') {
    final target = _object(raw, {'assessment_id'});
    localUuid(target['assessment_id']);
    return target;
  }
  _require(raw == null);
  return null;
}

void _errorBody(Map<String, dynamic> body, String code) {
  _object(body, {'success', 'message', 'error_code', 'error', 'detail'});
  final message = _text(body['message']);
  final error = _object(body['error'], {
    'code',
    'message',
    'fieldErrors',
    'correlationId',
  });
  _require(
    body['success'] == false &&
        body['error_code'] == code &&
        error['code'] == code,
  );
  _require(error['message'] == message && body['detail'] == message);
  _require(_correlation.hasMatch(_text(error['correlationId'], maximum: 128)));
  for (final raw in _array(error['fieldErrors'], 64)) {
    final field = _object(raw, {'field', 'code'});
    _text(field['field'], maximum: 128);
    _text(field['code'], maximum: 128);
  }
}

Map<String, dynamic> _successBody(
  Map<String, dynamic> body,
  LocalS2CorpusKind kind,
  String operation,
) {
  _object(body, {'success', 'message', 'data', 'meta'});
  _require(body['success'] == true);
  _text(body['message']);
  final data = _object(body['data']);
  final meta = _object(body['meta'], {
    'apiVersion',
    'dataStatus',
    'dataAsOf',
    'correlationId',
  });
  _require(meta['apiVersion'] == 'v1');
  _require(_correlation.hasMatch(_text(meta['correlationId'], maximum: 128)));
  var dataStatus = 'CACHED';
  DateTime? asOf;
  if (kind == LocalS2CorpusKind.risk) {
    if (operation == 'questionnaire') {
      LocalRiskQuestionnaire.fromJson(data);
    } else if (operation == 'draft_get' || operation == 'draft_put') {
      asOf = LocalRiskDraft.fromJson(data).updatedAt;
    } else if (operation == 'assessment_create' ||
        operation == 'assessment_detail') {
      asOf = LocalSavedRiskAssessment.fromJson(data).createdAt;
    } else if (operation == 'history') {
      LocalRiskHistory.fromJson(data);
    } else {
      _require(false);
    }
  } else if (operation == 'catalogue') {
    LocalInstrumentCatalog.fromJson(data);
  } else if (operation == 'portfolio_list') {
    LocalPortfolioList.fromJson(data);
  } else if (operation == 'holding_list') {
    LocalHoldingList.fromJson(data);
  } else if ([
    'portfolio_create',
    'portfolio_update',
    'portfolio_detail',
  ].contains(operation)) {
    asOf = LocalPortfolio.fromJson(data).updatedAt;
  } else if ([
    'holding_create',
    'holding_update',
    'holding_detail',
  ].contains(operation)) {
    asOf = LocalHolding.fromJson(data).updatedAt;
  } else if (operation == 'metrics') {
    final metrics = LocalPortfolioMetrics.fromJson(data);
    dataStatus = metrics.dataStatus;
    asOf = metrics.dataAsOf;
  } else if (operation == 'portfolio_delete' || operation == 'holding_delete') {
    final holding = operation == 'holding_delete';
    _object(data, {
      'scope',
      'contract_version',
      holding ? 'holding_version' : 'portfolio_version',
      'portfolio_id',
      if (holding) 'holding_id',
      'entity_type',
      'deleted',
    });
    requireLocalVersion(data);
    localUuid(data['portfolio_id']);
    if (holding) {
      localUuid(data['holding_id']);
    }
    _require(
      data[holding ? 'holding_version' : 'portfolio_version'] ==
          (holding ? 'holding.v1' : 'portfolio.v1'),
    );
    _require(
      data['entity_type'] == (holding ? 'holding' : 'portfolio') &&
          data['deleted'] == true,
    );
  } else {
    _require(false);
  }
  final actualTime = meta['dataAsOf'] == null
      ? null
      : localUtcTimestamp(meta['dataAsOf']);
  _require(meta['dataStatus'] == dataStatus && actualTime == asOf);
  return data;
}

void _validateRequest(
  Object? raw,
  Map<String, dynamic> data,
  String operation,
  Map<String, dynamic>? target,
) {
  if (operation == 'draft_put' || operation == 'assessment_create') {
    final complete = operation == 'assessment_create';
    final request = _object(raw, {
      'questionnaire_id',
      'questionnaire_version',
      'answers',
      if (complete) 'idempotency_key',
    });
    final input = LocalRiskInput.fromJson(
      {...request}..remove('idempotency_key'),
      complete: complete,
    );
    if (complete) {
      localUuid(request['idempotency_key']);
      _require(LocalSavedRiskAssessment.fromJson(data).input.equivalent(input));
    } else {
      final actual = LocalRiskDraft.fromJson(data);
      _require(
        actual.updatedAt != null &&
            _same(actual.input.toJson(), input.toJson()),
      );
    }
  } else if (operation == 'portfolio_create' ||
      operation == 'portfolio_update') {
    final request = _object(raw, {
      'portfolio_version',
      'name',
      'description',
      'currency',
    });
    _require(
      request['portfolio_version'] == 'portfolio.v1' &&
          request['currency'] == 'USD',
    );
    final input = PortfolioInput(
      name: request['name'] as String,
      description: request['description'] as String?,
    );
    // The public input emits the documented canonical strings. Compare a
    // separate four-field copy; retain the original captured request bytes.
    final canonicalRequest = {
      ...request,
      'name': (request['name'] as String).trim(),
      'description': (request['description'] as String?)?.trim(),
    };
    _require(_same(input.toJson(), canonicalRequest));
    _require(
      data['name'] == input.name && data['description'] == input.description,
    );
  } else if (operation == 'holding_create' || operation == 'holding_update') {
    final create = operation == 'holding_create';
    final request = _object(raw, {
      'holding_version',
      if (create) 'instrument_id',
      'quantity',
      'average_cost',
      'currency',
    });
    _require(
      request['holding_version'] == 'holding.v1' &&
          request['currency'] == 'USD',
    );
    final input = HoldingInput(
      instrumentId: create ? request['instrument_id'] as String : null,
      quantity: request['quantity'] as String,
      averageCost: request['average_cost'] as String,
    );
    _require(_same(input.toJson(), request));
    _require(
      data['quantity'] == input.quantity &&
          data['average_cost'] == input.averageCost,
    );
    _require(!create || data['instrument_id'] == input.instrumentId);
  } else {
    _require(raw == null);
    if (operation == 'assessment_detail') {
      _require(data['assessment_id'] == target!['assessment_id']);
    }
  }
}

void _riskRelationships(
  List<LocalS2CorpusCase> cases,
  Map<String, Map<String, dynamic>> data,
) {
  LocalS2CorpusCase item(String id) =>
      cases.singleWhere((item) => item.id == id);
  final original = data['assessment_created']!;
  final replay = item('assessment_equivalent_replay').request!;
  final first = item('assessment_created').request!;
  _require(replay['idempotency_key'] == first['idempotency_key']);
  _require(
    _same(replay['answers'], (first['answers'] as List).reversed.toList()),
  );
  for (final id in [
    'assessment_equivalent_replay',
    'assessment_detail',
    'assessment_after_restart',
  ]) {
    _require(_sameRecords(data[id], original));
  }
  _require(
    _sameRecords(data['draft_partial_saved'], data['draft_partial_resumed']),
  );
  _require(_sameRecords(data['draft_cleared'], data['draft_after_restart']));
  _require(
    (data['draft_initial']!['answers'] as List).isEmpty &&
        data['draft_initial']!['updated_at'] == null,
  );
  _require(
    (data['draft_cleared']!['answers'] as List).isEmpty &&
        data['draft_cleared']!['updated_at'] != null,
  );
  final records = [
    original,
    data['assessment_aggressive']!,
    data['assessment_conservative']!,
    data['assessment_inserted_between_pages']!,
  ];
  final suffixes = ['C', 'E', 'A', 'D'];
  for (var index = 0; index < records.length; index++) {
    final input = LocalRiskInput.fromJson(
      records[index]['input'],
      complete: true,
    );
    _require(
      input.answers.every(
        (answer) =>
            answer.answerCode == '${answer.questionId}_${suffixes[index]}',
      ),
    );
    _require(
      _same(records[index]['rules_snapshot'], original['rules_snapshot']) &&
          records[index]['rules_sha256'] == original['rules_sha256'],
    );
  }
  _require(
    records.map((record) => record['assessment_id']).toSet().length ==
        records.length,
  );
  _require(
    [
          'assessment_created',
          'assessment_aggressive',
          'assessment_conservative',
          'assessment_inserted_between_pages',
        ].map((id) => item(id).request!['idempotency_key']).toSet().length ==
        records.length,
  );
  final pages = {
    'history_initial': <Object?>[],
    'other_owner_history_empty': <Object?>[],
    'history_single': [original],
    'history_page_first': [records[2], records[1]],
    'history_page_next': [original],
    'history_after_relogin': [records[3], records[2]],
  };
  for (final entry in pages.entries) {
    _require(_sameRecords(data[entry.key]!['items'], entry.value));
    _require(
      (data[entry.key]!['next_cursor'] != null) ==
          ['history_page_first', 'history_after_relogin'].contains(entry.key),
    );
  }
  final cursor = data['history_page_first']!['next_cursor'];
  _require(item('history_page_next').target!['before'] == cursor);
  _require(
    BigInt.parse(data['history_after_relogin']!['next_cursor'] as String) >
        BigInt.parse(cursor as String),
  );
  for (final value in cases.where(
    (item) => item.operation == 'history' && item.id != 'history_page_next',
  )) {
    _require(value.target!['before'] == null);
  }
}

void _portfolioRelationships(Map<String, Map<String, dynamic>> data) {
  _require(
    _sameRecords(data['portfolio_updated'], data['portfolio_unchanged']),
  );
  _require(_sameRecords(data['holding_updated'], data['holding_unchanged']));
  for (final prefix in ['portfolio', 'holding']) {
    final created = data['${prefix}_created']!;
    final detail = data['${prefix}_detail']!;
    final changed = data['${prefix}_updated']!;
    _require(_sameRecords(created, detail));
    _require(created['${prefix}_id'] == changed['${prefix}_id']);
    _require(
      localUtcTimestamp(created['created_at']) ==
          localUtcTimestamp(changed['created_at']),
    );
  }
}

// Current writers use this controlled combined inventory. It is not inferred
// from untrusted artifact paths or required to equal another domain's list.
const _additionalRuntimePaths = {
  'backend/local_s2_evidence.py',
  'backend/verify_s2_evidence_pair.py',
  'backend/verify_s2_saved_risk.py',
  'backend/verify_s2_manual_portfolio.py',
  'ai/risk/contract.py',
  'ai/risk/scoring.py',
  'backend/data/questionnaire/risk_questionnaire_v1.json',
  'docs/features/local-application/S2-manual-portfolio-contract.md',
  'docs/features/local-application/S2-saved-risk-contract.md',
  'backend/tests/unit/test_local_s2_portfolio_native_harness.py',
  'backend/tests/unit/test_s2_saved_risk_corpus.py',
  'backend/tests/unit/test_local_s2_shared_evidence.py',
  'backend/tests/unit/test_local_s2_portfolio_expiry_risk.py',
  'backend/tests/unit/test_s2_evidence_pair_validation.py',
};

typedef LocalS2CorpusGitRunner = ProcessResult Function(
  String executable,
  List<String> arguments, {
  required String workingDirectory,
  required bool runInShell,
  required Map<String, String> environment,
  required bool includeParentEnvironment,
});

String _git(String directory, List<String> arguments) =>
    readLocalS2CorpusGit(directory, arguments);

// Test-only process seam, shared by the actual runtime metadata reader.
String readLocalS2CorpusGit(
  String directory,
  List<String> arguments, {
  LocalS2CorpusGitRunner? runProcess,
  Map<String, String>? inheritedEnvironment,
}) {
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
  final runner = runProcess ?? Process.runSync;
  final result = runner(
    'git',
    [
      '--no-replace-objects',
      '--no-lazy-fetch',
      '-c',
      'core.fsmonitor=false',
      ...arguments,
    ],
    workingDirectory: directory,
    runInShell: false,
    environment: environment,
    includeParentEnvironment: false,
  );
  _require(result.exitCode == 0 && result.stdout is String);
  return (result.stdout as String).trim();
}

LocalS2CorpusRuntime _currentRuntime() {
  final root = _git(Directory.current.path, ['rev-parse', '--show-toplevel']);
  _require(root.isNotEmpty && Directory(root).isAbsolute);
  final commit = _git(root, ['rev-parse', 'HEAD']);
  final tree = _git(root, ['rev-parse', 'HEAD^{tree}']);
  _require(
    _git(root, ['status', '--porcelain', '--untracked-files=all']).isEmpty,
  );
  final tracked = _git(root, ['ls-files', '--', 'backend/app']);
  final paths = {
    for (final path in tracked.split(RegExp(r'\r?\n')))
      if (path.startsWith('backend/app/') && path.endsWith('.py')) path,
    'backend/verify_s1_application.py',
    'data/fixtures/local_s1/contract_cases.v1.json',
    ..._additionalRuntimePaths,
  };
  _require(paths.any((path) => path.startsWith('backend/app/')));
  final canonicalRoot = Directory(root).resolveSymbolicLinksSync();
  final sourceBytes = <String, Uint8List>{};
  for (final path in paths) {
    _require(
      RegExp(r'^[A-Za-z0-9_./-]+$').hasMatch(path) &&
          !path.split('/').contains('..'),
    );
    final file = File('$root/$path');
    _require(
      FileSystemEntity.typeSync(file.path, followLinks: false) ==
          FileSystemEntityType.file,
    );
    final canonical = file.resolveSymbolicLinksSync();
    final foldedRoot = Platform.isWindows
        ? canonicalRoot.toLowerCase()
        : canonicalRoot;
    final foldedFile = Platform.isWindows ? canonical.toLowerCase() : canonical;
    _require(foldedFile.startsWith('$foldedRoot${Platform.pathSeparator}'));
    _require(file.lengthSync() <= 2097152);
    sourceBytes[path] = file.readAsBytesSync();
  }
  // Reject a concurrent checkout/source change instead of certifying old bytes.
  _require(
    _git(root, ['rev-parse', 'HEAD']) == commit &&
        _git(root, ['rev-parse', 'HEAD^{tree}']) == tree,
  );
  _require(
    _git(root, ['status', '--porcelain', '--untracked-files=all']).isEmpty,
  );
  return LocalS2CorpusRuntime(
    testedCommit: commit,
    testedTree: tree,
    workingTreeDirty: false,
    trackedDirty: false,
    sourceBytesByPath: Map.unmodifiable(sourceBytes),
    riskSourcePaths: Set.unmodifiable(paths),
    portfolioSourcePaths: Set.unmodifiable(paths),
  );
}
