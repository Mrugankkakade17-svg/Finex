import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/goal_models.dart';

class GoalException implements Exception {
  final String code;
  final String message;
  final int statusCode;

  const GoalException({
    required this.code,
    required this.message,
    this.statusCode = 400,
  });

  @override
  String toString() => 'GoalException($code, $statusCode): $message';
}

class GoalService {
  final Uri baseUri;
  final http.Client _client;
  final Future<String?> Function()? tokenProvider;

  GoalService({Uri? baseUri, http.Client? client, this.tokenProvider})
    : baseUri = baseUri ?? Uri.parse('http://127.0.0.1:8000'),
      _client = client ?? http.Client();

  Future<Map<String, String>> _headers() async {
    final token = tokenProvider != null ? await tokenProvider!() : null;
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<List<GoalResponse>> getGoals() async {
    final uri = baseUri.resolve('/api/v1/goals');
    final response = await _client.get(uri, headers: await _headers());
    final data = _unwrap(response, 200);
    return (data as List<dynamic>)
        .map((e) => GoalResponse.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<GoalResponse> createGoal(GoalCreateRequest request) async {
    final uri = baseUri.resolve('/api/v1/goals');
    final response = await _client.post(
      uri,
      headers: await _headers(),
      body: jsonEncode(request.toJson()),
    );
    final data = _unwrap(response, [200, 201]);
    return GoalResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<GoalResponse> getGoal(String goalId) async {
    final uri = baseUri.resolve('/api/v1/goals/$goalId');
    final response = await _client.get(uri, headers: await _headers());
    final data = _unwrap(response, 200);
    return GoalResponse.fromJson(data as Map<String, dynamic>);
  }

  dynamic _unwrap(http.Response response, dynamic expectedStatus) {
    final expectedList = expectedStatus is List<int>
        ? expectedStatus
        : [expectedStatus as int];
    Map<String, dynamic>? body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>?;
    } catch (_) {
      // not JSON
    }

    if (expectedList.contains(response.statusCode)) {
      if (body != null && body.containsKey('data')) {
        return body['data'];
      }
      return body;
    }

    final code = (body?['error_code'] ?? body?['code'] ?? 'ERROR').toString();
    final message = (body?['message'] ?? body?['detail'] ?? 'An error occurred')
        .toString();
    throw GoalException(
      code: code,
      message: message,
      statusCode: response.statusCode,
    );
  }
}
