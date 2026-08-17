'use client'

import { useEffect } from 'react'
import { useThemeStore, initThemeStore } from '@/stores/theme-store'

function applyTheme(pref: string) {
  const dark =
    pref === 'dark' ||
    (pref !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { preference, setPreference } = useThemeStore()

  // Hydrate store from localStorage on first mount
  useEffect(() => {
    const stored = initThemeStore()
    applyTheme(stored)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Re-apply whenever preference changes
  useEffect(() => {
    applyTheme(preference)

    if (preference === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = () => applyTheme('system')
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    }
  }, [preference])

  // Suppress unused-var warning — setPreference is consumed by child components via the store
  void setPreference

  return <>{children}</>
}
