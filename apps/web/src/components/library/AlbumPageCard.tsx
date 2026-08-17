'use client'

import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Job, StepUpdate } from '@/lib/types'
import { BACKEND_TO_VISUAL, TOTAL_VISUAL_STEPS } from '@/lib/constants'
import { useJobProgress } from '@/lib/websocket'
import { useJobsStore } from '@/stores/jobs-store'
import { getJob, deleteJob, startJob } from '@/lib/api'
import PipelineProgressWheel from './ProgressWheel'

interface AlbumPageCardProps {
  job: Job
  /** True when a different card is currently expanded — dims and scales this card */
  isOtherExpanded: boolean
  onExpand: () => void
}

// ── ThumbBox ────────────────────────────────────────────────────────────────

interface ThumbBoxProps {
  src: string | undefined
  width: number
  height: number
}

function ThumbBox({ src, width, height }: ThumbBoxProps) {
  return (
    <div
      className="flex-shrink-0 rounded-lg overflow-hidden bg-sa-surface"
      style={{ width, height }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt="Before"
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          {/* Photo icon placeholder — matches macOS empty state */}
          <svg
            viewBox="0 0 24 24"
            width={Math.round(width * 0.45)}
            height={Math.round(height * 0.45)}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="text-sa-stone-300 dark:text-sa-stone-600"
          >
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
        </div>
      )}
    </div>
  )
}

// ── AfterSection ─────────────────────────────────────────────────────────────

interface AfterSectionProps {
  job: Job
  height: number
}

function AfterSection({ job, height }: AfterSectionProps) {
  const completedCount =
    job.status === 'complete'
      ? TOTAL_VISUAL_STEPS
      : job.status === 'processing'
        ? (BACKEND_TO_VISUAL[job.current_step] ?? 0)
        : 0

  if (job.status === 'complete' && job.output_urls && job.output_urls.length > 0) {
    const photos = job.output_urls
    // Fixed-size thumbnails — each photo gets its own 72×88px box showing the
    // full image (object-contain). sa-flex-safe-center centers items when they
    // fit; falls back to flex-start (scrollable) when they overflow so the
    // right side remains reachable via horizontal scroll.
    const thumbW = 72
    return (
      <div
        className="sa-flex-safe-center [&::-webkit-scrollbar]:hidden"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          height,
          overflowX: 'auto',
          scrollbarWidth: 'none',
        }}
      >
        {photos.map((url, i) => (
          <div
            key={i}
            className="flex-shrink-0 rounded-[6px] overflow-hidden bg-sa-surface"
            style={{ width: thumbW, height }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={`Photo ${i + 1}`}
              className="w-full h-full object-contain"
            />
          </div>
        ))}
      </div>
    )
  }

  // Processing / uploading / failed — pie wheel
  return (
    <div
      className="flex items-center justify-center"
      style={{ height, minWidth: height }}
    >
      <PipelineProgressWheel
        completedCount={completedCount}
        size={height}
        isRunning={job.status === 'processing'}
      />
    </div>
  )
}

// ── AlbumPageCard ─────────────────────────────────────────────────────────────

export default function AlbumPageCard({ job, isOtherExpanded, onExpand }: AlbumPageCardProps) {
  const { upsertJob, removeJob } = useJobsStore()
  const [isHovered, setIsHovered] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)

  const isActive =
    job.status === 'uploading' || job.status === 'processing'

  // For jobs loaded from the list endpoint, output_urls / thumbnail_url may be absent.
  // Fetch the full job record once on mount when either is missing so thumbnails appear.
  useEffect(() => {
    const missingOutputUrls = job.status === 'complete' &&
      (!job.output_urls || job.output_urls.length === 0)
    const missingThumbnail = !job.thumbnail_url && !job.preview_url
    if (missingOutputUrls || missingThumbnail) {
      getJob(job.job_id)
        .then((full) => upsertJob({ ...full, preview_url: job.preview_url }))
        .catch(() => {})
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id])

  const handleUpdate = useCallback(
    (update: StepUpdate) => {
      if (update.status === 'complete' || update.status === 'failed') {
        getJob(update.jobId)
          .then((fullJob) => upsertJob(fullJob))
          .catch(() =>
            upsertJob({
              ...job,
              status: update.status,
              current_step: update.step,
              step_detail: update.detail,
            }),
          )
      } else {
        upsertJob({
          ...job,
          status: update.status,
          current_step: update.step,
          step_detail: update.detail,
          ...(update.photoCount > 0 && { photo_count: update.photoCount }),
        })
      }
    },
    [job, upsertJob],
  )

  useJobProgress({ jobId: job.job_id, onUpdate: handleUpdate, enabled: isActive })

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    setIsDeleting(true)
    try {
      await deleteJob(job.job_id)
    } finally {
      removeJob(job.job_id)
    }
  }

  async function handleRetry(e: React.MouseEvent) {
    e.stopPropagation()
    setIsRetrying(true)
    try {
      await startJob(job.job_id)
      const full = await getJob(job.job_id)
      upsertJob(full)
    } catch {
      setIsRetrying(false)
    }
  }

  // Before-thumbnail: 400px backend thumbnail → client preview_url from upload → nothing
  const beforeSrc = job.thumbnail_url ?? job.preview_url

  const thumbH = 88
  const deleteColor =
    job.status === 'processing' || job.status === 'uploading'
      ? 'text-sa-error'
      : 'text-sa-stone-400 dark:text-sa-stone-500'

  return (
    <motion.div
      data-testid="album-card"
      data-job-id={job.job_id}
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{
        opacity: isOtherExpanded ? 0.3 : 1,
        scale: isOtherExpanded ? 0.95 : 1,
        y: 0,
      }}
      transition={
        isOtherExpanded !== undefined
          ? { type: 'spring', stiffness: 280, damping: 22 }
          : { duration: 0.35, ease: [0.16, 1, 0.3, 1] }
      }
      className="relative rounded-xl overflow-hidden cursor-pointer select-none"
      style={{ background: 'rgb(var(--sa-card))', boxShadow: 'var(--sa-shadow-card)' }}
      onClick={onExpand}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* ── Thumbnail row (112px = 88px thumb + 24px vertical padding) ── */}
      <div className="flex items-center justify-center h-[112px] px-3">
        <div className="flex items-center gap-[10px] w-full">
          {/* Before thumbnail */}
          <ThumbBox src={beforeSrc} width={60} height={thumbH} />

          {/* Arrow — saAmber400 in compact card */}
          <span className="text-[11px] font-semibold text-sa-amber-400 flex-shrink-0 leading-none">
            →
          </span>

          {/* After section — flex:1 fills remaining space.
              No overflow-hidden here: the card root already clips for rounded
              corners, and a parent overflow:hidden would collapse the child
              overflow-x-auto scroll container used for centering thumbnails. */}
          <div className="flex-1 min-w-0">
            <AfterSection job={job} height={thumbH} />
          </div>
        </div>
      </div>

      {/* ── Filename ── */}
      <p
        className="text-center text-[12px] font-semibold text-sa-stone-700 dark:text-sa-stone-200 truncate px-3 pt-1 pb-2.5"
        title={job.input_filename}
        style={{
          // Middle truncation via direction trick isn't supported in CSS; use end truncation
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {job.input_filename}
      </p>

      {/* ── Retry row (failed jobs only) ── */}
      {job.status === 'failed' && (
        <div className="px-3 pb-2.5 flex justify-center" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            className="text-[11px] font-medium text-sa-amber-600 dark:text-sa-amber-400 hover:underline disabled:opacity-50"
          >
            {isRetrying ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      )}

      {/* ── Hover delete button ── */}
      <AnimatePresence>
        {isHovered && !isDeleting && (
          <motion.button
            key="delete"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`absolute top-2 right-2 w-5 h-5 flex items-center justify-center ${deleteColor} hover:opacity-70`}
            onClick={handleDelete}
            aria-label="Delete job"
          >
            {/* × circle — 16px matching macOS xmark.circle.fill */}
            <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
              <path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0zm3.25 10.19L10.19 11.25 8 9.06l-2.19 2.19L4.75 10.19 6.94 8 4.75 5.81 5.81 4.75 8 6.94l2.19-2.19 1.06 1.06L9.06 8l2.19 2.19z" />
            </svg>
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
