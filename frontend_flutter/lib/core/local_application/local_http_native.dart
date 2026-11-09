import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

// Never send local bearer authority through ambient environment proxies.
// IOClient has no cookie jar or cache; each API request disables redirects.
http.Client createLocalHttpClient() =>
    IOClient(HttpClient()..findProxy = (_) => 'DIRECT');
