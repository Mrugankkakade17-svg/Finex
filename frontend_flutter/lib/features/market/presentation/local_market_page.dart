import 'package:flutter/material.dart';

import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_s3_models.dart';
import '../../../core/local_application/local_s3_page.dart';

class LocalMarketPage extends LocalS3Page {
  const LocalMarketPage({super.key, required super.session});
  @override
  State<LocalMarketPage> createState() => _LocalMarketPageState();
}

class _LocalMarketPageState extends LocalS3PageState<LocalMarketPage> {
  final query = TextEditingController();
  LocalS3Reply<LocalMarketSearch>? results;
  LocalS3Reply<LocalMarketQuote>? quote;
  String? selected;
  @override
  void initState() {
    super.initState();
    afterFirstFrame(search);
  }

  @override
  void onOwnerReplaced() {
    query.clear();
    results = null;
    quote = null;
    selected = null;
    error = null;
    message = null;
    afterFirstFrame(search);
  }

  void changedQuery(String _) {
    invalidateWork();
    setState(() {
      quote = null;
      selected = null;
      error = null;
      message = null;
    });
  }

  Future<void> search() async {
    String normalized;
    try {
      normalized = localS3Query(query.text);
    } on LocalApiException catch (value) {
      showError(value);
      return;
    }
    await request((scope) => scope.marketSearch(query: normalized), (value) {
      results = value;
      quote = null;
      selected = null;
    });
  }

  Future<void> readQuote(String id) async {
    setState(() {
      quote = null;
      selected = id;
    });
    await request((scope) => scope.marketQuote(id), (value) => quote = value);
  }

  @override
  Widget build(
    BuildContext context,
  ) => page('Supported synthetic instruments', [
    TextField(
      key: const Key('s3-search-query'),
      controller: query,
      decoration: const InputDecoration(
        labelText: 'Search supported instrument ID or display name',
      ),
      onChanged: changedQuery,
      onSubmitted: (_) => search(),
    ),
    button('Search supported catalogue', search, key: const Key('s3-search')),
    if (results == null)
      const Text('No catalogue response has been confirmed yet.'),
    if (results != null) ...[
      Text(
        'Confirmed query: ${results!.value.query.isEmpty ? '(all supported instruments)' : results!.value.query}',
      ),
      Text(
        'Catalogue: synthetic_catalog.v1 · ${results!.dataStatus} · fixture ${results!.dataAsOf!.toIso8601String()}',
      ),
      if (results!.value.items.isEmpty)
        const Text('No supported instruments match this search.'),
      for (final item in results!.value.items) ...[
        Text('${item.instrumentId} · ${item.displayName}'),
        Text('${item.assetClass} · ${item.sector} · USD'),
        button(
          'Read synthetic quote for ${item.instrumentId}',
          () => readQuote(item.instrumentId),
          key: Key('s3-quote-${item.instrumentId}'),
        ),
      ],
    ],
    if (selected != null && quote == null && !busy)
      button(
        'Retry selected synthetic quote',
        () => readQuote(selected!),
        key: const Key('s3-quote-retry'),
      ),
    if (quote != null) ...[
      Text('Quote for ${quote!.value.instrumentId}'),
      Text('Status: ${quote!.value.status}'),
      Text(
        quote!.value.unitPrice == null
            ? 'Price unavailable — no zero price assumed.'
            : 'USD ${quote!.value.unitPrice}',
      ),
      const Text(
        'Source: finex.synthetic.portfolio · SYNTHETIC · synthetic_quotes.v1',
      ),
      const Text(
        'Fixture timestamp: 2026-01-01T00:00:00Z (not a current market price)',
      ),
      if (quote!.value.fetchedAt != null)
        Text('Retrieved: ${quote!.value.fetchedAt!.toIso8601String()}'),
      if (quote!.value.cacheExpiresAt != null)
        Text(
          'Cache expires: ${quote!.value.cacheExpiresAt!.toIso8601String()}',
        ),
      if (quote!.value.reason != null) Text('Reason: ${quote!.value.reason}'),
      button(
        'Refresh selected synthetic quote',
        () => readQuote(quote!.value.instrumentId),
      ),
    ],
  ]);
  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }
}
