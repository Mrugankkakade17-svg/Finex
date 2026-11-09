import 'package:flutter/material.dart';

import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_s3_api.dart';
import '../../../core/local_application/local_s3_models.dart';
import '../../../core/local_application/local_s3_page.dart';

class LocalWatchlistsPage extends LocalS3Page {
  const LocalWatchlistsPage({super.key, required super.session});
  @override
  State<LocalWatchlistsPage> createState() => _LocalWatchlistsPageState();
}

class _LocalWatchlistsPageState extends LocalS3PageState<LocalWatchlistsPage> {
  final createName = TextEditingController();
  final editName = TextEditingController();
  LocalWatchlistList? lists;
  LocalWatchlist? selected;
  LocalMarketSearch? catalogue;
  LocalApiException? catalogueError;
  bool editDirty = false;
  bool uncertainCreate = false;
  bool reconciledList = false;
  LocalS3Scope? deletionIntent;
  @override
  void initState() {
    super.initState();
    afterFirstFrame(initialLoad);
  }

  @override
  void onOwnerReplaced() {
    createName.clear();
    clearSelection();
    lists = null;
    catalogue = null;
    catalogueError = null;
    uncertainCreate = false;
    reconciledList = false;
    error = null;
    message = null;
    afterFirstFrame(initialLoad);
  }

  @override
  void onLeaseInvalidated() {
    if (deletionIntent != null && !deletionIntent!.isCurrent) {
      deletionIntent!.dispose();
      deletionIntent = null;
      if (mounted) setState(() {});
    }
  }

  void clearSelection() {
    selected = null;
    editName.clear();
    editDirty = false;
    deletionIntent?.dispose();
    deletionIntent = null;
  }

  Future<void> initialLoad() async {
    await reloadLists();
    // A later independent catalogue read must not erase a failed list read.
    // Without a confirmed collection, keep the error and explicit list retry.
    if (mounted &&
        session.canAccessFeatures &&
        lists != null &&
        error == null) {
      await reloadCatalogue();
    }
  }

  Future<void> reloadCatalogue() async {
    final accepted = await request((scope) => scope.marketSearch(), (value) {
      catalogue = value.value;
      catalogueError = null;
    });
    if (!accepted && mounted && session.canAccessFeatures && error != null) {
      setState(() {
        catalogueError = error;
        catalogue = null;
      });
    }
  }

  Future<void> reloadLists() async {
    final id = selected?.summary.id;
    await request(
      (scope) async {
        var reply = await scope.watchlists();
        LocalWatchlist? fresh;
        if (id != null && reply.value.items.any((item) => item.id == id)) {
          try {
            fresh = (await scope.watchlist(id)).value;
          } on LocalApiException catch (value) {
            if (value.code != 'WATCHLIST_NOT_FOUND' || value.status != 404) {
              rethrow;
            }
            // A concurrent deletion after the list read is not a saved detail.
            // Reconcile the stale collection with one further owned read;
            // do not leave its now-missing resource advertised as selectable.
            // No mutation is replayed and the same revocable scope guards it.
            reply = await scope.watchlists();
          }
        }
        return (reply.value, fresh);
      },
      (value) {
        lists = value.$1;
        if (id != null) {
          if (value.$2 == null) {
            clearSelection();
          } else {
            selected = value.$2;
            if (!editDirty) editName.text = selected!.summary.name;
          }
        }
        if (uncertainCreate) reconciledList = true;
      },
    );
  }

  Future<void> select(String id) async {
    await request((scope) => scope.watchlist(id), (value) {
      clearSelection();
      selected = value.value;
      editName.text = value.value.summary.name;
    });
  }

  Future<void> create() async {
    if (busy || !session.canAccessFeatures) return;
    if (uncertainCreate) {
      showError(const LocalApiException('CREATE_RECONCILE_REQUIRED'));
      return;
    }
    String name;
    try {
      name = localS3Name(createName.text);
    } on LocalApiException catch (value) {
      showError(value);
      return;
    }
    setState(() {
      uncertainCreate = true;
      reconciledList = false;
    });
    final accepted = await request((scope) => scope.createWatchlist(name), (
      value,
    ) {
      clearSelection();
      selected = value.value;
      editName.text = value.value.summary.name;
      createName.clear();
      uncertainCreate = false;
      message = 'Watchlist creation confirmed saved.';
    });
    if (!accepted &&
        mounted &&
        session.canAccessFeatures &&
        ['VALIDATION_ERROR', 'WATCHLIST_LIMIT'].contains(error?.code)) {
      setState(() => uncertainCreate = false);
    }
    if (accepted && mounted) await reloadLists();
  }

  Future<void> rename() async {
    final id = selected?.summary.id;
    if (id == null) return;
    String name;
    try {
      name = localS3Name(editName.text);
    } on LocalApiException catch (value) {
      showError(value);
      return;
    }
    final accepted = await request((scope) => scope.updateWatchlist(id, name), (
      value,
    ) {
      selected = value.value;
      editName.text = value.value.summary.name;
      editDirty = false;
      message = 'Watchlist rename confirmed saved.';
    });
    if (accepted && mounted) await reloadLists();
  }

  Future<void> changeItem(String instrument, {required bool add}) async {
    final parent = selected?.summary.id;
    if (parent == null) return;
    final accepted = await request(
      (scope) async {
        if (add) {
          await scope.putWatchlistItem(parent, instrument);
        } else {
          await scope.removeWatchlistItem(parent, instrument);
        }
        // The mutation may succeed even if this subsequent read fails. Keep old
        // confirmed items and offer a read retry; never claim an unconfirmed list.
        return scope.watchlist(parent);
      },
      (value) {
        selected = value.value;
        message = add
            ? 'Supported instrument confirmed saved.'
            : 'Instrument removal confirmed.';
      },
    );
    if (accepted && mounted) await reloadLists();
  }

  void askDelete() {
    deletionIntent?.dispose();
    setState(() => deletionIntent = session.createS3Scope());
  }

  Future<void> delete() async {
    final parent = selected?.summary.id;
    if (parent == null || deletionIntent?.isCurrent != true) return;
    deletionIntent!.dispose();
    deletionIntent = null;
    final accepted = await request((scope) => scope.deleteWatchlist(parent), (
      _,
    ) {
      clearSelection();
      message = 'Watchlist deletion confirmed.';
    });
    if (accepted && mounted) await reloadLists();
  }

  @override
  Widget build(BuildContext context) => page('Owned watchlists', [
    button(
      'Reload saved watchlist list',
      reloadLists,
      key: const Key('s3-watchlists-reload'),
    ),
    TextField(
      key: const Key('s3-create-name'),
      controller: createName,
      enabled: !busy,
      decoration: const InputDecoration(
        labelText: 'New watchlist name (non-sensitive teaching label)',
      ),
    ),
    if (uncertainCreate) ...[
      const Text(
        'A previous create was not confirmed. Reload and review the saved list before deliberately creating another item.',
      ),
      if (reconciledList)
        button('I reviewed the owned list; allow a deliberate new create', () {
          setState(() {
            uncertainCreate = false;
            reconciledList = false;
          });
        }, key: const Key('s3-reconcile-create')),
    ],
    button(
      'Create owned watchlist',
      create,
      key: const Key('s3-create'),
      enabled: !uncertainCreate,
    ),
    if (lists == null)
      const Text('No watchlist collection response has been confirmed yet.'),
    if (lists != null && lists!.items.isEmpty)
      const Text('No owned watchlists saved yet.'),
    if (lists != null)
      for (final item in lists!.items) ...[
        Text(item.name),
        Text(
          'Saved instruments: ${item.itemCount} · updated ${item.updatedAt.toIso8601String()}',
        ),
        button(
          'View owned watchlist ${item.name}',
          () => select(item.id),
          key: Key('s3-select-${item.id}'),
        ),
      ],
    if (selected != null) ...[
      const Divider(),
      Text('Selected watchlist: ${selected!.summary.name}'),
      Text('Saved supported instruments: ${selected!.items.length}'),
      Text(
        'Created ${selected!.summary.createdAt.toIso8601String()} · updated ${selected!.summary.updatedAt.toIso8601String()}',
      ),
      TextField(
        key: const Key('s3-edit-name'),
        controller: editName,
        enabled: !busy,
        decoration: const InputDecoration(
          labelText: 'Rename selected watchlist',
        ),
        onChanged: (_) => editDirty = true,
      ),
      button('Save watchlist rename', rename, key: const Key('s3-rename')),
      button(
        'Reload selected watchlist',
        () => select(selected!.summary.id),
        key: const Key('s3-detail-reload'),
      ),
      for (final item in selected!.items) ...[
        Text(
          '${item.instrument.instrumentId} · ${item.instrument.displayName} · saved ${item.addedAt.toIso8601String()}',
        ),
        button(
          'Remove ${item.instrument.instrumentId} from selected watchlist',
          () => changeItem(item.instrument.instrumentId, add: false),
          key: Key('s3-remove-${item.instrument.instrumentId}'),
        ),
      ],
      if (catalogueError != null)
        const Text(
          'Instrument catalogue is unavailable. Owned list management remains available; no unsupported instrument is assumed.',
        ),
      button(
        'Reload supported instruments',
        reloadCatalogue,
        key: const Key('s3-watchlist-catalogue-reload'),
      ),
      if (catalogue != null)
        for (final item in catalogue!.items)
          button(
            'Add ${item.instrumentId} to selected watchlist',
            () => changeItem(item.instrumentId, add: true),
            key: Key('s3-add-${item.instrumentId}'),
          ),
      button(
        'Delete selected watchlist',
        askDelete,
        key: const Key('s3-delete'),
      ),
      if (deletionIntent?.isCurrent == true) ...[
        Text(
          'Confirm deletion of ${selected!.summary.name}? Paper account and other domains are preserved.',
        ),
        button(
          'Confirm watchlist deletion',
          delete,
          key: const Key('s3-confirm-delete'),
        ),
        button('Cancel deletion', () {
          setState(() {
            deletionIntent?.dispose();
            deletionIntent = null;
          });
        }),
      ],
    ],
  ]);
  @override
  void dispose() {
    deletionIntent?.dispose();
    createName.dispose();
    editName.dispose();
    super.dispose();
  }
}
