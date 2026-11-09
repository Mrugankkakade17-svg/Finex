import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    '262KiB cap rejects oversized active stream before a stalled EOF',
    () async {
      final stream = StreamController<List<int>>();
      final api = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:8082'),
        timeout: const Duration(milliseconds: 60),
        client: MockClient.streaming(
          (_, _) async => http.StreamedResponse(stream.stream, 200),
        ),
      );
      addTearDown(() {
        api.close();
        unawaited(stream.close());
      });
      final request = api.state('shape-only');
      stream.add(List.filled(262145, 32));
      await expectLater(
        request,
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'bounded body rejection',
            'INVALID_API_RESPONSE',
          ),
        ),
      );
    },
  );
}
