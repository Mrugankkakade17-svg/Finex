import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'local_http_client.dart';
import 'local_models.dart';
import 'local_s2_api.dart';
import 'local_s2_models.dart';
import 'local_s3_api.dart';
import 'local_s3_models.dart';

part 'local_s2_http.dart';
part 'local_s3_http.dart';

abstract interface class LocalApplicationApi {
  Future<LocalLogin> login(String alias);
  Future<LocalUser> me(String bearer);
  Future<LocalOnboardingState> state(String bearer);
  Future<LocalOnboardingState> saveDraft(
    String bearer, {
    String? displayName,
    String? experienceLevel,
  });
  Future<LocalOnboardingState> consent(String bearer, bool accepted);
  Future<LocalOnboardingState> complete(String bearer);
  Future<void> logout(String bearer);
  void close();
}

/// No credential persistence, automatic mutation retries or raw server diagnostics.
class HttpLocalApplicationApi
    with _LocalS2HttpMethods, _LocalS3HttpMethods
    implements LocalApplicationApi, LocalS2Api, LocalS3Api {
  final Uri baseUri;
  final http.Client _client;
  final Duration timeout;

  HttpLocalApplicationApi(
    Uri origin, {
    http.Client? client,
    this.timeout = const Duration(seconds: 8),
  }) : baseUri = validateOrigin(origin),
       _client = client ?? createLocalHttpClient() {
    if (timeout <= Duration.zero || timeout > const Duration(seconds: 30)) {
      throw ArgumentError(
        'Request timeout must be between zero and 30 seconds.',
      );
    }
  }

  factory HttpLocalApplicationApi.fromEnvironment() {
    const address = String.fromEnvironment(
      'FINEX_API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    );
    final uri = Uri.tryParse(address);
    if (uri == null) throw const LocalApiException('INVALID_API_ORIGIN');
    return HttpLocalApplicationApi(uri);
  }

  static Uri validateOrigin(Uri uri) {
    if (!['http', 'https'].contains(uri.scheme) ||
        !['localhost', '127.0.0.1', '::1'].contains(uri.host) ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        uri.port <= 0 ||
        uri.port > 65535 ||
        !['', '/'].contains(uri.path)) {
      throw const LocalApiException('INVALID_API_ORIGIN');
    }
    return uri;
  }

  @override
  Future<Map<String, dynamic>> _s3Request(
    String method,
    String path, {
    String? bearer,
    Map<String, Object?>? body,
    int expectedStatus = 200,
  }) => _request(
    method,
    path,
    bearer: bearer,
    body: body,
    s3: true,
    expectedStatus: expectedStatus,
  );

  @override
  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    String? bearer,
    Map<String, Object?>? body,
    bool s2 = false,
    bool s3 = false,
    int expectedStatus = 200,
  }) async {
    final abort = Completer<void>();
    final request = http.AbortableRequest(
      method,
      baseUri.resolve(path),
      abortTrigger: abort.future,
    );
    request.followRedirects = false;
    request.headers.addAll({
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-Correlation-ID':
          'flutter-local-${Random.secure().nextInt(0x100000000).toRadixString(16)}',
      if (bearer != null) 'Authorization': 'Bearer $bearer',
    });
    if (body != null) request.body = jsonEncode(body);
    final elapsed = Stopwatch()..start();
    try {
      return await (() async {
        final streamed = await _client.send(request);
        if (streamed.statusCode == 401) {
          // Revoke local authority from the status; a stalled body is irrelevant.
          unawaited(streamed.stream.listen((_) {}).cancel());
          throw const LocalApiException('SESSION_INVALID', status: 401);
        }
        final bytes = BytesBuilder(copy: false);
        await for (final chunk in streamed.stream) {
          if (bytes.length + chunk.length > 262144) {
            if (!abort.isCompleted) abort.complete();
            invalidLocalResponse();
          }
          bytes.add(chunk);
        }
        final response = http.Response.bytes(
          bytes.takeBytes(),
          streamed.statusCode,
          headers: streamed.headers,
        );
        final data = s3
            ? _decodeS3Response(response, expectedStatus, method, path)
            : s2
            ? _decodeS2Response(response, expectedStatus, method, path)
            : _decodeResponse(response);
        if (elapsed.elapsed >= timeout) {
          throw TimeoutException('Local response timeout.');
        }
        return data;
      })().timeout(timeout);
    } on TimeoutException {
      if (!abort.isCompleted) abort.complete();
      throw const LocalApiException('REQUEST_TIMEOUT');
    } on LocalApiException {
      rethrow;
    } on Exception {
      throw const LocalApiException('API_UNAVAILABLE');
    }
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    if (response.statusCode == 401) {
      throw const LocalApiException('SESSION_INVALID', status: 401);
    }
    Object? decoded;
    if (response.bodyBytes.length > 262144) invalidLocalResponse();
    try {
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const LocalApiException('INVALID_API_RESPONSE');
    }
    final envelope = localObject(decoded);
    if (envelope['success'] is! bool) invalidLocalResponse();
    if (response.statusCode < 200 ||
        response.statusCode >= 300 ||
        envelope['success'] != true) {
      final rawCode = envelope['error_code'];
      const safeCodes = {
        'LOCAL_APPLICATION_ONLY',
        'LOCAL_STORE_UNAVAILABLE',
        'UNKNOWN_LOCAL_ALIAS',
        'CONSENT_VERSION_MISMATCH',
        'PROFILE_VERSION_MISMATCH',
        'CONSENT_REQUIRED',
        'PROFILE_INCOMPLETE',
        'ONBOARDING_REQUIRED',
        'VALIDATION_ERROR',
      };
      final error = envelope['error'];
      final fields = <String>{};
      if (error is Map<String, dynamic> && error['fieldErrors'] is List) {
        for (final item in error['fieldErrors'] as List) {
          if (item is Map &&
              [
                'display_name',
                'experience_level',
                'alias',
              ].contains(item['field'])) {
            fields.add(item['field'] as String);
          }
        }
      }
      throw LocalApiException(
        safeCodes.contains(rawCode) ? rawCode as String : 'REQUEST_FAILED',
        status: response.statusCode,
        fields: Set.unmodifiable(fields),
      );
    }
    final meta = localObject(envelope['meta']);
    if (meta['apiVersion'] != 'v1' ||
        meta['dataStatus'] != 'CACHED' ||
        !meta.containsKey('dataAsOf') ||
        meta['dataAsOf'] != null ||
        meta['correlationId'] is! String ||
        (meta['correlationId'] as String).isEmpty) {
      invalidLocalResponse();
    }
    final data = localObject(envelope['data']);
    requireLocalVersion(data);
    return data;
  }

  @override
  Future<LocalLogin> login(String alias) async {
    if (!localAliases.contains(alias)) {
      throw const LocalApiException('UNKNOWN_LOCAL_ALIAS');
    }
    final login = LocalLogin.fromJson(
      await _request(
        'POST',
        '/api/v1/local-auth/mock-login',
        body: {'alias': alias},
      ),
    );
    if (login.user.alias != alias) invalidLocalResponse();
    return login;
  }

  @override
  Future<LocalUser> me(String bearer) async => LocalUser.fromJson(
    (await _request('GET', '/api/v1/local-auth/me', bearer: bearer))['user'],
  );

  @override
  Future<LocalOnboardingState> state(String bearer) async =>
      LocalOnboardingState.fromJson(
        await _request('GET', '/api/v1/local-onboarding/state', bearer: bearer),
      );

  @override
  Future<LocalOnboardingState> saveDraft(
    String bearer, {
    String? displayName,
    String? experienceLevel,
  }) async {
    final trimmed = displayName?.trim();
    final normalized = trimmed == '' ? null : trimmed;
    final state = LocalOnboardingState.fromJson(
      await _request(
        'PUT',
        '/api/v1/local-onboarding/draft',
        bearer: bearer,
        body: {
          'profile_schema_version': localProfileVersion,
          'display_name': normalized,
          'experience_level': experienceLevel,
        },
      ),
    );
    if (state.displayName != normalized ||
        state.experienceLevel != experienceLevel ||
        state.draftUpdatedAt == null) {
      invalidLocalResponse();
    }
    return state;
  }

  @override
  Future<LocalOnboardingState> consent(String bearer, bool accepted) async {
    final state = LocalOnboardingState.fromJson(
      await _request(
        'POST',
        '/api/v1/local-onboarding/consent',
        bearer: bearer,
        body: {
          'consent_version': localConsentVersion,
          'consent_given': accepted,
        },
      ),
    );
    if (state.consent == null || state.consent!.accepted != accepted) {
      invalidLocalResponse();
    }
    return state;
  }

  @override
  Future<LocalOnboardingState> complete(String bearer) async {
    final state = LocalOnboardingState.fromJson(
      await _request(
        'POST',
        '/api/v1/local-onboarding/complete',
        bearer: bearer,
        body: {
          'consent_version': localConsentVersion,
          'profile_schema_version': localProfileVersion,
        },
      ),
    );
    if (!state.canAccessFeatures) invalidLocalResponse();
    return state;
  }

  @override
  Future<void> logout(String bearer) async {
    final data = await _request(
      'POST',
      '/api/v1/local-auth/logout',
      bearer: bearer,
      body: {},
    );
    if (data['signed_out'] != true) invalidLocalResponse();
  }

  @override
  void close() => _client.close();
}

/// Invalid compile-time configuration stays an actionable sign-in error.
class UnavailableLocalApplicationApi implements LocalApplicationApi {
  final LocalApiException error;
  const UnavailableLocalApplicationApi(this.error);
  @override
  Future<LocalLogin> login(String alias) async => throw error;
  @override
  Future<LocalUser> me(String bearer) async => throw error;
  @override
  Future<LocalOnboardingState> state(String bearer) async => throw error;
  @override
  Future<LocalOnboardingState> saveDraft(
    String bearer, {
    String? displayName,
    String? experienceLevel,
  }) async => throw error;
  @override
  Future<LocalOnboardingState> consent(String bearer, bool accepted) async =>
      throw error;
  @override
  Future<LocalOnboardingState> complete(String bearer) async => throw error;
  @override
  Future<void> logout(String bearer) async => throw error;
  @override
  void close() {}
}
