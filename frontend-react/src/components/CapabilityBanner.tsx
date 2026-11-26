import React from 'react';
import { Info, ShieldAlert } from 'lucide-react';
import './SharedStates.css';

export type CapabilityKind = 'EDUCATIONAL' | 'ANALYTICAL' | 'SIMULATED' | 'OPERATIONS';
export type CapabilityStatus = 'AVAILABLE' | 'LIMITED' | 'UNAVAILABLE';

export interface CapabilityBannerProps {
  kind: CapabilityKind;
  featureName: string;
  summary: string;
  status?: CapabilityStatus;
  sourceNote?: string;
  testId?: string;
}

const KIND_BADGE_CLASS: Record<CapabilityKind, string> = {
  EDUCATIONAL: 'badge-info',
  ANALYTICAL: 'badge-info',
  SIMULATED: 'badge-warning',
  OPERATIONS: 'badge-success',
};

const STATUS_LABEL: Record<CapabilityStatus, string> = {
  AVAILABLE: 'Backend connected',
  LIMITED: 'Limited capability',
  UNAVAILABLE: 'Capability unavailable',
};

const STATUS_COLOR: Record<CapabilityStatus, string> = {
  AVAILABLE: 'var(--status-success, #1D7A5F)',
  LIMITED: 'var(--status-warning, #C97A10)',
  UNAVAILABLE: 'var(--status-error, #D9483B)',
};

export const CapabilityBanner: React.FC<CapabilityBannerProps> = ({
  kind,
  featureName,
  summary,
  status = 'AVAILABLE',
  sourceNote,
  testId = 'shared-capability-banner',
}) => {
  const kindClass = `fx-capability-banner--${kind.toLowerCase()}`;
  const statusClass = status === 'UNAVAILABLE' ? ' fx-capability-banner--unavailable' : '';
  const isUnavailable = status === 'UNAVAILABLE';

  return (
    <section
      aria-label={`${featureName} capability notice`}
      data-testid={testId}
      className={`fx-capability-banner ${kindClass}${statusClass}`}
    >
      <div>
        <div className="fx-capability-banner__meta">
          <span className={`badge ${isUnavailable ? 'badge-warning' : KIND_BADGE_CLASS[kind]}`}>
            {kind}
          </span>
          <strong style={{ color: 'var(--color-text, #182C31)', fontSize: '0.92rem' }}>
            {featureName}
          </strong>
          <span
            className="fx-capability-banner__status"
            style={{ color: STATUS_COLOR[status] }}
          >
            {STATUS_LABEL[status]}
          </span>
        </div>
        <p className="fx-capability-banner__text">
          {summary}
          {sourceNote ? ` (${sourceNote})` : ''}
        </p>
      </div>
      <div
        style={{
          color: isUnavailable ? 'var(--status-error, #D9483B)' : 'var(--color-text-muted, #496368)',
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        {isUnavailable ? <ShieldAlert size={18} /> : <Info size={18} />}
      </div>
    </section>
  );
};
