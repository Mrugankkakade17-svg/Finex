// Test-only native artifact boundary, never application authentication.
import 'dart:typed_data';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';

class LocalS3CorpusRuntime {
  final String commit;
  final String tree;
  final bool dirty;
  final bool trackedDirty;
  final Map<String, Uint8List> sourceBytes;
  const LocalS3CorpusRuntime(
    this.commit,
    this.tree,
    this.dirty,
    this.trackedDirty,
    this.sourceBytes,
  );
}

class LocalS3Corpus {
  final Map<String, dynamic> document;
  final Map<String, dynamic> report;
  final Uint8List originalBytes;
  final List<Map<String, dynamic>> cases;
  const LocalS3Corpus(
    this.document,
    this.report,
    this.originalBytes,
    this.cases,
  );
}

LocalS3Corpus? loadLocalS3Corpus(
  Map<String, String> environment, {
  Uint8List Function(String)? readArtifact,
  LocalS3CorpusRuntime Function()? readRuntime,
}) {
  try {
    final flag = environment['FINEX_REQUIRE_LOCAL_S3_CORPUS'];
    _require(flag == null || flag == '0' || flag == '1');
    final corpusPath = environment['FINEX_LOCAL_S3_CORPUS'];
    final reportPath = environment['FINEX_LOCAL_S3_REPORT'];
    if (corpusPath == null && reportPath == null) {
      _require(flag != '1');
      return null;
    }
    _require(
      corpusPath != null &&
          corpusPath.trim().isNotEmpty &&
          reportPath != null &&
          reportPath.trim().isNotEmpty &&
          corpusPath != reportPath,
    );
    final reader = readArtifact ?? _readArtifact;
    final original = reader(corpusPath!);
    final reportBytes = reader(reportPath!);
    final corpus = _parse(original);
    final report = _parse(reportBytes);
    final runtimeReader = readRuntime ?? _runtime;
    final runtime = runtimeReader();
    _require(
      RegExp(r'^[0-9a-f]{40}$').hasMatch(runtime.commit) &&
          RegExp(r'^[0-9a-f]{40}$').hasMatch(runtime.tree) &&
          !runtime.dirty &&
          !runtime.trackedDirty,
    );
    _object(corpus, {
      'schema_version',
      ..._scopeKeys,
      'provenance',
      'source_hashes',
      'source_manifest_sha256',
      'cases',
    });
    _scope(corpus);
    _require(corpus['schema_version'] == 'finex.local_s3.foundation_corpus.v1');
    final provenance = _object(corpus['provenance'], {
      'kind',
      'source',
      'command',
      'tested_commit',
      'tested_tree',
    });
    _require(
      provenance['kind'] == 'native_tcp_capture' &&
          provenance['source'] == 'owned_loopback_uvicorn' &&
          provenance['command'] == 'python verify_s3_foundation.py' &&
          provenance['tested_commit'] == runtime.commit &&
          provenance['tested_tree'] == runtime.tree,
    );
    _object(report, {
      'schema_version',
      ..._scopeKeys,
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
    });
    _scope(report);
    _require(
      report['schema_version'] == 'finex.local_s3.foundation.acceptance.v1' &&
          report['success'] == true &&
          report['mode'] == 'owned_native_tcp' &&
          report['tested_commit'] == runtime.commit &&
          report['tested_tree'] == runtime.tree &&
          report['working_tree_dirty'] == false &&
          report['tracked_dirty'] == false &&
          _same(report['failures'], []) &&
          _same(report['required_checks'], localS3RequiredChecks) &&
          _same(
            report['corpus_case_ids'],
            localS3CaseSpecs.map((s) => s.$1).toList(),
          ) &&
          report['responses_checked'] is int &&
          (report['responses_checked'] as int) >= 48 &&
          (report['responses_checked'] as int) <= 100000 &&
          report['corpus_sha256'] == _hash(original),
    );
    final checks = _array(report['checks'], 21);
    _require(checks.length == 21);
    for (var i = 0; i < checks.length; i++) {
      final check = _object(checks[i], {'id', 'passed'});
      _require(
        check['id'] == localS3RequiredChecks[i] && check['passed'] == true,
      );
    }
    final process = _object(report['native_process'], {
      'starts',
      'application_restarts',
      'durable_restarts',
      'storage_fault_restarts',
      'owned_pids',
      'child_reaped',
      'temporary_directory_removed',
      'session_ttl_minutes',
      'real_expiry_elapsed_seconds',
      'shutdown',
    });
    for (final entry in {
      'starts': 6,
      'application_restarts': 4,
      'durable_restarts': 2,
      'storage_fault_restarts': 2,
      'session_ttl_minutes': 1,
    }.entries) {
      _require(process[entry.key] is int && process[entry.key] == entry.value);
    }
    final pids = _array(process['owned_pids'], 6);
    _require(
      pids.length == 6 &&
          pids.toSet().length == 6 &&
          pids.every((p) => p is int && p > 0 && p <= 2147483647),
    );
    final elapsed = process['real_expiry_elapsed_seconds'];
    _require(
      elapsed is num &&
          elapsed.isFinite &&
          elapsed >= 59 &&
          elapsed <= 75 &&
          process['child_reaped'] == true &&
          process['temporary_directory_removed'] == true &&
          process['shutdown'] == 'owned_terminate_and_reap',
    );
    _require(
      report['python_version'] is String &&
          RegExp(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')
              .hasMatch(report['python_version'] as String),
    );
    final limitations = _array(report['limitations'], 16);
    _require(limitations.isNotEmpty);
    for (final value in limitations) {
      _require(value is String && value.isNotEmpty && value.length <= 4096);
      _privateFree(value);
    }
    _sources(corpus, runtime);
    _sources(report, runtime);
    _require(
      _same(report['source_hashes'], corpus['source_hashes']) &&
          report['source_manifest_sha256'] == corpus['source_manifest_sha256'],
    );
    final entries = _array(corpus['cases'], 48);
    _require(entries.length == 48);
    final values = <String, Map<String, dynamic>>{};
    final frozen = <Map<String, dynamic>>[];
    for (var i = 0; i < entries.length; i++) {
      final entry = _object(entries[i], {
        'id',
        'operation',
        'target',
        'request',
        'status',
        'content_type',
        'body_utf8',
        'expected',
      });
      final spec = localS3CaseSpecs[i];
      _require(
        entry['id'] == spec.$1 &&
            entry['operation'] == spec.$2 &&
            entry['status'] is int &&
            entry['status'] == spec.$3 &&
            entry['content_type'] == 'application/json',
      );
      final expected = _object(entry['expected'], {
        'outcome',
        if (spec.$4 != null) 'error_code',
      });
      _require(
        expected['outcome'] == (spec.$4 == null ? 'success' : 'error') &&
            expected['error_code'] == spec.$4,
      );
      final target = _target(spec.$2, entry['target']);
      _privateFree(target);
      _privateFree(entry['request']);
      final bodyText = entry['body_utf8'];
      _require(bodyText is String);
      final bodyBytes = Uint8List.fromList(utf8.encode(bodyText as String));
      _require(bodyBytes.isNotEmpty && bodyBytes.length <= 262144);
      final body = _parse(bodyBytes);
      _privateFree(body);
      values[spec.$1] = _body(body, spec.$2, spec.$4, target, entry['request']);
      frozen.add(_freeze(entry) as Map<String, dynamic>);
    }
    _relationships(values, entries.cast<Map<String, dynamic>>());
    // Re-read both originals and current revision/source bytes to reject drift.
    _require(
      _same(reader(corpusPath), original) &&
          _same(reader(reportPath), reportBytes),
    );
    final again = runtimeReader();
    _require(
      again.commit == runtime.commit &&
          again.tree == runtime.tree &&
          !again.dirty &&
          !again.trackedDirty &&
          _same(again.sourceBytes, runtime.sourceBytes),
    );
    return LocalS3Corpus(
      _freeze(corpus) as Map<String, dynamic>,
      _freeze(report) as Map<String, dynamic>,
      Uint8List.fromList(original).asUnmodifiableView(),
      List.unmodifiable(frozen),
    );
  } catch (_) {
    throw const FormatException(
      'Current native local S3 evidence is missing or invalid.',
    );
  }
}

const _scopeKeys = {'scope', 'contract_version', 'foundation_version'};
void _require(bool value) {
  if (!value) throw const FormatException('Invalid bounded S3 evidence.');
}

Map<String, dynamic> _object(Object? value, Set<String> keys) {
  _require(value is Map<String, dynamic>);
  final result = value as Map<String, dynamic>;
  _require(result.length == keys.length && keys.every(result.containsKey));
  return result;
}

List<dynamic> _array(Object? value, int maximum) {
  _require(value is List && value.length <= maximum);
  return value as List;
}

void _scope(Map<String, dynamic> value) {
  _require(
    value['scope'] == localApplicationScope &&
        value['contract_version'] == localContractVersion &&
        value['foundation_version'] == localFoundationVersion,
  );
}

String _hash(List<int> bytes) => sha256.convert(bytes).toString();
bool _same(Object? a, Object? b) {
  if (a is Map && b is Map) {
    return a.length == b.length &&
        a.keys.every((k) => b.containsKey(k) && _same(a[k], b[k]));
  }
  if (a is List && b is List) {
    return a.length == b.length &&
        List.generate(a.length, (i) => _same(a[i], b[i])).every((v) => v);
  }
  return a == b;
}

Object? _freeze(Object? value) {
  if (value is Map<String, dynamic>) {
    return Map<String, dynamic>.unmodifiable(
      value.map((k, v) => MapEntry(k, _freeze(v))),
    );
  }
  if (value is List) return List<dynamic>.unmodifiable(value.map(_freeze));
  return value;
}

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
void _privateFree(Object? value, [int depth = 0]) {
  _require(depth <= 32);
  if (value is Map) {
    for (final e in value.entries) {
      _require(
        e.key is String &&
            !_privateKeys.contains(
              (e.key as String).toLowerCase().replaceAll(
                RegExp(r'[^a-z0-9]'),
                '',
              ),
            ),
      );
      _privateFree(e.value, depth + 1);
    }
  } else if (value is List) {
    for (final v in value) {
      _privateFree(v, depth + 1);
    }
  } else if (value is String) {
    _require(
      !RegExp(
            r'Bearer\s|github_pat_|(?:[A-Za-z]:[\\/]|file://|/(?:Users|home|tmp|var)/)',
            caseSensitive: false,
          ).hasMatch(value) &&
          !RegExp(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
              .hasMatch(value),
    );
  } else if (value is num) {
    _require(value.isFinite);
  }
}

Map<String, dynamic> _parse(Uint8List raw) {
  _require(raw.isNotEmpty && raw.length <= 2097152);
  final text = utf8.decode(raw, allowMalformed: false);
  _JsonMemberGuard(text).validate();
  final result = jsonDecode(text);
  _require(result is Map<String, dynamic>);
  return result as Map<String, dynamic>;
}

Uint8List _readArtifact(String path) {
  final file = File(path);
  _require(
    FileSystemEntity.typeSync(path, followLinks: false) ==
        FileSystemEntityType.file,
  );
  final before = file.statSync();
  _require(before.size > 0 && before.size <= 2097152);
  final bytes = file.readAsBytesSync();
  final after = file.statSync();
  _require(
    bytes.length == before.size &&
        after.size == before.size &&
        after.modified == before.modified,
  );
  return bytes;
}

void _sources(Map<String, dynamic> document, LocalS3CorpusRuntime runtime) {
  final supplied = _array(document['source_hashes'], 256);
  final rows = <Map<String, dynamic>>[];
  final expected = runtime.sourceBytes.keys.toList()..sort();
  _require(expected.isNotEmpty);
  _require(localS3SourcePaths.every(expected.contains));
  for (var i = 0; i < supplied.length; i++) {
    final row = _object(supplied[i], {'path', 'sha256'});
    final name = row['path'];
    final digest = row['sha256'];
    _require(
      name is String &&
          name.length <= 256 &&
          (localS3SourcePaths.contains(name) ||
              RegExp(r'^backend/app/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py$')
                  .hasMatch(name)) &&
          digest is String &&
          RegExp(r'^[0-9a-f]{64}$').hasMatch(digest) &&
          runtime.sourceBytes.containsKey(name),
    );
    _require(
      i < expected.length &&
          name == expected[i] &&
          _hash(runtime.sourceBytes[name]!) == digest,
    );
    rows.add(row);
  }
  _require(
    rows.length == expected.length &&
        document['source_manifest_sha256'] ==
            _hash(
              utf8.encode(
                rows
                    .map(
                      (r) =>
                          '${r['path']} ${(r['sha256'] as String).toUpperCase()}\n',
                    )
                    .join(),
              ),
            ),
  );
}

Map<String, dynamic>? _target(String operation, Object? raw) {
  if ([
    'watchlists',
    'watchlist_create',
    'account',
    'account_open',
  ].contains(operation)) {
    _require(raw == null);
    return null;
  }
  final keys = switch (operation) {
    'search' => {'query', 'limit'},
    'quote' => {'instrument_id'},
    'ledger' => {'limit', 'after_sequence'},
    'watchlist_item_put' ||
    'watchlist_item_delete' => {'watchlist_id', 'instrument_id'},
    _ => {'watchlist_id'},
  };
  final value = _object(raw, keys);
  if (value.containsKey('watchlist_id')) localUuid(value['watchlist_id']);
  if (value.containsKey('instrument_id')) {
    localS3InstrumentId(value['instrument_id']);
  }
  if (operation == 'search') {
    _require(
      value['query'] is String &&
          localS3Query(value['query'] as String) == value['query'],
    );
    _require(localS3Integer(value['limit'], maximum: 20) > 0);
  }
  if (operation == 'ledger') {
    _require(localS3Integer(value['limit'], maximum: 100) > 0);
    localS3Integer(value['after_sequence']);
  }
  return value;
}

Map<String, dynamic> _body(
  Map<String, dynamic> body,
  String operation,
  String? code,
  Map<String, dynamic>? target,
  Object? request,
) {
  if (code != null) {
    _require(request == null);
    _object(body, {'success', 'message', 'error_code', 'error', 'detail'});
    final inner = _object(body['error'], {
      'code',
      'message',
      'fieldErrors',
      'correlationId',
    });
    _require(
      body['success'] == false &&
          body['error_code'] == code &&
          inner['code'] == code &&
          body['message'] is String &&
          (body['message'] as String).isNotEmpty &&
          (body['message'] as String).length <= 4096 &&
          body['detail'] == body['message'] &&
          inner['message'] == body['message'],
    );
    _correlation(inner['correlationId']);
    for (final field in _array(inner['fieldErrors'], 64)) {
      final value = _object(field, {'field', 'code'});
      _require(value.values.every((v) => v is String && v.length <= 128));
    }
    return {};
  }
  _object(body, {'success', 'message', 'data', 'meta'});
  _require(
    body['success'] == true &&
        body['message'] is String &&
        (body['message'] as String).length <= 4096,
  );
  final meta = _object(body['meta'], {
    'apiVersion',
    'dataStatus',
    'dataAsOf',
    'correlationId',
  });
  _correlation(meta['correlationId']);
  _require(meta['apiVersion'] == 'v1');
  final data = localObject(body['data']);
  DateTime? time;
  String status = 'CACHED';
  switch (operation) {
    case 'search':
      final value = LocalMarketSearch.fromJson(data);
      _require(request == null);
      _require(
        value.query == target!['query'] && value.limit == target['limit'],
      );
      time = localUtcTimestamp(localS3FixtureTime);
    case 'quote':
      final value = LocalMarketQuote.fromJson(data);
      _require(request == null);
      _require(value.instrumentId == target!['instrument_id']);
      time = value.quoteAsOf;
      status = value.dataStatus;
    case 'watchlists':
      LocalWatchlistList.fromJson(data);
      _require(request == null);
    case 'watchlist_create' || 'watchlist_update' || 'watchlist_detail':
      final value = LocalWatchlist.fromJson(data);
      time = value.summary.updatedAt;
      if (operation != 'watchlist_create') {
        _require(value.summary.id == target!['watchlist_id']);
      }
      if (operation == 'watchlist_detail') {
        _require(request == null);
      } else {
        final payload = _object(request, {'name'});
        _require(
          payload['name'] is String &&
              value.summary.name == localS3Name(payload['name'] as String),
        );
        if (operation == 'watchlist_create') {
          _require(
            value.items.isEmpty &&
                value.summary.createdAt == value.summary.updatedAt,
          );
        }
      }
    case 'watchlist_item_put':
      final value = LocalWatchlistItemSaved.fromJson(data);
      _require(
        request == null &&
            value.watchlistId == target!['watchlist_id'] &&
            value.item.instrument.instrumentId == target['instrument_id'],
      );
      time = value.item.addedAt;
    case 'watchlist_item_delete' || 'watchlist_delete':
      final value = LocalWatchlistConfirmation.fromJson(
        data,
        item: operation == 'watchlist_item_delete',
      );
      _require(
        request == null &&
            value.watchlistId == target!['watchlist_id'] &&
            (operation == 'watchlist_delete' ||
                value.instrumentId == target['instrument_id']),
      );
      _require(meta['dataAsOf'] != null);
      time = localUtcTimestamp(meta['dataAsOf']);
    case 'account' || 'account_open':
      final value = LocalPaperAccountState.fromJson(data);
      time = value.account?.createdAt;
      if (operation == 'account_open') {
        _require(
          value.account != null &&
              _same(request, {
                'foundation_version': localFoundationVersion,
                'currency': 'USD',
              }),
        );
      } else {
        _require(request == null);
      }
    case 'ledger':
      final value = LocalPaperLedger.fromJson(data);
      _require(
        request == null &&
            value.limit == target!['limit'] &&
            value.afterSequence == target['after_sequence'],
      );
      time = value.items.isEmpty ? null : value.items.last.createdAt;
  }
  final actualTime = meta['dataAsOf'] == null
      ? null
      : localUtcTimestamp(meta['dataAsOf']);
  _require(actualTime == time && meta['dataStatus'] == status);
  return data;
}

void _correlation(Object? raw) {
  _require(
    raw is String &&
        RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$').hasMatch(raw),
  );
}

Object? _instants(Object? value) {
  if (value is Map<String, dynamic>) {
    return value.map(
      (k, v) => MapEntry(
        k,
        [
                  'created_at',
                  'updated_at',
                  'added_at',
                  'fetched_at',
                  'cache_expires_at',
                  'quote_as_of',
                  'fixture_as_of',
                ].contains(k) &&
                v != null
            ? localUtcTimestamp(v).toIso8601String()
            : _instants(v),
      ),
    );
  }
  if (value is List) return value.map(_instants).toList();
  return value;
}

void _relationships(
  Map<String, Map<String, dynamic>> data,
  List<Map<String, dynamic>> entries,
) {
  const instruments = [
    ('SYN:AAPL', 'Synthetic Apple example', 'EQUITY', 'TECHNOLOGY', '200.0000'),
    (
      'SYN:BND',
      'Synthetic bond-fund example',
      'BOND',
      'FIXED_INCOME',
      '80.0000',
    ),
    (
      'SYN:MSFT',
      'Synthetic Microsoft example',
      'EQUITY',
      'TECHNOLOGY',
      '400.0000',
    ),
    (
      'SYN:UNAVAILABLE',
      'Synthetic unavailable-price example',
      'EQUITY',
      'GENERAL',
      null,
    ),
  ];
  void instrument(Object? raw) {
    final value = localObject(raw);
    final spec = instruments.singleWhere((v) => v.$1 == value['instrument_id']);
    _require(
      value['display_name'] == spec.$2 &&
          value['asset_class'] == spec.$3 &&
          value['sector'] == spec.$4 &&
          value['currency'] == 'USD',
    );
  }

  final initial = data['search_default']!;
  final filtered = data['search_filtered']!;
  final empty = data['search_empty']!;
  _require(
    initial['query'] == '' &&
        initial['limit'] == 20 &&
        _same(
          (initial['items'] as List).map((v) => v['instrument_id']).toList(),
          instruments.map((v) => v.$1).toList(),
        ) &&
        filtered['query'] == 'apple' &&
        filtered['limit'] == 2 &&
        _same(
          (filtered['items'] as List).map((v) => v['instrument_id']).toList(),
          ['SYN:AAPL'],
        ) &&
        empty['query'] == 'no-match' &&
        (empty['items'] as List).isEmpty,
  );
  for (final item in initial['items'] as List) {
    instrument(item);
  }
  for (var i = 0; i < instruments.length; i++) {
    final quote =
        data[[
          'quote_aapl',
          'quote_bond',
          'quote_msft',
          'quote_unavailable',
        ][i]]!;
    final spec = instruments[i];
    _require(
      quote['instrument_id'] == spec.$1 &&
          quote['unit_price'] == spec.$5 &&
          quote['status'] == (spec.$5 == null ? 'UNAVAILABLE' : 'CACHED'),
    );
  }
  for (final pair in [
    ('quote_cache_hit', 'quote_aapl'),
    ('watchlist_rename_noop', 'watchlist_renamed'),
    ('watchlist_item_duplicate', 'watchlist_item_added'),
    ('watchlist_item_remove_noop', 'watchlist_item_removed'),
    ('repeated_account_open', 'opened_account'),
    ('account_after_restart', 'opened_account'),
    ('account_after_recompletion', 'opened_account'),
    ('account_after_watchlist_delete', 'opened_account'),
    ('account_after_expiry_relogin', 'opened_account'),
    ('restored_account', 'opened_account'),
  ]) {
    _require(_same(_instants(data[pair.$1]), _instants(data[pair.$2])));
    final first = jsonDecode(
      entries.singleWhere((e) => e['id'] == pair.$1)['body_utf8'] as String,
    ) as Map;
    final second = jsonDecode(
      entries.singleWhere((e) => e['id'] == pair.$2)['body_utf8'] as String,
    ) as Map;
    final a = first['meta']['dataAsOf'];
    final b = second['meta']['dataAsOf'];
    _require(
      (a == null ? null : localUtcTimestamp(a)) ==
          (b == null ? null : localUtcTimestamp(b)),
    );
  }
  for (final id in ['watchlists_empty', 'other_owner_empty']) {
    _require((data[id]!['items'] as List).isEmpty);
  }
  for (final id in ['unopened_account', 'other_owner_unopened']) {
    _require(data[id]!['account'] == null);
  }
  final account = localObject(data['opened_account']!['account']);
  final ledger = LocalPaperLedger.fromJson(data['opening_ledger']);
  _require(
    ledger.accountId == account['account_id'] &&
        ledger.items.single.id == account['opening_ledger_id'] &&
        ledger.items.single.createdAt ==
            localUtcTimestamp(account['created_at']),
  );
  _require(
    data['ledger_after_opening']!['account_id'] == account['account_id'] &&
        (data['ledger_after_opening']!['items'] as List).isEmpty,
  );
  final created = data['watchlist_created']!;
  final renamed = data['watchlist_renamed']!;
  _require(
    created['name'] == 'Synthetic review list' &&
        renamed['name'] == 'Synthetic review list renamed' &&
        created['watchlist_id'] == renamed['watchlist_id'] &&
        localUtcTimestamp(created['created_at']) ==
            localUtcTimestamp(renamed['created_at']) &&
        !localUtcTimestamp(renamed['updated_at'])
            .isBefore(localUtcTimestamp(created['updated_at'])),
  );
  for (final id in [
    'watchlist_detail',
    'watchlist_after_restart',
    'watchlist_deleted',
  ]) {
    _require(data[id]!['watchlist_id'] == created['watchlist_id']);
  }
  final detail = data['watchlist_detail']!;
  final added = data['watchlist_item_added']!;
  _require(
    added['watchlist_id'] == created['watchlist_id'] &&
        _same(_instants(detail['items']), [_instants(added['item'])]) &&
        detail['name'] == renamed['name'] &&
        localUtcTimestamp(detail['updated_at']) ==
            localUtcTimestamp(added['item']['added_at']),
  );
  for (final item in detail['items'] as List) {
    instrument(item);
  }
  final collection = data['watchlist_collection']!;
  _require(
    collection['count'] == 2 &&
        (collection['items'] as List).any(
          (row) => _same(
            _instants(row),
            _instants({
              for (final key in [
                'watchlist_id',
                'name',
                'created_at',
                'updated_at',
                'item_count',
              ])
                key: detail[key],
            }),
          ),
        ),
  );
  final restarted = data['watchlist_after_restart']!;
  _require(
    restarted['name'] == renamed['name'] &&
        localUtcTimestamp(restarted['created_at']) ==
            localUtcTimestamp(created['created_at']) &&
        (restarted['items'] as List).length == 1 &&
        restarted['items'][0]['instrument_id'] == 'SYN:BND',
  );
  for (final item in restarted['items'] as List) {
    instrument(item);
  }
  _require(
    data['watchlist_item_removed']!['watchlist_id'] ==
            created['watchlist_id'] &&
        data['watchlist_item_removed']!['instrument_id'] == 'SYN:AAPL',
  );
  for (final id in ['watchlist_other_owner', 'deleted_watchlist_not_found']) {
    _require(
      entries.singleWhere((e) => e['id'] == id)['target']['watchlist_id'] ==
          created['watchlist_id'],
    );
  }
}

const localS3SourcePaths = {
  'backend/local_s2_evidence.py',
  'backend/verify_s1_application.py',
  'backend/verify_s2_manual_portfolio.py',
  'backend/verify_s2_saved_risk.py',
  'backend/verify_s3_foundation.py',
  'backend/verify_s3_evidence.py',
  'backend/tests/unit/test_verify_s3_foundation.py',
  'backend/tests/support/local_s3_client.py',
  'backend/tests/contract/test_local_s3_foundation_api.py',
  'backend/tests/contract/test_local_s3_foundation_failures.py',
  'backend/tests/contract/test_local_s3_faults.py',
  'backend/tests/contract/test_local_s3_review_controls.py',
  'backend/tests/contract/test_local_s3_openapi.py',
  'backend/tests/unit/test_local_s3_schema.py',
  'backend/tests/integration/test_local_s3_foundation_atomicity.py',
  'data/fixtures/local_s1/contract_cases.v1.json',
  'docs/features/local-application/S3-market-foundation-contract.md',
  'ai/risk/contract.py',
  'ai/risk/scoring.py',
  'backend/data/questionnaire/risk_questionnaire_v1.json',
};
typedef LocalS3CorpusGitRunner = ProcessResult Function(
  String executable,
  List<String> arguments, {
  required String workingDirectory,
  required bool runInShell,
  required Map<String, String> environment,
  required bool includeParentEnvironment,
});

String _git(String root, List<String> args) => readLocalS3CorpusGit(root, args);

// Test-only process seam: the spy can inspect the actual command boundary
// without starting Git, a credential helper, or a network request.
String readLocalS3CorpusGit(
  String root,
  List<String> args, {
  LocalS3CorpusGitRunner? runProcess,
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
      ...args,
    ],
    workingDirectory: root,
    runInShell: false,
    environment: environment,
    includeParentEnvironment: false,
  );
  _require(result.exitCode == 0 && result.stdout is String);
  return (result.stdout as String).trim();
}

LocalS3CorpusRuntime _runtime() {
  final root = _git(Directory.current.path, ['rev-parse', '--show-toplevel']);
  _require(Directory(root).isAbsolute);
  final commit = _git(root, ['rev-parse', 'HEAD']);
  final tree = _git(root, ['rev-parse', 'HEAD^{tree}']);
  _require(
    _git(root, ['status', '--porcelain', '--untracked-files=all']).isEmpty,
  );
  final appPaths = Directory('$root/backend/app')
      .listSync(recursive: true, followLinks: false)
      .whereType<File>()
      .where((file) => file.path.endsWith('.py'))
      .map(
        (file) => file.path.substring(root.length + 1).replaceAll('\\', '/'),
      );
  final paths = {...localS3SourcePaths, ...appPaths};
  final bytes = <String, Uint8List>{};
  final canonicalRoot = Directory(root).resolveSymbolicLinksSync();
  for (final path in paths) {
    final file = File('$root/$path');
    _require(
      FileSystemEntity.typeSync(file.path, followLinks: false) ==
          FileSystemEntityType.file,
    );
    final resolved = file.resolveSymbolicLinksSync();
    _require(
      (Platform.isWindows ? resolved.toLowerCase() : resolved).startsWith(
        '${Platform.isWindows ? canonicalRoot.toLowerCase() : canonicalRoot}${Platform.pathSeparator}',
      ),
    );
    _require(file.lengthSync() <= 2097152);
    bytes[path] = file.readAsBytesSync();
  }
  _require(
    _git(root, ['rev-parse', 'HEAD']) == commit &&
        _git(root, ['rev-parse', 'HEAD^{tree}']) == tree &&
        _git(root, ['status', '--porcelain', '--untracked-files=all']).isEmpty,
  );
  return LocalS3CorpusRuntime(
    commit,
    tree,
    false,
    false,
    Map.unmodifiable(bytes),
  );
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
    throw const FormatException('Invalid bounded local S3 evidence.');
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

const localS3CaseSpecs = <(String, String, int, String?)>[
  ('local_application_only', 'search', 403, 'LOCAL_APPLICATION_ONLY'),
  ('session_missing', 'search', 401, 'SESSION_INVALID'),
  ('onboarding_required', 'watchlists', 409, 'ONBOARDING_REQUIRED'),
  ('search_default', 'search', 200, null),
  ('search_filtered', 'search', 200, null),
  ('search_empty', 'search', 200, null),
  ('quote_aapl', 'quote', 200, null),
  ('quote_bond', 'quote', 200, null),
  ('quote_msft', 'quote', 200, null),
  ('quote_unavailable', 'quote', 200, null),
  ('quote_cache_hit', 'quote', 200, null),
  ('instrument_not_found', 'quote', 404, 'INSTRUMENT_NOT_FOUND'),
  ('watchlists_empty', 'watchlists', 200, null),
  ('watchlist_created', 'watchlist_create', 201, null),
  ('watchlist_renamed', 'watchlist_update', 200, null),
  ('watchlist_rename_noop', 'watchlist_update', 200, null),
  ('watchlist_item_added', 'watchlist_item_put', 200, null),
  ('watchlist_item_duplicate', 'watchlist_item_put', 200, null),
  ('watchlist_detail', 'watchlist_detail', 200, null),
  ('watchlist_collection', 'watchlists', 200, null),
  ('other_owner_empty', 'watchlists', 200, null),
  ('watchlist_other_owner', 'watchlist_detail', 404, 'WATCHLIST_NOT_FOUND'),
  ('watchlist_item_removed', 'watchlist_item_delete', 200, null),
  ('watchlist_item_remove_noop', 'watchlist_item_delete', 200, null),
  ('unopened_account', 'account', 200, null),
  ('unopened_ledger', 'ledger', 404, 'PAPER_ACCOUNT_NOT_OPEN'),
  ('opened_account', 'account_open', 200, null),
  ('repeated_account_open', 'account_open', 200, null),
  ('opening_ledger', 'ledger', 200, null),
  ('ledger_after_opening', 'ledger', 200, null),
  ('other_owner_unopened', 'account', 200, null),
  ('account_after_restart', 'account', 200, null),
  ('watchlist_after_restart', 'watchlist_detail', 200, null),
  ('withdrawal_required', 'watchlists', 409, 'ONBOARDING_REQUIRED'),
  ('reaccepted_required', 'account', 409, 'ONBOARDING_REQUIRED'),
  ('account_after_recompletion', 'account', 200, null),
  ('watchlist_deleted', 'watchlist_delete', 200, null),
  (
    'deleted_watchlist_not_found',
    'watchlist_detail',
    404,
    'WATCHLIST_NOT_FOUND',
  ),
  ('account_after_watchlist_delete', 'account', 200, null),
  ('session_revoked', 'watchlists', 401, 'SESSION_INVALID'),
  ('session_after_restart_revoked', 'account', 401, 'SESSION_INVALID'),
  ('session_expired', 'account', 401, 'SESSION_INVALID'),
  ('account_after_expiry_relogin', 'account', 200, null),
  ('storage_unavailable', 'watchlists', 503, 'LOCAL_STORE_UNAVAILABLE'),
  ('restored_account', 'account', 200, null),
  ('invalid_watchlist_name', 'watchlist_create', 422, 'VALIDATION_ERROR'),
  (
    'foundation_version_mismatch',
    'account_open',
    409,
    'MARKET_FOUNDATION_VERSION_MISMATCH',
  ),
  ('watchlist_limit', 'watchlist_create', 409, 'WATCHLIST_LIMIT'),
];
const localS3RequiredChecks = [
  'disabled_body_boundary',
  'missing_credential_boundary',
  'current_completed_onboarding',
  'default_search_catalogue',
  'default_quote_states_and_cache_hit',
  'unsupported_instrument',
  'watchlist_crud_and_stable_noops',
  'owner_scoped_non_disclosure',
  'watchlist_capacity_atomic',
  'unopened_read_no_funding',
  'one_explicit_opening',
  'original_opening_ledger',
  'first_real_process_restart',
  'withdrawal_reacceptance_recompletion',
  'watchlist_delete_preserves_other_domains',
  'durable_logout_and_second_restart',
  'real_session_expiry',
  'safe_owned_database_fault',
  'digest_only_storage_no_leak',
  'complete_original_wire_corpus',
  'owned_cleanup',
];
