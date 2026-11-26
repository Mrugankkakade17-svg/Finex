import React, { useState } from 'react';
import { Target, TrendingUp, Calendar, Sparkles, Plus } from 'lucide-react';

interface GoalItem {
  id: string;
  title: string;
  current: number;
  target: number;
  pct: number;
  targetDate: string;
  monthly: string;
  status: 'On Track' | 'Building Momentum';
}

export const GoalsPage: React.FC = () => {
  const [goals, setGoals] = useState<GoalItem[]>([
    {
      id: 'goal-1',
      title: 'Weekend away',
      current: 34000,
      target: 50000,
      pct: 68,
      targetDate: 'Next Quarter',
      monthly: '₹ 4,000',
      status: 'On Track',
    },
    {
      id: 'goal-2',
      title: 'Emergency Cushion',
      current: 135000,
      target: 200000,
      pct: 67,
      targetDate: 'Dec 2027',
      monthly: '₹ 6,500',
      status: 'On Track',
    },
    {
      id: 'goal-3',
      title: 'Home Down Payment',
      current: 240000,
      target: 800000,
      pct: 30,
      targetDate: 'Jun 2029',
      monthly: '₹ 15,000',
      status: 'Building Momentum',
    },
  ]);

  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newTarget, setNewTarget] = useState('50000');

  const handleAddGoal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const targetVal = Number(newTarget) || 50000;
    const nextGoal: GoalItem = {
      id: `goal-${Date.now()}`,
      title: newTitle.trim(),
      current: Math.round(targetVal * 0.25),
      target: targetVal,
      pct: 25,
      targetDate: 'Custom Horizon',
      monthly: `₹ ${Math.max(1000, Math.round(targetVal / 12)).toLocaleString('en-IN')}`,
      status: 'On Track',
    };
    setGoals((prev) => [nextGoal, ...prev]);
    setNewTitle('');
    setShowNew(false);
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '14px',
          marginBottom: '28px',
        }}
      >
        <div>
          <p className="local-eyebrow">FOR YOUR GOALS</p>
          <h2 style={{ fontSize: '2rem', color: 'var(--color-text)' }}>
            Save in your own rhythm
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.98rem' }}>
            Deterministic projection scenarios and milestone tracking for every step ahead
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowNew((v) => !v)}
          style={{ fontSize: '0.92rem' }}
        >
          <Plus size={16} /> Add New Goal
        </button>
      </div>

      {showNew && (
        <form
          onSubmit={handleAddGoal}
          className="glass-card"
          style={{
            padding: '24px',
            marginBottom: '24px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '14px',
            alignItems: 'flex-end',
          }}
        >
          <div style={{ flex: '1 1 220px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.82rem',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginBottom: '6px',
              }}
            >
              Goal Title
            </label>
            <input
              type="text"
              placeholder="e.g. Solo trip to Goa"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              style={{ width: '100%' }}
              required
            />
          </div>
          <div style={{ flex: '1 1 180px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.82rem',
                fontWeight: 700,
                color: 'var(--color-text)',
                marginBottom: '6px',
              }}
            >
              Target Amount (₹)
            </label>
            <input
              type="number"
              min="1000"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              style={{ width: '100%' }}
              required
            />
          </div>
          <button type="submit" className="btn-primary">
            <Sparkles size={16} /> Create Goal
          </button>
        </form>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}
      >
        {goals.map((goal, idx) => (
          <div
            key={goal.id}
            className="glass-card"
            style={{
              padding: '28px',
              borderRadius: '24px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '12px',
              }}
            >
              <span
                style={{
                  fontSize: '0.76rem',
                  fontWeight: 800,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--color-text-muted)',
                }}
              >
                {idx === 0 ? 'NEXT GOAL' : 'MILESTONE'}
              </span>
              <span
                className={goal.status === 'On Track' ? 'badge badge-success' : 'badge badge-warning'}
              >
                {goal.status}
              </span>
            </div>

            <div
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: '2.1rem',
                fontWeight: 800,
                color: 'var(--color-text)',
                letterSpacing: '-0.03em',
                marginBottom: '6px',
              }}
            >
              ₹ {goal.target.toLocaleString('en-IN')}
            </div>

            <div
              style={{
                fontSize: '0.85rem',
                color: 'var(--color-text-muted)',
                marginBottom: '18px',
              }}
            >
              Saved so far: <strong>₹ {goal.current.toLocaleString('en-IN')}</strong> · Target:{' '}
              {goal.targetDate}
            </div>

            {/* Divider matching Good Money Energy card */}
            <div
              style={{
                height: '1.5px',
                background: 'var(--color-surface-divider)',
                marginBottom: '16px',
              }}
            />

            {/* Progress Bar */}
            <div
              style={{
                height: '8px',
                background: 'var(--color-surface-divider)',
                borderRadius: '999px',
                overflow: 'hidden',
                marginBottom: '16px',
              }}
            >
              <div
                style={{
                  width: `${goal.pct}%`,
                  height: '100%',
                  background:
                    goal.status === 'On Track'
                      ? 'linear-gradient(90deg, var(--color-accent-violet), var(--color-accent-coral))'
                      : 'linear-gradient(90deg, var(--color-accent-coral), #C97A10)',
                  borderRadius: '999px',
                  transition: 'width 0.8s ease',
                }}
              />
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {idx % 2 === 0 ? (
                  <Target size={18} color="var(--color-accent-coral)" />
                ) : (
                  <TrendingUp size={18} color="var(--color-accent-violet)" />
                )}
                <span style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text)' }}>
                  {goal.title}
                </span>
              </div>
              <span
                style={{
                  fontWeight: 800,
                  fontSize: '1.05rem',
                  color: 'var(--color-accent-violet)',
                }}
              >
                {goal.pct}%
              </span>
            </div>

            <div
              style={{
                fontSize: '0.82rem',
                color: 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Calendar size={14} /> Monthly rhythm: <strong>{goal.monthly}</strong>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
