'use client'

import { useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { sendCode, verifyCode } from '@/lib/api'
import { setToken, setUserHash } from '@/lib/auth'
import { useAuthStore } from '@/stores/auth-store'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

type Step = 'email' | 'code'

export default function AuthForm() {
  const router = useRouter()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sentMessage, setSentMessage] = useState<string | null>(null)

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setError(null)
    setLoading(true)

    try {
      const res = await sendCode(email.trim())
      setSentMessage(res.message ?? 'Code sent — check your email.')
      setStep('code')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send code.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCodeSubmit(e: FormEvent) {
    e.preventDefault()
    if (!code.trim()) return
    setError(null)
    setLoading(true)

    try {
      const res = await verifyCode(email.trim(), code.trim())
      setToken(res.session_token)
      setUserHash(res.user_hash)
      setAuth(res.session_token, res.user_hash)
      router.replace('/library')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid code. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white dark:bg-sa-stone-900 rounded-2xl border border-sa-stone-200 dark:border-sa-stone-800 shadow-sm p-8">
      {step === 'email' ? (
        <form onSubmit={handleEmailSubmit} className="flex flex-col gap-5">
          <div>
            <h2 className="font-display text-xl font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-1">
              Sign in
            </h2>
            <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400">
              Enter your email and we&apos;ll send you a code.
            </p>
          </div>

          <Input
            label="Email address"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            required
            error={error ?? undefined}
          />

          <Button type="submit" loading={loading} className="w-full">
            Send code
          </Button>
        </form>
      ) : (
        <form onSubmit={handleCodeSubmit} className="flex flex-col gap-5">
          <div>
            <h2 className="font-display text-xl font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-1">
              Enter your code
            </h2>
            {sentMessage && (
              <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400">
                {sentMessage}
              </p>
            )}
          </div>

          <Input
            label="Verification code"
            type="text"
            inputMode="numeric"
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="one-time-code"
            autoFocus
            required
            error={error ?? undefined}
          />

          <Button type="submit" loading={loading} className="w-full">
            Verify
          </Button>

          <button
            type="button"
            onClick={() => {
              setStep('email')
              setCode('')
              setError(null)
            }}
            className="text-sm text-sa-stone-500 hover:text-sa-stone-700 dark:text-sa-stone-400 dark:hover:text-sa-stone-200 transition-colors duration-[200ms] text-center"
          >
            Back — use a different email
          </button>
        </form>
      )}
    </div>
  )
}
