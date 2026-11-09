import 'dart:io';

import 'package:frontend_flutter/core/local_application/local_http_native.dart';
import 'package:http/http.dart' as http;

/// Isolated test process: no session, bearer, user data or external endpoint.
Future<void> main() async {
  final origin = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  var originRequests = 0;
  final subscription = origin.listen((request) async {
    originRequests++;
    request.response.write('synthetic-direct-origin');
    await request.response.close();
  });
  final client = createLocalHttpClient();
  try {
    final request = http.Request(
      'GET',
      Uri.parse('http://127.0.0.1:${origin.port}/synthetic-probe'),
    )..followRedirects = false;
    final response = await http.Response.fromStream(
      await client.send(request).timeout(const Duration(seconds: 3)),
    ).timeout(const Duration(seconds: 3));
    if (response.statusCode != 200 ||
        response.body != 'synthetic-direct-origin' ||
        originRequests != 1) {
      throw StateError('Synthetic request did not reach its loopback origin.');
    }
    stdout.writeln('SYNTHETIC_DIRECT_ORIGIN_CONFIRMED');
  } catch (_) {
    stderr.writeln('SYNTHETIC_LOCAL_TRANSPORT_NOT_DIRECT');
    exitCode = 1;
  } finally {
    client.close();
    await subscription.cancel();
    await origin.close(force: true);
  }
}
