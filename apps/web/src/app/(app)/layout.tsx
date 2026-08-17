'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { isAuthenticated, clearToken } from '@/lib/auth'
import { useAuthStore } from '@/stores/auth-store'
import { logout } from '@/lib/api'
import VersionFooter from '@/components/VersionFooter'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const clearAuth = useAuthStore((s) => s.clearAuth)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login')
    }
  }, [router])

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // ignore logout errors
    } finally {
      clearToken()
      clearAuth()
      router.replace('/login')
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-sa-stone-50 dark:bg-sa-stone-950">
      <header className="border-b border-sa-stone-200 dark:border-sa-stone-800 bg-white dark:bg-sa-stone-900">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link
            href="/library"
            className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 hover:text-sa-amber-600 dark:hover:text-sa-amber-400 transition-colors duration-[200ms]"
          >
            Sunday Album
          </Link>
          <nav className="flex items-center gap-6">
            <Link
              href="/library"
              className="text-sm text-sa-stone-600 dark:text-sa-stone-400 hover:text-sa-stone-900 dark:hover:text-sa-stone-50 transition-colors duration-[200ms]"
            >
              Library
            </Link>
            <Link
              href="/settings"
              className="text-sm text-sa-stone-600 dark:text-sa-stone-400 hover:text-sa-stone-900 dark:hover:text-sa-stone-50 transition-colors duration-[200ms]"
            >
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-sa-stone-500 hover:text-sa-stone-700 dark:text-sa-stone-500 dark:hover:text-sa-stone-300 transition-colors duration-[200ms]"
            >
              Sign out
            </button>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        {children}
      </main>
      <VersionFooter />
    </div>
  )
}
