import 'package:flutter/material.dart';

import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_view.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_view.dart';
import '../models/market_models.dart';
import '../services/market_service.dart';

class WatchlistPage extends StatefulWidget {
  const WatchlistPage({super.key});

  @override
  State<WatchlistPage> createState() => _WatchlistPageState();
}

class _WatchlistPageState extends State<WatchlistPage> {
  final _marketService = MarketService();

  bool _loading = true;
  String? _error;
  List<WatchlistItem>? _items;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final result = await _marketService.getWatchlist();
      setState(() => _items = result);
    } catch (e) {
      setState(() => _error = 'Unable to load your watchlist right now.');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _remove(String symbol) async {
    final updated = await _marketService.removeFromWatchlist(symbol);
    setState(() => _items = updated);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Watchlist'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _load,
          ),
        ],
      ),
      body: SafeArea(
        child: _buildBody(context),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const LoadingView(
        key: Key('watchlist-loading'),
        message: 'Loading your watchlist…',
      );
    }

    if (_error != null) {
      return ErrorView(
        key: const Key('watchlist-error'),
        message: _error!,
        onRetry: _load,
      );
    }

    final items = _items ?? const [];

    if (items.isEmpty) {
      return const EmptyView(
        key: Key('watchlist-empty'),
        title: 'Your watchlist is empty',
        message: 'Search for a security to add one.',
        icon: Icons.star_outline,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(20),
      itemCount: items.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final item = items[index];
        return AppCard(
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.symbol,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    Text(
                      item.name,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline),
                tooltip: 'Remove ${item.symbol} from watchlist',
                onPressed: () => _remove(item.symbol),
              ),
            ],
          ),
        );
      },
    );
  }
}
