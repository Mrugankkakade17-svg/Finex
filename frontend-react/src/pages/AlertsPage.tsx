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
