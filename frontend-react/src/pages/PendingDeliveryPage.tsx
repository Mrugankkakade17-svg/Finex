import React from 'react';
import { Link } from 'react-router-dom';

export function PendingDeliveryPage({ feature }: { feature: string; sprint?: string }) {
  return (
    <section className="local-card">
      <p className="local-eyebrow">Module preview</p>
      <h1 tabIndex={-1}>{feature} delivery is pending</h1>
      <p className="local-lede">
        Your current session and onboarding have been checked, and this module is being connected.
        No hardcoded financial metrics or pretend saves are shown.
      </p>
      <Link className="btn-secondary" to="/dashboard">
        Return to your learning space
      </Link>
    </section>
  );
}
