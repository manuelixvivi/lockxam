import React, { createContext, useContext, useEffect, useState } from "react";
import { apiClient } from "../api/client";

export const UserRole = {
  SUPER_ADMIN: "SUPERADMIN",
  SCHOOL_ADMIN: "SCHOOL_ADMIN",
  TEACHER: "TEACHER",
  STUDENT: "STUDENT",
} as const;

export type UserRole =
  | (typeof UserRole)[keyof typeof UserRole]
  | "SUPER_ADMIN"
  | "SUPERADMIN"
  | "ADMIN"
  | "SCHOOL_ADMIN";

export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  username?: string;
  name?: string;
  nis?: string;
  nisn?: string;
  birth_date?: string;
  gender?: string;
  class_name?: string;
  registered_year?: number;
  nip?: string;
  teacher_code?: string;
  role: UserRole;
  school_id?: number | null;
  school_name?: string | null;
  school_level_code?: string | null;
  must_change_password?: boolean;
  subjects_taught?: string[] | null;
  classes_taught?: string[] | null;
}

interface AuthContextType {
  user: UserProfile | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, refreshToken: string | null, user: UserProfile) => void;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Normalize role string (SUPER_ADMIN <-> SUPERADMIN, ADMIN <-> SCHOOL_ADMIN)
  const rawRole = user?.role || null;
  const role: UserRole | null =
    rawRole === "SUPER_ADMIN" || rawRole === "SUPERADMIN"
      ? UserRole.SUPER_ADMIN
      : rawRole === "ADMIN" || rawRole === "SCHOOL_ADMIN"
      ? UserRole.SCHOOL_ADMIN
      : rawRole;

  const isAuthenticated = !!user;

  const login = (token: string, _refreshToken: string | null, userProfile: any) => {
    apiClient.setAccessToken(token);
    const normalizedUser: UserProfile = {
      ...userProfile,
      id: userProfile.user_id || userProfile.id,
      email: userProfile.email || userProfile.username || "user@school.id",
      full_name: userProfile.name || userProfile.full_name || userProfile.username || "Pengguna Equigrade",
    };
    setUser(normalizedUser);
  };

  const logout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch {
      // Ignore logout request errors
    } finally {
      apiClient.clearTokens();
      setUser(null);
      window.history.replaceState({}, "", "/login");
    }
  };

  const refreshProfile = async () => {
    const currentToken = apiClient.getAccessToken();
    if (currentToken && user) {
      setIsLoading(false);
      return;
    }

    try {
      const refreshRes = await apiClient.post<{ access_token: string; user_profile?: any }>(
        "/api/v1/auth/refresh"
      );
      if (refreshRes && refreshRes.access_token) {
        apiClient.setAccessToken(refreshRes.access_token);
        if (refreshRes.user_profile) {
          const me = refreshRes.user_profile;
          const normalizedUser: UserProfile = {
            ...me,
            id: me.user_id || me.id,
            email: me.email || me.username || "user@school.id",
            full_name: me.name || me.full_name || me.username || "Pengguna Equigrade",
          };
          setUser(normalizedUser);
        }
      } else {
        apiClient.clearTokens();
        setUser(null);
      }
    } catch {
      apiClient.clearTokens();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshProfile();

    const handleAuthExpired = () => {
      apiClient.clearTokens();
      setUser(null);
      window.history.replaceState({}, "", "/login");
    };

    window.addEventListener("equigrade:auth_expired", handleAuthExpired);
    return () => {
      window.removeEventListener("equigrade:auth_expired", handleAuthExpired);
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isLoading,
        login,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
