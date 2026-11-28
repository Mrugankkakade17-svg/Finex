import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend_flutter/features/goals/models/goal_models.dart';
import 'package:frontend_flutter/features/goals/presentation/goals_page.dart';
import 'package:frontend_flutter/features/goals/services/goal_service.dart';

class FakeGoalService extends GoalService {
  List<GoalResponse> goalsToReturn = [];
  GoalResponse? createdGoalToReturn;
  Exception? errorToThrow;
  int getGoalsCalls = 0;
  GoalCreateRequest? lastCreatedRequest;

  @override
  Future<List<GoalResponse>> getGoals() async {
    getGoalsCalls++;
    if (errorToThrow != null) throw errorToThrow!;
    return goalsToReturn;
  }

  @override
  Future<GoalResponse> createGoal(GoalCreateRequest request) async {
    lastCreatedRequest = request;
    if (errorToThrow != null) throw errorToThrow!;
    return createdGoalToReturn ??
        GoalResponse(
          goalId: 'goal-fake-101',
          title: request.title,
          targetAmount: request.targetAmount,
          currentAmount: request.currentAmount,
          horizonYears: request.horizonYears,
          monthlyContribution: request.monthlyContribution,
          expectedAnnualReturnPct: request.expectedAnnualReturnPct,
          projectedFinalAmount: request.targetAmount * 1.1,
          shortfallOrSurplus: request.targetAmount * 0.1,
          isOnTrack: true,
          assumptionsStatement: 'Deterministic compounding.',
          projections: [
            GoalProjection(
              year: 1,
              projectedBalance: request.currentAmount + 1000,
              contributionsTotal: request.currentAmount + 800,
              growthTotal: 200,
            ),
          ],
        );
  }
}

void main() {
  Widget createTestWidget(WidgetTester tester, GoalService service) {
    tester.view.physicalSize = const Size(1000, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    return MaterialApp(home: GoalsPage(service: service));
  }

  group('GoalsPage Widget Tests', () {
    testWidgets('renders empty goals state initially when no goals exist', (
      tester,
    ) async {
      final service = FakeGoalService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(find.text('Financial Goals & Projections'), findsOneWidget);
      expect(find.text('Educational Financial Planning'), findsOneWidget);
      expect(find.text('No Goals Set Yet'), findsOneWidget);
      expect(find.text('0 saved goal(s)'), findsOneWidget);
    });

    testWidgets('renders active goals with progress and on-track badge', (
      tester,
    ) async {
      final service = FakeGoalService();
      service.goalsToReturn = [
        const GoalResponse(
          goalId: 'g-1',
          title: 'House Down Payment',
          targetAmount: 50000.0,
          currentAmount: 20000.0,
          horizonYears: 4,
          monthlyContribution: 600.0,
          expectedAnnualReturnPct: 6.0,
          projectedFinalAmount: 52000.0,
          shortfallOrSurplus: 2000.0,
          isOnTrack: true,
          assumptionsStatement: 'Deterministic model.',
          projections: [
            GoalProjection(
              year: 1,
              projectedBalance: 27500.0,
              contributionsTotal: 27200.0,
              growthTotal: 300.0,
            ),
          ],
        ),
      ];

      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(find.text('House Down Payment'), findsOneWidget);
      expect(find.text('ON TRACK'), findsOneWidget);
      expect(find.text('Current: \$20000.00 (40.0%)'), findsOneWidget);
      expect(find.text('Target: \$50000.00'), findsOneWidget);
      expect(find.text('View Projections Breakdown'), findsOneWidget);
    });

    testWidgets('toggles projections breakdown table', (tester) async {
      final service = FakeGoalService();
      service.goalsToReturn = [
        const GoalResponse(
          goalId: 'g-1',
          title: 'Retirement Cushion',
          targetAmount: 100000.0,
          currentAmount: 30000.0,
          horizonYears: 5,
          monthlyContribution: 1000.0,
          expectedAnnualReturnPct: 6.0,
          projectedFinalAmount: 105000.0,
          shortfallOrSurplus: 5000.0,
          isOnTrack: true,
          assumptionsStatement: 'Deterministic model.',
          projections: [
            GoalProjection(
              year: 1,
              projectedBalance: 42000.0,
              contributionsTotal: 41000.0,
              growthTotal: 1250.0,
            ),
          ],
        ),
      ];

      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      // Tap to expand projections
      await tester.tap(find.byKey(const Key('toggle-projections-g-1')));
      await tester.pumpAndSettle();

      expect(find.text('Hide Projections'), findsOneWidget);
      expect(find.text('Yr 1'), findsOneWidget);
      expect(find.text('\$42000.00'), findsOneWidget);
      expect(find.text('\$1250.00'), findsOneWidget); // growth
    });

    testWidgets('validates form inputs when creating goal', (tester) async {
      final service = FakeGoalService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      // Open create form
      await tester.tap(find.byKey(const Key('goals-add-toggle-btn')));
      await tester.pumpAndSettle();

      // Attempt to save without title
      await tester.tap(find.byKey(const Key('goal-submit-btn')));
      await tester.pump();
      expect(find.text('Please enter a goal title.'), findsOneWidget);

      // Enter title, but invalid target
      await tester.enterText(
        find.byKey(const Key('goal-title-input')),
        'Emergency Cushion',
      );
      await tester.enterText(find.byKey(const Key('goal-target-input')), '0');
      await tester.tap(find.byKey(const Key('goal-submit-btn')));
      await tester.pump();
      expect(
        find.text('Target amount must be greater than zero.'),
        findsOneWidget,
      );
    });

    testWidgets('creates goal successfully and updates list', (tester) async {
      final service = FakeGoalService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      // Open create form
      await tester.tap(find.byKey(const Key('goals-add-toggle-btn')));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('goal-title-input')),
        'Vacation 2027',
      );
      await tester.enterText(
        find.byKey(const Key('goal-target-input')),
        '8000',
      );
      await tester.enterText(
        find.byKey(const Key('goal-current-input')),
        '1000',
      );
      await tester.enterText(find.byKey(const Key('goal-horizon-input')), '2');
      await tester.enterText(
        find.byKey(const Key('goal-monthly-input')),
        '300',
      );

      await tester.tap(find.byKey(const Key('goal-submit-btn')));
      await tester.pumpAndSettle();

      expect(service.lastCreatedRequest?.title, 'Vacation 2027');
      expect(service.lastCreatedRequest?.targetAmount, 8000.0);
      expect(service.lastCreatedRequest?.horizonYears, 2);
      expect(find.byKey(const Key('goal-create-success')), findsOneWidget);
    });

    testWidgets('refresh button triggers reload', (tester) async {
      final service = FakeGoalService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(service.getGoalsCalls, 1);
      await tester.tap(find.byKey(const Key('goals-refresh-btn')));
      await tester.pumpAndSettle();
      expect(service.getGoalsCalls, 2);
    });
  });
}
