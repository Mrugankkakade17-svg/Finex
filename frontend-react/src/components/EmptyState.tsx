import React from 'react';
import { Inbox } from 'lucide-react';
import './SharedStates.css';

export interface EmptyStateProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
  testId?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  message,
  actionLabel,
  onAction,
  icon,
  testId = 'shared-empty-state',
}) => {
  return (
    <div data-testid={testId} className="fx-state-card fx-state-card--center">
      <div style={{ color: 'var(--color-text-muted, #496368)' }} aria-hidden="true">
        {icon ?? <Inbox size={28} />}
      </div>
      <h3 style={{ fontSize: '1.08rem', color: 'var(--color-text, #182c31)', margin: 0 }}>{title}</h3>
      <p className="fx-state-card__message" style={{ maxWidth: '520px', marginTop: 0 }}>
        {message}
      </p>
      {actionLabel && onAction && (
        <button type="button" className="btn-primary" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
};
