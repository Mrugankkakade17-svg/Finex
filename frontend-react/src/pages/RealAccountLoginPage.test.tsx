import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RealAccountLoginPage } from './RealAccountLoginPage';
import { ApiClientError, finexApiClient } from '../services/apiClient';
import { clearActiveAuthSession, getActiveAuthSession, realAuthService } from '../services/authService';

describe('RealAccountLoginPage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearActiveAuthSession();
  });

  afterEach(() => {
    clearActiveAuthSession();
    jest.restoreAllMocks();
  });

  test('renders login form by default and switches cleanly to registration form', () => {
    render(<RealAccountLoginPage />);

    expect(screen.getByRole('heading', { name: 'FinEx account' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Sign in' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByLabelText(/Full name/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));

    expect(screen.getByRole('tab', { name: 'Create account' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText(/Full name/i)).toBeInTheDocument();
  });

  test('rejects whitespace-only and too-short-after-trim full names without submitting', async () => {
    const registerSpy = jest.spyOn(realAuthService, 'register');
    render(<RealAccountLoginPage />);

    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));
    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: '    ' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'learner@example.test' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Full name is required.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toHaveAttribute('aria-invalid', 'true');
    expect(registerSpy).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: '  a  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Full name must be at least 2 characters.')).toBeInTheDocument();
    expect(registerSpy).not.toHaveBeenCalled();
  });

  test('validates email and password fields on registration before calling API', () => {
    const registerSpy = jest.spyOn(realAuthService, 'register');
    render(<RealAccountLoginPage />);

    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));
    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: 'Learner One' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'invalid-email' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByText('Password must be at least 8 characters.')).toBeInTheDocument();
    expect(registerSpy).not.toHaveBeenCalled();
  });

  test('clears password after registration-to-login transition and after direct login', async () => {
    const requestSpy = jest.spyOn(finexApiClient, 'request')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          data: { access_token: 'reg.a', refresh_token: 'reg.r', token_type: 'bearer' },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          data: { access_token: 'login.a', refresh_token: 'login.r', token_type: 'bearer' },
        }),
      } as Response);

    render(<RealAccountLoginPage />);

    // Registration flow -> transitions to Sign in and clears password
    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));
    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: '  Learner One  ' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: '  learner@example.test  ' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'secret1234' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Your account was created. You can now sign in.');
    });

    expect(requestSpy).toHaveBeenNthCalledWith(
      1,
      '/api/v1/auth/register',
      expect.objectContaining({
        body: JSON.stringify({
          name: 'Learner One',
          email: 'learner@example.test',
          password: 'secret1234',
        }),
      }),
    );
    expect(screen.getByRole('tab', { name: 'Sign in' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText(/Password/i)).toHaveValue('');
    expect(getActiveAuthSession()).toBeNull();

    // Direct login flow -> clears password state and input, keeps tokens in memory only
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'secret1234' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(
        'Sign-in succeeded. Real-account sessions are not connected to the local educational application.',
      );
    });

    expect(screen.getByLabelText(/Password/i)).toHaveValue('');
    expect(getActiveAuthSession()).toEqual({
      access_token: 'login.a',
      refresh_token: 'login.r',
      token_type: 'bearer',
    });
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test('displays backend HTTP 422 VALIDATION_ERROR field errors from API', async () => {
    jest.spyOn(realAuthService, 'register').mockRejectedValueOnce(
      new ApiClientError('Full name must be at least 2 characters. Enter a valid email address.', 'VALIDATION_ERROR', {
        status: 422,
        fieldErrors: {
          name: 'Full name must be at least 2 characters.',
          email: 'Enter a valid email address.',
        },
      }),
    );

    render(<RealAccountLoginPage />);
    fireEvent.click(screen.getByRole('tab', { name: 'Create account' }));
    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: 'Learner One' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'learner@example.test' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'secret1234' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => {
      expect(screen.getByText('Full name must be at least 2 characters.')).toBeInTheDocument();
    });
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/Email/i)).toHaveAttribute('aria-invalid', 'true');
  });

  test.each([
    ['EMAIL_EXISTS', 'An account with this email already exists.'],
    ['INVALID_CREDENTIALS', 'Email or password is incorrect.'],
    ['RATE_LIMIT_EXCEEDED', 'Too many failed attempts. Please wait before trying again.'],
    ['DATABASE_UNAVAILABLE', 'The account service is temporarily unavailable. Please try again later.'],
  ])('displays safe user-friendly message for %s API failure', async (code, expectedMessage) => {
    jest.spyOn(finexApiClient, 'request').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error: { code, message: 'raw backend secret details' } }),
    } as Response);

    render(<RealAccountLoginPage />);
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'learner@example.test' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'secret1234' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(expectedMessage);
    });
    expect(screen.queryByText(/raw backend secret details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/secret1234/i)).not.toBeInTheDocument();
  });
});
