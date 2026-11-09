import 'package:flutter/material.dart';

import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_s3_models.dart';
import '../../../core/local_application/local_s3_page.dart';

class LocalPaperAccountPage extends LocalS3Page {
  const LocalPaperAccountPage({super.key, required super.session});
  @override
  State<LocalPaperAccountPage> createState() => _LocalPaperAccountPageState();
}

class _LocalPaperAccountPageState
    extends LocalS3PageState<LocalPaperAccountPage> {
  LocalS3Reply<LocalPaperAccountState>? account;
  LocalS3Reply<LocalPaperLedger>? ledger;
  LocalApiException? ledgerError;
  @override
  void initState() {
    super.initState();
    afterFirstFrame(reload);
  }

  @override
  void onOwnerReplaced() {
    account = null;
    ledger = null;
    ledgerError = null;
    error = null;
    message = null;
    afterFirstFrame(reload);
  }

  Future<void> reload() async {
    final loaded = await request((scope) => scope.paperAccount(), (value) {
      account = value;
      ledger = null;
      ledgerError = null;
    });
    if (loaded && mounted && account?.value.account != null) await readLedger();
  }

  Future<void> readLedger() async {
    setState(() {
      ledger = null;
      ledgerError = null;
    });
    await request((scope) => scope.paperLedger(limit: 2), (value) {
      final current = account?.value.account;
      if (current == null ||
          value.value.accountId != current.id ||
          value.value.items.single.id != current.openingLedgerId ||
          value.value.items.single.createdAt != current.createdAt) {
        invalidLocalResponse();
      }
      ledger = value;
    });
    if (mounted) setState(() => ledgerError = error);
  }

  Future<void> open() async {
    final accepted = await request((scope) => scope.openPaperAccount(), (
      value,
    ) {
      final previous = account?.value.account;
      final actual = value.value.account!;
      if (previous != null &&
          (actual.id != previous.id ||
              actual.openingLedgerId != previous.openingLedgerId ||
              actual.createdAt != previous.createdAt)) {
        invalidLocalResponse();
      }
      account = value;
      ledger = null;
      message =
          'Simulated opening confirmed. This is not a deposit of real money.';
    });
    if (accepted && mounted) await readLedger();
  }

  @override
  Widget build(BuildContext context) => page('Simulated paper account', [
    const Text(
      'Reading an account never opens or funds it. One explicit educational opening creates USD 10000.00 simulated cash once.',
    ),
    button(
      'Reload simulated account state',
      reload,
      key: const Key('s3-account-reload'),
    ),
    if (account == null)
      const Text('No simulated account state has been confirmed yet.'),
    if (account != null && account!.value.account == null) ...[
      const Text('No simulated account has been opened.'),
      button(
        'Open simulated account once',
        open,
        key: const Key('s3-open-account'),
      ),
    ],
    if (account?.value.account != null) ...[
      Text(
        'Simulated cash balance: USD ${account!.value.account!.cashBalance}',
      ),
      Text(
        'Original simulated opening: USD ${account!.value.account!.openingCash}',
      ),
      Text('Opened: ${account!.value.account!.createdAt.toIso8601String()}'),
      Text('Account ID: ${account!.value.account!.id}'),
      const Text(
        'Opening ledger only. Orders, trades and goals remain pending Sprint 4; no real money is available.',
      ),
      button(
        'Reload immutable opening ledger',
        readLedger,
        key: const Key('s3-ledger-reload'),
      ),
      if (ledger == null)
        Text(
          ledgerError == null
              ? 'No opening ledger response has been confirmed yet.'
              : 'Opening ledger unavailable. Account state above remains last confirmed; retry the read.',
        ),
      if (ledger != null) ...[
        for (final item in ledger!.value.items)
          Text(
            'OPENING · sequence ${item.sequence} · USD ${item.cashDelta} · ${item.createdAt.toIso8601String()}',
          ),
        const Text('No further S3 ledger entries.'),
      ],
    ],
  ]);
}
