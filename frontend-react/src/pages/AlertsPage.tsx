import React, { useCallback, useEffect, useState } from 'react';
import { Bell, Check, Plus, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react';
import {
  CapabilityBanner,
  CapabilityStatus,
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components';
import {
  AlertConditionType,
  AlertRule,
  AlertRuleCreateInput,
  CapabilitiesSummary,
  ComparisonOperator,
  NotificationItem,
  PlatformApiClient,
  PlatformApiError,
  platformApi,
} from '../services/platformApi';

export interface AlertsPageProps {
  api?: PlatformApiClient;
}

const DEFAULT_RULE_FORM: {
  rule_name: string;
  condition_type: AlertConditionType;
  target_symbol_or_goal: string;
  comparison_operator: ComparisonOperator;
  threshold_value: string;
  cooldown_minutes: string;
} = {
  rule_name: '',
  condition_type: 'PRICE_THRESHOLD',
  target_symbol_or_goal: 'AAPL',
  comparison_operator: 'GT',
  threshold_value: '200',
  cooldown_minutes: '60',
};

export const AlertsPage: React.FC<AlertsPageProps> = ({ api = platformApi }) => {
  const [capabilities, setCapabilities] = useState<CapabilitiesSummary | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [rules, setRules] = useState<AlertRule[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [actionError, setActionError] = useState<{ message: string; code?: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState(DEFAULT_RULE_FORM);
  const [creatingRule, setCreatingRule] = useState(false);

  const loadAlerts = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      setActionError(null);
      try {
        const [caps, notifData, ruleList] = await Promise.all([
          api.getCapabilities(signal),
          api.listNotifications(signal),
          api.listAlertRules(signal),
        ]);
        if (signal?.aborted) return;
        setCapabilities(caps);
        setNotifications(notifData.notifications);
        setUnreadCount(notifData.unread_count);
        setRules(ruleList);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof PlatformApiError && err.code === 'REQUEST_CANCELLED') return;
        setError({
          message: err instanceof Error ? err.message : 'Unable to load alerts and rules.',
          code: err instanceof PlatformApiError ? err.code : undefined,
        });
        setNotifications(null);
        setRules(null);
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [api]
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadAlerts(controller.signal);
    return () => controller.abort();
  }, [loadAlerts]);

  const capabilityLimited =
    capabilities?.mounted === true && capabilities.capabilities.alerts === false;
  const bannerStatus: CapabilityStatus = error
    ? 'UNAVAILABLE'
    : capabilityLimited
      ? 'LIMITED'
      : 'AVAILABLE';

  const handleMarkRead = async (notifId: string) => {
    setActionError(null);
    setBusyId(notifId);
    try {
      const updated = await api.markNotificationRead(notifId);
      setNotifications((prev) => {
        if (!prev) return prev;
        const next = prev.map((item) => (item.notification_id === notifId ? updated : item));
        setUnreadCount(next.filter((item) => !item.is_read).length);
        return next;
      });
    } catch (err) {
      setActionError({
        message: err instanceof Error ? err.message : 'Could not mark notification as read.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setBusyId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (!notifications) return;
    const unread = notifications.filter((item) => !item.is_read);
    if (unread.length === 0) return;

    setActionError(null);
    setMarkingAll(true);
    try {
      const updatedItems = await Promise.all(
        unread.map((item) => api.markNotificationRead(item.notification_id))
      );
      const updatedMap = new Map(updatedItems.map((item) => [item.notification_id, item]));
      setNotifications((prev) => {
        if (!prev) return prev;
        const next = prev.map((item) => updatedMap.get(item.notification_id) ?? item);
        setUnreadCount(next.filter((item) => !item.is_read).length);
        return next;
      });
    } catch (err) {
      setActionError({
        message: err instanceof Error ? err.message : 'Could not mark all notifications as read.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setMarkingAll(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);

    const ruleName = ruleForm.rule_name.trim();
    const target = ruleForm.target_symbol_or_goal.trim();
    const threshold = Number(ruleForm.threshold_value);
    const cooldown = Number(ruleForm.cooldown_minutes);

    if (ruleName.length < 2) {
      setActionError({ message: 'Rule name must be at least 2 characters.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!target) {
      setActionError({ message: 'Enter a target symbol or goal identifier.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isFinite(threshold)) {
      setActionError({ message: 'Enter a valid numeric threshold.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isInteger(cooldown) || cooldown < 5 || cooldown > 1440) {
      setActionError({
        message: 'Cooldown must be between 5 and 1440 minutes.',
        code: 'VALIDATION_ERROR',
      });
      return;
    }

    const payload: AlertRuleCreateInput = {
      rule_name: ruleName,
      condition_type: ruleForm.condition_type,
      target_symbol_or_goal: target,
      comparison_operator: ruleForm.comparison_operator,
      threshold_value: threshold,
      cooldown_minutes: cooldown,
    };

    setCreatingRule(true);
    try {
      const created = await api.createAlertRule(payload);
      setRules((prev) => (prev ? [...prev, created] : [created]));
      setRuleForm(DEFAULT_RULE_FORM);
      setShowRuleForm(false);
    } catch (err) {
      setActionError({
        message: err instanceof Error ? err.message : 'Could not create alert rule.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setCreatingRule(false);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    setActionError(null);
    setBusyId(ruleId);
    try {
      await api.deleteAlertRule(ruleId);
      setRules((prev) => (prev ? prev.filter((r) => r.rule_id !== ruleId) : prev));
    } catch (err) {
      setActionError({
        message: err instanceof Error ? err.message : 'Could not delete alert rule.',
        code: err instanceof PlatformApiError ? err.code : undefined,
      });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="fx-page-header" style={{ marginBottom: '24px' }}>
        <div>
          <p className="local-eyebrow">STAY IN ORBIT</p>
          <h2 style={{ fontSize: '1.9rem', color: 'var(--color-text)' }}>
            Smart Alerts &amp; Notification Center
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Deduplicated notifications, alert rules, and read state persisted on the backend
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {!loading && !error && (
            <span className="badge badge-info" data-testid="alerts-unread-count">
              {unreadCount} unread
            </span>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadAlerts()}
            disabled={loading}
            style={{ fontSize: '0.88rem' }}
          >
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void handleMarkAllRead()}
            disabled={loading || markingAll || unreadCount === 0}
            style={{ fontSize: '0.88rem' }}
          >
            <Check size={14} aria-hidden="true" />
            {markingAll ? 'Updating…' : 'Mark All as Read'}
          </button>
        </div>
      </div>

      <CapabilityBanner
        kind="ANALYTICAL"
        featureName="Smart Alerts & Rule Evaluation"
        status={bannerStatus}
        summary={
          error
            ? 'Alert endpoints could not confirm saved rules or notifications. Retry to reconnect.'
            : capabilityLimited
              ? 'In-app notifications provide informational monitoring, not trade execution. Full-sprint capability flag is pending acceptance.'
              : 'In-app notifications are the authoritative alert record. Alerts provide informational monitoring, not trade execution.'
        }
        sourceNote={capabilities?.mounted ? 'Capabilities checked' : undefined}
        testId="alerts-capability-banner"
      />

      {actionError && (
        <div style={{ marginBottom: '20px' }}>
          <ErrorState
            title="Alert action failed"
            message={actionError.message}
            errorCode={actionError.code}
            testId="alerts-action-error"
          />
        </div>
      )}

      {loading && (
        <LoadingState
          title="Loading alerts and rules…"
          message="Fetching your in-app notifications and configured alert rules."
          testId="alerts-loading"
        />
      )}

      {!loading && error && (
        <ErrorState
          title="Failed to load alerts"
          message={error.message}
          errorCode={error.code}
          onRetry={() => void loadAlerts()}
          testId="alerts-error"
        />
      )}

      {!loading && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          <section aria-label="In-app notifications">
            <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', marginBottom: '14px' }}>
              Notifications
            </h3>
            {notifications && notifications.length === 0 ? (
              <EmptyState
                icon={<Bell size={28} />}
                title="No notifications yet"
                message="Triggered price, concentration, and goal alerts will appear here."
                testId="alerts-notifications-empty"
              />
            ) : (
              <div
                data-testid="alerts-notifications-list"
                style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                {notifications?.map((a) => (
                  <div
                    key={a.notification_id}
                    className="glass-card"
                    style={{
                      padding: '20px 24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '16px',
                      flexWrap: 'wrap',
                      borderLeft: a.is_read
                        ? '1px solid var(--color-surface-divider)'
                        : '5px solid var(--color-accent-coral)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div
                        style={{
                          padding: '12px',
                          borderRadius: '14px',
                          background: a.is_read ? '#F4F8F5' : 'rgba(255, 114, 94, 0.14)',
                        }}
                      >
                        {a.severity === 'WARNING' || a.severity === 'CRITICAL' ? (
                          <ShieldAlert size={20} color="var(--color-accent-violet)" aria-hidden="true" />
                        ) : (
                          <Bell size={20} color="var(--color-accent-coral)" aria-hidden="true" />
                        )}
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <h4 style={{ color: 'var(--color-text)', margin: 0, fontSize: '1.05rem' }}>
                            {a.title}
                          </h4>
                          <span className={`badge ${a.is_read ? 'badge-info' : 'badge-success'}`}>
                            {a.is_read ? 'Read' : 'Unread'}
                          </span>
                        </div>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', margin: 0 }}>
                          {a.body}
                        </p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                        {a.created_at}
                      </span>
                      {!a.is_read && (
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                          disabled={busyId === a.notification_id || markingAll}
                          onClick={() => void handleMarkRead(a.notification_id)}
                        >
                          {busyId === a.notification_id ? 'Saving…' : 'Mark Read'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section aria-label="Configured alert rules">
            <div className="fx-page-header" style={{ marginBottom: '14px' }}>
              <h3 style={{ fontSize: '1.15rem', color: 'var(--color-text)', margin: 0 }}>
                Alert Rules
              </h3>
              <button
                type="button"
                className="btn-primary"
                style={{ fontSize: '0.84rem', padding: '8px 14px' }}
                onClick={() => setShowRuleForm((prev) => !prev)}
              >
                <Plus size={14} aria-hidden="true" />
                {showRuleForm ? 'Cancel Rule' : 'New Alert Rule'}
              </button>
            </div>

            {showRuleForm && (
              <form
                onSubmit={handleCreateRule}
                className="glass-card"
                style={{
                  padding: '20px',
                  marginBottom: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                }}
              >
                <div className="fx-form-grid">
                  <div>
                    <label htmlFor="alert-rule-name" className="fx-label">
                      Rule Name
                    </label>
                    <input
                      id="alert-rule-name"
                      type="text"
                      className="fx-input"
                      placeholder="e.g. AAPL above 225"
                      value={ruleForm.rule_name}
                      onChange={(e) => setRuleForm((f) => ({ ...f, rule_name: e.target.value }))}
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="alert-condition-type" className="fx-label">
                      Condition Type
                    </label>
                    <select
                      id="alert-condition-type"
                      className="fx-input"
                      value={ruleForm.condition_type}
                      onChange={(e) =>
                        setRuleForm((f) => ({
                          ...f,
                          condition_type: e.target.value as AlertConditionType,
                        }))
                      }
                    >
                      <option value="PRICE_THRESHOLD">PRICE_THRESHOLD</option>
                      <option value="PCT_CHANGE">PCT_CHANGE</option>
                      <option value="CONCENTRATION_LIMIT">CONCENTRATION_LIMIT</option>
                      <option value="GOAL_OFF_TRACK">GOAL_OFF_TRACK</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="alert-target" className="fx-label">
                      Target Symbol or Goal
                    </label>
                    <input
                      id="alert-target"
                      type="text"
                      className="fx-input"
                      value={ruleForm.target_symbol_or_goal}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, target_symbol_or_goal: e.target.value }))
                      }
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="alert-operator" className="fx-label">
                      Operator
                    </label>
                    <select
                      id="alert-operator"
                      className="fx-input"
                      value={ruleForm.comparison_operator}
                      onChange={(e) =>
                        setRuleForm((f) => ({
                          ...f,
                          comparison_operator: e.target.value as ComparisonOperator,
                        }))
                      }
                    >
                      <option value="GT">GT (&gt;)</option>
                      <option value="GTE">GTE (&ge;)</option>
                      <option value="LT">LT (&lt;)</option>
                      <option value="LTE">LTE (&le;)</option>
                      <option value="EQ">EQ (=)</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="alert-threshold" className="fx-label">
                      Threshold Value
                    </label>
                    <input
                      id="alert-threshold"
                      type="number"
                      step="0.01"
                      className="fx-input"
                      value={ruleForm.threshold_value}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, threshold_value: e.target.value }))
                      }
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="alert-cooldown" className="fx-label">
                      Cooldown (Minutes)
                    </label>
                    <input
                      id="alert-cooldown"
                      type="number"
                      min="5"
                      max="1440"
                      className="fx-input"
                      value={ruleForm.cooldown_minutes}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, cooldown_minutes: e.target.value }))
                      }
                      required
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button type="submit" className="btn-primary" disabled={creatingRule}>
                    {creatingRule ? 'Saving Rule…' : 'Create Alert Rule'}
                  </button>
                </div>
              </form>
            )}

            {rules && rules.length === 0 ? (
              <EmptyState
                icon={<ShieldAlert size={28} />}
                title="No alert rules configured"
                message="Add a rule to monitor price thresholds, portfolio concentration, or goal drift."
                actionLabel="New Alert Rule"
                onAction={() => setShowRuleForm(true)}
                testId="alerts-rules-empty"
              />
            ) : (
              <div
                data-testid="alerts-rules-list"
                style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}
              >
                {rules?.map((rule) => (
                  <div
                    key={rule.rule_id}
                    className="glass-card"
                    style={{
                      padding: '16px 20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '16px',
                      flexWrap: 'wrap',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>
                        {rule.rule_name}
                      </div>
                      <div style={{ fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
                        {rule.condition_type} · {rule.target_symbol_or_goal} {rule.comparison_operator}{' '}
                        {rule.threshold_value} · Cooldown {rule.cooldown_minutes}m
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      aria-label={`Delete rule ${rule.rule_name}`}
                      disabled={busyId === rule.rule_id}
                      onClick={() => void handleDeleteRule(rule.rule_id)}
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                      {busyId === rule.rule_id ? 'Deleting…' : 'Delete'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
