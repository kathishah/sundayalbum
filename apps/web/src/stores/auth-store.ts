import { create } from 'zustand'

interface AuthState {
  token: string | null
  userHash: string | null
  setAuth: (token: string, userHash: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  userHash: null,
  setAuth: (token: string, userHash: string) => set({ token, userHash }),
  clearAuth: () => set({ token: null, userHash: null }),
}))
