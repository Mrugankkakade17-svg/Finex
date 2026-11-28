import 'package:flutter_test/flutter_test.dart';

import 'package:frontend_flutter/features/goals/models/goal_models.dart';
import 'package:frontend_flutter/features/paper_trading/models/paper_trading_models.dart';

void main() {
  group('Paper Trading & Goals Contract Parity with Backend Schemas', () {
    test('PaperOrder matches backend PaperOrder schema shape', () {
      final backendSampleOrder = {
        'order_id': 'ord-parity-1',
        'instrument_id': 'AAPL',
        'exchange': 'NASDAQ',
        'side': 'BUY',
        'quantity': 10,
        'executed_price': '225.50',
        'notional': '2255.00',
        'fee': '1.00',
        'cash_delta': '-2256.00',
        'status': 'FILLED',
        'quote_freshness': 'LIVE',
        'quote_as_of': '2026-11-27T10:00:00Z',
        'created_at': '2026-11-27T10:00:01Z',
        'simulation_notice':
            'SIMULATION ONLY: no real money or broker execution.',
      };

      final order = PaperOrder.fromJson(backendSampleOrder);
      expect(order.orderId, 'ord-parity-1');
      expect(order.instrumentId, 'AAPL');
      expect(order.exchange, 'NASDAQ');
      expect(order.side, 'BUY');
      expect(order.quantity, 10);
      expect(order.executedPrice, 225.50);
      expect(order.notional, 2255.00);
      expect(order.fee, 1.00);
      expect(order.cashDelta, -2256.00);
      expect(order.status, 'FILLED');
      expect(order.quoteFreshness, 'LIVE');
      expect(order.simulationNotice, contains('SIMULATION ONLY'));
    });

    test('PaperAccount matches backend PaperAccount schema shape', () {
      final backendSampleAccount = {
        'account_id': 'acc-parity-1',
        'currency': 'USD',
        'cash_balance': '10000.00',
        'portfolio_value': '0.00',
        'total_equity': '10000.00',
        'positions': [
          {
            'instrument_id': 'SPY',
            'exchange': 'NYSE',
            'quantity': 5,
            'average_cost': '500.00',
            'last_price': '510.00',
            'market_value': '2550.00',
            'unrealized_pnl': '50.00',
          },
        ],
        'recent_orders': [],
        'is_simulated': true,
      };

      final account = PaperAccount.fromJson(backendSampleAccount);
      expect(account.accountId, 'acc-parity-1');
      expect(account.currency, 'USD');
      expect(account.cashBalance, 10000.00);
      expect(account.portfolioValue, 0.00);
      expect(account.totalEquity, 10000.00);
      expect(account.positions.length, 1);
      expect(account.positions.first.instrumentId, 'SPY');
      expect(account.positions.first.unrealizedPnl, 50.00);
      expect(account.isSimulated, true);
    });

    test('GoalResponse matches backend GoalResponse schema shape', () {
      final backendSampleGoal = {
        'goal_id': 'goal-parity-1',
        'title': 'House Down Payment',
        'target_amount': '60000.00',
        'current_amount': '15000.00',
        'horizon_years': 4,
        'monthly_contribution': '800.00',
        'expected_annual_return_pct': '6.0',
        'projected_final_amount': '62450.00',
        'shortfall_or_surplus': '2450.00',
        'is_on_track': true,
        'assumptions_statement': 'Deterministic model based on constant monthly compounding. No guarantee of future performance.',
        'projections': [
          {
            'year': 1,
            'projected_balance': '25500.00',
            'contributions_total': '24600.00',
            'growth_total': '900.00',
          },
          {
            'year': 2,
            'projected_balance': '37000.00',
            'contributions_total': '34200.00',
            'growth_total': '2800.00',
          },
        ],
      };

      final goal = GoalResponse.fromJson(backendSampleGoal);
      expect(goal.goalId, 'goal-parity-1');
      expect(goal.title, 'House Down Payment');
      expect(goal.targetAmount, 60000.00);
      expect(goal.currentAmount, 15000.00);
      expect(goal.horizonYears, 4);
      expect(goal.monthlyContribution, 800.00);
      expect(goal.expectedAnnualReturnPct, 6.0);
      expect(goal.projectedFinalAmount, 62450.00);
      expect(goal.shortfallOrSurplus, 2450.00);
      expect(goal.isOnTrack, true);
      expect(goal.assumptionsStatement, contains('Deterministic model'));
      expect(goal.projections.length, 2);
      expect(goal.projections[0].year, 1);
      expect(goal.projections[1].year, 2);
    });
  });
}
