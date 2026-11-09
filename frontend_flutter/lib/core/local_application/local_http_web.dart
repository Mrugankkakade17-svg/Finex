import 'dart:async';
import 'dart:js_interop';

import 'package:http/http.dart' as http;
import 'package:web/web.dart' as web;

import 'local_models.dart';

@JS('fetch')
external JSPromise<web.Response> _fetch(
  web.RequestInfo input,
  web.RequestInit init,
);

http.Client createLocalHttpClient() => _CookieFreeClient();

/// Explicit `omit`, unlike BrowserClient's same-origin credential default.
class _CookieFreeClient extends http.BaseClient {
  final _active = <web.AbortController>{};
  bool _closed = false;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (_closed) throw http.ClientException('Local transport is closed.');
    final controller = web.AbortController();
    _active.add(controller);
    try {
      if (request case http.Abortable(:final abortTrigger?)) {
        unawaited(abortTrigger.then((_) => controller.abort()));
      }
      final body = await request.finalize().toBytes();
      final response = await _fetch(
        request.url.toString().toJS,
        web.RequestInit(
          method: request.method,
          headers: request.headers.jsify()! as web.HeadersInit,
          body: body.isEmpty ? null : body.toJS,
          credentials: 'omit',
          cache: 'no-store',
          redirect: 'error',
          signal: controller.signal,
        ),
      ).toDart;
      if (response.status == 401) {
        controller.abort();
        _active.remove(controller);
        return http.StreamedResponse(
          const Stream.empty(),
          401,
          request: request,
        );
      }
      final stream = response.body;
      if (stream == null) {
        _active.remove(controller);
        return http.StreamedResponse(
          const Stream.empty(),
          response.status,
          request: request,
          headers: {'content-type': response.headers.get('content-type') ?? ''},
        );
      }
      final reader = stream.getReader() as web.ReadableStreamDefaultReader;
      return http.StreamedResponse(
        _read(reader, controller),
        response.status,
        request: request,
        headers: {'content-type': response.headers.get('content-type') ?? ''},
      );
    } catch (_) {
      _active.remove(controller);
      controller.abort();
      // Never include a request URL, body, bearer or JS diagnostics in UI errors.
      throw http.ClientException('Local request could not be confirmed.');
    }
  }

  /// Do not arrayBuffer an untrusted response before the API's byte cap.
  /// This reader also bounds the upstream browser transport and cancels an
  /// oversized stream immediately, even if its sender never closes it.
  Stream<List<int>> _read(
    web.ReadableStreamDefaultReader reader,
    web.AbortController controller,
  ) async* {
    var count = 0;
    var complete = false;
    var cancelled = false;
    void cancel() {
      if (cancelled) return;
      cancelled = true;
      try {
        unawaited(
          reader.cancel().toDart.then<void>(
            (_) {},
            onError: (Object _, StackTrace _) {},
          ),
        );
      } catch (_) {
        /* safe cleanup only */
      }
    }

    try {
      while (true) {
        final result = await reader.read().toDart;
        if (result.done) {
          complete = true;
          break;
        }
        final bytes = (result.value as JSUint8Array).toDart;
        count += bytes.length;
        if (count > 262144) {
          cancel();
          controller.abort();
          throw const LocalApiException('INVALID_API_RESPONSE');
        }
        yield bytes;
      }
    } on LocalApiException {
      rethrow;
    } catch (_) {
      throw http.ClientException('Local response could not be confirmed.');
    } finally {
      if (!complete) cancel();
      try {
        reader.releaseLock();
      } catch (_) {
        /* no JS diagnostics */
      }
      _active.remove(controller);
    }
  }

  @override
  void close() {
    _closed = true;
    for (final controller in _active) {
      controller.abort();
    }
    _active.clear();
  }
}
