import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import './SharedStates.css';

export interface ErrorStateProps {
  title?: string;
  message: string;
  errorCode?: string;
  onRetry?: () => void;
  retryLabel?: string;
  testId?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Unable to load data',
  message,
  errorCode,
  onRetry,
  retryLabel = 'Retry',
  testId = 'shared-error-state',
}) => {
  return (
    <div role="alert" data-testid={testId} className="fx-state-card fx-state-card--error">
      <div className="fx-state-card__header">
        <div>
          <div className="fx-state-card__title">
            <AlertTriangle size={18} color="var(--status-error, #D9483B)" aria-hidden="true" />
            <span>{title}</span>
          </div>
          <p className="fx-state-card__message">{message}</p>
          {errorCode && <span className="fx-state-card__code">{errorCode}</span>}
        </div>
        {onRetry && (
          <button type="button" className="btn-secondary" onClick={onRetry}>
            <RefreshCw size={14} aria-hidden="true" />
            <span>{retryLabel}</span>
          </button>
        )}
      </div>
    </div>
  );
};
