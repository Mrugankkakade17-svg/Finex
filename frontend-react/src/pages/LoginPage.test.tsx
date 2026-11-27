import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { AuthProvider } from '../context/AuthContext';
import { authService } from '../services/authService';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

describe('LoginPage (PR #150 preserved UI and dynamic demo login)', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockReset();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('renders Good Money Energy welcome screen and supports dynamic user login', async () => {
    const loginSpy = jest.spyOn(authService, 'login').mockResolvedValue({
      user: {
        userId: 'usr_finex_member_01',
        displayName: 'Aarav',
        email: 'aarav@finex.app',
        avatarUrl: '',
        onboardingStatus: 'COMPLETED',
        riskProfile: 'MODERATE',
        preferredCurrency: 'INR',
      },
      isAuthenticated: true,
    });

    render(
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.getByRole('heading', { name: 'Welcome to finex*' })).toBeInTheDocument();
    expect(screen.getByText('Your Money, In Your Orbit:')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Your Name'), { target: { value: 'Aarav' } });
    fireEvent.click(screen.getByRole('button', { name: /Sign In & Build Your Rhythm/i }));

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith({ displayName: 'Aarav' });
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  test('supports quick demo login flow', async () => {
    const loginSpy = jest.spyOn(authService, 'login').mockResolvedValue({
      user: {
        userId: 'usr_finex_member_01',
        displayName: 'Demo Investor',
        email: 'demo.investor@finex.app',
        avatarUrl: '',
        onboardingStatus: 'COMPLETED',
        riskProfile: 'MODERATE',
        preferredCurrency: 'INR',
      },
      isAuthenticated: true,
    });

    render(
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Quick Demo Login/i }));

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith({ displayName: 'Demo Investor' });
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });
});
