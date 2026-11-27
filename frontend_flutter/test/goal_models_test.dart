import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/features/goals/models/goal_models.dart';

void main() {
  group('GoalCreateRequest', () {
    test('toJson and fromJson work correctly', () {
      const req = GoalCreateRequest(
        title: 'Emergency Cushion',
        targetAmount: 25000.0,
        currentAmount: 5000.0,
        horizonYears: 3,
        monthlyContribution: 500.0,
        expectedAnnualReturnPct: 5.5,
      );
      final json = req.toJson();
      expect(json['title'], 'Emergency Cushion');
      expect(json['target_amount'], 25000.0);
      expect(json['current_amount'], 5000.0);
      expect(json['horizon_years'], 3);
      expect(json['monthly_contribution'], 500.0);
      expect(json['expected_annual_return_pct'], 5.5);

      final decoded = GoalCreateRequest.fromJson(json);
      expect(decoded.title, req.title);
      expect(decoded.targetAmount, req.targetAmount);
      expect(decoded.currentAmount, req.currentAmount);
      expect(decoded.horizonYears, req.horizonYears);
      expect(decoded.monthlyContribution, req.monthlyContribution);
      expect(decoded.expectedAnnualReturnPct, req.expectedAnnualReturnPct);
    });
  });

  group('GoalResponse', () {
    test('fromJson parses projections and calculates progressPct', () {
      final json = {
        'goal_id': 'goal-1234abcd',
        'title': 'Down Payment',
        'target_amount': '100000.00',
        'current_amount': '25000.00',
        'horizon_years': 5,
        'monthly_contribution': '1200.00',
        'expected_annual_return_pct': '6.0',
        'projected_final_amount': '112500.00',
        'shortfall_or_surplus': '12500.00',
        'is_on_track': true,
        'assumptions_statement': 'Deterministic constant compounding.',
        'projections': [
          {
            'year': 1,
            'projected_balance': '40000.00',
            'contributions_total': '39400.00',
            'growth_total': '600.00',
          },
          {
            'year': 2,
            'projected_balance': '56000.00',
            'contributions_total': '53800.00',
            'growth_total': '2200.00',
          },
        ],
      };

      final goal = GoalResponse.fromJson(json);
      expect(goal.goalId, 'goal-1234abcd');
      expect(goal.title, 'Down Payment');
      expect(goal.targetAmount, 100000.00);
      expect(goal.currentAmount, 25000.00);
      expect(goal.progressPct, 25.0);
      expect(goal.isOnTrack, true);
      expect(goal.projections.length, 2);
      expect(goal.projections.first.year, 1);
      expect(goal.projections.first.growthTotal, 600.00);
    });

    test('progressPct bounds to 100% when current exceeds target', () {
      const goal = GoalResponse(
        goalId: 'g-1',
        title: 'Cushion',
        targetAmount: 10000.0,
        currentAmount: 15000.0,
        horizonYears: 1,
        monthlyContribution: 0.0,
        expectedAnnualReturnPct: 5.0,
        projectedFinalAmount: 15500.0,
        shortfallOrSurplus: 5500.0,
        isOnTrack: true,
      );
      expect(goal.progressPct, 100.0);
    });

    test('progressPct is 0% when target is 0 or negative', () {
      const goal = GoalResponse(
        goalId: 'g-2',
        title: 'Zero Target',
        targetAmount: 0.0,
        currentAmount: 500.0,
        horizonYears: 1,
        monthlyContribution: 0.0,
        expectedAnnualReturnPct: 5.0,
        projectedFinalAmount: 500.0,
        shortfallOrSurplus: 500.0,
        isOnTrack: true,
      );
      expect(goal.progressPct, 0.0);
    });
  });
}
