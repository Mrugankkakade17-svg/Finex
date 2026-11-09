import 'package:http/http.dart' as http;

import 'local_http_native.dart'
    if (dart.library.js_interop) 'local_http_web.dart'
    as platform;

/// Full-app requests never use a browser's ambient cookie authority.
http.Client createLocalHttpClient() => platform.createLocalHttpClient();
