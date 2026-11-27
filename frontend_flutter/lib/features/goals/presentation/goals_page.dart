import 'package:flutter/material.dart';

import '../../../core/local_application/local_session.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_view.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_view.dart';
import '../models/goal_models.dart';
import '../services/goal_service.dart';

class GoalsPage extends StatefulWidget {
  final LocalSession? session;
  final GoalService? service;

  const GoalsPage({super.key, this.session, this.service});

  @override
  State<GoalsPage> createState() => _GoalsPageState();
}

class _GoalsPageState extends State<GoalsPage> {
  late GoalService _service;

  // Data state
  bool _loading = true;
  String? _errorMessage;
  List<GoalResponse> _goals = [];
  String? _expandedGoalId;

  // Create form state
  bool _showCreateForm = false;
  final _titleController = TextEditingController();
  final _targetController = TextEditingController();
  final _currentController = TextEditingController(text: '0');
  final _horizonController = TextEditingController(text: '5');
  final _monthlyController = TextEditingController(text: '0');
  final _returnController = TextEditingController(text: '6.0');
  bool _submitting = false;
  String? _formValidationError;
  String? _formError;
  String? _successMessage;

  @override
  void initState() {
    super.initState();
    _initService();
    _loadGoals();
  }

  void _initService() {
    if (widget.service != null) {
      _service = widget.service!;
    } else {
      _service = GoalService();
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _targetController.dispose();
    _currentController.dispose();
    _horizonController.dispose();
    _monthlyController.dispose();
    _returnController.dispose();
    super.dispose();
  }

  Future<void> _loadGoals() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      final goals = await _service.getGoals();
      if (!mounted) return;
      setState(() {
        _goals = goals;
        _loading = false;
      });
    } on GoalException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '${e.code}: ${e.message}';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to connect to goals service.';
        _loading = false;
      });
    }
  }

  Future<void> _createGoal() async {
    if (_submitting) return;

    setState(() {
      _formValidationError = null;
      _formError = null;
      _successMessage = null;
    });

    final title = _titleController.text.trim();
    final target = double.tryParse(_targetController.text.trim());
    final current = double.tryParse(_currentController.text.trim()) ?? 0.0;
    final horizon = int.tryParse(_horizonController.text.trim());
    final monthly = double.tryParse(_monthlyController.text.trim()) ?? 0.0;
    final ret = double.tryParse(_returnController.text.trim()) ?? 6.0;

    if (title.isEmpty) {
      setState(() => _formValidationError = 'Please enter a goal title.');
      return;
    }
    if (title.length > 100) {
      setState(
        () => _formValidationError = 'Title cannot exceed 100 characters.',
      );
      return;
    }
    if (target == null || target <= 0) {
      setState(
        () => _formValidationError = 'Target amount must be greater than zero.',
      );
      return;
    }
    if (current < 0) {
      setState(
        () => _formValidationError = 'Current amount cannot be negative.',
      );
      return;
    }
    if (horizon == null || horizon <= 0 || horizon > 50) {
      setState(
        () => _formValidationError = 'Horizon must be between 1 and 50 years.',
      );
      return;
    }
    if (monthly < 0) {
      setState(
        () => _formValidationError = 'Monthly contribution cannot be negative.',
      );
      return;
    }
    if (ret < 0 || ret > 30) {
      setState(
        () => _formValidationError =
            'Expected annual return must be between 0% and 30%.',
      );
      return;
    }

    final request = GoalCreateRequest(
      title: title,
      targetAmount: target,
      currentAmount: current,
      horizonYears: horizon,
      monthlyContribution: monthly,
      expectedAnnualReturnPct: ret,
    );

    setState(() => _submitting = true);

    try {
      final created = await _service.createGoal(request);
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _showCreateForm = false;
        _successMessage =
            'Goal "${created.title}" created successfully with projections.';
        _titleController.clear();
        _targetController.clear();
        _currentController.text = '0';
        _horizonController.text = '5';
        _monthlyController.text = '0';
        _returnController.text = '6.0';
      });
      await _loadGoals();
    } on GoalException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _formError = '${e.code}: ${e.message}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _formError =
            'Failed to save goal due to network error. Please try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Financial Goals & Projections'),
        actions: [
          IconButton(
            key: const Key('goals-refresh-btn'),
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh goals',
            onPressed: _submitting ? null : _loadGoals,
          ),
          IconButton(
            key: const Key('goals-add-toggle-btn'),
            icon: Icon(_showCreateForm ? Icons.close : Icons.add),
            tooltip: _showCreateForm ? 'Cancel' : 'Add new goal',
            onPressed: () {
              setState(() {
                _showCreateForm = !_showCreateForm;
                _formValidationError = null;
                _formError = null;
              });
            },
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading && _goals.isEmpty) {
      return const LoadingView(message: 'Loading your financial goals...');
    }

    if (_errorMessage != null && _goals.isEmpty) {
      return ErrorView(message: _errorMessage!, onRetry: _loadGoals);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildEducationalBanner(),
          const SizedBox(height: 16),
          if (_successMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF064E3B),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFF059669)),
              ),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _successMessage!,
                  key: const Key('goal-create-success'),
                  style: const TextStyle(
                    color: Color(0xFFA7F3D0),
                    fontSize: 13,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
          if (_showCreateForm) ...[
            _buildCreateGoalCard(),
            const SizedBox(height: 16),
          ],
          _buildGoalsListHeader(),
          const SizedBox(height: 12),
          if (_goals.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: EmptyView(
                title: 'No Goals Set Yet',
                message: 'Tap the "+" button above to create your first financial goal and project future returns.',
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _goals.length,
              separatorBuilder: (_, _) => const SizedBox(height: 14),
              itemBuilder: (context, idx) => _buildGoalCard(_goals[idx]),
            ),
        ],
      ),
    );
  }

  Widget _buildEducationalBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.flag_outlined, color: Color(0xFF38BDF8), size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                Text(
                  'Educational Financial Planning',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color: Color(0xFFF1F5F9),
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Goal projections use deterministic monthly compounding formulas. Fees, slippage and taxes are not modeled. Projections are educational and not personalized investment advice.',
                  style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGoalsListHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          'Active Goals',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        Text(
          '${_goals.length} saved goal(s)',
          style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
        ),
      ],
    );
  }

  Widget _buildCreateGoalCard() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Create New Goal',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('goal-title-input'),
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: 'Goal Title',
              hintText: 'e.g. Retirement Cushion, House Down Payment',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('goal-target-input'),
                  controller: _targetController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Target Amount (\$)',
                    hintText: '50000',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  key: const Key('goal-current-input'),
                  controller: _currentController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Current Amount (\$)',
                    hintText: '0',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('goal-horizon-input'),
                  controller: _horizonController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Horizon (Years)',
                    hintText: '5',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  key: const Key('goal-monthly-input'),
                  controller: _monthlyController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Monthly Deposit (\$)',
                    hintText: '250',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('goal-return-input'),
            controller: _returnController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Expected Return % p.a.',
              hintText: '6.0',
              border: OutlineInputBorder(),
            ),
          ),
          if (_formValidationError != null) ...[
            const SizedBox(height: 10),
            Text(
              _formValidationError!,
              key: const Key('goal-validation-error'),
              style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13),
            ),
          ],
          if (_formError != null) ...[
            const SizedBox(height: 10),
            Text(
              _formError!,
              key: const Key('goal-form-error'),
              style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13),
            ),
          ],
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _submitting
                      ? null
                      : () => setState(() => _showCreateForm = false),
                  child: const Text('Cancel'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: AppButton(
                  key: const Key('goal-submit-btn'),
                  label: _submitting ? 'Saving...' : 'Save & Calculate',
                  loading: _submitting,
                  onPressed: _submitting ? null : _createGoal,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildGoalCard(GoalResponse goal) {
    final isExpanded = _expandedGoalId == goal.goalId;
    final onTrack = goal.isOnTrack;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  goal.title,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: onTrack
                      ? const Color(0xFF065F46)
                      : const Color(0xFF78350F),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  onTrack ? 'ON TRACK' : 'SHORTFALL',
                  style: TextStyle(
                    color: onTrack
                        ? const Color(0xFFA7F3D0)
                        : const Color(0xFFFDE68A),
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // Progress bar
          LinearProgressIndicator(
            value: goal.progressPct / 100.0,
            backgroundColor: const Color(0xFF334155),
            color: onTrack ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
            minHeight: 6,
            borderRadius: BorderRadius.circular(3),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Current: \$${goal.currentAmount.toStringAsFixed(2)} (${goal.progressPct.toStringAsFixed(1)}%)',
                style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
              ),
              Text(
                'Target: \$${goal.targetAmount.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFFF8FAFC),
                ),
              ),
            ],
          ),
          const Divider(height: 20),
          Row(
            children: [
              Expanded(
                child: _goalDetailItem('Horizon', '${goal.horizonYears} yr(s)'),
              ),
              Expanded(
                child: _goalDetailItem(
                  'Monthly Deposit',
                  '\$${goal.monthlyContribution.toStringAsFixed(2)}',
                ),
              ),
              Expanded(
                child: _goalDetailItem(
                  'Projected Final',
                  '\$${goal.projectedFinalAmount.toStringAsFixed(2)}',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            goal.assumptionsStatement,
            style: const TextStyle(
              fontSize: 11,
              fontStyle: FontStyle.italic,
              color: Color(0xFF64748B),
            ),
          ),
          if (goal.projections.isNotEmpty) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              key: Key('toggle-projections-${goal.goalId}'),
              icon: Icon(
                isExpanded ? Icons.expand_less : Icons.expand_more,
                size: 18,
              ),
              label: Text(
                isExpanded ? 'Hide Projections' : 'View Projections Breakdown',
              ),
              onPressed: () {
                setState(() {
                  _expandedGoalId = isExpanded ? null : goal.goalId;
                });
              },
            ),
            if (isExpanded) _buildProjectionsTable(goal.projections),
          ],
        ],
      ),
    );
  }

  Widget _goalDetailItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }

  Widget _buildProjectionsTable(List<GoalProjection> projections) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text(
                'Year',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
              ),
              Text(
                'Projected Total',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
              ),
              Text(
                'Contributions',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
              ),
              Text(
                'Growth',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
              ),
            ],
          ),
          const Divider(height: 12),
          for (final p in projections)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Yr ${p.year}', style: const TextStyle(fontSize: 11)),
                  Text(
                    '\$${p.projectedBalance.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    '\$${p.contributionsTotal.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFF94A3B8),
                    ),
                  ),
                  Text(
                    '\$${p.growthTotal.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFF10B981),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
