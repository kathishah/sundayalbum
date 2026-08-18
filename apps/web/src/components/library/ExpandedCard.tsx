'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import type { Job } from '@/lib/types'
import { BACKEND_TO_VISUAL, TOTAL_VISUAL_STEPS, VISUAL_STEP_LABELS } from '@/lib/constants'
import { useJobsStore } from '@/stores/jobs-store'
import { getJob } from '@/lib/api'
import PipelineProgressWheel from './ProgressWheel'

interface ExpandedCardProps {
  job: Job
  onClose: () => void
}

// ── JobStatusLine ─────────────────────────────────────────────────────────────

function JobStatusLine({ job }: { job: Job }) {
  const total = TOTAL_VISUAL_STEPS

  if (job.status === 'uploading') {
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-sa-stone-400 dark:text-sa-stone-500">
        <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor">
          <path d="M6 0a6 6 0 1 0 0 12A6 6 0 0 0 6 0zm.5 3v3.25l2.25 1.3-.5.87L5.5 6.75V3h1z" />
        </svg>
        Preparing…
      </div>
    )
  }

  if (job.status === 'processing') {
    const visualIdx = BACKEND_TO_VISUAL[job.current_step] ?? 0
    const stepNum = Math.min(visualIdx + 1, total)
    const stepName = VISUAL_STEP_LABELS[visualIdx] ?? job.current_step
    const progressFraction = stepNum / total

    return (
      <div className="flex items-center gap-1.5">
        {/* Slim progress bar — 52px wide, 3px tall, capsule */}
        <div className="relative flex-shrink-0 rounded-full bg-sa-stone-200 dark:bg-sa-stone-700 overflow-hidden" style={{ width: 52, height: 3 }}>
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-sa-amber-500 transition-all duration-[200ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
            style={{ width: `${progressFraction * 100}%` }}
          />
        </div>
        <span className="text-[11px] text-sa-stone-500 dark:text-sa-stone-400">
          Step {stepNum} of {total}: {stepName}
        </span>
      </div>
    )
  }

  if (job.status === 'complete') {
    const photoCount = job.photo_count
    const label = `${photoCount} photo${photoCount !== 1 ? 's' : ''} extracted`
    const timeLabel = job.processing_time > 0 ? ` · ${job.processing_time.toFixed(1)}s` : ''
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-sa-success">
        <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor">
          <path d="M6 0a6 6 0 1 0 0 12A6 6 0 0 0 6 0zm2.78 4.28L5.5 7.56 3.22 5.28l.78-.78L5.5 6l2.5-2.5.78.78z" />
        </svg>
        {label}{timeLabel}
      </div>
    )
  }

  // failed
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-sa-error">
      <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor">
        <path d="M6 0a6 6 0 1 0 0 12A6 6 0 0 0 6 0zm-.5 3h1v4h-1V3zm0 5h1v1.25h-1V8z" />
      </svg>
      {job.error_message || 'Processing failed'}
    </div>
  )
}

// ── ThumbBox (120×160) ────────────────────────────────────────────────────────

function ThumbBox({ src }: { src: string | undefined }) {
  return (
    <div className="flex-shrink-0 w-[120px] h-[160px] rounded-lg overflow-hidden bg-sa-surface">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="Before" className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          {/* Photo icon placeholder */}
          <svg
            viewBox="0 0 24 24"
            width="40"
            height="40"
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

// ── AfterSection (expanded) ───────────────────────────────────────────────────

function AfterSection({ job }: { job: Job }) {
  const height = 160
  const thumbW = 120  // matches ThumbBox width for visual symmetry
  const completedCount =
    job.status === 'complete'
      ? TOTAL_VISUAL_STEPS
      : BACKEND_TO_VISUAL[job.current_step] ?? 0

  if (job.status === 'complete' && job.output_urls && job.output_urls.length > 0) {
    const photos = job.output_urls
    // Fixed-size thumbnails (120×160px) showing the full image (object-contain).
    // sa-flex-safe-center centers when content fits; falls back to flex-start
    // (scrollable) when it overflows.
    return (
      <div
        className="sa-flex-safe-center [&::-webkit-scrollbar]:hidden"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
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

  return (
    <div className="flex items-center justify-center" style={{ height, minWidth: height }}>
      <PipelineProgressWheel completedCount={completedCount} size={height} />
    </div>
  )
}

// ── Per-photo step tree ───────────────────────────────────────────────────────

/**
 * Derives per-photo step completion from thumbnail_urls keys.
 * Per-photo thumbnails follow the pattern:
 *   05b_photo_{idx}_oriented  → visual step 3 (Orient)
 *   07_photo_{idx}_deglared   → visual step 4 (Glare)
 *   14_photo_{idx}_enhanced   → visual step 5 (Color)
 * Pre-photo steps (0–2) complete uniformly for all photos.
 */
function PerPhotoStepTree({ job }: { job: Job }) {
  const count = job.photo_count
  if (count <= 1) return null
  // Only show per-photo progress while processing — once complete the output photos
  // are already shown in AfterSection, making the dot strip redundant.
  if (job.status !== 'processing') return null

  // At this point status === 'processing' — isComplete is always false, dropped.
  const thumbUrls = job.thumbnail_urls ?? {}
  const hasThumbs = Object.keys(thumbUrls).length > 0
  const visualIdx = BACKEND_TO_VISUAL[job.current_step] ?? 0

  // Pre-photo steps 0–2 (Load / Page / Split) finish uniformly before per-photo work begins
  const preDone = visualIdx >= 2

  const photos: { idx: number; completed: boolean[] }[] = []
  for (let i = 1; i <= count; i++) {
    const photoNum = String(i).padStart(2, '0')

    let orientDone: boolean, glareDone: boolean, colorDone: boolean
    if (hasThumbs) {
      orientDone = !!thumbUrls[`05b_photo_${photoNum}_oriented`]
      glareDone  = !!thumbUrls[`07_photo_${photoNum}_deglared`]
      colorDone  = !!thumbUrls[`14_photo_${photoNum}_enhanced`]
    } else {
      // Uniform fallback when thumbnail_urls not yet available
      orientDone = visualIdx >= 3
      glareDone  = visualIdx >= 4
      colorDone  = visualIdx >= 5
    }

    photos.push({
      idx: i,
      completed: [preDone, preDone, preDone, orientDone, glareDone, colorDone],
    })
  }

  return (
    <div className="px-5 pb-3">
      <div className="flex flex-col gap-1.5">
        {photos.map(({ idx, completed }) => (
          <div key={idx} className="flex items-center gap-2">
            <span className="text-[11px] text-sa-stone-500 dark:text-sa-stone-400 w-14 flex-shrink-0">
              Photo {idx}
            </span>
            <div className="flex items-center gap-1">
              {completed.map((done, stepIdx) => (
                <div
                  key={stepIdx}
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    done
                      ? 'bg-sa-amber-500'
                      : 'bg-sa-stone-300 dark:bg-sa-stone-600'
                  }`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── ExpandedCard ──────────────────────────────────────────────────────────────

export default function ExpandedCard({ job, onClose }: ExpandedCardProps) {
  const router = useRouter()
  const { upsertJob } = useJobsStore()

  // Fetch the full job record when the card opens if we're missing presigned URLs
  // (list endpoint omits them) or per-photo thumbnail data needed for the step tree.
  useEffect(() => {
    const missingComplete =
      job.status === 'complete' &&
      (!job.debug_urls || !job.output_urls || job.output_urls.length === 0)
    const missingPerPhotoThumbs =
      job.photo_count > 1 && !job.thumbnail_urls

    if (missingComplete || missingPerPhotoThumbs) {
      getJob(job.job_id)
        .then((full) => upsertJob({ ...full, preview_url: job.preview_url }))
        .catch(() => {})
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id])

  // Before-thumbnail: 400px backend thumbnail → client preview_url → nothing
  const beforeSrc = job.thumbnail_url ?? job.preview_url

  function handleViewDetails() {
    onClose()
    router.push(`/jobs/${job.job_id}`)
  }

  return (
    <>
      {/* Backdrop — click to dismiss */}
      <motion.div
        key="backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
      />

      {/* Card — centered, max-width 640px, 48px padding from overlay edges */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-12 pointer-events-none">
        <motion.div
          key="card"
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.94 }}
          transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          className="w-full max-w-[640px] rounded-2xl overflow-hidden pointer-events-auto"
          style={{
            background: 'rgb(var(--sa-card))',
            border: '1px solid rgb(var(--sa-border-card))',
            boxShadow: 'var(--sa-shadow-expanded)',
          }}
        >
          {/* Thumbnail row — padding 20px */}
          <div className="flex items-center justify-center gap-4 p-5">
            <div className="flex items-center gap-4">
              <ThumbBox src={beforeSrc} />

              {/* Arrow — saAmber500 in expanded card */}
              <span className="text-base font-semibold text-sa-amber-500 flex-shrink-0 leading-none">
                →
              </span>

              <AfterSection job={job} />
            </div>
          </div>

          {/* Per-photo step tree — shown for multi-photo jobs */}
          <PerPhotoStepTree job={job} />

          {/* Divider */}
          <div className="h-px bg-sa-border-card" />

          {/* Footer — padding 20px */}
          <div className="flex items-center justify-between gap-3 p-5">
            <div className="flex flex-col gap-[5px] min-w-0">
              <p
                className="text-[14px] font-semibold text-sa-stone-700 dark:text-sa-stone-100 truncate"
                title={job.input_filename}
              >
                {job.input_filename}
              </p>
              <JobStatusLine job={job} />
            </div>

            <button
              onClick={handleViewDetails}
              className="flex-shrink-0 px-3 py-1.5 rounded-lg text-[13px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 transition-colors duration-[200ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
            >
              View Step Details
            </button>
          </div>
        </motion.div>
      </div>
    </>
  )
}
