import 'package:frontend_flutter/core/local_application/local_s2_api.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';

import 'local_s2_data.dart';

class FakeLocalS2Api implements LocalS2Api {
  final calls = <String>[];
  Future<LocalS2Reply<LocalPortfolioList>> Function()? onPortfolios;
  Future<LocalS2Reply<LocalRiskDraft>> Function(LocalRiskInput)? onDraft;
  Future<LocalS2Reply<LocalSavedRiskAssessment>> Function(
    LocalRiskInput,
    String,
  )?
  onAssess;
  Future<LocalS2Reply<LocalRiskHistory>> Function(String?)? onHistory;
  Future<LocalS2Reply<LocalPortfolio>> Function(PortfolioInput)? onCreate;
  Future<LocalS2Reply<LocalPortfolio>> Function(PortfolioInput)? onUpdate;
  Future<LocalS2Reply<LocalHolding>> Function(HoldingInput)? onCreateHolding;
  Future<LocalS2Reply<LocalHolding>> Function(HoldingInput)? onUpdateHolding;
  Future<LocalS2Reply<LocalPortfolioMetrics>> Function()? onMetrics;
  LocalRiskInput draft = LocalRiskInput([]);
  List<LocalSavedRiskAssessment> history = [];
  List<LocalPortfolio> portfolioItems = [];
  List<LocalHolding> holdingItems = [];
  LocalS2Reply<T> reply<T>(T value, [DateTime? time]) =>
      LocalS2Reply(value, 'CACHED', time);
  DateTime get time => DateTime.utc(2030);
  @override
  Future<LocalS2Reply<LocalRiskQuestionnaire>> riskQuestionnaire(
    String bearer,
  ) async {
    calls.add('questionnaire');
    return reply(LocalRiskQuestionnaire.fromJson(questionnaireData()));
  }

  @override
  Future<LocalS2Reply<LocalRiskDraft>> riskDraft(String bearer) async {
    calls.add('draft');
    final v = riskDraftData()..['answers'] = draft.toJson()['answers'];
    if (draft.answers.isNotEmpty) v['updated_at'] = s2Time;
    return reply(
      LocalRiskDraft.fromJson(v),
      draft.answers.isEmpty ? null : time,
    );
  }

  @override
  Future<LocalS2Reply<LocalRiskDraft>> saveRiskDraft(
    String bearer,
    LocalRiskInput input,
  ) async {
    calls.add('saveDraft');
    if (onDraft != null) return onDraft!(input);
    draft = input;
    final v = riskDraftData(saved: true)
      ..['answers'] = input.toJson()['answers'];
    return reply(LocalRiskDraft.fromJson(v), time);
  }

  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> assessRisk(
    String bearer,
    LocalRiskInput input,
    String retryKey,
  ) async {
    calls.add('assess');
    if (onAssess != null) return onAssess!(input, retryKey);
    final v = savedRiskData()..['input'] = input.toJson();
    final result = LocalSavedRiskAssessment.fromJson(v);
    history = [result];
    return reply(result, time);
  }

  @override
  Future<LocalS2Reply<LocalRiskHistory>> riskHistory(
    String bearer, {
    String? before,
  }) async {
    calls.add('history:${before ?? 'first'}');
    if (onHistory != null) return onHistory!(before);
    return reply(
      LocalRiskHistory.fromJson(
        s2Scoped({
          'items': history.isEmpty ? [] : [savedRiskData()],
          'next_cursor': null,
        }),
      ),
    );
  }

  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> riskAssessment(
    String bearer,
    String id,
  ) async {
    calls.add('assessment');
    return reply(
      LocalSavedRiskAssessment.fromJson(
        savedRiskData()..['assessment_id'] = id,
      ),
      time,
    );
  }

  @override
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments(
    String bearer,
  ) async {
    calls.add('instruments');
    return reply(LocalInstrumentCatalog.fromJson(catalogData()));
  }

  @override
  Future<LocalS2Reply<LocalPortfolioList>> portfolios(String bearer) async {
    calls.add('portfolios');
    if (onPortfolios != null) return onPortfolios!();
    return reply(
      LocalPortfolioList.fromJson(
        s2Scoped({
          'portfolio_version': 'portfolio.v1',
          'items': [
            for (final p in portfolioItems)
              portfolioData(id: p.portfolioId)
                ..['name'] = p.name
                ..['description'] = p.description,
          ],
          'count': portfolioItems.length,
        }),
      ),
    );
  }

  @override
  Future<LocalS2Reply<LocalPortfolio>> portfolio(
    String bearer,
    String id,
  ) async {
    calls.add('portfolio');
    return reply(portfolioItems.firstWhere((p) => p.portfolioId == id), time);
  }

  @override
  Future<LocalS2Reply<LocalPortfolio>> createPortfolio(
    String bearer,
    PortfolioInput input,
  ) async {
    calls.add('createPortfolio');
    if (onCreate != null) return onCreate!(input);
    final v = portfolioData()
      ..['name'] = input.name
      ..['description'] = input.description;
    final result = LocalPortfolio.fromJson(v);
    portfolioItems = [...portfolioItems, result];
    return reply(result, time);
  }

  @override
  Future<LocalS2Reply<LocalPortfolio>> updatePortfolio(
    String bearer,
    String id,
    PortfolioInput input,
  ) async {
    calls.add('updatePortfolio');
    if (onUpdate != null) return onUpdate!(input);
    final v = portfolioData(id: id)
      ..['name'] = input.name
      ..['description'] = input.description;
    final result = LocalPortfolio.fromJson(v);
    portfolioItems = [
      for (final p in portfolioItems)
        if (p.portfolioId == id) result else p,
    ];
    return reply(result, time);
  }

  @override
  Future<LocalS2Reply<bool>> deletePortfolio(String bearer, String id) async {
    calls.add('deletePortfolio');
    portfolioItems = portfolioItems.where((p) => p.portfolioId != id).toList();
    holdingItems = [];
    return reply(true);
  }

  @override
  Future<LocalS2Reply<LocalHoldingList>> holdings(
    String bearer,
    String parent,
  ) async {
    calls.add('holdings');
    return reply(
      LocalHoldingList.fromJson(
        s2Scoped({
          'holding_version': 'holding.v1',
          'catalog_version': 'synthetic_catalog.v1',
          'portfolio_id': parent,
          'items': [
            for (final h in holdingItems)
              holdingData()
                ..['portfolio_id'] = parent
                ..['holding_id'] = h.holdingId
                ..['quantity'] = h.quantity
                ..['average_cost'] = h.averageCost,
          ],
          'count': holdingItems.length,
        }),
      ),
    );
  }

  @override
  Future<LocalS2Reply<LocalHolding>> holding(
    String bearer,
    String parent,
    String id,
  ) async {
    calls.add('holding');
    return reply(holdingItems.firstWhere((h) => h.holdingId == id), time);
  }

  @override
  Future<LocalS2Reply<LocalHolding>> createHolding(
    String bearer,
    String parent,
    HoldingInput input,
  ) async {
    calls.add('createHolding');
    if (onCreateHolding != null) return onCreateHolding!(input);
    final v = holdingData()
      ..['portfolio_id'] = parent
      ..['quantity'] = input.quantity
      ..['average_cost'] = input.averageCost;
    final result = LocalHolding.fromJson(v);
    holdingItems = [...holdingItems, result];
    return reply(result, time);
  }

  @override
  Future<LocalS2Reply<LocalHolding>> updateHolding(
    String bearer,
    String parent,
    String id,
    HoldingInput input,
  ) async {
    calls.add('updateHolding');
    if (onUpdateHolding != null) return onUpdateHolding!(input);
    final v = holdingData()
      ..['portfolio_id'] = parent
      ..['holding_id'] = id
      ..['quantity'] = input.quantity
      ..['average_cost'] = input.averageCost;
    final result = LocalHolding.fromJson(v);
    holdingItems = [
      for (final h in holdingItems)
        if (h.holdingId == id) result else h,
    ];
    return reply(result, time);
  }

  @override
  Future<LocalS2Reply<bool>> deleteHolding(
    String bearer,
    String parent,
    String id,
  ) async {
    calls.add('deleteHolding');
    holdingItems = holdingItems.where((h) => h.holdingId != id).toList();
    return reply(true);
  }

  @override
  Future<LocalS2Reply<LocalPortfolioMetrics>> metrics(
    String bearer,
    String parent,
  ) async {
    calls.add('metrics');
    if (onMetrics != null) return onMetrics!();
    final v = metricsData(empty: holdingItems.isEmpty)
      ..['portfolio_id'] = parent;
    final result = LocalPortfolioMetrics.fromJson(v);
    return LocalS2Reply(result, result.dataStatus, result.dataAsOf);
  }
}
