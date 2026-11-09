import React from 'react';
import { Link } from 'react-router-dom';

export function PendingDeliveryPage({ feature, sprint }: { feature: string; sprint: string }) {
  return <section className="local-card">
    <p className="local-eyebrow">{sprint} · Not connected yet</p>
    <h1 tabIndex={-1}>{feature} delivery is pending</h1>
    <p className="local-lede">Your current session and onboarding have been checked, but this full-application
      feature is not delivered in Sprint 1. No hardcoded financial metrics or pretend saves are shown.</p>
    <Link className="btn-secondary" to="/dashboard">Return to your learning space</Link>
  </section>;
}
