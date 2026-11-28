import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/paper_trading_models.dart';

class PaperTradingException implements Exception {
  final String code;
  final String message;
  final int statusCode;

  const PaperTradingException({
    required this.code,
    required this.message,
    this.statusCode = 400,
  });

  @override
  String toString() => 'PaperTradingException($code, $statusCode): $message';
}

class PaperTradingService {
  final Uri baseUri;
  final http.Client _client;
  final Future<String?> Function()? tokenProvider;

  PaperTradingService({Uri? baseUri, http.Client? client, this.tokenProvider})
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

  Future<PaperAccount> getAccount() async {
    final uri = baseUri.resolve('/api/v1/paper/account');
    final response = await _client.get(uri, headers: await _headers());
    final data = _unwrap(response, 200);
    return PaperAccount.fromJson(data as Map<String, dynamic>);
  }

  Future<List<PaperPosition>> getPositions() async {
    final uri = baseUri.resolve('/api/v1/paper/positions');
    final response = await _client.get(uri, headers: await _headers());
    final data = _unwrap(response, 200);
    return (data as List<dynamic>)
        .map((e) => PaperPosition.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<PaperOrder>> getOrders({int limit = 20}) async {
    final uri = baseUri.replace(
      path: '/api/v1/paper/orders',
      queryParameters: {'limit': limit.toString()},
    );
    final response = await _client.get(uri, headers: await _headers());
    final data = _unwrap(response, 200);
    return (data as List<dynamic>)
        .map((e) => PaperOrder.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<PaperOrder> submitOrder(PaperOrderRequest request) async {
    final uri = baseUri.resolve('/api/v1/paper/orders');
    final response = await _client.post(
      uri,
      headers: await _headers(),
      body: jsonEncode(request.toJson()),
    );
    // Backend returns 201 for new order, 200 for replayed idempotent order
    final data = _unwrap(response, [200, 201]);
    return PaperOrder.fromJson(data as Map<String, dynamic>);
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
    throw PaperTradingException(
      code: code,
      message: message,
      statusCode: response.statusCode,
    );
  }
}
