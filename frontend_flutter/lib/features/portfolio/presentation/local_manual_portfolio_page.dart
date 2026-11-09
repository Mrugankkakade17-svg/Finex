import 'package:flutter/material.dart';

import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_s2_models.dart';
import '../../../core/local_application/local_s2_page.dart';
import '../../../core/local_application/local_session.dart';
import '../../../shared/widgets/app_card.dart';

class LocalManualPortfolioPage extends StatefulWidget {
  final LocalSession session;
  const LocalManualPortfolioPage({super.key, required this.session});
  @override
  State<LocalManualPortfolioPage> createState() =>
      _LocalManualPortfolioPageState();
}

class _LocalManualPortfolioPageState
    extends LocalS2PageState<LocalManualPortfolioPage> {
  @override
  LocalSession get session => widget.session;
  final _name = TextEditingController();
  final _description = TextEditingController();
  final _quantity = TextEditingController();
  final _cost = TextEditingController();
  final _nameFocus = FocusNode();
  final _descriptionFocus = FocusNode();
  final _quantityFocus = FocusNode();
  final _costFocus = FocusNode();
  final _instrumentFocus = FocusNode();
  final _portfolioForm = GlobalKey<FormState>();
  final _holdingForm = GlobalKey<FormState>();
  LocalPortfolioList? _list;
  LocalInstrumentCatalog? _catalog;
  LocalPortfolio? _selected;
  LocalPortfolio? _editing;
  LocalHoldingList? _holdings;
  LocalPortfolioMetrics? _metrics;
  LocalHolding? _editingHolding;
  String? _instrument;
  bool _portfolioUncertain = false;
  bool _portfolioReconciled = false;
  bool _holdingUncertain = false;
  bool _holdingReconciled = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _quantity.dispose();
    _cost.dispose();
    _nameFocus.dispose();
    _descriptionFocus.dispose();
    _quantityFocus.dispose();
    _costFocus.dispose();
    _instrumentFocus.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (!mounted || busy || session.isBusy || !session.canAccessFeatures) {
      return;
    }
    setState(() {
      _list = null;
      _catalog = null;
      _metrics = null;
      _holdings = null;
    });
    final accepted = await request((scope) => scope.portfolios(), (value) {
      _list = value.value;
      if (_portfolioUncertain) _portfolioReconciled = true;
      if (_selected != null &&
          !_list!.items.any((p) => p.portfolioId == _selected!.portfolioId)) {
        _selected = null;
        _editing = null;
        _editingHolding = null;
      }
      message = 'Owned portfolios loaded. Read the saved list before retrying an uncertain create.';
    });
    if (accepted && _selected != null) await _select(_selected!);
    if (accepted) await _reloadCatalogue();
  }

  Future<void> _reloadCatalogue() async {
    if (!mounted || busy || session.isBusy || !session.canAccessFeatures) {
      return;
    }
    setState(() => _catalog = null);
    await request((scope) => scope.instruments(), (value) {
      _catalog = value.value;
      message = 'Synthetic instrument catalogue confirmed for new holdings.';
    });
  }

  Future<void> _select(LocalPortfolio portfolio) async {
    if (!mounted || busy || session.isBusy || !session.canAccessFeatures) {
      return;
    }
    if (_holdingUncertain && _selected?.portfolioId != portfolio.portfolioId) {
      showError(const LocalApiException('CREATE_RECONCILE_REQUIRED'));
      return;
    }
    setState(() {
      if (_selected?.portfolioId != portfolio.portfolioId) {
        _editingHolding = null;
        _instrument = null;
        _quantity.clear();
        _cost.clear();
      }
      _selected = portfolio;
      _holdings = null;
      _metrics = null;
    });
    final accepted = await request(
      (scope) async => (
        (await scope.portfolio(portfolio.portfolioId)).value,
        (await scope.holdings(portfolio.portfolioId)).value,
      ),
      (value) {
        _selected = value.$1;
        _holdings = value.$2;
        if (_holdingUncertain) _holdingReconciled = true;
        message =
            'Saved manual holdings confirmed. Valuation is checked separately.';
      },
    );
    if (accepted) await _reloadMetrics(portfolio.portfolioId);
  }

  Future<void> _reloadMetrics(String portfolioId) async {
    if (!mounted ||
        busy ||
        session.isBusy ||
        !session.canAccessFeatures ||
        _selected?.portfolioId != portfolioId ||
        _holdings?.portfolioId != portfolioId) {
      return;
    }
    // Confirmed manual records survive a quote/storage fault. Never retain a
    // previous valuation while a new calculation is unconfirmed, and keep the
    // optional read under the same owner/page lifetime guards as every action.
    setState(() => _metrics = null);
    await request((scope) => scope.metrics(portfolioId), (value) {
      _metrics = value.value;
      message =
          'Backend-calculated valuation confirmed for the saved holdings.';
    });
  }

  Future<void> _savePortfolio() async {
    if (!_portfolioForm.currentState!.validate()) {
      _focusField(
        _name.text.trim().isEmpty || _name.text.trim().runes.length > 100
            ? _nameFocus
            : _descriptionFocus,
      );
      return;
    }
    if (_editing == null && _portfolioUncertain) {
      showError(const LocalApiException('CREATE_RECONCILE_REQUIRED'));
      return;
    }
    final input = PortfolioInput(
      name: _name.text,
      description: _description.text.isEmpty ? null : _description.text,
    );
    final editing = _editing;
    if (editing == null) {
      _portfolioUncertain = true;
      _portfolioReconciled = false;
    }
    final accepted = await request(
      (scope) => editing == null
          ? scope.createPortfolio(input)
          : scope.updatePortfolio(editing.portfolioId, input),
      (value) {
        _portfolioUncertain = false;
        _portfolioReconciled = false;
        _editing = null;
        _name.clear();
        _description.clear();
        _selected = value.value;
        message = 'Portfolio saved on the server.';
      },
    );
    if (accepted) await _load();
  }

  Future<void> _saveHolding() async {
    if (_editingHolding == null && _catalog == null) {
      showError(
        const LocalApiException('LOCAL_CATALOG_UNAVAILABLE', status: 503),
      );
      return;
    }
    if (!_holdingForm.currentState!.validate()) {
      _focusField(
        _instrument == null
            ? _instrumentFocus
            : _quantityError(_quantity.text) != null
            ? _quantityFocus
            : _costFocus,
      );
      return;
    }
    final parent = _selected!;
    final editing = _editingHolding;
    if (editing == null && _holdingUncertain) {
      showError(const LocalApiException('CREATE_RECONCILE_REQUIRED'));
      return;
    }
    if (editing == null && _instrument == null) {
      showError(const LocalApiException('INSTRUMENT_REQUIRED'));
      return;
    }
    final input = HoldingInput(
      instrumentId: editing == null ? _instrument : null,
      quantity: _quantity.text,
      averageCost: _cost.text,
    );
    if (editing == null) {
      _holdingUncertain = true;
      _holdingReconciled = false;
    }
    final accepted = await request(
      (scope) => editing == null
          ? scope.createHolding(parent.portfolioId, input)
          : scope.updateHolding(parent.portfolioId, editing.holdingId, input),
      (value) {
        _holdingUncertain = false;
        _holdingReconciled = false;
        _editingHolding = null;
        _quantity.clear();
        _cost.clear();
        _instrument = null;
        message = 'Holding saved on the server.';
      },
    );
    if (accepted) await _select(parent);
  }

  Future<bool> _confirm(String text) async {
    if (busy || session.isBusy || !session.canAccessFeatures) return false;
    final intent = session.createS2Scope();
    var finished = false;
    BuildContext? dialogContext;
    void invalidate() {
      if (intent.isCurrent || finished) return;
      finished = true;
      final current = dialogContext;
      if (current != null && current.mounted) Navigator.of(current).pop(false);
    }

    session.addListener(invalidate);
    try {
      final answer = await showDialog<bool>(
        context: context,
        builder: (context) {
          dialogContext = context;
          return AlertDialog(
            title: const Text('Confirm deletion'),
            content: Text(text),
            actions: [
              TextButton(
                onPressed: () {
                  if (finished) return;
                  finished = true;
                  Navigator.pop(context, false);
                },
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () {
                  if (finished) return;
                  finished = true;
                  Navigator.pop(context, true);
                },
                child: const Text('Delete saved item'),
              ),
            ],
          );
        },
      );
      return answer == true &&
          mounted &&
          intent.isCurrent &&
          !busy &&
          !session.isBusy &&
          session.canAccessFeatures;
    } finally {
      session.removeListener(invalidate);
      intent.dispose();
    }
  }

  Future<void> _deletePortfolio(LocalPortfolio value) async {
    if (!await _confirm(
      'Delete ${value.name} and all of its saved holdings?',
    )) {
      return;
    }
    if (!mounted) return;
    final accepted = await request(
      (scope) => scope.deletePortfolio(value.portfolioId),
      (_) {
        _selected = null;
        _editing = null;
        _editingHolding = null;
        _holdings = null;
        _metrics = null;
        message = 'Deletion confirmed by the server.';
      },
    );
    if (accepted) await _load();
  }

  Future<void> _deleteHolding(LocalHolding value) async {
    if (!await _confirm(
      'Delete ${value.instrument.displayName} from this manual portfolio?',
    )) {
      return;
    }
    if (!mounted) return;
    final accepted = await request(
      (scope) => scope.deleteHolding(value.portfolioId, value.holdingId),
      (_) {
        _editingHolding = null;
        message = 'Holding deletion confirmed.';
      },
    );
    if (accepted && _selected != null) await _select(_selected!);
  }

  String? _quantityError(String? value) {
    try {
      canonicalLocalNumber(value ?? '', 6, positive: true);
      return null;
    } on LocalApiException {
      return 'Enter 0.000001–1000000 units, at most six decimal places; no sign or exponent.';
    }
  }

  void _focusField(FocusNode node) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      node.requestFocus();
      final field = node.context;
      if (field != null) {
        Scrollable.ensureVisible(
          field,
          duration: const Duration(milliseconds: 150),
          alignment: .1,
        );
      }
    });
  }

  String? _costError(String? value) {
    try {
      canonicalLocalNumber(value ?? '', 4, positive: false);
      return null;
    } on LocalApiException {
      return 'Enter 0–1000000 USD per unit, at most four decimal places; no sign or exponent.';
    }
  }

  String _money(String? value) => value == null ? 'Unavailable' : '$value USD';
  String _percent(String? value) =>
      value == null ? 'Unavailable / undefined' : '$value%';
  @override
  Widget build(BuildContext context) => page('Manual portfolios', [
    const Text(
      'Saved manual holdings in USD, not broker positions. Twenty portfolios per learner; one holding per supported instrument, up to 100 per portfolio. Prices are fixed synthetic fixtures, not market data.',
    ),
    button(
      'Reload saved portfolio list',
      _load,
      key: const Key('portfolio-reload'),
    ),
    if (_catalog == null)
      const Text('Catalogue not confirmed. New holdings are unavailable.'),
    button(
      _catalog == null
          ? 'Retry synthetic catalogue'
          : 'Refresh synthetic catalogue',
      _reloadCatalogue,
      key: const Key('catalogue-retry'),
      enabled: _list != null,
    ),
    if (_list != null && _list!.items.isEmpty)
      const Text('No saved portfolios yet.'),
    if (_list != null)
      for (final p in _list!.items)
        AppCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(p.name, style: Theme.of(context).textTheme.titleMedium),
              if (p.description != null) Text(p.description!),
              Text('USD • Updated UTC ${p.updatedAt.toIso8601String()}'),
              button('Open ${p.name}', () => _select(p)),
              button('Edit ${p.name}', () {
                setState(() {
                  _editing = p;
                  _name.text = p.name;
                  _description.text = p.description ?? '';
                });
              }, enabled: !_portfolioUncertain),
              button('Delete ${p.name}', () => _deletePortfolio(p)),
            ],
          ),
        ),
    const SizedBox(height: 16),
    Text(
      _editing == null ? 'Create a manual portfolio' : 'Edit saved portfolio',
      style: Theme.of(context).textTheme.titleLarge,
    ),
    Form(
      key: _portfolioForm,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            key: const Key('portfolio-name'),
            focusNode: _nameFocus,
            controller: _name,
            readOnly: busy,
            decoration: const InputDecoration(
              labelText: 'Portfolio name',
              helperText: 'Required synthetic label, up to 100 characters.',
            ),
            validator: (v) =>
                v == null || v.trim().isEmpty || v.trim().runes.length > 100
                ? 'Enter a synthetic name of 1–100 characters.'
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const Key('portfolio-description'),
            focusNode: _descriptionFocus,
            controller: _description,
            readOnly: busy,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Purpose / description (optional)',
              helperText:
                  'Synthetic educational purpose, up to 500 characters.',
            ),
            validator: (v) => (v?.trim().runes.length ?? 0) > 500
                ? 'Keep the description within 500 characters.'
                : null,
          ),
          button(
            _editing == null
                ? 'Create saved portfolio'
                : 'Save portfolio changes',
            _savePortfolio,
            key: const Key('portfolio-save'),
            enabled: _list != null,
          ),
          if (_editing != null)
            button('Cancel portfolio edit', () {
              setState(() {
                _editing = null;
                _name.clear();
                _description.clear();
              });
            }),
        ],
      ),
    ),
    if (_portfolioUncertain) ...[
      const Text(
        'Create is not idempotent. Confirmation is uncertain; input was kept. Reload the saved list and check whether this portfolio already exists before deliberately creating another.',
      ),
      button('I checked the list; allow a new portfolio create', () {
        setState(() {
          _portfolioUncertain = false;
          _portfolioReconciled = false;
        });
      }, enabled: _portfolioReconciled),
    ],
    if (_selected case final parent?) ...[
      const SizedBox(height: 24),
      Text(
        'Holdings: ${parent.name}',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      button(
        'Reload selected holdings and metrics',
        () => _select(parent),
        key: const Key('holding-reload'),
      ),
      if (_holdings != null && _holdings!.items.isEmpty)
        const Text('This portfolio has no saved holdings.'),
      if (_holdings != null)
        for (final h in _holdings!.items)
          AppCard(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${h.instrument.displayName} • ${h.instrument.instrumentId}',
                ),
                Text('${h.instrument.assetClass} • ${h.instrument.sector}'),
                Text(
                  'Quantity: ${h.quantity} units • Average cost: ${h.averageCost} USD per unit',
                ),
                button('Edit holding ${h.instrument.instrumentId}', () {
                  setState(() {
                    _editingHolding = h;
                    _quantity.text = h.quantity;
                    _cost.text = h.averageCost;
                    _instrument = h.instrument.instrumentId;
                  });
                }),
                button(
                  'Delete holding ${h.instrument.instrumentId}',
                  () => _deleteHolding(h),
                ),
              ],
            ),
          ),
      Text(
        _editingHolding == null ? 'Add a holding' : 'Edit holding amounts',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      Form(
        key: _holdingForm,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_catalog != null)
              DropdownButtonFormField<String>(
                focusNode: _instrumentFocus,
                key: ValueKey('holding-instrument-$_instrument'),
                initialValue: _instrument,
                isExpanded: true,
                onTap: watchOwnedPopup,
                decoration: const InputDecoration(
                  labelText: 'Supported synthetic instrument',
                  helperText:
                      'No market search; choose from the server catalogue.',
                ),
                items: [
                  for (final i in _catalog!.items)
                    DropdownMenuItem(
                      value: i.instrumentId,
                      child: Text(
                        '${i.instrumentId} • ${i.displayName}',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: busy || _editingHolding != null
                    ? null
                    : (value) {
                        if (!currentPopupIntent) return;
                        endOwnedPopup();
                        setState(() => _instrument = value);
                      },
                validator: (v) =>
                    v == null ? 'Choose a supported instrument.' : null,
              ),
            const SizedBox(height: 12),
            TextFormField(
              key: const Key('holding-quantity'),
              focusNode: _quantityFocus,
              controller: _quantity,
              readOnly: busy,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Quantity (units)',
                helperText:
                    'Required positive amount, up to six decimal places.',
              ),
              validator: _quantityError,
            ),
            const SizedBox(height: 12),
            TextFormField(
              key: const Key('holding-cost'),
              focusNode: _costFocus,
              controller: _cost,
              readOnly: busy,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Average cost (USD per unit)',
                helperText:
                    'Required nonnegative amount, up to four decimal places.',
              ),
              validator: _costError,
            ),
            button(
              _editingHolding == null
                  ? 'Create saved holding'
                  : 'Save holding changes',
              _saveHolding,
              key: const Key('holding-save'),
              enabled:
                  _holdings != null &&
                  (_editingHolding != null || _catalog != null),
            ),
            if (_editingHolding != null)
              button('Cancel holding edit', () {
                setState(() {
                  _editingHolding = null;
                  _instrument = null;
                  _quantity.clear();
                  _cost.clear();
                });
              }),
          ],
        ),
      ),
      if (_holdingUncertain) ...[
        const Text(
          'Holding create is not idempotent. Reload saved holdings before a deliberate retry. The first request may already have succeeded.',
        ),
        button('I checked holdings; allow a new holding create', () {
          setState(() {
            _holdingUncertain = false;
            _holdingReconciled = false;
          });
        }, enabled: _holdingReconciled),
      ],
      if (_holdings != null) ...[
        if (_metrics == null)
          const Text(
            'Valuation not confirmed. Saved manual holdings remain available.',
          ),
        button(
          _metrics == null
              ? 'Retry backend valuation'
              : 'Refresh backend valuation',
          () => _reloadMetrics(parent.portfolioId),
          key: const Key('metrics-retry'),
        ),
      ],
    ],
    if (_metrics case final metrics?)
      AppCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Backend portfolio metrics',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text('Valuation ${metrics.status} • Data ${metrics.dataStatus}'),
            const Text(
              'Source: finex.synthetic.portfolio • SYNTHETIC • synthetic_quotes.v1',
            ),
            const Text(
              'Fixture as of UTC: 2026-01-01T00:00:00Z (not refreshed market prices)',
            ),
            Text(
              'Response source time: ${metrics.dataAsOf?.toIso8601String() ?? 'Unavailable / not applicable'}',
            ),
            Text('Calculated UTC: ${metrics.calculatedAt.toIso8601String()}'),
            Text('Cost basis: ${_money(metrics.totals.costBasis)}'),
            Text('Market value: ${_money(metrics.totals.marketValue)}'),
            Text(
              'Gain / loss: ${_money(metrics.totals.gainLoss)} • ${_percent(metrics.totals.gainPercent)}',
            ),
            Text(
              'Largest-instrument concentration: ${_percent(metrics.totals.concentration)}',
            ),
            Text('HHI: ${metrics.totals.hhi ?? 'Unavailable / undefined'}'),
            Text(
              'Educational allocation spread: ${_percent(metrics.totals.spread)}',
            ),
            if (metrics.missingInstrumentIds.isNotEmpty)
              Text(
                'Missing synthetic quotes: ${metrics.missingInstrumentIds.join(', ')}. Overall values and allocations are unavailable; priced rows are not renormalized.',
              ),
            const Text('Allocation by asset class'),
            if (metrics.totals.assetAllocation == null)
              const Text('Unavailable')
            else
              for (final a in metrics.totals.assetAllocation!)
                Text(
                  '${a.group}: ${_money(a.marketValue)} • ${_percent(a.weightPercent)}',
                ),
            const Text('Allocation by sector'),
            if (metrics.totals.sectorAllocation == null)
              const Text('Unavailable')
            else
              for (final a in metrics.totals.sectorAllocation!)
                Text(
                  '${a.group}: ${_money(a.marketValue)} • ${_percent(a.weightPercent)}',
                ),
            for (final h in metrics.holdings)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${h.instrument.instrumentId} • ${h.instrument.displayName}',
                    ),
                    Text(
                      'Quote ${h.quote.status} • Unit price ${h.quote.unitPrice ?? 'Unavailable'} USD • As of ${h.quote.asOf?.toIso8601String() ?? 'Unavailable'}',
                    ),
                    if (h.quote.reason != null) Text(h.quote.reason!),
                    Text(
                      'Cost ${_money(h.costBasis)} • Value ${_money(h.marketValue)} • Gain/loss ${_money(h.gainLoss)} • ${_percent(h.gainPercent)} • Weight ${_percent(h.weightPercent)}',
                    ),
                  ],
                ),
              ),
            const Text(
              'Limits: synthetic quotes are not market data; manual holdings are not broker positions; spread describes allocation only; no fund look-through or suitability recommendation.',
            ),
          ],
        ),
      ),
  ]);
}
