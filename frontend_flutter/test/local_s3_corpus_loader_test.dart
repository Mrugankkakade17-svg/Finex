// Synthetic in-memory artifacts prove loader guards only, not native execution.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/local_s3_corpus.dart';
import 'support/local_s3_data.dart';

Uint8List bytes(Object? value) =>
    Uint8List.fromList(utf8.encode(jsonEncode(value)));
void main() {
  // Pure spies exercise the actual process boundary. They never invoke Git.
  test('S3 metadata Git disables lazy fetch before every read command', () {
    var calls = 0;
    for (final command in [
      ['rev-parse', '--show-toplevel'],
      ['rev-parse', 'HEAD', 'HEAD^{tree}'],
      ['status', '--porcelain', '--untracked-files=all'],
    ]) {
      final value = readLocalS3CorpusGit(
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
  test('S3 metadata Git scrubs mixed-case overrides but preserves PATH', () {
    readLocalS3CorpusGit(
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
    'S3 metadata Git unsupported flag fails without diagnostic reflection',
    () {
      Object? failure;
      try {
        readLocalS3CorpusGit(
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
  late Map<String, dynamic> corpus;
  late Map<String, dynamic> report;
  const commit = '1111111111111111111111111111111111111111';
  const tree = '2222222222222222222222222222222222222222';
  final source = {
    for (final path in {...localS3SourcePaths, 'backend/app/unit_fixture.py'})
      path: Uint8List.fromList(utf8.encode('Synthetic source')),
  };
  late Map<String, String> env;
  LocalS3Corpus? load() => loadLocalS3Corpus(
    env,
    readArtifact: (path) => bytes(path == 'corpus' ? corpus : report),
    readRuntime: () => LocalS3CorpusRuntime(commit, tree, false, false, source),
  );
  void rebind() {
    report['corpus_sha256'] = sha256.convert(bytes(corpus)).toString();
  }

  setUp(() {
    env = {
      'FINEX_REQUIRE_LOCAL_S3_CORPUS': '1',
      'FINEX_LOCAL_S3_CORPUS': 'corpus',
      'FINEX_LOCAL_S3_REPORT': 'report',
    };
    final names = source.keys.toList()..sort();
    final rows = [
      for (final name in names)
        {'path': name, 'sha256': sha256.convert(source[name]!).toString()},
    ];
    final manifest = sha256
        .convert(
          utf8.encode(
            rows
                .map((r) => '${r['path']} ${r['sha256']!.toUpperCase()}\n')
                .join(),
          ),
        )
        .toString();
    corpus = {
      ...s3Root(),
      'schema_version': 'finex.local_s3.foundation_corpus.v1',
      'provenance': {
        'kind': 'native_tcp_capture',
        'source': 'owned_loopback_uvicorn',
        'command': 'python verify_s3_foundation.py',
        'tested_commit': commit,
        'tested_tree': tree,
      },
      'source_hashes': rows,
      'source_manifest_sha256': manifest,
      'cases': localS3CaseSpecs.map((spec) {
        final (id, operation, status, error) = spec;
        Map<String, dynamic>? target;
        Map<String, dynamic>? request;
        Map<String, dynamic> data;
        String? asOf;
        switch (operation) {
          case 'search':
            target = {'query': '', 'limit': 20};
            data = s3Search();
            asOf = s3FixtureTime;
          case 'quote':
            target = {'instrument_id': 'SYN:AAPL'};
            data = s3Quote();
            asOf = s3FixtureTime;
          case 'watchlists':
            data = s3Watchlists();
            if (id.contains('empty')) {
              data['items'] = <Object?>[];
              data['count'] = 0;
            }
          case 'watchlist_create':
            request = {'name': ' Synthetic list '};
            data = s3Watchlist();
            asOf = s3Time;
          case 'watchlist_update':
            request = {'name': 'Synthetic list'};
            target = {'watchlist_id': s3Id};
            data = s3Watchlist();
            asOf = s3Time;
          case 'watchlist_detail':
            target = {'watchlist_id': s3Id};
            data = s3Watchlist();
            asOf = s3Time;
          case 'watchlist_delete':
            target = {'watchlist_id': s3Id};
            data = {
              ...s3Root(),
              'watchlist_version': 'watchlist.v1',
              'watchlist_id': s3Id,
              'deleted': true,
            };
            asOf = s3Time;
          case 'watchlist_item_put':
            target = {'watchlist_id': s3Id, 'instrument_id': 'SYN:AAPL'};
            data = {
              ...s3Root(),
              'watchlist_version': 'watchlist.v1',
              'watchlist_item_version': 'watchlist_item.v1',
              'watchlist_id': s3Id,
              'item': s3Item(),
            };
            asOf = s3Time;
          case 'watchlist_item_delete':
            target = {'watchlist_id': s3Id, 'instrument_id': 'SYN:AAPL'};
            data = {
              ...s3Root(),
              'watchlist_version': 'watchlist.v1',
              'watchlist_item_version': 'watchlist_item.v1',
              'watchlist_id': s3Id,
              'instrument_id': 'SYN:AAPL',
              'removed': true,
            };
            asOf = s3Time;
          case 'account':
            data = s3Account(
              opened: ![
                'unopened_account',
                'other_owner_unopened',
              ].contains(id),
            );
            asOf = data['account'] == null ? null : s3Time;
          case 'account_open':
            request = {
              'foundation_version': 'market_foundation.v1',
              'currency': 'USD',
            };
            data = s3Account();
            asOf = s3Time;
          case 'ledger':
            final after = id == 'ledger_after_opening' ? 1 : 0;
            target = {'limit': 2, 'after_sequence': after};
            data = s3Ledger(after: after, limit: 2);
            asOf = after == 0 ? s3Time : null;
          default:
            throw StateError('Known synthetic operation required');
        }
        return {
          'id': id,
          'operation': operation,
          'target': target,
          'request': error == null ? request : null,
          'status': status,
          'content_type': 'application/json',
          'body_utf8': jsonEncode(
            error == null ? s3Success(data, time: asOf) : s3Error(error),
          ),
          'expected': {
            'outcome': error == null ? 'success' : 'error',
            'error_code': ?error,
          },
        };
      }).toList(),
    };
    // Match the independently frozen native case semantics, not just valid DTO
    // shapes. These remain handcrafted unit inputs, never claimed as capture.
    Map<String, dynamic> row(String id) => (corpus['cases'] as List)
        .cast<Map<String, dynamic>>()
        .singleWhere((r) => r['id'] == id);
    void wire(
      String id,
      Map<String, dynamic> data, {
      String? time = s3Time,
      String status = 'CACHED',
    }) {
      row(id)['body_utf8'] = jsonEncode(
        s3Success(data, time: time, status: status),
      );
    }

    final instruments = [
      {...s3Instrument(), 'display_name': 'Synthetic Apple example'},
      {
        ...s3Instrument('SYN:BND'),
        'display_name': 'Synthetic bond-fund example',
        'asset_class': 'BOND',
        'sector': 'FIXED_INCOME',
      },
      {
        ...s3Instrument('SYN:MSFT'),
        'display_name': 'Synthetic Microsoft example',
      },
      {
        ...s3Instrument('SYN:UNAVAILABLE'),
        'display_name': 'Synthetic unavailable-price example',
        'sector': 'GENERAL',
      },
    ];
    wire(
      'search_default',
      s3Search()
        ..['count'] = 4
        ..['items'] = instruments,
      time: s3FixtureTime,
    );
    row('search_filtered')['target'] = {'query': 'apple', 'limit': 2};
    wire(
      'search_filtered',
      s3Search(query: 'apple', limit: 2)..['items'] = [instruments.first],
      time: s3FixtureTime,
    );
    row('search_empty')['target'] = {'query': 'no-match', 'limit': 20};
    wire(
      'search_empty',
      s3Search(query: 'no-match')
        ..['items'] = <Object?>[]
        ..['count'] = 0,
      time: s3FixtureTime,
    );
    for (final spec in [
      ('quote_bond', 'SYN:BND', '80.0000'),
      ('quote_msft', 'SYN:MSFT', '400.0000'),
    ]) {
      row(spec.$1)['target'] = {'instrument_id': spec.$2};
      wire(
        spec.$1,
        s3Quote()
          ..['instrument_id'] = spec.$2
          ..['unit_price'] = spec.$3,
        time: s3FixtureTime,
      );
    }
    row('quote_unavailable')['target'] = {'instrument_id': 'SYN:UNAVAILABLE'};
    wire(
      'quote_unavailable',
      s3Quote(status: 'UNAVAILABLE')..['instrument_id'] = 'SYN:UNAVAILABLE',
      time: null,
      status: 'UNAVAILABLE',
    );
    row('watchlist_created')['request'] = {'name': ' Synthetic review list '};
    wire('watchlist_created', s3Watchlist(name: 'Synthetic review list'));
    for (final id in ['watchlist_renamed', 'watchlist_rename_noop']) {
      row(id)['request'] = {'name': 'Synthetic review list renamed'};
      wire(id, s3Watchlist(name: 'Synthetic review list renamed'));
    }
    final item = {...instruments.first, 'added_at': s3Time};
    for (final id in ['watchlist_item_added', 'watchlist_item_duplicate']) {
      wire(id, {
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_item_version': 'watchlist_item.v1',
        'watchlist_id': s3Id,
        'item': item,
      });
    }
    final detail = s3Watchlist(
      name: 'Synthetic review list renamed',
      item: true,
    )..['items'] = [item];
    wire('watchlist_detail', detail);
    wire(
      'watchlist_collection',
      s3Watchlists()
        ..['count'] = 2
        ..['items'] = [
          s3Summary(name: 'Synthetic review list renamed', count: 1),
          s3Summary(id: s3OtherId, name: 'Second synthetic list'),
        ],
      time: null,
    );
    wire(
      'watchlist_after_restart',
      s3Watchlist(name: 'Synthetic review list renamed', item: true)
        ..['items'] = [
          {...instruments[1], 'added_at': s3Time},
        ],
    );
    report = {
      ...s3Root(),
      'schema_version': 'finex.local_s3.foundation.acceptance.v1',
      'success': true,
      'mode': 'owned_native_tcp',
      'tested_commit': commit,
      'tested_tree': tree,
      'working_tree_dirty': false,
      'tracked_dirty': false,
      'source_hashes': rows,
      'source_manifest_sha256': manifest,
      'checks': localS3RequiredChecks
          .map((id) => {'id': id, 'passed': true})
          .toList(),
      'required_checks': localS3RequiredChecks,
      'failures': <Object?>[],
      'responses_checked': 48,
      'corpus_case_ids': localS3CaseSpecs.map((s) => s.$1).toList(),
      'native_process': {
        'starts': 6,
        'application_restarts': 4,
        'durable_restarts': 2,
        'storage_fault_restarts': 2,
        'owned_pids': [1, 2, 3, 4, 5, 6],
        'child_reaped': true,
        'temporary_directory_removed': true,
        'session_ttl_minutes': 1,
        'real_expiry_elapsed_seconds': 60.1,
        'shutdown': 'owned_terminate_and_reap',
      },
      'python_version': '3.12.14',
      'limitations': ['Synthetic loader-unit artifact, not native proof'],
    };
    rebind();
  });
  test(
    'source manifest canonical uppercase SHA lines accept lowercase rows',
    () {
      final rows = (corpus['source_hashes'] as List)
          .cast<Map<String, dynamic>>();
      expect(
        rows.every(
          (row) =>
              row['sha256'] is String &&
              row['sha256'] == (row['sha256'] as String).toLowerCase(),
        ),
        isTrue,
      );
      // The approved native producer preserves lowercase individual digests but
      // hashes ordinal path SPACE UPPERCASE digest LF rows, including final LF.
      final canonical = sha256
          .convert(
            utf8.encode(
              rows.map((row) {
                final digest = row['sha256'] as String;
                return '${row['path']} ${digest.toUpperCase()}\n';
              }).join(),
            ),
          )
          .toString();
      corpus['source_manifest_sha256'] = canonical;
      report['source_manifest_sha256'] = canonical;
      rebind();
      final result = load()!;
      expect(result.cases.length, 48);
      expect(result.originalBytes, bytes(corpus));
    },
  );
  test(
    'source manifest lowercase aggregate is rejected despite matching pair',
    () {
      final rows = (corpus['source_hashes'] as List)
          .cast<Map<String, dynamic>>();
      final invalid = sha256
          .convert(
            utf8.encode(
              rows.map((row) {
                final digest = row['sha256'] as String;
                return '${row['path']} ${digest.toLowerCase()}\n';
              }).join(),
            ),
          )
          .toString();
      corpus['source_manifest_sha256'] = invalid;
      report['source_manifest_sha256'] = invalid;
      rebind();
      // Agreement alone cannot authorize an alternate manifest wire contract.
      expect(load, throwsFormatException);
    },
  );
  test('complete synthetic guard fixture loads 48 original byte cases', () {
    final result = load()!;
    expect(result.cases.length, 48);
    expect(result.originalBytes, bytes(corpus));
  });
  test('optional absent input returns null; required absent fails', () {
    expect(loadLocalS3Corpus({}), isNull);
    expect(
      () => loadLocalS3Corpus({'FINEX_REQUIRE_LOCAL_S3_CORPUS': '1'}),
      throwsFormatException,
    );
  });
  for (final key in ['FINEX_LOCAL_S3_CORPUS', 'FINEX_LOCAL_S3_REPORT']) {
    test(
      'missing $key fails with no fallback',
      () => expect(() {
        env.remove(key);
        load();
      }, throwsFormatException),
    );
  }
  for (final key in ['success', 'working_tree_dirty', 'tracked_dirty']) {
    test(
      'report $key contradiction is rejected',
      () => expect(() {
        report[key] = key != 'success';
        load();
      }, throwsFormatException),
    );
  }
  test(
    'removed case with rebound digest fails',
    () => expect(() {
      (corpus['cases'] as List).removeLast();
      rebind();
      load();
    }, throwsFormatException),
  );
  test(
    'missing cleanup is rejected',
    () => expect(() {
      report['native_process']['child_reaped'] = false;
      load();
    }, throwsFormatException),
  );
  test(
    'wrong source digest is rejected',
    () => expect(() {
      report['source_hashes'] = [
        {'path': source.keys.first, 'sha256': '0' * 64},
      ];
      load();
    }, throwsFormatException),
  );
  test(
    'body duplicate escaped key cannot overwrite a private earlier message',
    () {
      final first = (corpus['cases'] as List).first;
      first['body_utf8'] = (first['body_utf8'] as String).replaceFirst(
        '{',
        '{"message":"Bearer synthetic-only",',
      );
      rebind();
      expect(load, throwsFormatException);
    },
  );
  for (final key in ['quote', 'catalogue', 'restart', 'collection']) {
    test('native $key meaning cannot be replaced with another valid DTO', () {
      final rows = (corpus['cases'] as List).cast<Map<String, dynamic>>();
      void mutate(String id, void Function(Map<String, dynamic>) apply) {
        final row = rows.singleWhere((r) => r['id'] == id);
        final body =
            jsonDecode(row['body_utf8'] as String) as Map<String, dynamic>;
        apply(body['data'] as Map<String, dynamic>);
        row['body_utf8'] = jsonEncode(body);
      }

      switch (key) {
        case 'quote':
          for (final id in ['quote_aapl', 'quote_cache_hit']) {
            mutate(id, (v) => v['unit_price'] = '300.0000');
          }
        case 'catalogue':
          mutate('search_default', (v) {
            (v['items'] as List).removeLast();
            v['count'] = 3;
          });
        case 'restart':
          mutate('watchlist_after_restart', (v) {
            v['items'] = [
              {
                ...s3Instrument(),
                'display_name': 'Synthetic Apple example',
                'added_at': s3Time,
              },
            ];
          });
        case 'collection':
          mutate('watchlist_collection', (v) {
            (v['items'] as List).removeLast();
            v['count'] = 1;
          });
      }
      rebind();
      expect(load, throwsFormatException);
    });
  }
  for (final flag in ['', 'true', '2']) {
    test(
      'unknown required flag fails closed',
      () => expect(() {
        env['FINEX_REQUIRE_LOCAL_S3_CORPUS'] = flag;
        load();
      }, throwsFormatException),
    );
  }
  for (final key in [
    'kind',
    'source',
    'command',
    'tested_commit',
    'tested_tree',
  ]) {
    test(
      'wrong native provenance $key fails',
      () => expect(() {
        corpus['provenance'][key] = 'invalid';
        rebind();
        load();
      }, throwsFormatException),
    );
  }
  for (final key in [
    'starts',
    'application_restarts',
    'durable_restarts',
    'storage_fault_restarts',
    'session_ttl_minutes',
    'temporary_directory_removed',
    'shutdown',
  ]) {
    test(
      'native lifecycle $key cannot be missing',
      () => expect(() {
        (report['native_process'] as Map).remove(key);
        load();
      }, throwsFormatException),
    );
  }
  for (final elapsed in [58.9, 75.1, '60', true]) {
    test(
      'invalid real expiry evidence ${elapsed.runtimeType} is rejected',
      () => expect(() {
        report['native_process']['real_expiry_elapsed_seconds'] = elapsed;
        load();
      }, throwsFormatException),
    );
  }
  for (final key in [
    'user_id',
    'Owner-Id',
    'access_token',
    'AUTHORIZATION',
    'db_path',
    'cookie',
    'diagnostics',
  ]) {
    test(
      'recursive private $key cannot enter a response even with updated digest',
      () => expect(() {
        final row = (corpus['cases'] as List)[3] as Map;
        final body =
            jsonDecode(row['body_utf8'] as String) as Map<String, dynamic>;
        (body['data'] as Map)[key] = 'Synthetic private marker';
        row['body_utf8'] = jsonEncode(body);
        rebind();
        load();
      }, throwsFormatException),
    );
  }
  for (final key in ['plain', 'escaped', 'nested']) {
    test(
      '$key duplicate member in original response bytes is rejected safely',
      () => expect(() {
        final row = (corpus['cases'] as List).first as Map;
        var body = row['body_utf8'] as String;
        if (key == 'plain') {
          body = body.replaceFirst('{', '{"message":"Bearer synthetic-only",');
        }
        if (key == 'escaped') {
          body = body.replaceFirst(
            '{',
            r'{"messa\u0067e":"Bearer synthetic-only",',
          );
        }
        if (key == 'nested') {
          body = body.replaceFirst(
            '"error":{',
            '"error":{"code":"Bearer synthetic-only",',
          );
        }
        row['body_utf8'] = body;
        rebind();
        load();
      }, throwsFormatException),
    );
  }
  test('outer corpus/report duplicate decoded keys cannot hide early private content', () {
    for (final outer in ['corpus', 'report']) {
      final raw = utf8.encode(
        jsonEncode(outer == 'corpus' ? corpus : report)
            .replaceFirst('{', r'{"succe\u0073s":false,"success":true,'),
      );
      final changed = Map<String, dynamic>.from(report);
      if (outer == 'corpus') {
        changed['corpus_sha256'] = sha256.convert(raw).toString();
      }
      expect(
        () => loadLocalS3Corpus(
          env,
          readArtifact: (path) => Uint8List.fromList(
            path == outer
                ? raw
                : utf8.encode(jsonEncode(path == 'corpus' ? corpus : changed)),
          ),
          readRuntime: () =>
              LocalS3CorpusRuntime(commit, tree, false, false, source),
        ),
        throwsFormatException,
      );
    }
  });
  test('invalid UTF8 never reflects raw parser bytes', () {
    expect(
      () => loadLocalS3Corpus(
        env,
        readArtifact: (_) => Uint8List.fromList([0xc3, 0x28]),
        readRuntime: () =>
            LocalS3CorpusRuntime(commit, tree, false, false, source),
      ),
      throwsFormatException,
    );
  });
  test(
    'body byte cap cannot be exceeded by padding',
    () => expect(() {
      final row = (corpus['cases'] as List).first as Map;
      row['body_utf8'] = '${row['body_utf8']}${' ' * 262144}';
      rebind();
      load();
    }, throwsFormatException),
  );
  test('artifact byte cap is checked before parsing', () {
    expect(
      () => loadLocalS3Corpus(
        env,
        readArtifact: (_) => Uint8List(2097153),
        readRuntime: () =>
            LocalS3CorpusRuntime(commit, tree, false, false, source),
      ),
      throwsFormatException,
    );
  });
  for (final dirty in [true, false]) {
    test(
      'current checkout dirty binding ${dirty ? 'working' : 'tracked'} is rejected',
      () {
        expect(
          () => loadLocalS3Corpus(
            env,
            readArtifact: (path) => bytes(path == 'corpus' ? corpus : report),
            readRuntime: () =>
                LocalS3CorpusRuntime(commit, tree, dirty, !dirty, source),
          ),
          throwsFormatException,
        );
      },
    );
  }
  test('revision drift between validation and acceptance is rejected', () {
    var reads = 0;
    expect(
      () => loadLocalS3Corpus(
        env,
        readArtifact: (path) => bytes(path == 'corpus' ? corpus : report),
        readRuntime: () => LocalS3CorpusRuntime(
          ++reads == 1 ? commit : tree,
          tree,
          false,
          false,
          source,
        ),
      ),
      throwsFormatException,
    );
  });
  test('source drift and missing inventory are rejected', () {
    final changed = Map<String, Uint8List>.from(source)
      ..remove(localS3SourcePaths.first);
    expect(
      () => loadLocalS3Corpus(
        env,
        readArtifact: (path) => bytes(path == 'corpus' ? corpus : report),
        readRuntime: () =>
            LocalS3CorpusRuntime(commit, tree, false, false, changed),
      ),
      throwsFormatException,
    );
  });
  test('escaped quotes and Unicode retain original artifact bytes', () {
    final raw = utf8.encode(
      jsonEncode(corpus).replaceAll('Synthetic', r'\u0053ynthetic'),
    );
    final changed = Map<String, dynamic>.from(report)
      ..['corpus_sha256'] = sha256.convert(raw).toString();
    final result = loadLocalS3Corpus(
      env,
      readArtifact: (path) => Uint8List.fromList(
        path == 'corpus' ? raw : utf8.encode(jsonEncode(changed)),
      ),
      readRuntime: () =>
          LocalS3CorpusRuntime(commit, tree, false, false, source),
    );
    expect(result!.originalBytes, raw);
  });
  for (final operation in ['search', 'quote']) {
    test(
      'captured GET $operation requires a null request, not ignored extra data',
      () {
        final rows = (corpus['cases'] as List).cast<Map<String, dynamic>>();
        rows.firstWhere(
          (r) => r['operation'] == operation && r['status'] == 200,
        )['request'] = {
          'unexpected': 'synthetic extra',
        };
        rebind();
        expect(load, throwsFormatException);
      },
    );
  }
}
