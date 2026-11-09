class RiskOption {
  final String id;
  final String text;
  final int points;
  final String? detail;

  const RiskOption({
    required this.id,
    required this.text,
    required this.points,
    this.detail,
  });

  factory RiskOption.fromJson(Map<String, dynamic> json) {
    return RiskOption(
      id: json['id']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
      points: (json['points'] ?? 0) as int,
      detail: json['detail']?.toString(),
    );
  }
}

class RiskQuestion {
  final String id;
  final String category; // 'willingness', 'capacity', 'knowledge'
  final String questionText;
  final String subtitle;
  final List<RiskOption> options;

  const RiskQuestion({
    required this.id,
    required this.category,
    required this.questionText,
    required this.subtitle,
    required this.options,
  });
}

class RiskAssessmentResult {
  final int totalScore;
  final int willingnessScore;
  final int capacityScore;
  final String profileTier; // 'Conservative', 'Moderate', 'Aggressive'
  final String summaryExplanation;
  final List<String> topFactors;
  final DateTime assessedAt;

  const RiskAssessmentResult({
    required this.totalScore,
    required this.willingnessScore,
    required this.capacityScore,
    required this.profileTier,
    required this.summaryExplanation,
    required this.topFactors,
    required this.assessedAt,
  });

  factory RiskAssessmentResult.calculate({
    required Map<String, RiskOption> answers,
    required List<RiskQuestion> questions,
  }) {
    int total = 0;
    int willingness = 0;
    int capacity = 0;
    List<String> factors = [];

    for (final q in questions) {
      final selected = answers[q.id];
      if (selected != null) {
        total += selected.points;
        if (q.category == 'willingness') {
          willingness += selected.points;
        } else {
          capacity += selected.points;
        }
        factors.add('${q.questionText}: ${selected.text}');
      }
    }

    String tier;
    String explanation;

    if (total <= 7) {
      tier = 'Conservative';
      explanation =
          'Your responses show a strong preference for capital preservation and lower tolerance for short-term market volatility.';
    } else if (total <= 13) {
      tier = 'Moderate';
      explanation =
          'You demonstrate a balanced profile, willing to accept moderate market fluctuations in exchange for steady multi-year capital growth.';
    } else {
      tier = 'Aggressive';
      explanation =
          'You have high risk tolerance and a long-term horizon, targeting maximum capital appreciation despite high short-term volatility.';
    }

    return RiskAssessmentResult(
      totalScore: total,
      willingnessScore: willingness,
      capacityScore: capacity,
      profileTier: tier,
      summaryExplanation: explanation,
      topFactors: factors.take(3).toList(),
      assessedAt: DateTime.now(),
    );
  }
}
