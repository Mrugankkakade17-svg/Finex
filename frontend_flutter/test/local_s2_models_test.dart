import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';

import 'support/local_s2_data.dart';

void main() {
  final invalid = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'safe code',
      'INVALID_API_RESPONSE',
    ),
  );
  test('actual ordered ten-question definitions are preserved', () {
    final q = LocalRiskQuestionnaire.fromJson(questionnaireData());
    expect(q.questions.map((item) => item.id), [
      'W1',
      'W2',
      'W3',
      'W4',
      'W5',
      'C1',
      'C2',
      'C3',
      'C4',
      'C5',
    ]);
    expect(q.questions.first.options.map((item) => item.code), [
      'W1_A',
      'W1_B',
      'W1_C',
      'W1_D',
      'W1_E',
    ]);
  });
  test('partial and empty saved drafts retain required nullable time', () {
    expect(LocalRiskDraft.fromJson(riskDraftData()).updatedAt, isNull);
    expect(
      LocalRiskDraft.fromJson(riskDraftData(partial: true))
          .input
          .answers
          .length,
      1,
    );
  });
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'pilot scope': (v) => v['scope'] = 'local_educational_pilot',
    'bad version': (v) => v['questionnaire_version'] = 'v2',
    'reordered questions': (v) => (v['questions'] as List).insert(
      0,
      (v['questions'] as List).removeLast(),
    ),
    'missing hash': (v) => v.remove('rules_sha256'),
    'extra owner': (v) => v['owner_id'] = 'synthetic-owner',
    'duplicate option': (v) =>
        ((v['questions'] as List).first['options'] as List)[1] =
            ((v['questions'] as List).first['options'] as List)[0],
  }.entries) {
    test('questionnaire rejects ${mutation.key}', () {
      final raw = questionnaireData();
      mutation.value(raw);
      expect(() => LocalRiskQuestionnaire.fromJson(raw), invalid);
    });
  }
  test('saved assessment keeps server results and immutable input order', () {
    final raw = savedRiskData();
    final value = LocalSavedRiskAssessment.fromJson(raw);
    expect(value.composite, 50);
    expect(value.category, 'Moderate');
    expect(value.tension, isNull);
    expect(value.input.answers.first.questionId, 'W1');
    (raw['input'] as Map)['answers'] = [];
    expect(value.input.answers.length, 10);
  });
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'pilot not persisted': (v) => v['persisted'] = false,
    'omitted nullable tension': (v) =>
        (v['assessment'] as Map).remove('informational_tension'),
    'mismatched created time': (v) => v['created_at'] = '2030-01-02T00:00:00Z',
    'invalid UTC': (v) => v['created_at'] = '2030-01-01T00:00:00',
    'missing complete question': (v) =>
        ((v['input'] as Map)['answers'] as List).removeLast(),
    'wrong explanation version': (v) => v['explanation_version'] = 'v0',
    'nonfinite score': (v) =>
        (v['assessment'] as Map)['composite_score'] = double.nan,
    'bad UUID': (v) => v['assessment_id'] = 'other-user',
  }.entries) {
    test('saved risk rejects ${mutation.key}', () {
      final raw = savedRiskData();
      mutation.value(raw);
      expect(() => LocalSavedRiskAssessment.fromJson(raw), invalid);
    });
  }
  test(
    'record inputs canonicalize exact scaled units without binary floats',
    () {
      expect(
        PortfolioInput(name: '  Training  ', description: ' notes ').name,
        'Training',
      );
      expect(
        HoldingInput(
          instrumentId: 'SYN:AAPL',
          quantity: '10',
          averageCost: '150.0',
        ).quantity,
        '10.000000',
      );
      expect(
        HoldingInput(
          instrumentId: 'SYN:AAPL',
          quantity: '0.000001',
          averageCost: '0',
        ).averageCost,
        '0.0000',
      );
    },
  );
  for (final bad in [
    '0',
    '-1',
    '1e3',
    '01',
    ' 1',
    '1000000.000001',
    '0.0000001',
    'NaN',
  ]) {
    test('reject invalid exact quantity $bad', () {
      expect(
        () => HoldingInput(
          instrumentId: 'SYN:AAPL',
          quantity: bad,
          averageCost: '1',
        ),
        throwsA(isA<LocalApiException>()),
      );
    });
  }
  test('owned records bind parent, canonical IDs and ordered UTC times', () {
    expect(LocalPortfolio.fromJson(portfolioData()).portfolioId, portfolioA);
    expect(LocalHolding.fromJson(holdingData()).quantity, '10.000000');
    final raw = portfolioData()..['updated_at'] = '2029-01-01T00:00:00Z';
    expect(() => LocalPortfolio.fromJson(raw), invalid);
  });
  for (final field in ['description', 'created_at', 'updated_at']) {
    test('portfolio rejects missing required $field', () {
      final raw = portfolioData()..remove(field);
      expect(() => LocalPortfolio.fromJson(raw), invalid);
    });
  }
  test('catalogue and owned lists reject duplicate or unsorted records', () {
    final raw = catalogData();
    (raw['items'] as List).insert(0, (raw['items'] as List).removeLast());
    expect(() => LocalInstrumentCatalog.fromJson(raw), invalid);
    expect(
      () => LocalPortfolioList.fromJson(
        s2Scoped({
          'portfolio_version': 'portfolio.v1',
          'items': [portfolioData(), portfolioData()],
          'count': 2,
        }),
      ),
      invalid,
    );
  });
  for (final mode in ['complete', 'empty', 'unavailable']) {
    test('backend metrics retain honest $mode fields and amounts', () {
      final m = LocalPortfolioMetrics.fromJson(
        metricsData(empty: mode == 'empty', unavailable: mode == 'unavailable'),
      );
      expect(m.status, mode.toUpperCase());
      expect(
        m.totals.marketValue,
        mode == 'unavailable'
            ? null
            : mode == 'empty'
            ? '0.00'
            : '2000.00',
      );
    });
  }
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'invented live status': (v) =>
        ((v['holdings'] as List).first['quote'] as Map)['data_status'] = 'LIVE',
    'missing nullable quote reason': (v) =>
        ((v['holdings'] as List).first['quote'] as Map).remove('reason'),
    'wrong source': (v) => v['source'] = 'yfinance',
    'fake refreshed source time': (v) => v['fixture_as_of'] = s2Time,
    'unavailable value fallback': (v) =>
        (v['totals'] as Map)['market_value'] = '0.00',
    'unavailable weight fallback': (v) =>
        (v['holdings'] as List).first['weight_percent'] = '100.00',
    'missing limitation': (v) => (v['limitations'] as List).removeLast(),
  }.entries) {
    test('metrics reject ${mutation.key}', () {
      final raw = metricsData(unavailable: true);
      mutation.value(raw);
      expect(() => LocalPortfolioMetrics.fromJson(raw), invalid);
    });
  }
  Map<String, dynamic> metricTarget(Map<String, dynamic> raw, String section) {
    final totals = raw['totals'] as Map<String, dynamic>;
    return switch (section) {
      'totals' => totals,
      'holding' => (raw['holdings'] as List).first as Map<String, dynamic>,
      'asset' =>
        (totals['allocation_by_asset_class'] as List).first
            as Map<String, dynamic>,
      'sector' =>
        (totals['allocation_by_sector'] as List).first as Map<String, dynamic>,
      _ => throw StateError('Unknown synthetic metric target'),
    };
  }

  // Bounds are the accepted API DTO authority, not a client recalculation.
  for (final (section, field, minimum, maximum) in [
    ('totals', 'cost_basis', '0.00', '100000000000000.00'),
    ('totals', 'market_value', '0.00', '100000000000000.00'),
    ('holding', 'cost_basis', '0.00', '100000000000000.00'),
    ('holding', 'market_value', '0.00', '100000000000000.00'),
    ('asset', 'market_value', '0.00', '100000000000000.00'),
    ('sector', 'market_value', '0.00', '100000000000000.00'),
    ('totals', 'gain_loss', '-100000000000000.00', '100000000000000.00'),
    ('holding', 'gain_loss', '-100000000000000.00', '100000000000000.00'),
    ('totals', 'gain_loss_percent', '-100.00', '1000000000000000000.00'),
    ('holding', 'gain_loss_percent', '-100.00', '1000000000000000000.00'),
  ]) {
    final lower = BigInt.parse(minimum.replaceAll('.', ''));
    final upper = BigInt.parse(maximum.replaceAll('.', ''));
    String fixed(BigInt units) {
      final digits = units.abs().toString().padLeft(3, '0');
      return '${units.isNegative ? '-' : ''}${digits.substring(0, digits.length - 2)}.${digits.substring(digits.length - 2)}';
    }

    for (final (label, units) in [
      ('below', lower - BigInt.one),
      ('above', upper + BigInt.one),
    ]) {
      test('bounded metric rejects $section.$field $label authority', () {
        final raw = metricsData();
        metricTarget(raw, section)[field] = fixed(units);
        expect(() => LocalPortfolioMetrics.fromJson(raw), invalid);
      });
    }
    // Boundary controls inspect the individual wire DTO to avoid inventing
    // cross-field financial calculations in this decoder test.
    for (final (label, value) in [('minimum', minimum), ('maximum', maximum)]) {
      test('bounded metric accepts $section.$field $label authority', () {
        final raw = metricsData();
        final target = metricTarget(raw, section)..[field] = value;
        if (section == 'holding' && field == 'cost_basis' && value == '0.00') {
          target['gain_loss_percent'] = null;
        }
        final Object decoded = switch (section) {
          'totals' => LocalPortfolioTotals.fromJson(target),
          'holding' => LocalMetricHolding.fromJson(target),
          _ => LocalPortfolioAllocation.fromJson(target),
        };
        expect(decoded, isNotNull);
      });
    }
  }
}
