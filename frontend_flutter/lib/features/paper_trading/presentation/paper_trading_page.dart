import 'dart:math';

import 'package:flutter/material.dart';

import '../../../core/local_application/local_session.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_view.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_view.dart';
import '../models/paper_trading_models.dart';
import '../services/paper_trading_service.dart';

class PaperTradingPage extends StatefulWidget {
  final LocalSession? session;
  final PaperTradingService? service;

  const PaperTradingPage({super.key, this.session, this.service});

  @override
  State<PaperTradingPage> createState() => _PaperTradingPageState();
}

class _PaperTradingPageState extends State<PaperTradingPage> {
  late PaperTradingService _service;

  // Account & data state
  bool _loading = true;
  String? _errorMessage;
  PaperAccount? _account;

  // Order form state
  final _symbolController = TextEditingController(text: 'AAPL');
  final _quantityController = TextEditingController(text: '10');
  String _selectedSide = 'BUY';
  String _selectedExchange = 'NASDAQ';
  bool _submitting = false;
  String? _validationError;
  String? _orderError;
  String? _successMessage;

  // Idempotency management: preserves logical order key for safe retries
  String? _currentIdempotencyKey;
  PaperOrderRequest? _lastAttemptedRequest;

  @override
  void initState() {
    super.initState();
    _initService();
    _loadAccount();
  }

  void _initService() {
    if (widget.service != null) {
      _service = widget.service!;
    } else {
      _service = PaperTradingService();
    }
  }

  @override
  void dispose() {
    _symbolController.dispose();
    _quantityController.dispose();
    super.dispose();
  }

  String _generateIdempotencyKey(String symbol, String side) {
    final now = DateTime.now().millisecondsSinceEpoch;
    final rand = Random().nextInt(999999);
    return 'pt-$symbol-$side-$now-$rand';
  }

  Future<void> _loadAccount() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      final account = await _service.getAccount();
      if (!mounted) return;
      setState(() {
        _account = account;
        _loading = false;
      });
    } on PaperTradingException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '${e.code}: ${e.message}';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to connect to paper trading service.';
        _loading = false;
      });
    }
  }

  Future<void> _submitOrder({bool isRetry = false}) async {
    // Prevent duplicate submission while busy
    if (_submitting) return;

    setState(() {
      _validationError = null;
      _orderError = null;
      _successMessage = null;
    });

    final symbol = _symbolController.text.trim().toUpperCase();
    final qtyText = _quantityController.text.trim();
    final qty = int.tryParse(qtyText);

    if (symbol.isEmpty) {
      setState(() => _validationError = 'Please enter an instrument symbol.');
      return;
    }
    if (qty == null || qty <= 0) {
      setState(() => _validationError = 'Quantity must be a positive integer.');
      return;
    }
    if (qty > 100000) {
      setState(
        () => _validationError = 'Quantity cannot exceed 100,000 shares.',
      );
      return;
    }

    // Reuse idempotency key on retry, or generate new one for fresh order
    final idempotencyKey = (isRetry && _currentIdempotencyKey != null)
        ? _currentIdempotencyKey!
        : _generateIdempotencyKey(symbol, _selectedSide);

    final request = PaperOrderRequest(
      instrumentId: symbol,
      exchange: _selectedExchange,
      side: _selectedSide,
      quantity: qty,
      idempotencyKey: idempotencyKey,
    );

    setState(() {
      _submitting = true;
      _currentIdempotencyKey = idempotencyKey;
      _lastAttemptedRequest = request;
    });

    try {
      final order = await _service.submitOrder(request);
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _currentIdempotencyKey = null; // Reset on success
        _lastAttemptedRequest = null;
        _successMessage =
            'Order Confirmed: ${order.side} ${order.quantity} ${order.instrumentId} @ \$${order.executedPrice.toStringAsFixed(2)} (${order.quoteFreshness})';
      });
      // Refresh account balances and positions after successful order
      await _loadAccount();
    } on PaperTradingException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _orderError = '${e.code}: ${e.message}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _orderError = 'Order submission failed due to a network error. You can safely retry without placing a duplicate order.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Simulated Paper Trading'),
        actions: [
          IconButton(
            key: const Key('paper-refresh-btn'),
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh account',
            onPressed: _submitting ? null : _loadAccount,
          ),
        ],
      ),
      body: SafeArea(child: _buildContent()),
    );
  }

  Widget _buildContent() {
    if (_loading && _account == null) {
      return const LoadingView(message: 'Loading paper account...');
    }

    if (_errorMessage != null && _account == null) {
      return ErrorView(message: _errorMessage!, onRetry: _loadAccount);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildEducationalBanner(),
          const SizedBox(height: 16),
          if (_account != null) _buildAccountSummary(_account!),
          const SizedBox(height: 16),
          _buildOrderEntryCard(),
          const SizedBox(height: 16),
          if (_account != null) _buildPositionsCard(_account!.positions),
          const SizedBox(height: 16),
          if (_account != null) _buildOrderHistoryCard(_account!.recentOrders),
        ],
      ),
    );
  }

  Widget _buildEducationalBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: Color(0xFF38BDF8), size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                Text(
                  'Educational Simulation Only',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color: Color(0xFFF1F5F9),
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'This account uses simulated paper money with zero real-money risk or broker execution. Quotes reflect real-time or delayed educational feeds.',
                  style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAccountSummary(PaperAccount account) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Account Overview (${account.currency})',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _metricTile(
                  label: 'Cash Balance',
                  value: '\$${account.cashBalance.toStringAsFixed(2)}',
                  key: const Key('paper-cash-balance'),
                ),
              ),
              Expanded(
                child: _metricTile(
                  label: 'Portfolio Value',
                  value: '\$${account.portfolioValue.toStringAsFixed(2)}',
                  key: const Key('paper-portfolio-value'),
                ),
              ),
              Expanded(
                child: _metricTile(
                  label: 'Total Equity',
                  value: '\$${account.totalEquity.toStringAsFixed(2)}',
                  key: const Key('paper-total-equity'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metricTile({required String label, required String value, Key? key}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          key: key,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: Color(0xFFF8FAFC),
          ),
        ),
      ],
    );
  }

  Widget _buildOrderEntryCard() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Place Paper Order',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          // Side selection (BUY / SELL)
          Row(
            children: [
              Expanded(
                child: ChoiceChip(
                  key: const Key('paper-buy-chip'),
                  label: const Center(
                    child: Text(
                      'BUY',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ),
                  selected: _selectedSide == 'BUY',
                  selectedColor: const Color(0xFF059669),
                  onSelected: (selected) {
                    if (selected) setState(() => _selectedSide = 'BUY');
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ChoiceChip(
                  key: const Key('paper-sell-chip'),
                  label: const Center(
                    child: Text(
                      'SELL',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ),
                  selected: _selectedSide == 'SELL',
                  selectedColor: const Color(0xFFDC2626),
                  onSelected: (selected) {
                    if (selected) setState(() => _selectedSide = 'SELL');
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          // Instrument Symbol
          TextField(
            key: const Key('paper-symbol-input'),
            controller: _symbolController,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: 'Symbol',
              hintText: 'e.g. AAPL, SPY, MSFT',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          // Quick Symbol Selector
          Wrap(
            spacing: 8,
            children: ['AAPL', 'SPY', 'MSFT', 'NVDA', 'GOOGL'].map((sym) {
              return ActionChip(
                label: Text(sym, style: const TextStyle(fontSize: 11)),
                onPressed: () => setState(() => _symbolController.text = sym),
              );
            }).toList(),
          ),
          const SizedBox(height: 14),
          // Quantity and Exchange
          Row(
            children: [
              Expanded(
                flex: 2,
                child: TextField(
                  key: const Key('paper-quantity-input'),
                  controller: _quantityController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Quantity',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: DropdownButtonFormField<String>(
                  key: const Key('paper-exchange-dropdown'),
                  initialValue: _selectedExchange,
                  decoration: const InputDecoration(
                    labelText: 'Exchange',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'NASDAQ', child: Text('NASDAQ')),
                    DropdownMenuItem(value: 'NYSE', child: Text('NYSE')),
                  ],
                  onChanged: (val) {
                    if (val != null) setState(() => _selectedExchange = val);
                  },
                ),
              ),
            ],
          ),
          if (_validationError != null) ...[
            const SizedBox(height: 12),
            Text(
              _validationError!,
              key: const Key('paper-validation-error'),
              style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13),
            ),
          ],
          if (_orderError != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFF450A0A),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFFB91C1C)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      _orderError!,
                      key: const Key('paper-order-error'),
                      style: const TextStyle(
                        color: Color(0xFFFCA5A5),
                        fontSize: 13,
                      ),
                    ),
                  ),
                  if (_lastAttemptedRequest != null) ...[
                    const SizedBox(height: 8),
                    TextButton.icon(
                      key: const Key('paper-retry-order-btn'),
                      onPressed: _submitting
                          ? null
                          : () => _submitOrder(isRetry: true),
                      icon: const Icon(Icons.refresh, size: 16),
                      label: const Text('Safe Retry (Reusing Key)'),
                    ),
                  ],
                ],
              ),
            ),
          ],
          if (_successMessage != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFF064E3B),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFF059669)),
              ),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _successMessage!,
                  key: const Key('paper-order-success'),
                  style: const TextStyle(
                    color: Color(0xFFA7F3D0),
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),
          AppButton(
            key: const Key('paper-submit-order-btn'),
            label: _submitting
                ? 'Submitting Order...'
                : 'Submit $_selectedSide Order',
            loading: _submitting,
            onPressed: _submitting ? null : () => _submitOrder(isRetry: false),
          ),
        ],
      ),
    );
  }

  Widget _buildPositionsCard(List<PaperPosition> positions) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Holdings & Positions',
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              Text(
                '${positions.length} position(s)',
                style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (positions.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: EmptyView(
                title: 'No Open Positions',
                message: 'Execute a paper order above to open your first simulated position.',
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: positions.length,
              separatorBuilder: (_, _) => const Divider(height: 16),
              itemBuilder: (context, idx) {
                final pos = positions[idx];
                final pnlColor = pos.unrealizedPnl >= 0
                    ? const Color(0xFF10B981)
                    : const Color(0xFFEF4444);
                return Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${pos.instrumentId} (${pos.exchange})',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${pos.quantity} shares @ avg \$${pos.averageCost.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF94A3B8),
                          ),
                        ),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '\$${pos.marketValue.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${pos.unrealizedPnl >= 0 ? '+' : ''}\$${pos.unrealizedPnl.toStringAsFixed(2)}',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: pnlColor,
                          ),
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _buildOrderHistoryCard(List<PaperOrder> orders) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Recent Orders',
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              Text(
                '${orders.length} order(s)',
                style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (orders.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: EmptyView(
                title: 'No Orders Yet',
                message: 'Your recent simulated trade fills will appear here.',
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: orders.length,
              separatorBuilder: (_, _) => const Divider(height: 16),
              itemBuilder: (context, idx) {
                final ord = orders[idx];
                final isBuy = ord.side.toUpperCase() == 'BUY';
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: isBuy
                                    ? const Color(0xFF065F46)
                                    : const Color(0xFF991B1B),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                ord.side,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              '${ord.quantity}x ${ord.instrumentId}',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFF334155),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            ord.quoteFreshness,
                            style: const TextStyle(
                              color: Color(0xFF38BDF8),
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Price: \$${ord.executedPrice.toStringAsFixed(2)} | Fee: \$${ord.fee.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontSize: 11,
                            color: Color(0xFF94A3B8),
                          ),
                        ),
                        Text(
                          'Total: \$${ord.notional.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}
