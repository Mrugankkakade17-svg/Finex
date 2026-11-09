import 'local_s2_models.dart';

/// Raw transport injection for tests/composition, never exposed by LocalSession.
abstract interface class LocalS2Api {
  Future<LocalS2Reply<LocalRiskQuestionnaire>> riskQuestionnaire(String bearer);
  Future<LocalS2Reply<LocalRiskDraft>> riskDraft(String bearer);
  Future<LocalS2Reply<LocalRiskDraft>> saveRiskDraft(
    String bearer,
    LocalRiskInput input,
  );
  Future<LocalS2Reply<LocalSavedRiskAssessment>> assessRisk(
    String bearer,
    LocalRiskInput input,
    String retryKey,
  );
  Future<LocalS2Reply<LocalRiskHistory>> riskHistory(
    String bearer, {
    String? before,
  });
  Future<LocalS2Reply<LocalSavedRiskAssessment>> riskAssessment(
    String bearer,
    String id,
  );
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments(String bearer);
  Future<LocalS2Reply<LocalPortfolioList>> portfolios(String bearer);
  Future<LocalS2Reply<LocalPortfolio>> portfolio(String bearer, String id);
  Future<LocalS2Reply<LocalPortfolio>> createPortfolio(
    String bearer,
    PortfolioInput input,
  );
  Future<LocalS2Reply<LocalPortfolio>> updatePortfolio(
    String bearer,
    String id,
    PortfolioInput input,
  );
  Future<LocalS2Reply<bool>> deletePortfolio(String bearer, String id);
  Future<LocalS2Reply<LocalHoldingList>> holdings(String bearer, String parent);
  Future<LocalS2Reply<LocalHolding>> holding(
    String bearer,
    String parent,
    String id,
  );
  Future<LocalS2Reply<LocalHolding>> createHolding(
    String bearer,
    String parent,
    HoldingInput input,
  );
  Future<LocalS2Reply<LocalHolding>> updateHolding(
    String bearer,
    String parent,
    String id,
    HoldingInput input,
  );
  Future<LocalS2Reply<bool>> deleteHolding(
    String bearer,
    String parent,
    String id,
  );
  Future<LocalS2Reply<LocalPortfolioMetrics>> metrics(
    String bearer,
    String parent,
  );
}

/// A session-created, revocable request scope. No bearer or adapter getter.
abstract interface class LocalS2Scope {
  bool get isCurrent;
  void dispose();
  Future<LocalS2Reply<LocalRiskQuestionnaire>> riskQuestionnaire();
  Future<LocalS2Reply<LocalRiskDraft>> riskDraft();
  Future<LocalS2Reply<LocalRiskDraft>> saveRiskDraft(LocalRiskInput input);
  Future<LocalS2Reply<LocalSavedRiskAssessment>> assessRisk(
    LocalRiskInput input,
    String retryKey,
  );
  Future<LocalS2Reply<LocalRiskHistory>> riskHistory({String? before});
  Future<LocalS2Reply<LocalSavedRiskAssessment>> riskAssessment(String id);
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments();
  Future<LocalS2Reply<LocalPortfolioList>> portfolios();
  Future<LocalS2Reply<LocalPortfolio>> portfolio(String id);
  Future<LocalS2Reply<LocalPortfolio>> createPortfolio(PortfolioInput input);
  Future<LocalS2Reply<LocalPortfolio>> updatePortfolio(
    String id,
    PortfolioInput input,
  );
  Future<LocalS2Reply<bool>> deletePortfolio(String id);
  Future<LocalS2Reply<LocalHoldingList>> holdings(String parent);
  Future<LocalS2Reply<LocalHolding>> holding(String parent, String id);
  Future<LocalS2Reply<LocalHolding>> createHolding(
    String parent,
    HoldingInput input,
  );
  Future<LocalS2Reply<LocalHolding>> updateHolding(
    String parent,
    String id,
    HoldingInput input,
  );
  Future<LocalS2Reply<bool>> deleteHolding(String parent, String id);
  Future<LocalS2Reply<LocalPortfolioMetrics>> metrics(String parent);
}
