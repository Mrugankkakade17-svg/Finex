import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('native local factory bypasses environment proxies', () async {
    final proxy = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    var proxyRequests = 0;
    final subscription = proxy.listen((request) async {
      proxyRequests++;
      request.response.statusCode = 502;
      request.response.write('synthetic-proxy-only');
      await request.response.close();
    });
    final configFile = File('.dart_tool/package_config.json').absolute;
    final config = jsonDecode(await configFile.readAsString()) as Map;
    final flutter = (config['packages'] as List).cast<Map>().firstWhere(
      (package) => package['name'] == 'flutter',
    );
    final root = flutter['rootUri'] as String;
    final flutterUri = configFile.uri.resolve(
      root.endsWith('/') ? root : '$root/',
    );
    final dart = flutterUri.resolve(
      '../../bin/cache/dart-sdk/bin/dart${Platform.isWindows ? '.exe' : ''}',
    );
    final syntheticProxy = 'http://127.0.0.1:${proxy.port}';
    Process? process;
    try {
      process = await Process.start(
        dart.toFilePath(),
        [
          '--packages=.dart_tool/package_config.json',
          'test/support/native_proxy_probe.dart',
        ],
        environment: {
          'HTTP_PROXY': syntheticProxy,
          'http_proxy': syntheticProxy,
          'HTTPS_PROXY': syntheticProxy,
          'https_proxy': syntheticProxy,
          'NO_PROXY': '',
          'no_proxy': '',
        },
      );
      final output = process.stdout.transform(utf8.decoder).join();
      final errors = process.stderr.transform(utf8.decoder).join();
      final status = await process.exitCode.timeout(
        const Duration(seconds: 15),
      );
      expect(
        proxyRequests,
        0,
        reason: 'Loopback requests must never reach a proxy.',
      );
      expect(status, 0, reason: await errors);
      expect(await output, contains('SYNTHETIC_DIRECT_ORIGIN_CONFIRMED'));
    } finally {
      process?.kill();
      await subscription.cancel();
      await proxy.close(force: true);
    }
  });
}
