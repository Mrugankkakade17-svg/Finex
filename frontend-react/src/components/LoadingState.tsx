import React from 'react';
import { Loader2 } from 'lucide-react';
import './SharedStates.css';

export interface LoadingStateProps {
  title?: string;
  message?: string;
  testId?: string;
  compact?: boolean;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  title = 'Loading…',
  message = 'Fetching the latest confirmed data from the FinEx backend.',
  testId = 'shared-loading-state',
  compact = false,
}) => {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={testId}
      className={`fx-state-card fx-state-card--loading${compact ? '' : ' fx-state-card--center'}`}
    >
      <div className="fx-state-card__title">
        <Loader2 size={20} className="fx-spinner" aria-hidden="true" />
        <span>{title}</span>
      </div>
      {message && <p className="fx-state-card__message">{message}</p>}
    </div>
  );
};
