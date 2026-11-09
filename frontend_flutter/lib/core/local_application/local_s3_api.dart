import 'local_s3_models.dart';

/// Composition-only transport. The session never exposes this adapter or bearer.
abstract interface class LocalS3Api {
  Future<LocalS3Reply<LocalMarketSearch>> marketSearch(
    String bearer, {
    String query = '',
    int limit = 20,
  });
  Future<LocalS3Reply<LocalMarketQuote>> marketQuote(
    String bearer,
    String instrument,
  );
  Future<LocalS3Reply<LocalWatchlistList>> watchlists(String bearer);
  Future<LocalS3Reply<LocalWatchlist>> watchlist(String bearer, String id);
  Future<LocalS3Reply<LocalWatchlist>> createWatchlist(
    String bearer,
    String name,
  );
  Future<LocalS3Reply<LocalWatchlist>> updateWatchlist(
    String bearer,
    String id,
    String name,
  );
  Future<LocalS3Reply<LocalWatchlistConfirmation>> deleteWatchlist(
    String bearer,
    String id,
  );
  Future<LocalS3Reply<LocalWatchlistItemSaved>> putWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  );
  Future<LocalS3Reply<LocalWatchlistConfirmation>> removeWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  );
  Future<LocalS3Reply<LocalPaperAccountState>> paperAccount(String bearer);
  Future<LocalS3Reply<LocalPaperAccountState>> openPaperAccount(String bearer);
  Future<LocalS3Reply<LocalPaperLedger>> paperLedger(
    String bearer, {
    int after = 0,
    int limit = 100,
  });
}

/// Typed revocable owner lease; no generic authenticated callback or token getter.
abstract interface class LocalS3Scope {
  bool get isCurrent;
  void dispose();
  Future<LocalS3Reply<LocalMarketSearch>> marketSearch({
    String query = '',
    int limit = 20,
  });
  Future<LocalS3Reply<LocalMarketQuote>> marketQuote(String instrument);
  Future<LocalS3Reply<LocalWatchlistList>> watchlists();
  Future<LocalS3Reply<LocalWatchlist>> watchlist(String id);
  Future<LocalS3Reply<LocalWatchlist>> createWatchlist(String name);
  Future<LocalS3Reply<LocalWatchlist>> updateWatchlist(String id, String name);
  Future<LocalS3Reply<LocalWatchlistConfirmation>> deleteWatchlist(String id);
  Future<LocalS3Reply<LocalWatchlistItemSaved>> putWatchlistItem(
    String parent,
    String instrument,
  );
  Future<LocalS3Reply<LocalWatchlistConfirmation>> removeWatchlistItem(
    String parent,
    String instrument,
  );
  Future<LocalS3Reply<LocalPaperAccountState>> paperAccount();
  Future<LocalS3Reply<LocalPaperAccountState>> openPaperAccount();
  Future<LocalS3Reply<LocalPaperLedger>> paperLedger({
    int after = 0,
    int limit = 100,
  });
}
