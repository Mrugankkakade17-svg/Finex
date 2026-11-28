import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { CapabilityBanner, EmptyState, ErrorState, LoadingState } from './index';

describe('Shared UI state components', () => {
  test('LoadingState renders accessible busy status', () => {
    render(<LoadingState title="Loading goals" message="Fetching saved records" />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Loading goals')).toBeInTheDocument();
    expect(screen.getByText('Fetching saved records')).toBeInTheDocument();
  });

  test('EmptyState renders title, message, and optional action button', () => {
    const onAction = jest.fn();
    render(
      <EmptyState
        title="Nothing saved"
        message="Create your first item."
        actionLabel="Create item"
        onAction={onAction}
      />
    );
    expect(screen.getByText('Nothing saved')).toBeInTheDocument();
    expect(screen.getByText('Create your first item.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create item' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  test('ErrorState renders alert, error code, and retry callback', () => {
    const onRetry = jest.fn();
    render(
      <ErrorState
        title="Request failed"
        message="Backend unreachable."
        errorCode="API_UNAVAILABLE"
        onRetry={onRetry}
      />
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Request failed')).toBeInTheDocument();
    expect(screen.getByText('Backend unreachable.')).toBeInTheDocument();
    expect(screen.getByText('API_UNAVAILABLE')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test('CapabilityBanner displays capability kind, status, and notice', () => {
    const { rerender } = render(
      <CapabilityBanner
        kind="EDUCATIONAL"
        featureName="Goal Planning"
        summary="Deterministic projections only."
        status="AVAILABLE"
      />
    );
    expect(screen.getByText('EDUCATIONAL')).toBeInTheDocument();
    expect(screen.getByText('Backend connected')).toBeInTheDocument();
    expect(screen.getByText(/Deterministic projections only\./)).toBeInTheDocument();

    rerender(
      <CapabilityBanner
        kind="OPERATIONS"
        featureName="Ops"
        summary="Limited capability."
        status="LIMITED"
      />
    );
    expect(screen.getByText('Limited capability')).toBeInTheDocument();

    rerender(
      <CapabilityBanner
        kind="OPERATIONS"
        featureName="Ops"
        summary="Disabled by flag."
        status="UNAVAILABLE"
      />
    );
    expect(screen.getByText('Capability unavailable')).toBeInTheDocument();
  });
});
