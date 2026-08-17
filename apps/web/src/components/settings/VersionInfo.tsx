'use client'

import { useEffect, useState } from 'react'

interface DeployInfo {
  deployed_at: string | null
  sha: string | null
  is_latest: boolean | null
}

interface VersionData {
  web: DeployInfo
  backend: DeployInfo
}

function formatPT(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(iso))
}

function StatusBadge({ isLatest }: { isLatest: boolean | null }) {
  if (isLatest === null) return null
  return isLatest ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-sa-success">
      <span className="w-1.5 h-1.5 rounded-full bg-sa-success" />
      Up to date
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-sa-error">
      <span className="w-1.5 h-1.5 rounded-full bg-sa-error" />
      Outdated
    </span>
  )
}

function Row({ label, info }: { label: string; info: DeployInfo }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-sa-stone-100 dark:border-sa-stone-800 last:border-0">
      <div>
        <p className="text-sm font-medium text-sa-stone-800 dark:text-sa-stone-100">{label}</p>
        <p className="text-xs text-sa-stone-500 dark:text-sa-stone-400 mt-0.5">
          {formatPT(info.deployed_at)}
          {info.sha && (
            <span className="ml-2 font-mono text-sa-stone-400 dark:text-sa-stone-600">
              {info.sha}
            </span>
          )}
        </p>
      </div>
      <StatusBadge isLatest={info.is_latest} />
    </div>
  )
}

export default function VersionInfo() {
  const [info, setInfo] = useState<VersionData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/version')
      .then((r) => r.json())
      .then((d) => {
        if (!d.error) setInfo(d)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="bg-white dark:bg-sa-stone-900 rounded-2xl border border-sa-stone-200 dark:border-sa-stone-800 shadow-sm p-6 max-w-xl">
      <h2 className="font-display text-lg font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-1">
        Deployed versions
      </h2>
      <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 mb-4">
        Last deploy time for each component, in Pacific time.
      </p>

      {loading && (
        <div className="flex items-center gap-2 py-4 text-sa-stone-400">
          <div className="w-4 h-4 rounded-full border-2 border-sa-stone-300 border-t-sa-amber-500 animate-spin" />
          <span className="text-sm">Checking…</span>
        </div>
      )}

      {!loading && !info && (
        <p className="text-sm text-sa-stone-400 py-4">Version info unavailable.</p>
      )}

      {info && (
        <div>
          <Row label="Web frontend" info={info.web} />
          <Row label="Backend (API + Pipeline)" info={info.backend} />
        </div>
      )}
    </div>
  )
}
