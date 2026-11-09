import 'dart:convert';
import 'dart:io';

import 'package:frontend_flutter/core/local_application/local_models.dart';

const portfolioA = '00000000-0000-4000-8000-000000000191';
const holdingA = '00000000-0000-4000-8000-000000000192';
const assessmentA = '00000000-0000-4000-8000-000000000190';
const s2Time = '2030-01-01T00:00:00+00:00';
const quoteTime = '2026-01-01T00:00:00Z';
const ruleHash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

Map<String, dynamic> s2Scoped(Map<String, dynamic> fields) => {
  'scope': localApplicationScope,
  'contract_version': localContractVersion,
  ...fields,
};
Map<String, dynamic> copyS2(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;
Map<String, dynamic> riskInput({String suffix = 'C', bool partial = false}) => {
  'questionnaire_id': 'risk_questionnaire_v1',
  'questionnaire_version': 'v1',
  'answers': [
    for (final prefix in ['W', 'C'])
      for (var index = 1; index <= 5; index++)
        if (!partial || (prefix == 'W' && index == 1))
          {
            'question_id': '$prefix$index',
            'answer_code': '$prefix${index}_$suffix',
          },
  ],
};
Map<String, dynamic> questionnaireData() => s2Scoped({
  'questionnaire_id': 'risk_questionnaire_v1',
  'questionnaire_version': 'v1',
  'scoring_version': 'deterministic_v1.0.0',
  'explanation_version': 'educational_v1.0.0',
  'rules_sha256': ruleHash,
  'questions': [
    for (final prefix in ['W', 'C'])
      for (var index = 1; index <= 5; index++)
        {
          'question_id': '$prefix$index',
          'dimension': prefix == 'W' ? 'willingness' : 'capacity',
          'text': 'Synthetic question $prefix$index',
          'options': [
            for (final suffix in ['A', 'B', 'C', 'D', 'E'])
              {
                'code': '$prefix${index}_$suffix',
                'label': 'Synthetic option $suffix',
              },
          ],
        },
  ],
  'limitation': {
    'code': 'EDUCATIONAL_SELF_REPORTED_PROFILE',
    'message': 'This educational profile is based on self-reported answers and is not individualized financial, legal, tax, or investment advice.',
  },
});
Map<String, dynamic> riskDraftData({
  bool partial = false,
  bool saved = false,
}) => s2Scoped({
  ...riskInput(partial: true),
  'answers': partial ? riskInput(partial: true)['answers'] : <Object?>[],
  'updated_at': saved || partial ? s2Time : null,
});
Map<String, dynamic> savedRiskData() {
  final rules = jsonDecode(
    File('../backend/data/questionnaire/risk_questionnaire_v1.json')
        .readAsStringSync(),
  );
  return s2Scoped({
    'persisted': true,
    'assessment_id': assessmentA,
    'created_at': s2Time,
    'input': riskInput(),
    'assessment': {
      'contract_version': 's2-risk-contract/v1.0',
      'questionnaire_id': 'risk_questionnaire_v1',
      'questionnaire_version': 'v1',
      'scoring_version': 'deterministic_v1.0.0',
      'willingness_score': 50.0,
      'capacity_score': 50.0,
      'composite_score': 50.0,
      'risk_category': {'code': 'MODERATE', 'label': 'Moderate'},
      'calculated_at': s2Time,
      'limitation': questionnaireData()['limitation'],
      'informational_tension': null,
    },
    'explanation': {
      'summary': 'Synthetic moderate profile.',
      'dimensions': 'Willingness 50; capacity 50.',
      'method': 'Server deterministic scoring; no client calculation.',
      'questionnaire_version': 'v1',
      'scoring_version': 'deterministic_v1.0.0',
      'calculated_at': s2Time,
      'limitation': (questionnaireData()['limitation'] as Map)['message'],
    },
    'explanation_version': 'educational_v1.0.0',
    'rules_sha256': ruleHash,
    'rules_snapshot': rules,
  });
}

Map<String, dynamic> portfolioData({
  String id = portfolioA,
  String name = 'Synthetic portfolio',
}) => s2Scoped({
  'portfolio_version': 'portfolio.v1',
  'portfolio_id': id,
  'name': name,
  'description': null,
  'currency': 'USD',
  'created_at': s2Time,
  'updated_at': s2Time,
});
Map<String, dynamic> instrumentData(String id) => {
  'instrument_id': id,
  'display_name': 'Synthetic ${id.substring(4)}',
  'asset_class': id == 'SYN:BND' ? 'BOND' : 'EQUITY',
  'sector': id == 'SYN:BND' ? 'FIXED_INCOME' : 'TECHNOLOGY',
  'currency': 'USD',
};
Map<String, dynamic> catalogData() => s2Scoped({
  'catalog_version': 'synthetic_catalog.v1',
  'currency': 'USD',
  'items': [
    for (final id in ['SYN:AAPL', 'SYN:BND', 'SYN:MSFT', 'SYN:UNAVAILABLE'])
      instrumentData(id),
  ],
  'count': 4,
});
Map<String, dynamic> holdingData({
  String id = holdingA,
  String instrument = 'SYN:AAPL',
  String quantity = '10.000000',
  String cost = '150.0000',
}) => s2Scoped({
  'holding_version': 'holding.v1',
  'catalog_version': 'synthetic_catalog.v1',
  'portfolio_id': portfolioA,
  'holding_id': id,
  ...instrumentData(instrument),
  'quantity': quantity,
  'average_cost': cost,
  'created_at': s2Time,
  'updated_at': s2Time,
});
Map<String, dynamic> metricsData({
  bool unavailable = false,
  bool empty = false,
}) => s2Scoped({
  'metrics_version': 'portfolio_metrics.v1',
  'formula_version': 'manual_portfolio_math.v1',
  'catalog_version': 'synthetic_catalog.v1',
  'quote_snapshot_version': 'synthetic_quotes.v1',
  'portfolio_id': portfolioA,
  'currency': 'USD',
  'valuation_status': empty
      ? 'EMPTY'
      : unavailable
      ? 'UNAVAILABLE'
      : 'COMPLETE',
  'source': 'finex.synthetic.portfolio',
  'source_type': 'SYNTHETIC',
  'fixture_as_of': quoteTime,
  'calculated_at': s2Time,
  'missing_instrument_ids': unavailable ? ['SYN:UNAVAILABLE'] : <String>[],
  'limitations': [
    'SYNTHETIC_QUOTES_NOT_MARKET_DATA',
    'MANUAL_HOLDINGS_NOT_BROKER_POSITIONS',
    'SPREAD_IS_ALLOCATION_ONLY',
    'NO_FUND_LOOKTHROUGH_OR_SUITABILITY',
  ],
  'holdings': empty
      ? <Object?>[]
      : [
          {
            'holding_version': 'holding.v1',
            'portfolio_id': portfolioA,
            'holding_id': holdingA,
            ...instrumentData(unavailable ? 'SYN:UNAVAILABLE' : 'SYN:AAPL'),
            'quantity': '10.000000',
            'average_cost': '150.0000',
            'cost_basis': '1500.00',
            'quote': {
              'unit_price': unavailable ? null : '200.0000',
              'data_status': unavailable ? 'UNAVAILABLE' : 'CACHED',
              'quote_as_of': unavailable ? null : quoteTime,
              'reason': unavailable ? 'SYNTHETIC_QUOTE_UNAVAILABLE' : null,
            },
            'market_value': unavailable ? null : '2000.00',
            'gain_loss': unavailable ? null : '500.00',
            'gain_loss_percent': unavailable ? null : '33.33',
            'weight_percent': unavailable ? null : '100.00',
          },
        ],
  'totals': {
    'cost_basis': empty ? '0.00' : '1500.00',
    'market_value': empty
        ? '0.00'
        : unavailable
        ? null
        : '2000.00',
    'gain_loss': empty
        ? '0.00'
        : unavailable
        ? null
        : '500.00',
    'gain_loss_percent': empty || unavailable ? null : '33.33',
    'allocation_by_asset_class': unavailable
        ? null
        : empty
        ? <Object?>[]
        : [
            {
              'group': 'EQUITY',
              'market_value': '2000.00',
              'weight_percent': '100.00',
            },
          ],
    'allocation_by_sector': unavailable
        ? null
        : empty
        ? <Object?>[]
        : [
            {
              'group': 'TECHNOLOGY',
              'market_value': '2000.00',
              'weight_percent': '100.00',
            },
          ],
    'concentration_percent': empty || unavailable ? null : '100.00',
    'hhi': empty || unavailable ? null : '1.000000',
    'educational_spread_percent': empty || unavailable ? null : '0.00',
  },
});
String s2Envelope(
  Map<String, dynamic> data, {
  String status = 'CACHED',
  Object? asOf,
}) => jsonEncode({
  'success': true,
  'message': 'Synthetic safe response',
  'data': data,
  'meta': {
    'apiVersion': 'v1',
    'dataStatus': status,
    'dataAsOf': asOf,
    'correlationId': 'synthetic-s2-test',
  },
});
String s2Error(String code, {String message = 'Synthetic safe error'}) =>
    jsonEncode({
      'success': false,
      'message': message,
      'error_code': code,
      'error': {
        'code': code,
        'message': message,
        'fieldErrors': <Object?>[],
        'correlationId': 'synthetic-s2-test',
      },
      'detail': message,
    });
