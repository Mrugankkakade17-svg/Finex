import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppShell } from './AppShell';

jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { displayName: 'Unrelated mock user', riskProfile: 'MODERATE', avatarUrl: '/mock' },
    isAuthenticated: true,
    toggleAuth: jest.fn(),
    logout: jest.fn(),
  }),
}));

test.each(['/risk', '/onboarding', '/consent'])(
  'educational pilot shell does not present a mock identity or precomputed risk at %s',
  (path) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <AppShell>
          <p>Pilot</p>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.queryByText('Unrelated mock user')).not.toBeInTheDocument();
    expect(screen.queryByText('MODERATE Risk')).not.toBeInTheDocument();
    expect(screen.getByText('No saved assessment')).toBeInTheDocument();
    expect(screen.getByText(path === '/risk' ? 'Sprint 2' : 'Sprint 1')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mock Auth:/ })).not.toBeInTheDocument();
  },
);

test('mobile navigation exposes its state and closes after selecting a route', () => {
  render(
    <MemoryRouter initialEntries={['/risk']}>
      <AppShell>
        <p>Pilot</p>
      </AppShell>
    </MemoryRouter>,
  );
  const toggle = screen.getByRole('button', { name: 'Toggle navigation' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  fireEvent.click(screen.getByRole('link', { name: 'Onboarding' }));
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
});
