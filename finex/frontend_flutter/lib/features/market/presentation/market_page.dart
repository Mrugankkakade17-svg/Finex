import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_view.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_view.dart';
import '../models/market_models.dart';
import '../services/market_service.dart';

class MarketPage extends StatefulWidget {
  const MarketPage({super.key});

  @override
  State<MarketPage> createState() => _MarketPageState();
}

class _MarketPageState extends State<MarketPage> {
  final _marketService = MarketService();
  final _queryController = TextEditingController();

  bool _searchLoading = false;
  String? _validationError;
  String? _searchError;
  List<MarketSecurity>? _results;

  MarketSecurity? _selectedSecurity;
  bool _quoteLoading = false;
  String? _quoteError;
  MarketQuote? _quote;

  final Set<String> _watchlistSymbols = {'AAPL'};

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _queryController.text.trim();

    setState(() {
      _validationError = null;
      _searchError = null;
    });

    if (query.isEmpty) {
      setState(() {
        _validationError = 'Enter a symbol or company name to search.';
        _results = null;
      });
      return;
    }

    setState(() => _searchLoading = true);

    try {
      final found = await _marketService.search(query);
      setState(() => _results = found);
    } catch (e) {
      setState(() {
        _searchError = 'Search is temporarily unavailable.';
        _results = null;
      });
    } finally {
      setState(() => _searchLoading = false);
    }
  }

  Future<void> _loadQuote(MarketSecurity security) async {
    setState(() {
      _selectedSecurity = security;
      _quote = null;
      _quoteError = null;
      _quoteLoading = true;
    });

    try {
      final result = await _marketService.getQuote(security.symbol);
      setState(() => _quote = result);
    } catch (e) {
      setState(() => _quoteError = 'PRICE_UNAVAILABLE');
    } finally {
      setState(() => _quoteLoading = false);
    }
  }

  Future<void> _addToWatchlist(MarketSecurity security) async {
    final updated = await _marketService.addToWatchlist(security);
    setState(() {
      _watchlistSymbols
        ..clear()
        ..addAll(updated.map((item) => item.symbol));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Market Search')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Search supported securities and view the latest available quote',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _queryController,
                      decoration: const InputDecoration(
                        labelText: 'Search',
                        hintText: 'Symbol or name (e.g. AAPL)',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onSubmitted: (_) => _search(),
                    ),
                  ),
                  const SizedBox(width: 12),
                  FilledButton(
                    onPressed: _search,
                    child: const Text('Search'),
                  ),
                ],
              ),
              if (_validationError != null) ...[
                const SizedBox(height: 12),
                _InlineMessage(
                  key: const Key('market-validation-error'),
                  message: _validationError!,
                  color: Colors.amber,
                ),
              ],
              if (_searchError != null) ...[
                const SizedBox(height: 12),
                _InlineMessage(
                  key: const Key('market-search-error'),
                  message: _searchError!,
                  color: Theme.of(context).colorScheme.error,
                  onRetry: _search,
                ),
              ],
              const SizedBox(height: 20),
              if (_searchLoading)
                const LoadingView(message: 'Searching securities…')
              else if (_results != null && _results!.isEmpty)
                const EmptyView(
                  title: 'No matches',
                  message: 'No supported securities matched your search.',
                  icon: Icons.search_off,
                )
              else if (_results != null && _results!.isNotEmpty)
                _buildResultsAndQuote(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResultsAndQuote(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Results', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        ..._results!.map((security) {
          final selected = _selectedSecurity?.securityId == security.securityId;
          return Padding(
            key: Key('market-result-${security.symbol}'),
            padding: const EdgeInsets.only(bottom: 8),
            child: AppCard(
              onTap: () => _loadQuote(security),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          security.symbol,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                color: selected ? AppTheme.primary : null,
                                fontWeight: FontWeight.bold,
                              ),
                        ),
                        Text(
                          security.name,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  Text(
                    security.exchange,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ],
              ),
            ),
          );
        }),
        const SizedBox(height: 20),
        Text('Latest Available Quote', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        if (_selectedSecurity == null)
          const Text('Select a security from the results to view its quote.')
        else if (_quoteLoading)
          const LoadingView(message: 'Loading quote…')
        else if (_quoteError != null)
          ErrorView(
            key: const Key('quote-unavailable'),
            title: 'Price unavailable',
            message:
                'Price unavailable for ${_selectedSecurity!.symbol}. The market data provider did not return a usable price.',
            onRetry: () => _loadQuote(_selectedSecurity!),
          )
        else if (_quote != null)
          _buildQuoteCard(context, _quote!)
      ],
    );
  }

  Widget _buildQuoteCard(BuildContext context, MarketQuote quote) {
    final isUnavailable = quote.dataStatus == DataStatus.unavailable;
    final isPositive = quote.changeValue >= 0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${quote.price.toStringAsFixed(2)} ${quote.currency}',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(width: 12),
              Icon(
                isPositive ? Icons.trending_up : Icons.trending_down,
                color: isPositive ? AppTheme.primary : Colors.redAccent,
                size: 18,
              ),
              Text(
                '${(quote.changePercent * 100).toStringAsFixed(2)}%',
                style: TextStyle(
                  color: isPositive ? AppTheme.primary : Colors.redAccent,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (isUnavailable)
            Container(
              key: const Key('quote-unavailable'),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withAlpha(20),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.red.withAlpha(80)),
              ),
              child: const Text(
                'Price unavailable. Try again shortly.',
                style: TextStyle(color: Colors.redAccent),
              ),
            )
          else
            Text(
              key: const Key('quote-freshness'),
              'Source: ${quote.source} • Status: ${quote.dataStatus.label} • As of ${TimeOfDay.fromDateTime(quote.dataAsOf).format(context)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          const SizedBox(height: 6),
          Text(
            'This is prototype educational data, not a guaranteed live feed.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _watchlistSymbols.contains(quote.symbol)
                ? null
                : () => _addToWatchlist(_selectedSecurity!),
            icon: const Icon(Icons.star_outline),
            label: Text(
              _watchlistSymbols.contains(quote.symbol) ? 'On Watchlist' : 'Add to Watchlist',
            ),
          ),
        ],
      ),
    );
  }
}

class _InlineMessage extends StatelessWidget {
  final String message;
  final Color color;
  final VoidCallback? onRetry;

  const _InlineMessage({
    super.key,
    required this.message,
    required this.color,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withAlpha(20),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withAlpha(80)),
        ),
        child: Row(
          children: [
            Expanded(child: Text(message, style: TextStyle(color: color))),
            if (onRetry != null)
              TextButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
          ],
        ),
      ),
    );
  }
}
