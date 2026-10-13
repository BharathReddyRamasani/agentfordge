"use client";

import { useRouter } from "next/navigation";
import { create } from "zustand";
import { api } from "@/lib/api";
import type { User } from "@/types";

const TOKEN_KEY = "agentforge_token";
const USER_KEY = "agentforge_user";

interface AuthState {
  token: string | null;
  user: User | null;
  initialized: boolean;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  user: null,
  initialized: false,
  init: async () => {
    const token = getToken();
    if (!token) {
      set({ initialized: true });
      return;
    }
    try {
      const user = await api.me(token);
      set({ token, user, initialized: true });
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      set({ token: null, user: null, initialized: true });
    }
  },
  login: async (email, password) => {
    const res = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(res.user));
    set({ token: res.access_token, user: res.user });
  },
  register: async (email, name, password) => {
    const res = await api.register(email, name, password);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(res.user));
    set({ token: res.access_token, user: res.user });
  },
  logout: async () => {
    const token = getToken();
    if (token) {
      try {
        await api.logout(token);
      } catch {
        /* already invalid */
      }
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null });
  },
}));

export function useRequireAuth() {
  const router = useRouter();
  const { initialized, token } = useAuth();
  if (initialized && !token) {
    router.replace("/login");
  }
  return { initialized, token };
}
