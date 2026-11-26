import { User } from '../types/auth';

export interface LoginRequest {
  displayName?: string;
  email?: string;
}

export interface LoginResponse {
  user: User;
  isAuthenticated: boolean;
}

const DEFAULT_USER: User = {
  userId: 'usr_finex_member_01',
  displayName: 'Investor',
  email: 'member@finex.app',
  avatarUrl:
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  onboardingStatus: 'COMPLETED',
  riskProfile: 'MODERATE',
  preferredCurrency: 'INR',
};

export const authService = {
  login: async (
    request?: LoginRequest
  ): Promise<LoginResponse> => {
    await new Promise((resolve) => setTimeout(resolve, 180));
    const cleanName = request?.displayName?.trim();
    const generatedEmail =
      request?.email?.trim() ||
      (cleanName
        ? `${cleanName.toLowerCase().replace(/[^a-z0-9]/g, '.')}@finex.app`
        : DEFAULT_USER.email);

    return {
      user: {
        ...DEFAULT_USER,
        ...(cleanName ? { displayName: cleanName } : {}),
        email: generatedEmail,
      },
      isAuthenticated: true,
    };
  },

  logout: async (): Promise<void> => {
    await new Promise((resolve) => setTimeout(resolve, 120));
  },

  getCurrentUser: async (): Promise<User> => {
    await new Promise((resolve) => setTimeout(resolve, 120));
    const saved = localStorage.getItem('finex_auth_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // Fallback to default user
      }
    }
    return DEFAULT_USER;
  },
};
