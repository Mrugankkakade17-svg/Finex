// These in-memory reports/corpora are SYNTHETIC loader-unit inputs, not native
// captures or accepted process evidence. No fixture file or credential is saved.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/local_s2_corpus.dart';
import 'support/local_s2_data.dart';

const _artifactKeys = [
  'FINEX_LOCAL_S2_RISK_CORPUS',
  'FINEX_LOCAL_S2_RISK_REPORT',
  'FINEX_LOCAL_S2_PORTFOLIO_CORPUS',
  'FINEX_LOCAL_S2_PORTFOLIO_REPORT',
];
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
final _unitCommit = List.filled(40, 'a').join();
final _unitTree = List.filled(40, 'b').join();

Map<String, dynamic> _object(Object? value) => value as Map<String, dynamic>;
List<dynamic> _list(Object? value) => value as List<dynamic>;
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    _object(jsonDecode(jsonEncode(value)));
Uint8List _jsonBytes(Object value) =>
    Uint8List.fromList(utf8.encode('${jsonEncode(value)}\n'));
String _hash(List<int> value) => sha256.convert(value).toString();

Map<String, dynamic> _unitAssessment(String id, String suffix) {
  final value = savedRiskData();
  value['assessment_id'] = id;
  value['input'] = riskInput(suffix: suffix);
  final score = switch (suffix) {
    'A' => 0,
    'E' => 100,
    'D' => 75,
    _ => 50,
  };
  final assessment = _object(value['assessment']);
  for (final key in [
    'willingness_score',
    'capacity_score',
    'composite_score',
  ]) {
    assessment[key] = score;
  }
  final category = score == 0
      ? ('CONSERVATIVE', 'Conservative')
      : score >= 67
      ? ('AGGRESSIVE', 'Aggressive')
      : ('MODERATE', 'Moderate');
  assessment['risk_category'] = {'code': category.$1, 'label': category.$2};
  return value;
}

Map<String, dynamic> _history(
  List<Map<String, dynamic>> items, [
  String? cursor,
]) => s2Scoped({'items': items, 'next_cursor': cursor});

Map<String, dynamic> _unitRiskCase((String, String, int, String?) spec) {
  final (id, operation, status, code) = spec;
  final original = _unitAssessment(assessmentA, 'C');
  final aggressive = _unitAssessment(
    '00000000-0000-4000-8000-000000000194',
    'E',
  );
  final conservative = _unitAssessment(
    '00000000-0000-4000-8000-000000000195',
    'A',
  );
  final inserted = _unitAssessment('00000000-0000-4000-8000-000000000196', 'D');
  Map<String, dynamic>? data;
  Map<String, dynamic>? request;
  Map<String, dynamic>? target;
  String? asOf;
  if (operation == 'history') {
    target = {'limit': 2, 'before': id == 'history_page_next' ? '2' : null};
  } else if (operation == 'assessment_detail') {
    target = {'assessment_id': assessmentA};
  }
  if (code == null) {
    if (operation == 'questionnaire') {
      data = questionnaireData();
    } else if (operation == 'draft_get' || operation == 'draft_put') {
      final partial =
          id == 'draft_partial_saved' || id == 'draft_partial_resumed';
      final saved =
          partial || id == 'draft_cleared' || id == 'draft_after_restart';
      data = riskDraftData(partial: partial, saved: saved);
      asOf = saved ? s2Time : null;
      if (operation == 'draft_put') {
        request = {
          'questionnaire_id': 'risk_questionnaire_v1',
          'questionnaire_version': 'v1',
          'answers': partial ? _list(riskInput(partial: true)['answers']) : [],
        };
      }
    } else if (operation == 'assessment_create') {
      final assessment = id == 'assessment_aggressive'
          ? aggressive
          : id == 'assessment_conservative'
          ? conservative
          : id == 'assessment_inserted_between_pages'
          ? inserted
          : original;
      data = assessment;
      request = _copy(_object(assessment['input']))
        ..['idempotency_key'] = assessment['assessment_id'];
      if (id == 'assessment_equivalent_replay') {
        request['answers'] = _list(request['answers']).reversed.toList();
      }
      asOf = s2Time;
    } else if (operation == 'assessment_detail') {
      data = original;
      asOf = s2Time;
    } else if (operation == 'history') {
      data = switch (id) {
        'history_initial' || 'other_owner_history_empty' => _history([]),
        'history_page_first' => _history([conservative, aggressive], '2'),
        'history_after_relogin' => _history([inserted, conservative], '3'),
        _ => _history([original]),
      };
    }
  }
  return {
    'id': id,
    'operation': operation,
    'target': target,
    'request': request,
    'status': status,
    'content_type': 'application/json',
    'body_utf8': code == null ? s2Envelope(data!, asOf: asOf) : s2Error(code),
    'expected': code == null
        ? {'outcome': 'success'}
        : {'outcome': 'error', 'error_code': code},
  };
}

Map<String, dynamic> _unitPortfolioCase((String, String, int, String?) spec) {
  final (id, operation, status, code) = spec;
  Map<String, dynamic>? data;
  Map<String, dynamic>? request;
  String? asOf;
  var dataStatus = 'CACHED';
  if (code == null) {
    if (operation == 'catalogue') {
      data = catalogData();
    } else if (operation == 'portfolio_list') {
      data = s2Scoped({
        'portfolio_version': 'portfolio.v1',
        'items': [portfolioData()],
        'count': 1,
      });
    } else if (operation == 'holding_list') {
      data = s2Scoped({
        'holding_version': 'holding.v1',
        'catalog_version': 'synthetic_catalog.v1',
        'portfolio_id': portfolioA,
        'items': [holdingData()],
        'count': 1,
      });
    } else if (operation == 'portfolio_delete' ||
        operation == 'holding_delete') {
      data = s2Scoped({
        operation == 'portfolio_delete'
            ? 'portfolio_version'
            : 'holding_version': operation == 'portfolio_delete'
            ? 'portfolio.v1'
            : 'holding.v1',
        'portfolio_id': portfolioA,
        if (operation == 'holding_delete') 'holding_id': holdingA,
        'entity_type': operation == 'portfolio_delete'
            ? 'portfolio'
            : 'holding',
        'deleted': true,
      });
    } else if (operation.startsWith('portfolio_')) {
      final changed = id == 'portfolio_updated' || id == 'portfolio_unchanged';
      data = portfolioData(
        name: changed ? 'Synthetic portfolio changed' : 'Synthetic portfolio',
      );
      asOf = s2Time;
      if (operation == 'portfolio_create' || operation == 'portfolio_update') {
        request = {
          'portfolio_version': 'portfolio.v1',
          'name': _object(data)['name'],
          'description': null,
          'currency': 'USD',
        };
      }
    } else if (operation.startsWith('holding_')) {
      final changed = id == 'holding_updated' || id == 'holding_unchanged';
      data = holdingData(
        quantity: changed ? '2.000000' : '10.000000',
        cost: changed ? '100.0000' : '150.0000',
      );
      asOf = s2Time;
      if (operation == 'holding_create' || operation == 'holding_update') {
        request = {
          'holding_version': 'holding.v1',
          if (operation == 'holding_create') 'instrument_id': 'SYN:AAPL',
          'quantity': _object(data)['quantity'],
          'average_cost': _object(data)['average_cost'],
          'currency': 'USD',
        };
      }
    } else if (operation == 'metrics') {
      // Loader-unit cases exercise the envelope/binding boundary, not the six
      // mathematical goldens. Native-byte parity below verifies actual goldens.
      data = metricsData(
        unavailable: id == 'unavailable',
        empty: id == 'empty',
      );
      if (id == 'partial') {
        final partial = _object(data);
        final missing = _copy(
          _object(_list(metricsData(unavailable: true)['holdings']).single),
        );
        missing['holding_id'] = '00000000-0000-4000-8000-000000000197';
        final known = _object(_list(partial['holdings']).single);
        known['weight_percent'] = null;
        partial['valuation_status'] = 'INCOMPLETE';
        partial['missing_instrument_ids'] = ['SYN:UNAVAILABLE'];
        partial['holdings'] = [known, missing];
        partial['totals'] = _copy(
          _object(metricsData(unavailable: true)['totals']),
        );
        _object(partial['totals'])['cost_basis'] = '3000.00';
      }
      final metrics = _object(data);
      dataStatus =
          ['INCOMPLETE', 'UNAVAILABLE'].contains(metrics['valuation_status'])
          ? 'UNAVAILABLE'
          : 'CACHED';
      asOf = metrics['valuation_status'] == 'COMPLETE' ? quoteTime : null;
    }
  }
  return {
    'id': id,
    'operation': operation,
    'request': request,
    'status': status,
    'content_type': 'application/json',
    'body_utf8': code == null
        ? s2Envelope(data!, status: dataStatus, asOf: asOf)
        : s2Error(code),
    'expected': code == null
        ? {'outcome': 'success'}
        : {'outcome': 'error', 'error_code': code},
  };
}

class _UnitBundle {
  late final Map<String, Uint8List> sourceBytes;
  late final Set<String> riskPaths;
  late final Set<String> portfolioPaths;
  late final Map<String, dynamic> risk;
  late final Map<String, dynamic> portfolio;
  late final Map<String, dynamic> riskReport;
  late final Map<String, dynamic> portfolioReport;
  late Map<String, Uint8List> artifacts;

  _UnitBundle() {
    sourceBytes = {
      'backend/app/main.py': Uint8List.fromList(
        utf8.encode('synthetic main source\r\n'),
      ),
      'backend/local_s2_evidence.py': Uint8List.fromList(
        utf8.encode('synthetic neutral source\n'),
      ),
      'backend/verify_s2_manual_portfolio.py': Uint8List.fromList(
        utf8.encode('synthetic portfolio driver\n'),
      ),
      'backend/verify_s2_saved_risk.py': Uint8List.fromList(
        utf8.encode('synthetic risk driver\n'),
      ),
    };
    riskPaths = {
      'backend/app/main.py',
      'backend/local_s2_evidence.py',
      'backend/verify_s2_saved_risk.py',
    };
    portfolioPaths = {...riskPaths, 'backend/verify_s2_manual_portfolio.py'};
    risk = _corpus(true, _riskSpecs.map(_unitRiskCase).toList());
    portfolio = _corpus(
      false,
      _portfolioSpecs.map(_unitPortfolioCase).toList(),
    );
    riskReport = _report(true, risk);
    portfolioReport = _report(false, portfolio);
    reseal();
  }

  Map<String, String> get environment => {
    'FINEX_REQUIRE_LOCAL_S2_CORPUS': '1',
    for (final key in _artifactKeys) key: 'C:/finex-unit-only/$key.json',
  };

  LocalS2CorpusRuntime runtime({
    String? commit,
    String? tree,
    bool dirty = false,
    bool trackedDirty = false,
    Map<String, Uint8List>? sources,
  }) => LocalS2CorpusRuntime(
    testedCommit: commit ?? _unitCommit,
    testedTree: tree ?? _unitTree,
    workingTreeDirty: dirty,
    trackedDirty: trackedDirty,
    sourceBytesByPath: sources ?? sourceBytes,
    riskSourcePaths: riskPaths,
    portfolioSourcePaths: portfolioPaths,
  );

  Uint8List read(String path) => artifacts[path]!;

  Map<String, dynamic> _corpus(bool isRisk, List<Map<String, dynamic>> cases) =>
      {
        'schema_version': isRisk
            ? 'finex.local_s2.saved_risk_corpus.v1'
            : 'finex.local_s2.portfolio_corpus.v1',
        'scope': 'local_educational_application',
        'contract_version': 'local.v1',
        'provenance': {
          'kind': 'native_tcp_capture',
          'source': 'owned_loopback_uvicorn',
          'command': isRisk
              ? 'python verify_s2_saved_risk.py'
              : 'python verify_s2_manual_portfolio.py',
          'tested_commit': _unitCommit,
          'tested_tree': _unitTree,
        },
        'source_hashes': _sources(isRisk ? riskPaths : portfolioPaths),
        'source_manifest_sha256': _manifest(
          _sources(isRisk ? riskPaths : portfolioPaths),
        ),
        'cases': cases,
      };

  List<Map<String, dynamic>> _sources(Set<String> paths) => [
    for (final path in paths.toList()..sort())
      {'path': path, 'sha256': _hash(sourceBytes[path]!)},
  ];

  Map<String, dynamic> _report(bool isRisk, Map<String, dynamic> corpus) {
    final checks = isRisk ? _riskChecks : _portfolioChecks;
    final starts = isRisk ? 4 : 5;
    return {
      'schema_version': isRisk
          ? 'finex.local_s2.saved_risk.acceptance.v1'
          : 'finex.local_s2.manual_portfolio.acceptance.v1',
      'scope': 'local_educational_application',
      'contract_version': 'local.v1',
      'success': true,
      'mode': 'owned_native_tcp',
      'tested_commit': _unitCommit,
      'tested_tree': _unitTree,
      'working_tree_dirty': false,
      'tracked_dirty': false,
      'source_hashes': _copy({'rows': corpus['source_hashes']})['rows'],
      'source_manifest_sha256': corpus['source_manifest_sha256'],
      'checks': <Map<String, dynamic>>[
        for (final id in checks) <String, dynamic>{'id': id, 'passed': true},
      ],
      'required_checks': checks.toList(),
      'failures': [],
      'responses_checked': isRisk ? 33 : 226,
      'corpus_sha256': _hash(_jsonBytes(corpus)),
      'corpus_case_ids': [
        for (final item in _list(corpus['cases'])) _object(item)['id'],
      ],
      'native_process': {
        'starts': starts,
        'application_restarts': 2,
        'owned_pids': [for (var n = 0; n < starts; n++) 101 + n],
        'child_reaped': true,
        'temporary_directory_removed': true,
        'session_ttl_minutes': 1,
        'real_expiry_elapsed_seconds': isRisk ? null : 60.1,
        'shutdown': 'owned_terminate_and_reap',
      },
      'python_version': '3.12.14',
      'limitations': ['Synthetic loader-unit input only; not native evidence.'],
    };
  }

  void reseal() {
    riskReport['corpus_sha256'] = _hash(_jsonBytes(risk));
    portfolioReport['corpus_sha256'] = _hash(_jsonBytes(portfolio));
    artifacts = {
      environment[_artifactKeys[0]]!: _jsonBytes(risk),
      environment[_artifactKeys[1]]!: _jsonBytes(riskReport),
      environment[_artifactKeys[2]]!: _jsonBytes(portfolio),
      environment[_artifactKeys[3]]!: _jsonBytes(portfolioReport),
    };
  }

  Map<String, dynamic> item(bool isRisk, String id) =>
      _list((isRisk ? risk : portfolio)['cases'])
          .cast<Map<String, dynamic>>()
          .singleWhere((item) => item['id'] == id);

  void changeBody(
    bool isRisk,
    String id,
    void Function(Map<String, dynamic>) change,
  ) {
    final itemValue = item(isRisk, id);
    final body = _object(jsonDecode(itemValue['body_utf8'] as String));
    change(body);
    itemValue['body_utf8'] = jsonEncode(body);
  }
}

String _manifest(List<Map<String, dynamic>> rows) => _hash(
  utf8.encode(
    rows
        .map(
          (row) =>
              '${row['path']} ${(row['sha256'] as String).toUpperCase()}\n',
        )
        .join(),
  ),
);

void _expectRejected(
  _UnitBundle bundle, {
  Map<String, String>? environment,
  LocalS2CorpusRuntime Function()? runtime,
  Uint8List Function(String)? reader,
  String? forbidden,
}) {
  Object? error;
  try {
    loadLocalS2Corpora(
      environment ?? bundle.environment,
      readArtifactBytes: reader ?? bundle.read,
      readRuntime: runtime ?? bundle.runtime,
    );
  } catch (failure) {
    error = failure;
  }
  expect(
    error is FormatException,
    isTrue,
    reason: 'Invalid evidence must fail safely, not skip or fall back.',
  );
  if (forbidden != null) {
    expect(error.toString().contains(forbidden), isFalse);
  }
}

// Deliberately malformed JSON exists only in this synthetic in-memory input.
// The later valid member preserves the old jsonDecode last-member-wins shape,
// so rejection must come from the original-byte boundary, not unrelated DTOs.
String _earlierDuplicate(
  String source,
  String member, {
  required bool escapedName,
  int occurrence = 0,
}) {
  final literalName = jsonEncode(member);
  final needle = '$literalName:';
  var offset = -1;
  for (var index = 0; index <= occurrence; index++) {
    offset = source.indexOf(needle, offset + 1);
    if (offset < 0) {
      throw StateError('Synthetic duplicate-member test setup is invalid.');
    }
  }
  final name = escapedName
      ? '"\\u${member.codeUnitAt(0).toRadixString(16).padLeft(4, '0')}${member.substring(1)}"'
      : literalName;
  final earlier = jsonEncode('Bearer synthetic-duplicate-private-marker');
  return source.replaceRange(offset, offset, '$name:$earlier,');
}

bool _sameLastMemberWinsShape(String left, String right) {
  try {
    return jsonEncode(jsonDecode(left)) == jsonEncode(jsonDecode(right));
  } catch (_) {
    return false;
  }
}

void _setRawArtifact(
  _UnitBundle bundle,
  int artifactIndex,
  String originalJson,
) {
  final bytes = Uint8List.fromList(utf8.encode(originalJson));
  final path = bundle.environment[_artifactKeys[artifactIndex]]!;
  bundle.artifacts[path] = bytes;
  if (artifactIndex == 0 || artifactIndex == 2) {
    final report = artifactIndex == 0
        ? bundle.riskReport
        : bundle.portfolioReport;
    report['corpus_sha256'] = _hash(bytes);
    bundle.artifacts[bundle.environment[_artifactKeys[artifactIndex + 1]]!] =
        _jsonBytes(report);
  }
}

void main() {
  // Pure spies exercise the actual process boundary. They never invoke Git.
  test('S2 metadata Git disables lazy fetch before every read command', () {
    var calls = 0;
    for (final command in [
      ['rev-parse', '--show-toplevel'],
      ['rev-parse', 'HEAD', 'HEAD^{tree}'],
      ['status', '--porcelain', '--untracked-files=all'],
    ]) {
      final value = readLocalS2CorpusGit(
        'synthetic-owned-directory',
        command,
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
                  ...command,
                ]).matches(arguments, <Object?, Object?>{}),
                isTrue,
                reason: 'Global no-network controls must precede the command.',
              );
              expect(workingDirectory == 'synthetic-owned-directory', isTrue);
              expect(runInShell, isFalse);
              return ProcessResult(0, 0, 'synthetic metadata\n', '');
            },
      );
      expect(value == 'synthetic metadata', isTrue);
    }
    expect(calls, 3);
  });
  test('S2 metadata Git scrubs mixed-case overrides but preserves PATH', () {
    readLocalS2CorpusGit(
      'synthetic-owned-directory',
      ['rev-parse', 'HEAD'],
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
            return ProcessResult(0, 0, 'synthetic metadata', '');
          },
    );
  });
  test(
    'S2 metadata Git unsupported flag fails without diagnostic reflection',
    () {
      Object? failure;
      try {
        readLocalS2CorpusGit(
          'synthetic-owned-directory',
          ['rev-parse', 'HEAD'],
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
  test(
    'optional absence performs no artifact/runtime read and no fallback',
    () {
      var touched = false;
      final result = loadLocalS2Corpora(
        const {},
        readArtifactBytes: (_) {
          touched = true;
          return Uint8List(0);
        },
        readRuntime: () {
          touched = true;
          return _UnitBundle().runtime();
        },
      );
      expect(result, isNull);
      expect(touched, isFalse);
    },
  );

  test('synthetic loader-unit pair validates bindings without becoming native proof', () {
    final bundle = _UnitBundle();
    final pair = loadLocalS2Corpora(
      bundle.environment,
      readArtifactBytes: bundle.read,
      readRuntime: bundle.runtime,
    );
    expect(pair != null, isTrue);
    expect(
      pair!.risk.cases.map((item) => item.id).toList(),
      _riskSpecs.map((item) => item.$1).toList(),
    );
    expect(
      pair.portfolio.cases.map((item) => item.id).toList(),
      _portfolioSpecs.map((item) => item.$1).toList(),
    );
    expect(
      pair.risk.originalBytes,
      bundle.artifacts[bundle.environment[_artifactKeys[0]]],
    );
  });

  for (final id in ['portfolio_updated', 'portfolio_unchanged']) {
    test('portfolio trim boundary loader accepts original padded $id', () {
      final bundle = _UnitBundle();
      // All of these bytes are synthetic unit inputs. The authoritative
      // updated/no-op response records agree before a raw request is padded.
      for (final recordId in ['portfolio_updated', 'portfolio_unchanged']) {
        _object(bundle.item(false, recordId)['request'])['description'] =
            'Synthetic note';
        bundle.changeBody(false, recordId, (body) {
          _object(body['data'])['description'] = 'Synthetic note';
        });
      }
      final item = bundle.item(false, id);
      final request = _object(item['request']);
      request['name'] = ' \t${request['name']}\n ';
      request['description'] = ' \t${request['description']}\n ';
      final originalRequest = _jsonBytes(request);
      final originalResponse = item['body_utf8'];
      bundle.reseal();
      final originalCorpus =
          bundle.artifacts[bundle.environment[_artifactKeys[2]]]!;
      final pair = loadLocalS2Corpora(
        bundle.environment,
        readArtifactBytes: bundle.read,
        readRuntime: bundle.runtime,
      );
      expect(pair != null, isTrue);
      final loaded = pair!.portfolio.caseById(id);
      // The boundary must not repair the capture or relabel this as native.
      expect(
        _hash(_jsonBytes(loaded.request!)) == _hash(originalRequest),
        isTrue,
      );
      expect(loaded.bodyUtf8 == originalResponse, isTrue);
      expect(
        _hash(pair.portfolio.originalBytes) == _hash(originalCorpus),
        isTrue,
      );
    });
  }

  final trimBoundaryMutations = <String, void Function(Map<String, dynamic>)>{
    'interior name alteration': (value) =>
        value['name'] = (value['name'] as String).replaceFirst(' ', '  '),
    'different name': (value) => value['name'] = 'Different synthetic name',
    'different description': (value) => value['description'] = 'Different note',
    'null to empty description': (value) => value['description'] = '',
    'wrong name type': (value) => value['name'] = 1,
    'wrong description type': (value) => value['description'] = false,
    'blank name': (value) => value['name'] = ' \t\n ',
    'normalized name bound': (value) =>
        value['name'] = ' ${List.filled(101, 'n').join()} ',
    'normalized description bound': (value) =>
        value['description'] = ' ${List.filled(501, 'd').join()} ',
    'wrong version': (value) => value['portfolio_version'] = 'portfolio.v0',
    'wrong currency': (value) => value['currency'] = 'EUR',
    'extra field': (value) => value['unexpected'] = true,
    'private field': (value) =>
        value['secret'] = 'synthetic-private-trim-marker',
  };
  for (final entry in trimBoundaryMutations.entries) {
    test('portfolio trim boundary loader rejects ${entry.key}', () {
      final bundle = _UnitBundle();
      entry.value(_object(bundle.item(false, 'portfolio_updated')['request']));
      bundle.reseal();
      _expectRejected(bundle, forbidden: 'synthetic-private-trim-marker');
    });
  }
  test(
    'portfolio trim boundary loader keeps empty distinct from null description',
    () {
      final bundle = _UnitBundle();
      for (final id in ['portfolio_updated', 'portfolio_unchanged']) {
        _object(bundle.item(false, id)['request'])['description'] = '';
        bundle.changeBody(false, id, (body) {
          _object(body['data'])['description'] = '';
        });
      }
      _object(
        bundle.item(false, 'portfolio_updated')['request'],
      )['description'] = null;
      bundle.reseal();
      _expectRejected(bundle);
    },
  );
  test('portfolio trim boundary loader never trims a holding number', () {
    final bundle = _UnitBundle();
    _object(bundle.item(false, 'holding_created')['request'])['quantity'] =
        ' 10.000000 ';
    bundle.reseal();
    _expectRejected(bundle);
  });
  test('portfolio trim boundary loader never trims a risk version', () {
    final bundle = _UnitBundle();
    _object(
      bundle.item(true, 'draft_partial_saved')['request'],
    )['questionnaire_version'] = ' v1 ';
    bundle.reseal();
    _expectRejected(bundle);
  });

  for (
    var artifactIndex = 0;
    artifactIndex < _artifactKeys.length;
    artifactIndex++
  ) {
    final isCorpus = artifactIndex.isEven;
    for (final nested in [false, true]) {
      for (final escapedName in [false, true]) {
        test(
          'original artifact rejects ${nested ? 'nested' : 'root'} ${escapedName ? 'escaped-equivalent' : 'plain'} duplicate member: $artifactIndex',
          () {
            final bundle = _UnitBundle();
            final path = bundle.environment[_artifactKeys[artifactIndex]]!;
            final original = utf8.decode(bundle.artifacts[path]!);
            final member = nested
                ? (isCorpus ? 'source' : 'shutdown')
                : (isCorpus ? 'scope' : 'success');
            final duplicate = _earlierDuplicate(
              original,
              member,
              escapedName: escapedName,
            );
            // Only safe booleans are asserted; neither original bytes nor the
            // overwritten private marker become matcher diagnostics.
            expect(_sameLastMemberWinsShape(duplicate, original), isTrue);
            _setRawArtifact(bundle, artifactIndex, duplicate);
            _expectRejected(
              bundle,
              forbidden: 'synthetic-duplicate-private-marker',
            );
          },
        );
      }
    }
  }

  for (final isRisk in [true, false]) {
    for (final variant in ['success root', 'error root', 'error nested']) {
      for (final escapedName in [false, true]) {
        test(
          'original body bytes reject ${isRisk ? 'risk' : 'portfolio'} $variant ${escapedName ? 'escaped-equivalent' : 'plain'} duplicate message',
          () {
            final bundle = _UnitBundle();
            final id = variant == 'success root'
                ? (isRisk ? 'questionnaire' : 'portfolio_detail')
                : 'session_invalid';
            final item = bundle.item(isRisk, id);
            final original = item['body_utf8'] as String;
            final duplicate = _earlierDuplicate(
              original,
              'message',
              escapedName: escapedName,
              occurrence: variant == 'error nested' ? 1 : 0,
            );
            expect(_sameLastMemberWinsShape(duplicate, original), isTrue);
            item['body_utf8'] = duplicate;
            bundle.reseal();
            _expectRejected(
              bundle,
              forbidden: 'synthetic-duplicate-private-marker',
            );
          },
        );
      }
    }
    test(
      'distinct nested message members, escaped quotes and Unicode remain valid: ${isRisk ? 'risk' : 'portfolio'}',
      () {
        final bundle = _UnitBundle();
        const message = 'Quoted "text", café, 雪 and 🧪; {"message":"text"}.';
        bundle.changeBody(isRisk, 'session_invalid', (body) {
          body['message'] = message;
          body['detail'] = message;
          _object(body['error'])['message'] = message;
        });
        final item = bundle.item(isRisk, 'session_invalid');
        item['body_utf8'] = (item['body_utf8'] as String).replaceFirst(
          '"message":',
          r'"\u006dessage":',
        );
        bundle.reseal();
        final pair = loadLocalS2Corpora(
          bundle.environment,
          readArtifactBytes: bundle.read,
          readRuntime: bundle.runtime,
        );
        expect(pair != null, isTrue);
      },
    );
  }

  for (
    var artifactIndex = 0;
    artifactIndex < _artifactKeys.length;
    artifactIndex++
  ) {
    test('one escaped member in original artifact remains valid: $artifactIndex', () {
      final bundle = _UnitBundle();
      final path = bundle.environment[_artifactKeys[artifactIndex]]!;
      final member = artifactIndex.isEven ? 'scope' : 'success';
      final encoded =
          '"\\u${member.codeUnitAt(0).toRadixString(16).padLeft(4, '0')}${member.substring(1)}":';
      final original = utf8.decode(bundle.artifacts[path]!);
      _setRawArtifact(
        bundle,
        artifactIndex,
        original.replaceFirst('${jsonEncode(member)}:', encoded),
      );
      final pair = loadLocalS2Corpora(
        bundle.environment,
        readArtifactBytes: bundle.read,
        readRuntime: bundle.runtime,
      );
      expect(pair != null, isTrue);
    });
  }

  for (final flag in ['yes', '', 'true', '2']) {
    test('unknown required flag is not treated as optional: $flag', () {
      final bundle = _UnitBundle();
      _expectRejected(
        bundle,
        environment: {
          ...bundle.environment,
          'FINEX_REQUIRE_LOCAL_S2_CORPUS': flag,
        },
      );
    });
  }
  for (final key in _artifactKeys) {
    for (final empty in [false, true]) {
      test(
        'required complete four-path gate rejects ${empty ? 'empty' : 'missing'} $key',
        () {
          final bundle = _UnitBundle();
          final environment = {...bundle.environment};
          if (empty) {
            environment[key] = '  ';
          } else {
            environment.remove(key);
          }
          _expectRejected(bundle, environment: environment);
        },
      );
    }
  }
  test('required absence cannot silently skip', () {
    _expectRejected(
      _UnitBundle(),
      environment: {'FINEX_REQUIRE_LOCAL_S2_CORPUS': '1'},
    );
  });
  test(
    'partial supplied evidence fails even when the required flag is zero',
    () {
      final bundle = _UnitBundle();
      _expectRejected(
        bundle,
        environment: {
          'FINEX_REQUIRE_LOCAL_S2_CORPUS': '0',
          _artifactKeys.first: bundle.environment[_artifactKeys.first]!,
        },
      );
    },
  );
  test(
    'optional complete supplied evidence receives the same strict checks',
    () {
      final bundle = _UnitBundle();
      bundle.riskReport['success'] = false;
      bundle.reseal();
      _expectRejected(
        bundle,
        environment: {
          ...bundle.environment,
          'FINEX_REQUIRE_LOCAL_S2_CORPUS': '0',
        },
      );
    },
  );

  for (final kind in [
    'file failure',
    'malformed UTF8',
    'malformed JSON',
    'oversized corpus',
  ]) {
    test('artifact failures are sanitized: $kind', () {
      final bundle = _UnitBundle();
      const marker = 'synthetic-private-diagnostic-marker';
      _expectRejected(
        bundle,
        reader: (path) {
          if (path != bundle.environment[_artifactKeys.first]) {
            return bundle.read(path);
          }
          return switch (kind) {
            'file failure' => throw StateError(marker),
            'malformed UTF8' => Uint8List.fromList([0xc3, 0x28]),
            'malformed JSON' => Uint8List.fromList(
              utf8.encode('{"token":"$marker"'),
            ),
            _ => Uint8List(2097153),
          };
        },
        forbidden: marker,
      );
    });
  }
  test('runtime metadata failure is sanitized', () {
    _expectRejected(
      _UnitBundle(),
      runtime: () => throw StateError('synthetic-private-runtime'),
      forbidden: 'synthetic-private-runtime',
    );
  });

  for (final isRisk in [true, false]) {
    final name = isRisk ? 'risk' : 'portfolio';
    for (final (field, value) in <(String, Object?)>[
      ('schema_version', 'obsolete'),
      ('scope', 'local_educational_pilot'),
      ('contract_version', 'local.v0'),
    ]) {
      test('$name corpus requires exact $field', () {
        final bundle = _UnitBundle();
        (isRisk ? bundle.risk : bundle.portfolio)[field] = value;
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    for (final field in ['source_hashes', 'cases', 'provenance']) {
      test('$name corpus rejects absent $field', () {
        final bundle = _UnitBundle();
        (isRisk ? bundle.risk : bundle.portfolio).remove(field);
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    test('$name corpus rejects extra root keys', () {
      final bundle = _UnitBundle();
      (isRisk ? bundle.risk : bundle.portfolio)['unexpected'] = true;
      bundle.reseal();
      _expectRejected(bundle);
    });
    for (final (field, value) in <(String, Object?)>[
      ('kind', 'synthetic_fixture'),
      ('source', 'handcrafted'),
      ('command', 'python different_driver.py'),
      ('tested_commit', List.filled(40, 'c').join()),
      ('tested_tree', List.filled(40, 'd').join()),
    ]) {
      test('$name native provenance rejects wrong $field', () {
        final bundle = _UnitBundle();
        _object(
          (isRisk ? bundle.risk : bundle.portfolio)['provenance'],
        )[field] = value;
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    for (final (field, value) in <(String, Object?)>[
      ('success', false),
      ('mode', 'mock'),
      ('working_tree_dirty', true),
      ('tracked_dirty', true),
      ('tested_commit', List.filled(40, 'e').join()),
      ('tested_tree', List.filled(40, 'f').join()),
      ('responses_checked', 0),
      (
        'failures',
        [
          {'code': 'NATIVE_FAILED'},
        ],
      ),
      ('schema_version', 'obsolete'),
    ]) {
      test('$name report rejects invalid $field', () {
        final bundle = _UnitBundle();
        (isRisk ? bundle.riskReport : bundle.portfolioReport)[field] = value;
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    test('$name report rejects extra or missing native-process keys', () {
      for (final extra in [false, true]) {
        final bundle = _UnitBundle();
        final process = _object(
          (isRisk
              ? bundle.riskReport
              : bundle.portfolioReport)['native_process'],
        );
        if (extra) {
          process['unreviewed'] = true;
        } else {
          process.remove('child_reaped');
        }
        bundle.reseal();
        _expectRejected(bundle);
      }
    });
    for (final (field, value) in <(String, Object?)>[
      ('starts', 0),
      ('application_restarts', 1),
      ('child_reaped', false),
      ('temporary_directory_removed', false),
      ('session_ttl_minutes', 2),
      ('shutdown', 'unknown'),
      ('owned_pids', [101, 101]),
      ('real_expiry_elapsed_seconds', isRisk ? 60.0 : 58.9),
    ]) {
      test('$name lifecycle rejects invalid $field', () {
        final bundle = _UnitBundle();
        _object(
          (isRisk
              ? bundle.riskReport
              : bundle.portfolioReport)['native_process'],
        )[field] = value;
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    for (final corruption in [
      'missing',
      'duplicate',
      'reordered',
      'failed',
      'required mismatch',
    ]) {
      test('$name report rejects $corruption required check', () {
        final bundle = _UnitBundle();
        final report = isRisk ? bundle.riskReport : bundle.portfolioReport;
        final checks = _list(report['checks']);
        switch (corruption) {
          case 'missing':
            checks.removeLast();
            break;
          case 'duplicate':
            checks[checks.length - 1] = _copy(_object(checks.first));
            break;
          case 'reordered':
            final first = checks.removeAt(0);
            checks.add(first);
            break;
          case 'failed':
            _object(checks.first)['passed'] = false;
            break;
          default:
            _list(report['required_checks']).removeLast();
        }
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
    for (final corruption in [
      'missing',
      'duplicate',
      'reordered',
      'operation',
      'status',
      'expected code',
      'extra key',
    ]) {
      test('$name case map rejects $corruption coverage', () {
        final bundle = _UnitBundle();
        final cases = _list((isRisk ? bundle.risk : bundle.portfolio)['cases']);
        switch (corruption) {
          case 'missing':
            cases.removeLast();
            break;
          case 'duplicate':
            cases[cases.length - 1] = _copy(_object(cases.first));
            break;
          case 'reordered':
            final first = cases.removeAt(0);
            cases.add(first);
            break;
          case 'operation':
            _object(cases.first)['operation'] = 'logout';
            break;
          case 'status':
            _object(cases.last)['status'] = 503;
            break;
          case 'expected code':
            _object(_object(cases.last)['expected'])['error_code'] =
                'SESSION_INVALID';
            break;
          default:
            _object(cases.first)['unreviewed'] = true;
        }
        bundle.reseal();
        _expectRejected(bundle);
      });
    }
  }

  for (final dirty in [true, false]) {
    test(
      'current runtime must be clean: ${dirty ? 'working tree' : 'tracked'}',
      () {
        final bundle = _UnitBundle();
        _expectRejected(
          bundle,
          runtime: () => bundle.runtime(dirty: dirty, trackedDirty: !dirty),
        );
      },
    );
  }
  for (final field in ['commit', 'tree']) {
    test('current runtime rejects mismatched $field', () {
      final bundle = _UnitBundle();
      _expectRejected(
        bundle,
        runtime: () => bundle.runtime(
          commit: field == 'commit' ? List.filled(40, 'c').join() : null,
          tree: field == 'tree' ? List.filled(40, 'd').join() : null,
        ),
      );
    });
  }
  test('actual source bytes are hashed without EOL normalization', () {
    final bundle = _UnitBundle();
    final changed = {...bundle.sourceBytes};
    changed['backend/app/main.py'] = Uint8List.fromList(
      utf8.encode('synthetic main source\n'),
    );
    _expectRejected(bundle, runtime: () => bundle.runtime(sources: changed));
  });
  for (final corruption in [
    'digest',
    'manifest',
    'report list',
    'duplicate path',
    'path traversal',
    'missing neutral source',
    'uppercase digest',
  ]) {
    test('source binding rejects $corruption', () {
      final bundle = _UnitBundle();
      final rows = _list(bundle.risk['source_hashes']);
      switch (corruption) {
        case 'digest':
          _object(rows.first)['sha256'] = List.filled(64, '0').join();
          break;
        case 'manifest':
          bundle.risk['source_manifest_sha256'] = List.filled(64, '0').join();
          break;
        case 'report list':
          _list(bundle.riskReport['source_hashes']).removeLast();
          break;
        case 'duplicate path':
          rows[1] = _copy(_object(rows.first));
          break;
        case 'path traversal':
          _object(rows.first)['path'] = '../private-data.json';
          break;
        case 'missing neutral source':
          rows.removeWhere(
            (row) => _object(row)['path'] == 'backend/local_s2_evidence.py',
          );
          break;
        default:
          _object(rows.first)['sha256'] =
              (_object(rows.first)['sha256'] as String).toUpperCase();
      }
      bundle.reseal();
      _expectRejected(bundle);
    });
  }
  test('exact raw corpus digest rejects a whitespace-only file rewrite', () {
    final bundle = _UnitBundle();
    final key = bundle.environment[_artifactKeys.first]!;
    bundle.artifacts[key] = Uint8List.fromList([
      ...bundle.artifacts[key]!,
      0x20,
    ]);
    _expectRejected(bundle);
  });
  test('source_hashes repository paths are legitimate provenance fields', () {
    final bundle = _UnitBundle();
    final pair = loadLocalS2Corpora(
      bundle.environment,
      readArtifactBytes: bundle.read,
      readRuntime: bundle.runtime,
    );
    expect(pair != null, isTrue);
  });

  for (final key in [
    'access_token',
    'Authorization',
    'cookie',
    'owner_id',
    'user_id',
    'session_id',
    'db_path',
    'path',
    'headers',
  ]) {
    for (final request in [true, false]) {
      test(
        'recursive ${request ? 'request' : 'response'} privacy rejects $key',
        () {
          final bundle = _UnitBundle();
          if (request) {
            _object(
              bundle.item(true, 'draft_partial_saved')['request'],
            )['nested'] = {
              key: 'synthetic-private-marker',
            };
          } else {
            bundle.changeBody(false, 'portfolio_detail', (body) {
              _object(body['data'])['nested'] = {
                key: 'synthetic-private-marker',
              };
            });
          }
          bundle.reseal();
          _expectRejected(bundle, forbidden: 'synthetic-private-marker');
        },
      );
    }
  }
  test(
    'body byte cap rejects a multibyte oversized response before decoding',
    () {
      final bundle = _UnitBundle();
      bundle.item(true, 'questionnaire')['body_utf8'] = List.filled(
        131073,
        'é',
      ).join();
      bundle.reseal();
      _expectRejected(bundle);
    },
  );
  for (final badDetail in [null, 7, 'different safe detail']) {
    test('legacy error detail must equal both text messages: $badDetail', () {
      final bundle = _UnitBundle();
      bundle.changeBody(false, 'portfolio_not_found', (body) {
        body['detail'] = badDetail;
      });
      bundle.reseal();
      _expectRejected(bundle);
    });
  }

  for (final badTarget in [
    {'limit': 1, 'before': null},
    {'limit': 2, 'before': 2},
    {'limit': 2, 'before': '02'},
    {'limit': 2, 'before': '9223372036854775808'},
    {'limit': 2, 'before': null, 'owner_id': 'synthetic'},
  ]) {
    test(
      'risk history target is exact and bounded: variant ${badTarget.length}:${badTarget['before']}',
      () {
        final bundle = _UnitBundle();
        bundle.item(true, 'history_page_next')['target'] = badTarget;
        bundle.reseal();
        _expectRejected(bundle);
      },
    );
  }
  test('risk next-page target must equal the frozen first-page cursor', () {
    final bundle = _UnitBundle();
    _object(bundle.item(true, 'history_page_next')['target'])['before'] = '3';
    bundle.reseal();
    _expectRejected(bundle);
  });
  test(
    'risk detail target cannot be changed independently of original data',
    () {
      final bundle = _UnitBundle();
      _object(
        bundle.item(true, 'assessment_detail')['target'],
      )['assessment_id'] = '00000000-0000-4000-8000-000000000199';
      bundle.reseal();
      _expectRejected(bundle);
    },
  );
  test('frozen portfolio v1 rejects an invented target field', () {
    final bundle = _UnitBundle();
    bundle.item(false, 'portfolio_detail')['target'] = {
      'portfolio_id': portfolioA,
    };
    bundle.reseal();
    _expectRejected(bundle);
  });
  for (final id in [
    'questionnaire',
    'history_initial',
    'unsupported_version',
    'validation_error',
  ]) {
    test('risk GET/error capture keeps request null: $id', () {
      final bundle = _UnitBundle();
      bundle.item(true, id)['request'] = riskInput();
      bundle.reseal();
      _expectRejected(bundle);
    });
  }
  for (final id in ['catalogue', 'portfolio_not_found', 'validation_error']) {
    test('portfolio GET/error capture keeps request null: $id', () {
      final bundle = _UnitBundle();
      bundle.item(false, id)['request'] = {'currency': 'USD'};
      bundle.reseal();
      _expectRejected(bundle);
    });
  }
  test('successful mutations require the exact original safe DTO', () {
    final bundle = _UnitBundle();
    _object(bundle.item(false, 'holding_created')['request'])['quantity'] = 10;
    bundle.reseal();
    _expectRejected(bundle);
  });
  test('equivalent retry must retain original UUID/time/input order', () {
    final bundle = _UnitBundle();
    bundle.changeBody(true, 'assessment_equivalent_replay', (body) {
      _object(_object(body['data'])['input'])['answers'] = _list(
        _object(_object(body['data'])['input'])['answers'],
      ).reversed.toList();
    });
    bundle.reseal();
    _expectRejected(bundle);
  });
  test('cleared draft remains empty across the native restart', () {
    final bundle = _UnitBundle();
    bundle.changeBody(true, 'draft_after_restart', (body) {
      _object(body['data'])['answers'] = _list(
        riskInput(partial: true)['answers'],
      );
    });
    bundle.reseal();
    _expectRejected(bundle);
  });
  test('insert between pages cannot replace or duplicate the original next-page record', () {
    final bundle = _UnitBundle();
    bundle.changeBody(true, 'history_page_next', (body) {
      _object(_list(_object(body['data'])['items']).single)['assessment_id'] =
          '00000000-0000-4000-8000-000000000196';
    });
    bundle.reseal();
    _expectRejected(bundle);
  });
}
