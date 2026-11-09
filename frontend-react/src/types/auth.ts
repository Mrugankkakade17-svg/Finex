export interface User {
  userId: string;
  displayName: string;
  email: string;
  avatarUrl: string;
  onboardingStatus: 'COMPLETED' | 'IN_PROGRESS' | 'NOT_STARTED';
  riskProfile?: 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';
  preferredCurrency: string;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (userData?: Partial<User>) => void;
  logout: () => void;
  toggleAuth: () => void;
  updateUser: (userData: Partial<User>) => void;
}

export interface RouteConfig {
  path: string;
  label: string;
  iconName: string;
  isProtected: boolean;
  category: 'core' | 'finance' | 'ai' | 'user';
}
