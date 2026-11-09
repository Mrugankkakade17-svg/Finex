import 'dart:convert';

import 'package:flutter/material.dart';

import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_s2_models.dart';
import '../../../core/local_application/local_s2_page.dart';
import '../../../core/local_application/local_session.dart';
import '../../../shared/widgets/app_card.dart';

class LocalSavedRiskPage extends StatefulWidget {
  final LocalSession session;
  const LocalSavedRiskPage({super.key, required this.session});
  @override
  State<LocalSavedRiskPage> createState() => _LocalSavedRiskPageState();
}

class _LocalSavedRiskPageState extends LocalS2PageState<LocalSavedRiskPage> {
  @override
  LocalSession get session => widget.session;
  LocalRiskQuestionnaire? _questions;
  LocalRiskHistory? _history;
  LocalSavedRiskAssessment? _selected;
  final _answers = <String, String>{};
  DateTime? _draftTime;
  LocalRiskInput? _pendingInput;
  String? _pendingKey;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    if (busy) return;
    setState(() {
      _selected = null;
      _history = null;
    });
    await request(
      (scope) async => (
        (await scope.riskQuestionnaire()).value,
        (await scope.riskDraft()).value,
        (await scope.riskHistory()).value,
      ),
      (value) {
        _questions = value.$1;
        _draftTime = value.$2.updatedAt;
        _history = value.$3;
        // Reload is explicit replacement; pending submissions remain frozen.
        if (_pendingInput == null) {
          _answers.clear();
          for (final a in value.$2.input.answers) {
            _answers[a.questionId] = a.answerCode;
          }
        }
        message = 'Server-saved draft and history loaded. History pages contain at most two assessments.';
      },
    );
  }

  LocalRiskInput _input({bool complete = false}) => LocalRiskInput([
    for (final id in localQuestionIds)
      if (_answers.containsKey(id)) LocalRiskAnswer(id, _answers[id]!),
  ], complete: complete);
  Future<void> _save({bool clear = false}) async {
    final input = clear ? LocalRiskInput([]) : _input();
    await request((scope) => scope.saveRiskDraft(input), (value) {
      _answers.clear();
      for (final a in value.value.input.answers) {
        _answers[a.questionId] = a.answerCode;
      }
      _draftTime = value.value.updatedAt;
      message = clear
          ? 'Saved draft cleared on the server. Assessment history was not deleted.'
          : 'Draft saved on the server. Sign in again to resume it.';
    });
  }

  Future<void> _assess() async {
    if (_pendingInput == null) {
      if (_answers.length != 10) {
        showError(const LocalApiException('RISK_INCOMPLETE'));
        return;
      }
      _pendingInput = _input(complete: true);
      _pendingKey = newLocalRetryKey();
    }
    final input = _pendingInput!;
    final key = _pendingKey!;
    final accepted = await request((scope) => scope.assessRisk(input, key), (
      value,
    ) {
      _selected = value.value;
      _pendingInput = null;
      _pendingKey = null;
      message = 'Immutable assessment saved on the server.';
    });
    if (accepted) {
      await request((scope) => scope.riskHistory(), (value) {
        _history = value.value;
        message = 'Immutable assessment saved; history refreshed.';
      });
    }
  }

  Future<void> _historyPage(String? cursor) async {
    if (busy) return;
    setState(() => _selected = null);
    await request((scope) => scope.riskHistory(before: cursor), (value) {
      _history = value.value;
      message = 'History page loaded in server sequence order.';
    });
  }

  @override
  Widget build(BuildContext context) => page('Saved risk questionnaire', [
    const Text(
      'Questionnaire v1 • deterministic_v1.0.0 • educational_v1.0.0. Ten ordered questions; partial drafts can be saved. Scoring and explanations are produced only by the server.',
    ),
    button('Reload saved risk data', _load, key: const Key('risk-reload')),
    if (_questions != null) ...[
      Text('Rules SHA-256: ${_questions!.rulesHash}'),
      Text(
        _draftTime == null
            ? 'No saved draft yet.'
            : 'Draft updated UTC: ${_draftTime!.toIso8601String()}',
      ),
      for (final q in _questions!.questions)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: AppCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${q.id} • ${q.dimension}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(q.text),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: ValueKey('risk-${q.id}-${_answers[q.id]}'),
                  initialValue: _answers[q.id],
                  isExpanded: true,
                  itemHeight: null,
                  onTap: watchOwnedPopup,
                  decoration: InputDecoration(
                    labelText: 'Answer ${q.id}',
                    helperText: 'Choose one option; required for assessment.',
                  ),
                  items: [
                    for (final option in q.options)
                      DropdownMenuItem(
                        value: option.code,
                        child: Text(option.label),
                      ),
                  ],
                  onChanged: busy || _pendingInput != null
                      ? null
                      : (value) {
                          if (!currentPopupIntent) return;
                          endOwnedPopup();
                          setState(() {
                            if (value != null) _answers[q.id] = value;
                          });
                        },
                ),
              ],
            ),
          ),
        ),
      Text(
        '${_answers.length} of 10 answered. No score is calculated on this device.',
      ),
      button(
        'Save partial risk draft',
        () => _save(),
        key: const Key('risk-save'),
        enabled: _pendingInput == null,
      ),
      button(
        'Clear saved risk draft',
        () => _save(clear: true),
        key: const Key('risk-clear'),
        enabled: _pendingInput == null,
      ),
      button(
        _pendingInput == null
            ? 'Save immutable assessment'
            : 'Retry same frozen assessment',
        _assess,
        key: const Key('risk-assess'),
      ),
      if (_pendingInput != null) ...[
        const Text(
          'Confirmation is uncertain. The complete answers and retry UUID are frozen. Retry uses the same submission; no automatic replay.',
        ),
        button('Discard pending retry and edit', () {
          setState(() {
            _pendingInput = null;
            _pendingKey = null;
            error = null;
            message = 'Pending retry discarded locally. A previously saved assessment may still be in history; reload before a new submission.';
          });
        }),
      ],
    ],
    const SizedBox(height: 20),
    Text(
      'Immutable saved history',
      style: Theme.of(context).textTheme.titleLarge,
    ),
    if (_history != null && _history!.items.isEmpty)
      const Text('No saved assessments yet.'),
    if (_history != null)
      for (final item in _history!.items)
        button(
          '${item.category} • ${item.createdAt.toIso8601String()} • ${item.assessmentId} • open saved assessment',
          key: ValueKey('risk-history-${item.assessmentId}'),
          () => request((scope) => scope.riskAssessment(item.assessmentId), (
            value,
          ) {
            _selected = value.value;
            message = 'Original saved result and rules loaded.';
          }),
        ),
    if (_history?.nextCursor != null)
      button('Older assessments', () => _historyPage(_history!.nextCursor)),
    if (_history != null)
      button('Newest assessments', () => _historyPage(null)),
    if (_selected case final saved?)
      AppCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Saved result: ${saved.category}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              'Assessment ${saved.assessmentId} • UTC ${saved.createdAt.toIso8601String()}',
            ),
            Text(
              'Willingness ${saved.willingness}/100 • Capacity ${saved.capacity}/100 • Composite ${saved.composite}/100',
            ),
            Text(saved.summary),
            Text(saved.dimensions),
            Text(saved.method),
            if (saved.tension != null)
              Text('Informational tension: ${saved.tension}'),
            const Text(localRiskLimitation),
            const Text(
              'Original input and rules are immutable; current questionnaire changes never rescore this result.',
            ),
            for (final a in saved.input.answers)
              Text('${a.questionId}: ${a.answerCode}'),
            Text('Rules SHA-256: ${saved.rulesHash}'),
            ExpansionTile(
              title: const Text('Original approved rules and assumptions'),
              children: [
                SelectableText(
                  const JsonEncoder.withIndent('  ')
                      .convert(saved.rulesSnapshot),
                ),
              ],
            ),
          ],
        ),
      ),
  ]);
}
