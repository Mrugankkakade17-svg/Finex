import { User } from '../types/auth';

export interface LoginRequest {
  displayName?: string;
  email?: string;
}

export interface LoginResponse {
  user: User;
  isAuthenticated: boolean;
}

const MOCK_USER: User = {
  userId: 'usr_alpha_khyati_01',
  displayName: 'Khyati',
  email: 'khyati@finex.app',
  avatarUrl:
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  onboardingStatus: 'COMPLETED',
  riskProfile: 'MODERATE',
  preferredCurrency: 'USD',
};

export const authService = {
  login: async (
    request?: LoginRequest
  ): Promise<LoginResponse> => {
    // Mock response while backend/API is pending.
    await new Promise((resolve) => setTimeout(resolve, 300));

    return {
      user: {
        ...MOCK_USER,
        ...(request?.displayName
          ? { displayName: request.displayName }
          : {}),
        ...(request?.email
          ? { email: request.email }
          : {}),
      },
      isAuthenticated: true,
    };
  },

  logout: async (): Promise<void> => {
    // Mock response while backend/API is pending.
    await new Promise((resolve) => setTimeout(resolve, 200));
  },

  getCurrentUser: async (): Promise<User> => {
    // Mock response while backend/API is pending.
    await new Promise((resolve) => setTimeout(resolve, 200));

    return MOCK_USER;
  },
};