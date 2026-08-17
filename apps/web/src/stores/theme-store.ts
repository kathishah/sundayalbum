import { create } from 'zustand'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'sa_theme'

function readStored(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  const v = localStorage.getItem(STORAGE_KEY)
  if (v === 'light' || v === 'dark' || v === 'system') return v
  return 'system'
}

interface ThemeState {
  preference: ThemePreference
  setPreference: (p: ThemePreference) => void
}

export const useThemeStore = create<ThemeState>()((set) => ({
  preference: 'system',
  setPreference: (preference) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, preference)
    }
    set({ preference })
  },
}))

/** Called once on mount by ThemeProvider to hydrate the store from localStorage. */
export function initThemeStore() {
  const stored = readStored()
  useThemeStore.setState({ preference: stored })
  return stored
}
