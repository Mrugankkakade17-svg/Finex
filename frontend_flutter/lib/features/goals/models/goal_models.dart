library;

/// Request and response models for authenticated goals and projections.
/// Matches backend contracts in backend/app/schemas/sprint4_paper_goals.py.

class GoalCreateRequest {
  final String title;
  final double targetAmount;
  final double currentAmount;
  final int horizonYears;
  final double monthlyContribution;
  final double expectedAnnualReturnPct;

  const GoalCreateRequest({
    required this.title,
    required this.targetAmount,
    this.currentAmount = 0.0,
    required this.horizonYears,
    this.monthlyContribution = 0.0,
    this.expectedAnnualReturnPct = 6.0,
  });

  Map<String, dynamic> toJson() => {
    'title': title,
    'target_amount': targetAmount,
    'current_amount': currentAmount,
    'horizon_years': horizonYears,
    'monthly_contribution': monthlyContribution,
    'expected_annual_return_pct': expectedAnnualReturnPct,
  };

  factory GoalCreateRequest.fromJson(Map<String, dynamic> json) {
    return GoalCreateRequest(
      title: json['title'] as String,
      targetAmount: _toDouble(json['target_amount']),
      currentAmount: _toDouble(json['current_amount']),
      horizonYears: (json['horizon_years'] as num).toInt(),
      monthlyContribution: _toDouble(json['monthly_contribution']),
      expectedAnnualReturnPct: _toDouble(json['expected_annual_return_pct']),
    );
  }
}

class GoalProjection {
  final int year;
  final double projectedBalance;
  final double contributionsTotal;
  final double growthTotal;

  const GoalProjection({
    required this.year,
    required this.projectedBalance,
    required this.contributionsTotal,
    required this.growthTotal,
  });

  factory GoalProjection.fromJson(Map<String, dynamic> json) {
    return GoalProjection(
      year: (json['year'] as num).toInt(),
      projectedBalance: _toDouble(json['projected_balance']),
      contributionsTotal: _toDouble(json['contributions_total']),
      growthTotal: _toDouble(json['growth_total']),
    );
  }

  Map<String, dynamic> toJson() => {
    'year': year,
    'projected_balance': projectedBalance.toStringAsFixed(2),
    'contributions_total': contributionsTotal.toStringAsFixed(2),
    'growth_total': growthTotal.toStringAsFixed(2),
  };
}

class GoalResponse {
  final String goalId;
  final String title;
  final double targetAmount;
  final double currentAmount;
  final int horizonYears;
  final double monthlyContribution;
  final double expectedAnnualReturnPct;
  final double projectedFinalAmount;
  final double shortfallOrSurplus;
  final bool isOnTrack;
  final String assumptionsStatement;
  final List<GoalProjection> projections;

  const GoalResponse({
    required this.goalId,
    required this.title,
    required this.targetAmount,
    required this.currentAmount,
    required this.horizonYears,
    required this.monthlyContribution,
    required this.expectedAnnualReturnPct,
    required this.projectedFinalAmount,
    required this.shortfallOrSurplus,
    required this.isOnTrack,
    this.assumptionsStatement =
        'Deterministic model based on constant monthly compounding. '
        'No guarantee of future performance.',
    this.projections = const [],
  });

  factory GoalResponse.fromJson(Map<String, dynamic> json) {
    return GoalResponse(
      goalId: json['goal_id'] as String,
      title: json['title'] as String,
      targetAmount: _toDouble(json['target_amount']),
      currentAmount: _toDouble(json['current_amount']),
      horizonYears: (json['horizon_years'] as num).toInt(),
      monthlyContribution: _toDouble(json['monthly_contribution']),
      expectedAnnualReturnPct: _toDouble(json['expected_annual_return_pct']),
      projectedFinalAmount: _toDouble(json['projected_final_amount']),
      shortfallOrSurplus: _toDouble(json['shortfall_or_surplus']),
      isOnTrack: (json['is_on_track'] as bool?) ?? false,
      assumptionsStatement:
          (json['assumptions_statement'] as String?) ??
          'Deterministic model based on constant monthly compounding. '
              'No guarantee of future performance.',
      projections:
          (json['projections'] as List<dynamic>?)
              ?.map((e) => GoalProjection.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
    'goal_id': goalId,
    'title': title,
    'target_amount': targetAmount.toStringAsFixed(2),
    'current_amount': currentAmount.toStringAsFixed(2),
    'horizon_years': horizonYears,
    'monthly_contribution': monthlyContribution.toStringAsFixed(2),
    'expected_annual_return_pct': expectedAnnualReturnPct.toStringAsFixed(2),
    'projected_final_amount': projectedFinalAmount.toStringAsFixed(2),
    'shortfall_or_surplus': shortfallOrSurplus.toStringAsFixed(2),
    'is_on_track': isOnTrack,
    'assumptions_statement': assumptionsStatement,
    'projections': projections.map((p) => p.toJson()).toList(),
  };

  double get progressPct {
    if (targetAmount <= 0) return 0.0;
    final pct = (currentAmount / targetAmount) * 100.0;
    return pct > 100.0 ? 100.0 : pct;
  }
}

double _toDouble(dynamic value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? 0.0;
  return 0.0;
}
