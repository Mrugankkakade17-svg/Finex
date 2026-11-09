import 'dart:async';

import 'package:flutter/foundation.dart';

import 'local_api_client.dart';
import 'local_models.dart';
import 'local_s2_api.dart';
import 'local_s2_models.dart';
import 'local_s3_api.dart';
import 'local_s3_models.dart';

/// A cold instance is signed out. Server data, not local flow flags, authorizes UI.
class LocalSession extends ChangeNotifier {
  final LocalApplicationApi _api;
  final LocalS2Api? _s2Api;
  final LocalS3Api? _s3Api;
  final DateTime Function() _clock;
  String? _bearer;
  LocalUser? _user;
  LocalOnboardingState? _onboarding;
  int _generation = 0;
  int _domainEpoch = 0;
  bool _disposed = false;
  bool _authBusy = false;
  bool _loadingState = false;
  bool _saving = false;
  Timer? _expiryTimer;
  LocalApiException? _authError;
  LocalApiException? _loadError;
  LocalApiException? _operationError;

  LocalSession({
    required this._api,
    this._s2Api,
    this._s3Api,
    DateTime Function()? clock,
  }) : _clock = clock ?? (() => DateTime.now().toUtc());

  /// Revocable typed operations, never a bearer or authenticated adapter getter.
  LocalS2Scope createS2Scope() =>
      _OwnedS2Scope(this, _generation, _domainEpoch);
  LocalS3Scope createS3Scope() =>
      _OwnedS3Scope(this, _generation, _domainEpoch);

  LocalUser? get user => _user;
  LocalOnboardingState? get onboarding => _onboarding;
  int get generation => _generation;
  bool get isAuthenticated => _bearer != null && _user != null;
  bool get isBusy => _authBusy || _loadingState || _saving;
  bool get authBusy => _authBusy;
  bool get loadingState => _loadingState;
  bool get saving => _saving;
  LocalApiException? get authError => _authError;
  LocalApiException? get loadError => _loadError;
  LocalApiException? get operationError => _operationError;
  bool get canAccessFeatures =>
      isAuthenticated &&
      !_authBusy &&
      !_loadingState &&
      !_saving &&
      _authError == null &&
      _loadError == null &&
      _operationError == null &&
      _onboarding?.canAccessFeatures == true;

  bool _current(int generation) => !_disposed && generation == _generation;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _clear({LocalApiException? reason}) {
    _generation++;
    _domainEpoch++;
    _expiryTimer?.cancel();
    _bearer = null;
    _user = null;
    _onboarding = null;
    _authBusy = false;
    _loadingState = false;
    _saving = false;
    _loadError = null;
    _operationError = null;
    _authError = reason;
    _notify();
  }

  Future<bool> signIn(String alias) async {
    if (_disposed) return false;
    if (isAuthenticated) {
      _authError = const LocalApiException('SIGN_OUT_FIRST');
      _notify();
      return false;
    }
    _clear();
    final generation = _generation;
    _authBusy = true;
    _notify();
    try {
      final login = await _api.login(alias);
      if (!_current(generation)) return false;
      if (login.user.alias != alias || !login.expiresAt.isAfter(_clock())) {
        throw const LocalApiException('INVALID_API_RESPONSE');
      }
      final checkedUser = await _api.me(login.accessToken);
      if (!_current(generation)) return false;
      if (checkedUser.id != login.user.id ||
          checkedUser.alias != login.user.alias) {
        throw const LocalApiException('INVALID_API_RESPONSE');
      }
      _bearer = login.accessToken;
      _user = checkedUser;
      _expiryTimer = Timer(login.expiresAt.difference(_clock()), () {
        if (_current(generation)) {
          _clear(reason: const LocalApiException('SESSION_INVALID'));
        }
      });
      _authBusy = false;
      await refreshOnboarding();
      return _current(generation) && isAuthenticated;
    } on LocalApiException catch (error) {
      if (_current(generation)) _clear(reason: error);
      return false;
    } on Exception {
      if (_current(generation)) {
        _clear(reason: const LocalApiException('API_UNAVAILABLE'));
      }
      return false;
    } finally {
      if (_current(generation)) {
        _authBusy = false;
        _notify();
      }
    }
  }

  Future<void> refreshOnboarding() async {
    final bearer = _bearer;
    if (_disposed || bearer == null || _loadingState || _saving || _authBusy) {
      return;
    }
    final generation = _generation;
    _domainEpoch++;
    _loadingState = true;
    _onboarding = null;
    _loadError = null;
    _operationError = null;
    _notify();
    try {
      final state = await _api.state(bearer);
      if (_current(generation)) {
        _onboarding = state;
        _authError = null;
      }
    } on LocalApiException catch (error) {
      if (_current(generation)) {
        if (error.status == 401) {
          _clear(reason: error);
        } else {
          _loadError = error;
        }
      }
    } on Exception {
      if (_current(generation)) {
        _loadError = const LocalApiException('API_UNAVAILABLE');
      }
    } finally {
      if (_current(generation)) {
        _loadingState = false;
        _notify();
      }
    }
  }

  Future<bool> _mutation(
    Future<LocalOnboardingState> Function(String) operation,
  ) async {
    final bearer = _bearer;
    if (_disposed || bearer == null || _saving || _loadingState || _authBusy) {
      return false;
    }
    final generation = _generation;
    _domainEpoch++;
    _saving = true;
    _operationError = null;
    _notify();
    try {
      final state = await operation(bearer);
      if (!_current(generation)) return false;
      _onboarding = state;
      _loadError = null;
      return true;
    } on LocalApiException catch (error) {
      if (_current(generation)) {
        if (error.status == 401) {
          _clear(reason: error);
        } else {
          _operationError = error;
          if (error.code == 'ONBOARDING_REQUIRED') _onboarding = null;
        }
      }
      return false;
    } on Exception {
      if (_current(generation)) {
        _operationError = const LocalApiException('API_UNAVAILABLE');
      }
      return false;
    } finally {
      if (_current(generation)) {
        _saving = false;
        _notify();
      }
    }
  }

  Future<bool> saveDraft({String? displayName, String? experienceLevel}) =>
      _mutation(
        (bearer) => _api.saveDraft(
          bearer,
          displayName: displayName,
          experienceLevel: experienceLevel,
        ),
      );
  Future<bool> recordConsent(bool accepted) =>
      _mutation((bearer) => _api.consent(bearer, accepted));
  Future<bool> complete() => _mutation(_api.complete);

  Future<bool> signOut() async {
    final bearer = _bearer;
    if (_disposed || bearer == null || _authBusy) return false;
    final generation = _generation;
    _domainEpoch++;
    _authBusy = true;
    _authError = null;
    _notify();
    try {
      await _api.logout(bearer);
      if (!_current(generation)) return false;
      _clear();
      return true;
    } on LocalApiException catch (error) {
      if (_current(generation)) {
        if (error.status == 401) {
          _clear(reason: error);
          return true;
        }
        _authError = error;
      }
      return false;
    } on Exception {
      if (_current(generation)) {
        _authError = const LocalApiException('API_UNAVAILABLE');
      }
      return false;
    } finally {
      if (_current(generation)) {
        _authBusy = false;
        _notify();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    _domainEpoch++;
    _expiryTimer?.cancel();
    _bearer = null;
    _user = null;
    _onboarding = null;
    super.dispose();
  }
}

class _OwnedS2Scope implements LocalS2Scope {
  final LocalSession _session;
  final int _ownerGeneration;
  final int _epoch;
  bool _disposed = false;
  _OwnedS2Scope(this._session, this._ownerGeneration, this._epoch);
  @override
  bool get isCurrent =>
      !_disposed &&
      !_session._disposed &&
      _ownerGeneration == _session._generation &&
      _epoch == _session._domainEpoch &&
      _session.isAuthenticated;
  @override
  void dispose() {
    _disposed = true;
  }

  Future<LocalS2Reply<T>> _run<T>(
    Future<LocalS2Reply<T>> Function(LocalS2Api, String) operation,
  ) async {
    if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
    if (!_session.canAccessFeatures) {
      throw const LocalApiException('ONBOARDING_REQUIRED', status: 409);
    }
    final api = _session._s2Api;
    if (api == null) throw const LocalApiException('FEATURE_UNAVAILABLE');
    final bearer = _session._bearer!;
    try {
      final result = await operation(api, bearer);
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      return result;
    } on LocalApiException catch (error) {
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      if (error.status == 401) {
        _session._clear(reason: error);
      } else if (error.code == 'ONBOARDING_REQUIRED' && error.status == 409) {
        _session._domainEpoch++;
        _session._onboarding = null;
        _session._operationError = error;
        _session._notify();
      }
      rethrow;
    } on Exception {
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      throw const LocalApiException('API_UNAVAILABLE');
    }
  }

  @override
  Future<LocalS2Reply<LocalRiskQuestionnaire>> riskQuestionnaire() =>
      _run((api, b) => api.riskQuestionnaire(b));
  @override
  Future<LocalS2Reply<LocalRiskDraft>> riskDraft() =>
      _run((api, b) => api.riskDraft(b));
  @override
  Future<LocalS2Reply<LocalRiskDraft>> saveRiskDraft(LocalRiskInput input) =>
      _run((api, b) => api.saveRiskDraft(b, input));
  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> assessRisk(
    LocalRiskInput input,
    String key,
  ) => _run((api, b) => api.assessRisk(b, input, key));
  @override
  Future<LocalS2Reply<LocalRiskHistory>> riskHistory({String? before}) =>
      _run((api, b) => api.riskHistory(b, before: before));
  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> riskAssessment(String id) =>
      _run((api, b) => api.riskAssessment(b, id));
  @override
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments() =>
      _run((api, b) => api.instruments(b));
  @override
  Future<LocalS2Reply<LocalPortfolioList>> portfolios() =>
      _run((api, b) => api.portfolios(b));
  @override
  Future<LocalS2Reply<LocalPortfolio>> portfolio(String id) =>
      _run((api, b) => api.portfolio(b, id));
  @override
  Future<LocalS2Reply<LocalPortfolio>> createPortfolio(PortfolioInput input) =>
      _run((api, b) => api.createPortfolio(b, input));
  @override
  Future<LocalS2Reply<LocalPortfolio>> updatePortfolio(
    String id,
    PortfolioInput input,
  ) => _run((api, b) => api.updatePortfolio(b, id, input));
  @override
  Future<LocalS2Reply<bool>> deletePortfolio(String id) =>
      _run((api, b) => api.deletePortfolio(b, id));
  @override
  Future<LocalS2Reply<LocalHoldingList>> holdings(String parent) =>
      _run((api, b) => api.holdings(b, parent));
  @override
  Future<LocalS2Reply<LocalHolding>> holding(String parent, String id) =>
      _run((api, b) => api.holding(b, parent, id));
  @override
  Future<LocalS2Reply<LocalHolding>> createHolding(
    String parent,
    HoldingInput input,
  ) => _run((api, b) => api.createHolding(b, parent, input));
  @override
  Future<LocalS2Reply<LocalHolding>> updateHolding(
    String parent,
    String id,
    HoldingInput input,
  ) => _run((api, b) => api.updateHolding(b, parent, id, input));
  @override
  Future<LocalS2Reply<bool>> deleteHolding(String parent, String id) =>
      _run((api, b) => api.deleteHolding(b, parent, id));
  @override
  Future<LocalS2Reply<LocalPortfolioMetrics>> metrics(String parent) =>
      _run((api, b) => api.metrics(b, parent));
}

class _OwnedS3Scope implements LocalS3Scope {
  final LocalSession _session;
  final int _ownerGeneration;
  final int _epoch;
  bool _disposed = false;
  _OwnedS3Scope(this._session, this._ownerGeneration, this._epoch);
  @override
  bool get isCurrent =>
      !_disposed &&
      !_session._disposed &&
      _ownerGeneration == _session._generation &&
      _epoch == _session._domainEpoch &&
      _session.isAuthenticated;
  @override
  void dispose() {
    _disposed = true;
  }

  Future<LocalS3Reply<T>> _run<T>(
    Future<LocalS3Reply<T>> Function(LocalS3Api, String) operation,
  ) async {
    if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
    if (!_session.canAccessFeatures) {
      throw const LocalApiException('ONBOARDING_REQUIRED', status: 409);
    }
    final api = _session._s3Api;
    if (api == null) throw const LocalApiException('S3_FEATURE_UNAVAILABLE');
    try {
      final reply = await operation(api, _session._bearer!);
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      return reply;
    } on LocalApiException catch (error) {
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      if (error.status == 401) {
        _session._clear(reason: error);
      } else if (error.code == 'ONBOARDING_REQUIRED' && error.status == 409) {
        _session._domainEpoch++;
        _session._onboarding = null;
        _session._operationError = error;
        _session._notify();
      }
      rethrow;
    } on Exception {
      if (!isCurrent) throw const LocalApiException('SESSION_CHANGED');
      throw const LocalApiException('API_UNAVAILABLE');
    }
  }

  @override
  Future<LocalS3Reply<LocalMarketSearch>> marketSearch({
    String query = '',
    int limit = 20,
  }) => _run((api, b) => api.marketSearch(b, query: query, limit: limit));
  @override
  Future<LocalS3Reply<LocalMarketQuote>> marketQuote(String instrument) =>
      _run((api, b) => api.marketQuote(b, instrument));
  @override
  Future<LocalS3Reply<LocalWatchlistList>> watchlists() =>
      _run((api, b) => api.watchlists(b));
  @override
  Future<LocalS3Reply<LocalWatchlist>> watchlist(String id) =>
      _run((api, b) => api.watchlist(b, id));
  @override
  Future<LocalS3Reply<LocalWatchlist>> createWatchlist(String name) =>
      _run((api, b) => api.createWatchlist(b, name));
  @override
  Future<LocalS3Reply<LocalWatchlist>> updateWatchlist(
    String id,
    String name,
  ) => _run((api, b) => api.updateWatchlist(b, id, name));
  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> deleteWatchlist(String id) =>
      _run((api, b) => api.deleteWatchlist(b, id));
  @override
  Future<LocalS3Reply<LocalWatchlistItemSaved>> putWatchlistItem(
    String parent,
    String instrument,
  ) => _run((api, b) => api.putWatchlistItem(b, parent, instrument));
  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> removeWatchlistItem(
    String parent,
    String instrument,
  ) => _run((api, b) => api.removeWatchlistItem(b, parent, instrument));
  @override
  Future<LocalS3Reply<LocalPaperAccountState>> paperAccount() =>
      _run((api, b) => api.paperAccount(b));
  @override
  Future<LocalS3Reply<LocalPaperAccountState>> openPaperAccount() =>
      _run((api, b) => api.openPaperAccount(b));
  @override
  Future<LocalS3Reply<LocalPaperLedger>> paperLedger({
    int after = 0,
    int limit = 100,
  }) => _run((api, b) => api.paperLedger(b, after: after, limit: limit));
}
