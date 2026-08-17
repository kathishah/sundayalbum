'use client'

import { useEffect, useRef } from 'react'
import { WS_URL, POLLING_INTERVAL_MS } from '@/lib/constants'
import { getJob } from '@/lib/api'
import type { StepUpdate, Job, JobStatus } from '@/lib/types'

export function createWebSocketUrl(jobId: string): string {
  return `${WS_URL}?jobId=${jobId}`
}

function jobToStepUpdate(job: Job): StepUpdate {
  return {
    type: 'step_update',
    jobId: job.job_id,
    status: job.status as JobStatus,
    step: job.current_step ?? '',
    detail: job.step_detail ?? '',
    progress: 0,
    photoCount: job.photo_count ?? 0,
  }
}

interface UseJobProgressOptions {
  jobId: string
  onUpdate: (update: StepUpdate) => void
  enabled?: boolean
}

export function useJobProgress({
  jobId,
  onUpdate,
  enabled = true,
}: UseJobProgressOptions): void {
  const wsRef = useRef<WebSocket | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onUpdateRef = useRef(onUpdate)
  onUpdateRef.current = onUpdate

  useEffect(() => {
    if (!enabled || !jobId) return

    let useFallback = false

    function startPolling() {
      if (pollingRef.current) return
      pollingRef.current = setInterval(async () => {
        try {
          const job = await getJob(jobId)
          onUpdateRef.current(jobToStepUpdate(job))
          if (job.status === 'complete' || job.status === 'failed') {
            stopPolling()
          }
        } catch {
          // ignore polling errors
        }
      }, POLLING_INTERVAL_MS)
    }

    function stopPolling() {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }

    function stopWs() {
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.onerror = null
        wsRef.current.onmessage = null
        wsRef.current.close()
        wsRef.current = null
      }
    }

    try {
      const ws = new WebSocket(createWebSocketUrl(jobId))
      wsRef.current = ws

      const connectionTimer = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          useFallback = true
          stopWs()
          startPolling()
        }
      }, 3000)

      ws.onopen = () => {
        clearTimeout(connectionTimer)
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as StepUpdate
          if (data.type === 'step_update' && data.jobId === jobId) {
            onUpdateRef.current(data)
            if (data.status === 'complete' || data.status === 'failed') {
              stopWs()
            }
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        if (!useFallback) {
          useFallback = true
          stopWs()
          startPolling()
        }
      }

      ws.onclose = () => {
        if (!useFallback) {
          useFallback = true
          startPolling()
        }
      }
    } catch {
      useFallback = true
      startPolling()
    }

    return () => {
      stopWs()
      stopPolling()
    }
  }, [jobId, enabled])
}
