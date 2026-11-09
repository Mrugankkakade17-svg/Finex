import 'package:flutter/foundation.dart';
import '../models/risk_question.dart';
import '../../onboarding/services/onboarding_service.dart';

class RiskService extends ChangeNotifier {
  static final RiskService _instance = RiskService._internal();
  factory RiskService() => _instance;
  RiskService._internal();

  final List<RiskQuestion> _questions = const [
    RiskQuestion(
      id: 'q1_volatility',
      category: 'willingness',
      questionText: 'If your investment portfolio drops 20% over a 3-month period, what would you do?',
      subtitle: 'Measures your emotional tolerance for market drawdowns',
      options: [
        RiskOption(id: 'q1_opt1', text: 'Sell all remaining holdings immediately to prevent further loss', points: 1),
        RiskOption(id: 'q1_opt2', text: 'Sell a portion of the portfolio to preserve cash', points: 2),
        RiskOption(id: 'q1_opt3', text: 'Do nothing and wait for market recovery', points: 3),
        RiskOption(id: 'q1_opt4', text: 'Invest additional funds to buy assets at lower prices', points: 4),
      ],
    ),
    RiskQuestion(
      id: 'q2_horizon',
      category: 'capacity',
      questionText: 'When do you anticipate needing to withdraw a significant portion of this money?',
      subtitle: 'Evaluates your financial time horizon and liquidity requirements',
      options: [
        RiskOption(id: 'q2_opt1', text: 'Within the next 12 months', points: 1),
        RiskOption(id: 'q2_opt2', text: 'In 1 to 3 years', points: 2),
        RiskOption(id: 'q2_opt3', text: 'In 3 to 7 years', points: 3),
        RiskOption(id: 'q2_opt4', text: 'Not for at least 7+ years', points: 4),
      ],
    ),
    RiskQuestion(
      id: 'q3_emergency_fund',
      category: 'capacity',
      questionText: 'How many months of living expenses do you have set aside in secure cash/savings?',
      subtitle: 'Assesses financial capacity to absorb unexpected shocks',
      options: [
        RiskOption(id: 'q3_opt1', text: 'Less than 1 month of expenses', points: 1),
        RiskOption(id: 'q3_opt2', text: '1 to 3 months of expenses', points: 2),
        RiskOption(id: 'q3_opt3', text: '3 to 6 months of expenses', points: 3),
        RiskOption(id: 'q3_opt4', text: 'More than 6 months of living expenses', points: 4),
      ],
    ),
    RiskQuestion(
      id: 'q4_experience',
      category: 'willingness',
      questionText: 'What is your familiarity with volatile investments like stocks, ETFs, and index funds?',
      subtitle: 'Gauges investment knowledge and behavioral readiness',
      options: [
        RiskOption(id: 'q4_opt1', text: 'None — I have only kept money in bank savings / CDs', points: 1),
        RiskOption(id: 'q4_opt2', text: 'Limited — I understand the basics but rarely invest', points: 2),
        RiskOption(id: 'q4_opt3', text: 'Moderate — I actively hold mutual funds or individual stocks', points: 3),
        RiskOption(id: 'q4_opt4', text: 'Extensive — I actively manage diversified multi-asset portfolios', points: 4),
      ],
    ),
    RiskQuestion(
      id: 'q5_goal_tradeoff',
      category: 'willingness',
      questionText: 'Which statement best matches your overall investment priority?',
      subtitle: 'Determines the balance between downside safety and upside potential',
      options: [
        RiskOption(id: 'q5_opt1', text: 'Protect my initial capital with minimal or zero risk of loss', points: 1),
        RiskOption(id: 'q5_opt2', text: 'Focus on steady modest gains with low-to-medium fluctuations', points: 2),
        RiskOption(id: 'q5_opt3', text: 'Balance growth and safety to beat inflation over time', points: 3),
        RiskOption(id: 'q5_opt4', text: 'Maximize long-term wealth growth, accepting sharp price swings', points: 4),
      ],
    ),
  ];

  final Map<String, RiskOption> _selectedAnswers = {};
  RiskAssessmentResult? _latestResult;
  bool _isSubmitting = false;

  List<RiskQuestion> get questions => _questions;
  Map<String, RiskOption> get selectedAnswers => _selectedAnswers;
  RiskAssessmentResult? get latestResult => _latestResult;
  bool get isSubmitting => _isSubmitting;
  bool get isAllAnswered => _questions.every((q) => _selectedAnswers.containsKey(q.id));

  void selectAnswer(String questionId, RiskOption option) {
    _selectedAnswers[questionId] = option;
    notifyListeners();
  }

  /// Calculates deterministic risk score and submits result
  Future<RiskAssessmentResult> submitAssessment() async {
    _isSubmitting = true;
    notifyListeners();

    try {
      await Future.delayed(const Duration(milliseconds: 500));

      final result = RiskAssessmentResult.calculate(
        answers: _selectedAnswers,
        questions: _questions,
      );

      _latestResult = result;
      _isSubmitting = false;

      // Update onboarding service
      final onboarding = OnboardingService();
      await onboarding.completeOnboarding(riskProfile: result.profileTier);

      notifyListeners();
      return result;
    } catch (e) {
      _isSubmitting = false;
      notifyListeners();
      rethrow;
    }
  }

  void reset() {
    _selectedAnswers.clear();
    _latestResult = null;
    _isSubmitting = false;
    notifyListeners();
  }
}
