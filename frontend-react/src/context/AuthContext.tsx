import React, {
  createContext,
  useContext,
  useState,
  useEffect,
} from 'react';
import { User, AuthContextType } from '../types/auth';
import { authService } from '../services/authService';

const defaultUser: User = {
  userId: 'usr_finex_member_01',
  displayName: 'Investor',
  email: 'member@finex.app',
  avatarUrl:
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  onboardingStatus: 'COMPLETED',
  riskProfile: 'MODERATE',
  preferredCurrency: 'INR',
};

const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);

export const AuthProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('finex_auth_user');

    if (!saved) {
      return defaultUser;
    }

    try {
      const parsed = JSON.parse(saved) as User;
      // Migrate any legacy cached 'Khyati' placeholder to the active user or default
      if (parsed && parsed.displayName === 'Khyati' && parsed.userId === 'usr_alpha_khyati_01') {
        return defaultUser;
      }
      return parsed;
    } catch {
      localStorage.removeItem('finex_auth_user');
      return defaultUser;
    }
  });

  const [isAuthenticated, setIsAuthenticated] =
    useState<boolean>(() => {
      const saved = localStorage.getItem(
        'finex_is_authenticated'
      );

      if (saved === null) {
        return false;
      }

      try {
        return JSON.parse(saved);
      } catch {
        localStorage.removeItem('finex_is_authenticated');
        return false;
      }
    });

  const [, setIsLoading] = useState(false);

  useEffect(() => {
    localStorage.setItem(
      'finex_is_authenticated',
      JSON.stringify(isAuthenticated)
    );

    if (user) {
      localStorage.setItem(
        'finex_auth_user',
        JSON.stringify(user)
      );
    } else {
      localStorage.removeItem('finex_auth_user');
    }
  }, [isAuthenticated, user]);

  const login = (userData?: Partial<User>) => {
    const cleanName = userData?.displayName?.trim();
    const updatedUser: User = {
      ...defaultUser,
      ...(user || {}),
      ...userData,
      ...(cleanName ? { displayName: cleanName } : {}),
    };

    setUser(updatedUser);
    setIsAuthenticated(true);
  };

  const logout = () => {
    setIsLoading(true);

    authService.logout()
      .then(() => {
        setIsAuthenticated(false);
        setUser(null);
      })
      .catch((error) => {
        console.error('Logout failed:', error);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  const toggleAuth = () => {
    if (isAuthenticated) {
      logout();
    } else {
      login();
    }
  };

  const updateUser = (userData: Partial<User>) => {
    setUser((currentUser) => {
      const base = currentUser || defaultUser;
      return {
        ...base,
        ...userData,
      };
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        login,
        logout,
        toggleAuth,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (!context) {
    return {
      user: defaultUser,
      isAuthenticated: false,
      login: () => undefined,
      logout: () => undefined,
      toggleAuth: () => undefined,
      updateUser: () => undefined,
    };
  }

  return context;
};
