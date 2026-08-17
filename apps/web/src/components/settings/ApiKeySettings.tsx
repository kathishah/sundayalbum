'use client'

import { useState, useEffect, type FormEvent } from 'react'
import { getApiKeys, updateApiKeys, deleteApiKeys } from '@/lib/api'
import type { ApiKeyStatus } from '@/lib/types'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="w-4 h-4 text-sa-success flex-shrink-0"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  )
}

export default function ApiKeySettings() {
  const [status, setStatus] = useState<ApiKeyStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')

  useEffect(() => {
    getApiKeys()
      .then(setStatus)
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load key status.')
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    if (!anthropicKey.trim() && !openaiKey.trim()) {
      setError('Enter at least one API key.')
      return
    }
    setError(null)
    setSuccessMessage(null)
    setSaving(true)

    try {
      const payload: { anthropic_api_key?: string; openai_api_key?: string } = {}
      if (anthropicKey.trim()) payload.anthropic_api_key = anthropicKey.trim()
      if (openaiKey.trim()) payload.openai_api_key = openaiKey.trim()
      await updateApiKeys(payload)

      // Refresh status
      const updated = await getApiKeys()
      setStatus(updated)
      setAnthropicKey('')
      setOpenaiKey('')
      setSuccessMessage('API keys saved successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save keys.')
    } finally {
      setSaving(false)
    }
  }

  async function handleRemove() {
    setError(null)
    setSuccessMessage(null)
    setRemoving(true)

    try {
      await deleteApiKeys()
      const updated = await getApiKeys()
      setStatus(updated)
      setSuccessMessage('API keys removed.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove keys.')
    } finally {
      setRemoving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sa-stone-400">
        <div className="w-5 h-5 rounded-full border-2 border-sa-stone-300 border-t-sa-amber-500 animate-spin" />
        <span className="text-sm">Loading…</span>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-sa-stone-900 rounded-2xl border border-sa-stone-200 dark:border-sa-stone-800 shadow-sm p-6 max-w-xl">
      <h2 className="font-display text-lg font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-1">
        API Keys
      </h2>
      <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 mb-6">
        Your keys are stored securely and used only during processing. We never
        display saved key values.
      </p>

      {/* Current status */}
      <div className="flex flex-col gap-2 mb-6 p-4 rounded-xl bg-sa-stone-50 dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700">
        <p className="text-xs font-semibold text-sa-stone-500 dark:text-sa-stone-400 uppercase tracking-wide mb-1">
          Active keys
        </p>
        <div className="flex items-center gap-2">
          {status?.has_anthropic_key ? (
            <CheckIcon />
          ) : (
            <span className="w-4 h-4 rounded-full border-2 border-sa-stone-300 dark:border-sa-stone-600 flex-shrink-0" />
          )}
          <span
            className={
              status?.has_anthropic_key
                ? 'text-sm text-sa-stone-800 dark:text-sa-stone-100'
                : 'text-sm text-sa-stone-400 dark:text-sa-stone-500'
            }
          >
            Anthropic (Claude)
          </span>
        </div>
        <div className="flex items-center gap-2">
          {status?.has_openai_key ? (
            <CheckIcon />
          ) : (
            <span className="w-4 h-4 rounded-full border-2 border-sa-stone-300 dark:border-sa-stone-600 flex-shrink-0" />
          )}
          <span
            className={
              status?.has_openai_key
                ? 'text-sm text-sa-stone-800 dark:text-sa-stone-100'
                : 'text-sm text-sa-stone-400 dark:text-sa-stone-500'
            }
          >
            OpenAI (GPT image)
          </span>
        </div>
      </div>

      {/* Feedback messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-sa-error text-sa-error text-sm">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 dark:bg-green-950 border border-sa-success text-sa-success text-sm">
          {successMessage}
        </div>
      )}

      {/* Update form */}
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <Input
          label="Anthropic API key"
          type="password"
          placeholder={
            status?.has_anthropic_key ? '••••••••••••  (set — enter to replace)' : 'sk-ant-…'
          }
          value={anthropicKey}
          onChange={(e) => setAnthropicKey(e.target.value)}
          autoComplete="off"
        />
        <Input
          label="OpenAI API key"
          type="password"
          placeholder={
            status?.has_openai_key ? '••••••••••••  (set — enter to replace)' : 'sk-…'
          }
          value={openaiKey}
          onChange={(e) => setOpenaiKey(e.target.value)}
          autoComplete="off"
        />

        <div className="flex items-center gap-3 mt-2">
          <Button type="submit" loading={saving} className="flex-1">
            Save keys
          </Button>
          {(status?.has_anthropic_key || status?.has_openai_key) && (
            <Button
              type="button"
              variant="ghost"
              loading={removing}
              onClick={handleRemove}
              className="text-sa-error hover:text-sa-error"
            >
              Remove all
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}
