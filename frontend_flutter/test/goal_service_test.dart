import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:frontend_flutter/features/goals/models/goal_models.dart';
import 'package:frontend_flutter/features/goals/services/goal_service.dart';

void main() {
  group('GoalService', () {
    test('getGoals parses list of goal responses', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/goals');
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Goals retrieved successfully',
            'data': [
              {
                'goal_id': 'goal-1',
                'title': 'Emergency Fund',
                'target_amount': '20000.00',
                'current_amount': '5000.00',
                'horizon_years': 3,
                'monthly_contribution': '400.00',
                'expected_annual_return_pct': '5.0',
                'projected_final_amount': '21000.00',
                'shortfall_or_surplus': '1000.00',
                'is_on_track': true,
                'assumptions_statement': 'Deterministic compounding.',
                'projections': [],
              },
            ],
            'correlation_id': 'corr-goals',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = GoalService(client: mockClient);
      final goals = await service.getGoals();
      expect(goals.length, 1);
      expect(goals.first.goalId, 'goal-1');
      expect(goals.first.title, 'Emergency Fund');
      expect(goals.first.isOnTrack, true);
    });

    test('createGoal posts JSON and returns calculated projections', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/goals');
        expect(request.method, 'POST');
        final body = jsonDecode(request.body);
        expect(body['title'], 'New House');
        expect(body['target_amount'], 100000.0);
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Goal created successfully',
            'data': {
              'goal_id': 'goal-created-99',
              'title': 'New House',
              'target_amount': '100000.00',
              'current_amount': '10000.00',
              'horizon_years': 5,
              'monthly_contribution': '1200.00',
              'expected_annual_return_pct': '6.0',
              'projected_final_amount': '98000.00',
              'shortfall_or_surplus': '-2000.00',
              'is_on_track': false,
              'assumptions_statement': 'Deterministic compounding.',
              'projections': [
                {
                  'year': 1,
                  'projected_balance': '25000.00',
                  'contributions_total': '24400.00',
                  'growth_total': '600.00',
                },
              ],
            },
            'correlation_id': 'corr-created',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = GoalService(client: mockClient);
      const req = GoalCreateRequest(
        title: 'New House',
        targetAmount: 100000.0,
        currentAmount: 10000.0,
        horizonYears: 5,
        monthlyContribution: 1200.0,
        expectedAnnualReturnPct: 6.0,
      );
      final goal = await service.createGoal(req);
      expect(goal.goalId, 'goal-created-99');
      expect(goal.title, 'New House');
      expect(goal.isOnTrack, false);
      expect(goal.shortfallOrSurplus, -2000.00);
      expect(goal.projections.length, 1);
    });

    test('getGoal returns single goal detail', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/goals/goal-single');
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Goal details retrieved',
            'data': {
              'goal_id': 'goal-single',
              'title': 'Vacation',
              'target_amount': '5000.00',
              'current_amount': '2500.00',
              'horizon_years': 1,
              'monthly_contribution': '200.00',
              'expected_annual_return_pct': '4.0',
              'projected_final_amount': '5100.00',
              'shortfall_or_surplus': '100.00',
              'is_on_track': true,
              'assumptions_statement': 'Deterministic model.',
              'projections': [],
            },
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = GoalService(client: mockClient);
      final goal = await service.getGoal('goal-single');
      expect(goal.goalId, 'goal-single');
      expect(goal.title, 'Vacation');
      expect(goal.progressPct, 50.0);
    });

    test('throws GoalException on 404 or backend failure', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Goal not found.'}),
          404,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = GoalService(client: mockClient);
      expect(
        () => service.getGoal('non-existent'),
        throwsA(
          isA<GoalException>()
              .having((e) => e.statusCode, 'statusCode', 404)
              .having((e) => e.message, 'message', 'Goal not found.'),
        ),
      );
    });
  });
}
