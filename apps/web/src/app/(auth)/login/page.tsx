'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/auth'
import AuthForm from '@/components/auth/AuthForm'
import VersionFooter from '@/components/VersionFooter'

export default function LoginPage() {
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace('/library')
    }
  }, [router])

  return (
    <div className="min-h-screen flex flex-col bg-sa-stone-50 dark:bg-sa-stone-950">
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="mb-10 text-center">
            <h1 className="font-display text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
              Sunday Album
            </h1>
            <p className="text-sa-stone-500 dark:text-sa-stone-400">
              Digitise your physical photo albums
            </p>
          </div>
          <AuthForm />
        </div>
      </main>
      <VersionFooter />
    </div>
  )
}
