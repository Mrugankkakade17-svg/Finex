import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'core/local_application/local_api_client.dart';
import 'core/local_application/local_models.dart';
import 'core/local_application/local_session.dart';
import 'core/local_application/local_s2_api.dart';
import 'core/local_application/local_s3_api.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

void main() {
  runApp(const FinExApp());
}

class FinExApp extends StatefulWidget {
  final LocalApplicationApi? api;
  final LocalS2Api? s2Api;
  final LocalS3Api? s3Api;
  final LocalSession? session;
  final String initialLocation;
  const FinExApp({
    super.key,
    this.api,
    this.s2Api,
    this.s3Api,
    this.session,
    this.initialLocation = '/',
  });

  @override
  State<FinExApp> createState() => _FinExAppState();
}

class _FinExAppState extends State<FinExApp> {
  LocalApplicationApi? _ownedApi;
  late LocalSession _session;
  late GoRouter _router;
  bool _ownsSession = false;

  @override
  void initState() {
    super.initState();
    _createResources();
  }

  void _createResources() {
    _ownedApi = null;
    _ownsSession = widget.session == null;
    if (widget.session != null) {
      _session = widget.session!;
    } else {
      LocalApplicationApi api;
      try {
        api = widget.api ?? HttpLocalApplicationApi.fromEnvironment();
      } on LocalApiException catch (error) {
        api = UnavailableLocalApplicationApi(error);
      }
      if (widget.api == null) _ownedApi = api;
      _session = LocalSession(
        api: api,
        s2Api: widget.s2Api ?? (api is HttpLocalApplicationApi ? api : null),
        s3Api: widget.s3Api ?? (api is HttpLocalApplicationApi ? api : null),
      );
    }
    _router = AppRouter.create(
      _session,
      initialLocation: widget.initialLocation,
    );
  }

  @override
  void didUpdateWidget(covariant FinExApp oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, widget.session) ||
        (widget.session == null &&
            (!identical(oldWidget.api, widget.api) ||
                !identical(oldWidget.s2Api, widget.s2Api) ||
                !identical(oldWidget.s3Api, widget.s3Api)))) {
      _disposeResources();
      _createResources();
    }
  }

  void _disposeResources() {
    _router.dispose();
    if (_ownsSession) _session.dispose();
    _ownedApi?.close();
  }

  @override
  void dispose() {
    _disposeResources();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      key: ObjectKey(_router),
      title: 'FinEx',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      routerConfig: _router,
    );
  }
}
