import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_card.dart';
import '../../onboarding/services/s1_onboarding_journey_store.dart';
import '../services/s2_risk_contract_client.dart';

class S2RiskPage extends StatefulWidget {
  final S2RiskClient? client;
  final S1OnboardingJourneyStore? journeyStore;
  final String onboardingPath;
  const S2RiskPage({
    super.key,
    this.client,
    this.journeyStore,
    this.onboardingPath = '/onboarding',
  });
  @override
  State<S2RiskPage> createState() => _S2RiskPageState();
}

class _S2RiskPageState extends State<S2RiskPage> {
  S2RiskClient? _client;
  S1OnboardingJourney? _journey;
  S2Questionnaire? _questionnaire;
  S2RiskResult? _result;
  final _answers = <String, String>{};
  final _headingFocus = FocusNode();
  int _index = 0;
  String? _preset;
  String? _error;
  bool _loading = true;
  bool _allowed = false;
  static const _api =
      String.fromEnvironment('FINEX_RISK_MODE', defaultValue: 'fixture') ==
      'api';
  @override
  void initState() {
    super.initState();
    try {
      _client =
          widget.client ??
          (_api
              ? HttpS2RiskClient(
                  Uri.parse(
                    const String.fromEnvironment(
                      'FINEX_API_BASE_URL',
                      defaultValue: 'http://127.0.0.1:8000',
                    ),
                  ),
                )
              : FixtureS2RiskClient());
    } catch (_) {
      _error = const S2RiskException('LOCAL_PILOT_ONLY').message;
    }
    _load();
  }

  @override
  void dispose() {
    if (widget.client == null) _client?.close();
    _headingFocus.dispose();
    super.dispose();
  }

  void _focusHeading() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (mounted) _headingFocus.requestFocus();
  });
  Future<void> _load() async {
    setState(() {
      _loading = true;
      if (_client != null) _error = null;
    });
    try {
      final journey =
          await (widget.journeyStore ??
                  const SharedPreferencesS1OnboardingJourneyStore())
              .load();
      final allowed =
          journey?.consentRecorded == true && journey?.completed == true;
      if (mounted) {
        setState(() {
          _journey = journey;
          _allowed = allowed;
        });
      }
      final questionnaire = allowed && _client != null
          ? await _client!.loadQuestionnaire()
          : null;
      if (mounted) {
        setState(() {
          _journey = journey;
          _allowed = allowed;
          _questionnaire = questionnaire;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'The questionnaire is unavailable. Please retry.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        _focusHeading();
      }
    }
  }

  Future<void> _next() async {
    final questionnaire = _questionnaire;
    if (questionnaire == null || _loading) return;
    if (!_answers.containsKey(questionnaire.questions[_index].id)) {
      setState(() => _error = 'Please select an option to continue.');
      return;
    }
    if (_index < questionnaire.questions.length - 1) {
      setState(() {
        _index += 1;
        _error = null;
      });
      _focusHeading();
      return;
    }
    if (questionnaire.questions.any(
      (question) => !_answers.containsKey(question.id),
    )) {
      setState(() => _error = 'Please answer every required question.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _client!.submit({
        'questionnaire_id': questionnaire.id,
        'questionnaire_version': questionnaire.version,
        'answers': questionnaire.questions
            .map(
              (question) => {
                'question_id': question.id,
                'answer_code': _answers[question.id],
              },
            )
            .toList(),
      }, correlationId: _journey?.correlationId);
      if (mounted) setState(() => _result = result);
    } on S2RiskException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'The assessment service is unavailable. Please retry.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        _focusHeading();
      }
    }
  }

  void _restart() {
    setState(() {
      _result = null;
      _answers.clear();
      _index = 0;
      _preset = null;
      _error = null;
    });
    _focusHeading();
  }

  Widget _heading(String value) => Focus(
    focusNode: _headingFocus,
    child: Semantics(
      header: true,
      child: Text(value, style: Theme.of(context).textTheme.headlineSmall),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final result = _result;
    final questionnaire = _questionnaire;
    return SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: AppCard(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Sprint 2 · ${_api ? 'Local API pilot' : 'Synthetic fixture replay'}',
                    style: const TextStyle(
                      color: AppTheme.primary,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_loading)
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        questionnaire == null
                            ? 'Loading questionnaire…'
                            : 'Calculating educational profile…',
                      ),
                    ),
                  if (!_allowed && !_loading && _error == null) ...[
                    _heading('Complete onboarding first'),
                    const Text(
                      'Educational consent and a completed local profile are required before this pilot.',
                    ),
                    TextButton(
                      onPressed: () => context.go(widget.onboardingPath),
                      child: const Text('Return to onboarding'),
                    ),
                  ],
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Semantics(
                        key: const Key('s2-error'),
                        liveRegion: true,
                        child: Text(
                          _error!,
                          style: const TextStyle(color: Colors.redAccent),
                        ),
                      ),
                    ),
                  if ((_allowed || _error != null) &&
                      questionnaire == null &&
                      !_loading) ...[
                    _heading('Educational risk questionnaire'),
                    ElevatedButton(
                      key: const Key('s2-retry-load'),
                      onPressed: _load,
                      child: const Text('Retry questionnaire'),
                    ),
                  ],
                  if (result != null) ...[
                    _heading('Your educational risk profile'),
                    const SizedBox(height: 12),
                    const Text(
                      'Self-reported answers, not a suitability decision.',
                    ),
                    const SizedBox(height: 16),
                    Text(
                      result.category,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    Text('Composite: ${_score(result.composite)}/100'),
                    Text('Willingness: ${_score(result.willingness)}/100'),
                    Text('Capacity: ${_score(result.capacity)}/100'),
                    const SizedBox(height: 16),
                    Text(result.summary),
                    const SizedBox(height: 8),
                    Text(result.dimensions),
                    const SizedBox(height: 8),
                    Text(result.method),
                    if (result.tension != null) ...[
                      const SizedBox(height: 8),
                      Text(result.tension!),
                    ],
                    const SizedBox(height: 16),
                    Text(
                      'Questionnaire ${result.questionnaireVersion} · ${result.scoringVersion} · Calculated ${result.calculatedAt}',
                    ),
                    const SizedBox(height: 16),
                    const Text(s2RiskLimitation),
                    const SizedBox(height: 12),
                    const Text(
                      'Answers and results stay in memory only. This pilot does not save an assessment.',
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      key: const Key('s2-restart'),
                      onPressed: _restart,
                      child: const Text('Start a new assessment'),
                    ),
                  ] else if (_allowed && questionnaire != null)
                    ..._questionWidgets(questionnaire),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _questionWidgets(S2Questionnaire questionnaire) {
    final question = questionnaire.questions[_index];
    final profiles = _client!.profiles;
    return [
      _heading('Question ${_index + 1} of ${questionnaire.questions.length}'),
      const SizedBox(height: 8),
      Text(
        'Questionnaire ${questionnaire.version} · ${questionnaire.contractVersion}',
      ),
      const SizedBox(height: 12),
      Semantics(
        label: 'Question ${_index + 1} of 10',
        child: LinearProgressIndicator(
          value: (_index + 1) / questionnaire.questions.length,
        ),
      ),
      if (profiles.isNotEmpty) ...[
        const SizedBox(height: 20),
        DropdownButtonFormField<String>(
          key: const Key('s2-preset'),
          initialValue: _preset,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: 'Approved synthetic profile',
          ),
          items: profiles
              .map(
                (profile) => DropdownMenuItem(
                  value: profile['case_id'] as String,
                  child: Text(
                    profile['title'] as String,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              )
              .toList(),
          onChanged: _loading
              ? null
              : (value) {
                  if (value == null) return;
                  final profile = profiles.singleWhere(
                    (row) => row['case_id'] == value,
                  );
                  setState(() {
                    _preset = value;
                    _answers.clear();
                    for (final answer
                        in (profile['request'] as Map)['answers'] as List) {
                      _answers[answer['question_id'] as String] =
                          answer['answer_code'] as String;
                    }
                    _error = null;
                  });
                },
        ),
        const SizedBox(height: 8),
        const Text(
          'Offline mode replays approved vectors only. Use the local API for other answer combinations.',
        ),
      ],
      const SizedBox(height: 20),
      Semantics(
        header: true,
        child: Text(
          question.text,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      RadioGroup<String>(
        groupValue: _answers[question.id],
        onChanged: (value) {
          if (!_loading && value != null) {
            setState(() {
              _answers[question.id] = value;
              _error = null;
            });
          }
        },
        child: Column(
          children: question.options
              .map(
                (option) => RadioListTile<String>(
                  key: Key('s2-option-${option.code}'),
                  value: option.code,
                  enabled: !_loading,
                  contentPadding: EdgeInsets.zero,
                  title: Text(option.label),
                ),
              )
              .toList(),
        ),
      ),
      const SizedBox(height: 16),
      const Text(s2RiskLimitation),
      const SizedBox(height: 20),
      OutlinedButton(
        key: const Key('s2-previous'),
        onPressed: _loading || _index == 0
            ? null
            : () {
                setState(() {
                  _index -= 1;
                  _error = null;
                });
                _focusHeading();
              },
        child: const Text('Previous question'),
      ),
      const SizedBox(height: 10),
      ElevatedButton(
        key: const Key('s2-next'),
        onPressed: _loading ? null : _next,
        child: Text(
          _index < 9
              ? 'Next question'
              : _error != null
              ? 'Retry assessment'
              : 'Calculate educational profile',
        ),
      ),
    ];
  }

  String _score(num value) => value == value.roundToDouble()
      ? value.toInt().toString()
      : value.toString();
}
