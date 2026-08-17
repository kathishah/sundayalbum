'use client'

import { useEffect, useState } from 'react'

interface VersionData {
  web: { deployed_at: string | null; is_latest: boolean | null }
  backend: { deployed_at: string | null; is_latest: boolean | null }
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

export default function VersionFooter() {
  const [info, setInfo] = useState<VersionData | null>(null)

  useEffect(() => {
    fetch('/api/version')
      .then((r) => r.json())
      .then((d) => {
        if (!d.error) setInfo(d)
      })
      .catch(() => {})
  }, [])

  if (!info) return null

  return (
    <footer className="border-t border-sa-stone-200 dark:border-sa-stone-800 py-3 px-4">
      <p className="text-center text-xs text-sa-stone-400 dark:text-sa-stone-600">
        Web{info.web.is_latest === false ? ' ⚠' : ''} {formatPT(info.web.deployed_at)}
        <span className="mx-2">·</span>
        Backend{info.backend.is_latest === false ? ' ⚠' : ''} {formatPT(info.backend.deployed_at)}
      </p>
    </footer>
  )
}
