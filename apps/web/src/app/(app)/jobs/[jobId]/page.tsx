'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import { getJob, reprocessJob } from '@/lib/api'
import type { Job } from '@/lib/types'
import {
  JOB_STEP_TREE, PHOTO_STEP_TREE, POLLING_INTERVAL_MS,
  BACKEND_TO_VISUAL, STEP_PROGRESS, STEP_LABELS, TOTAL_VISUAL_STEPS,
} from '@/lib/constants'
import GlareRemovalView from '@/components/step-detail/GlareRemovalView'
import PhotoSplitView from '@/components/step-detail/PhotoSplitView'
import ResultsView from '@/components/step-detail/ResultsView'

// ── Backend step → tree step key mappings (for running indicators) ─────────────

/** Maps backend step name to the JOB_STEP_TREE stepKey it belongs to */
const BACKEND_TO_JOB_TREE: Record<string, string> = {
  load: 'load', normalize: 'load',
  page_detect: 'page_detect',
  perspective: 'perspective',
  photo_detect: 'photo_split', photo_split: 'photo_split',
}

/** Maps backend step name to the PHOTO_STEP_TREE stepKey it belongs to */
const BACKEND_TO_PHOTO_TREE: Record<string, string> = {
  ai_orient: 'ai_orient',
  glare_remove: 'glare_remove', geometry: 'glare_remove',
  color_restore: 'color_restore',
}

// ── Types ──────────────────────────────────────────────────────────────────────

type StepSelection =
  | { kind: 'job'; stepKey: string }
  | { kind: 'photo'; photoIdx: number; stepKey: string }
  | { kind: 'results' }

function photoNum(idx: number): string {
  return String(idx).padStart(2, '0')
}

function getDebugUrl(job: Job, sel: StepSelection): string | undefined {
  const urls = job.debug_urls ?? {}
  if (sel.kind === 'job') {
    const cfg = JOB_STEP_TREE.find((s) => s.stepKey === sel.stepKey)
    return cfg ? urls[cfg.debugKey] : undefined
  }
  if (sel.kind === 'photo') {
    const cfg = PHOTO_STEP_TREE.find((s) => s.stepKey === sel.stepKey)
    const n = photoNum(sel.photoIdx)
    return cfg ? urls[cfg.debugKeyFn(n)] : undefined
  }
  return undefined
}

function selectionLabel(sel: StepSelection): string {
  if (sel.kind === 'results') return 'Results'
  if (sel.kind === 'job') {
    return JOB_STEP_TREE.find((s) => s.stepKey === sel.stepKey)?.label ?? sel.stepKey
  }
  return PHOTO_STEP_TREE.find((s) => s.stepKey === sel.stepKey)?.label ?? sel.stepKey
}

// ── StepTree ───────────────────────────────────────────────────────────────────

function TreeRow({
  label,
  active,
  available,
  isRunning = false,
  indented = false,
  onClick,
}: {
  label: string
  active: boolean
  available: boolean
  isRunning?: boolean
  indented?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={!available}
      className={[
        'w-full text-left py-2 text-[13px] transition-colors duration-[200ms] border-l-2',
        indented ? 'pl-8 pr-3' : 'px-4',
        active
          ? 'border-sa-amber-500 text-sa-amber-600 dark:text-sa-amber-400 font-semibold bg-sa-amber-50 dark:bg-sa-amber-950/20'
          : available
          ? 'border-transparent text-sa-stone-700 dark:text-sa-stone-300 hover:text-sa-stone-900 dark:hover:text-sa-stone-100 hover:bg-sa-stone-100 dark:hover:bg-sa-stone-800'
          : 'border-transparent text-sa-stone-300 dark:text-sa-stone-600 cursor-not-allowed',
      ].join(' ')}
    >
      <span className="flex items-center justify-between gap-2">
        <span>{label}</span>
        {isRunning && (
          <span className="relative flex h-2 w-2 flex-shrink-0 mr-0.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sa-amber-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-sa-amber-500" />
          </span>
        )}
      </span>
    </button>
  )
}

function StepTree({
  job,
  selection,
  onSelect,
  reprocessingPhotoIdx,
}: {
  job: Job
  selection: StepSelection
  onSelect: (s: StepSelection) => void
  reprocessingPhotoIdx: number | null
}) {
  const urls = job.debug_urls ?? {}
  const isProcessing = job.status === 'processing'
  const activeJobStepKey = isProcessing ? (BACKEND_TO_JOB_TREE[job.current_step] ?? null) : null
  const activePhotoStepKey = isProcessing ? (BACKEND_TO_PHOTO_TREE[job.current_step] ?? null) : null

  const isJobActive = (key: string) =>
    selection.kind === 'job' && selection.stepKey === key
  const isPhotoActive = (idx: number, key: string) =>
    selection.kind === 'photo' && selection.photoIdx === idx && selection.stepKey === key
  const isResultsActive = selection.kind === 'results'

  return (
    <nav data-testid="step-tree" className="w-[196px] flex-shrink-0 flex flex-col py-2 overflow-y-auto">
      {/* Pre-split job steps */}
      {JOB_STEP_TREE.map(({ stepKey, label, debugKey }) => (
        <TreeRow
          key={stepKey}
          label={label}
          active={isJobActive(stepKey)}
          available={!!urls[debugKey]}
          isRunning={activeJobStepKey === stepKey}
          onClick={() => onSelect({ kind: 'job', stepKey })}
        />
      ))}

      {/* Per-photo sections */}
      {Array.from({ length: Math.max(job.photo_count, 1) }, (_, i) => i + 1).map((photoIdx) => (
        <div key={photoIdx}>
          {job.photo_count > 1 && (
            <div className="px-4 pt-3 pb-1">
              <span className="text-[11px] font-semibold text-sa-stone-400 dark:text-sa-stone-500 uppercase tracking-wider">
                Photo {photoIdx}
              </span>
            </div>
          )}
          {PHOTO_STEP_TREE.map(({ stepKey, label, debugKeyFn }) => {
            const n = photoNum(photoIdx)
            return (
              <TreeRow
                key={`${photoIdx}-${stepKey}`}
                label={label}
                active={isPhotoActive(photoIdx, stepKey)}
                available={!!urls[debugKeyFn(n)]}
                isRunning={activePhotoStepKey === stepKey && (reprocessingPhotoIdx === null || reprocessingPhotoIdx === photoIdx)}
                indented={job.photo_count > 1}
                onClick={() => onSelect({ kind: 'photo', photoIdx, stepKey })}
              />
            )
          })}
        </div>
      ))}

      {/* Results — available when output_urls present */}
      {(job.output_urls?.length ?? 0) > 0 && (
        <TreeRow
          label="Results"
          active={isResultsActive}
          available={true}
          onClick={() => onSelect({ kind: 'results' })}
        />
      )}
    </nav>
  )
}

// ── Step canvas views ──────────────────────────────────────────────────────────

function DebugImageCanvas({ url, label }: { url: string | undefined; label: string }) {
  const [loaded, setLoaded] = useState(false)

  // Reset loaded state when url changes (new step selected)
  useEffect(() => { setLoaded(false) }, [url])

  if (!url) {
    return (
      <div className="flex-1 flex items-center justify-center text-sa-stone-400 dark:text-sa-stone-500 text-sm">
        No debug image for this step
      </div>
    )
  }
  return (
    <div className="flex-1 flex justify-center p-6 overflow-auto">
      {!loaded && (
        <div className="w-full max-w-2xl aspect-[4/3] rounded-xl bg-sa-stone-200 dark:bg-sa-stone-800 animate-pulse self-start" />
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt={label}
        onLoad={() => setLoaded(true)}
        className={[
          'max-w-full h-auto rounded-xl shadow-md object-contain self-start',
          loaded ? 'opacity-100' : 'opacity-0 absolute pointer-events-none',
        ].join(' ')}
      />
    </div>
  )
}

const ROTATION_OPTIONS = [0, 90, 180, 270] as const

function OrientationView({
  job,
  photoIdx,
  onStarted,
}: {
  job: Job
  photoIdx: number
  onStarted: () => void
}) {
  const n = photoNum(photoIdx)
  const url = job.debug_urls?.[`05b_photo_${n}_oriented`]

  const [selected, setSelected] = useState<number>(0)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const dirty = selected !== 0

  async function handleApply() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      await reprocessJob(job.job_id, {
        from_step: 'ai_orient',
        photo_index: photoIdx,
        config: { forced_rotation_degrees: selected },
      })
      onStarted()
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to start reprocessing')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Image canvas */}
      <div className="flex-1 flex justify-center p-6 overflow-auto min-h-0">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={`Photo ${photoIdx} — oriented`}
            className="max-h-full w-auto rounded-xl shadow-md object-contain self-start"
            style={{ transform: `rotate(${selected}deg)`, transition: 'transform 0.3s ease' }}
          />
        ) : (
          <div className="flex items-center justify-center text-sa-stone-400 dark:text-sa-stone-500 text-sm">
            No image available
          </div>
        )}
      </div>

      {/* Controls footer */}
      <div className="flex-shrink-0 border-t border-sa-amber-200 bg-sa-amber-50 px-6 py-4 flex items-center gap-3 flex-wrap">
        <span className="text-[12px] font-medium text-sa-stone-500 dark:text-sa-stone-400 flex-shrink-0">
          Rotate
        </span>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {ROTATION_OPTIONS.map((deg) => (
            <button
              key={deg}
              onClick={() => setSelected(deg)}
              className={[
                'px-3 py-1.5 rounded text-[12px] font-medium transition-colors duration-[200ms]',
                selected === deg
                  ? 'bg-sa-amber-500 text-white'
                  : 'bg-white dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-600 dark:text-sa-stone-300 hover:bg-sa-stone-100 dark:hover:bg-sa-stone-700',
              ].join(' ')}
            >
              {deg}°
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {submitError && (
          <p className="text-[11px] text-sa-error flex-shrink-0">{submitError}</p>
        )}
        {dirty && !submitting && (
          <button
            onClick={() => { setSelected(0); setSubmitError(null) }}
            className="px-3 py-1.5 rounded-lg text-[12px] text-sa-stone-500 dark:text-sa-stone-400 hover:text-sa-stone-700 dark:hover:text-sa-stone-200 transition-colors duration-[200ms] flex-shrink-0"
          >
            Discard
          </button>
        )}
        <button
          onClick={handleApply}
          disabled={!dirty || submitting}
          className="px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-[200ms] flex-shrink-0"
        >
          {submitting ? 'Starting…' : 'Apply & Reprocess'}
        </button>
      </div>
    </div>
  )
}

// Default PipelineConfig values for color sliders
const DEFAULT_SATURATION = 15  // saturation_boost 0.15 → 15%
const DEFAULT_SHARPNESS = 50   // sharpen_amount 0.50 → 50%

function ColorRestoreView({
  job,
  photoIdx,
  onStarted,
}: {
  job: Job
  photoIdx: number
  onStarted: () => void
}) {
  const n = photoNum(photoIdx)
  const url = job.debug_urls?.[`14_photo_${n}_enhanced`]

  const [saturation, setSaturation] = useState(DEFAULT_SATURATION)
  const [sharpness, setSharpness] = useState(DEFAULT_SHARPNESS)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const dirty = saturation !== DEFAULT_SATURATION || sharpness !== DEFAULT_SHARPNESS

  async function handleApply() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      await reprocessJob(job.job_id, {
        from_step: 'color_restore',
        photo_index: photoIdx,
        config: {
          color_restore_vibrance_boost: saturation / 100,
          sharpen_amount: sharpness / 100,
        },
      })
      onStarted()
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to start reprocessing')
    } finally {
      setSubmitting(false)
    }
  }

  function displayVal(v: number) {
    return v === 0 ? '0%' : v > 0 ? `+${v}%` : `${v}%`
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Image canvas */}
      <div className="flex-1 flex justify-center p-6 overflow-auto min-h-0">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={`Photo ${photoIdx} — color restored`}
            className="max-h-full w-auto rounded-xl shadow-md object-contain self-start"
          />
        ) : (
          <div className="flex items-center justify-center text-sa-stone-400 dark:text-sa-stone-500 text-sm">
            No image available
          </div>
        )}
      </div>

      {/* Controls footer */}
      <div className="flex-shrink-0 border-t border-sa-amber-200 bg-sa-amber-50 px-6 py-4">
        <div className="flex items-center gap-6 flex-wrap">
          {/* Saturation */}
          <div className="flex items-center gap-3 min-w-[180px] flex-1">
            <span className="text-[12px] text-sa-stone-600 dark:text-sa-stone-300 flex-shrink-0 w-20">Saturation</span>
            <input
              type="range"
              min={0}
              max={50}
              value={saturation}
              onChange={(e) => setSaturation(Number(e.target.value))}
              className="flex-1 h-1.5 rounded-full accent-sa-amber-500 cursor-pointer"
            />
            <span className="text-[11px] text-sa-stone-400 dark:text-sa-stone-500 w-9 text-right flex-shrink-0">{displayVal(saturation)}</span>
          </div>

          {/* Sharpness */}
          <div className="flex items-center gap-3 min-w-[180px] flex-1">
            <span className="text-[12px] text-sa-stone-600 dark:text-sa-stone-300 flex-shrink-0 w-20">Sharpness</span>
            <input
              type="range"
              min={0}
              max={100}
              value={sharpness}
              onChange={(e) => setSharpness(Number(e.target.value))}
              className="flex-1 h-1.5 rounded-full accent-sa-amber-500 cursor-pointer"
            />
            <span className="text-[11px] text-sa-stone-400 dark:text-sa-stone-500 w-9 text-right flex-shrink-0">{displayVal(sharpness)}</span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0 ml-auto">
            {submitError && (
              <span className="text-[11px] text-sa-error">{submitError}</span>
            )}
            {dirty && !submitting && (
              <button
                onClick={() => { setSaturation(DEFAULT_SATURATION); setSharpness(DEFAULT_SHARPNESS); setSubmitError(null) }}
                className="px-3 py-1.5 rounded-lg text-[12px] text-sa-stone-500 dark:text-sa-stone-400 hover:text-sa-stone-700 dark:hover:text-sa-stone-200 transition-colors duration-[200ms]"
              >
                Discard
              </button>
            )}
            <button
              onClick={handleApply}
              disabled={!dirty || submitting}
              className="px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-[200ms]"
            >
              {submitting ? 'Starting…' : 'Apply & Reprocess'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Step thumbnail strip (single-photo jobs, shown below breadcrumb) ──────────

/** Maps thumbnail_urls label → StepSelection (single-photo only) */
const THUMB_KEY_TO_SELECTION: Record<string, StepSelection> = {
  '01_loaded':             { kind: 'job',   stepKey: 'load'         },
  '02_page_detected':      { kind: 'job',   stepKey: 'page_detect'  },
  '03_page_warped':        { kind: 'job',   stepKey: 'perspective'  },
  '04_photo_boundaries':   { kind: 'job',   stepKey: 'photo_split'  },
  '05b_photo_01_oriented': { kind: 'photo', photoIdx: 1, stepKey: 'ai_orient'    },
  '07_photo_01_deglared':  { kind: 'photo', photoIdx: 1, stepKey: 'glare_remove' },
  '14_photo_01_enhanced':  { kind: 'photo', photoIdx: 1, stepKey: 'color_restore'},
}

const THUMB_STRIP_KEYS = [
  '01_loaded', '02_page_detected', '03_page_warped', '04_photo_boundaries',
  '05b_photo_01_oriented', '07_photo_01_deglared', '14_photo_01_enhanced',
] as const

const THUMB_STRIP_LABELS: Record<string, string> = {
  '01_loaded':             'Load',
  '02_page_detected':      'Page',
  '03_page_warped':        'Warp',
  '04_photo_boundaries':   'Split',
  '05b_photo_01_oriented': 'Orient',
  '07_photo_01_deglared':  'Glare',
  '14_photo_01_enhanced':  'Color',
}

function selectionMatchesThumbKey(sel: StepSelection, key: string): boolean {
  const target = THUMB_KEY_TO_SELECTION[key]
  if (!target) return false
  if (target.kind !== sel.kind) return false
  if (target.kind === 'job' && sel.kind === 'job') return target.stepKey === sel.stepKey
  if (target.kind === 'photo' && sel.kind === 'photo')
    return target.stepKey === sel.stepKey && target.photoIdx === sel.photoIdx
  return false
}

function StepThumbnailStrip({
  thumbnailUrls,
  selection,
  onSelect,
}: {
  thumbnailUrls: Record<string, string>
  selection: StepSelection
  onSelect: (s: StepSelection) => void
}) {
  return (
    <div data-testid="thumb-strip" className="flex-shrink-0 border-b border-sa-stone-200 dark:border-sa-stone-800 bg-sa-stone-50 dark:bg-sa-stone-900 overflow-x-auto">
      <div className="flex gap-1 px-4 py-2 w-max">
        {THUMB_STRIP_KEYS.map((key) => {
          const url = thumbnailUrls[key]
          if (!url) return null
          const active = selectionMatchesThumbKey(selection, key)
          const target = THUMB_KEY_TO_SELECTION[key]
          return (
            <button
              key={key}
              onClick={() => target && onSelect(target)}
              className={[
                'flex flex-col items-center gap-1 flex-shrink-0 p-1.5 rounded-lg transition-colors duration-[200ms]',
                active
                  ? 'bg-sa-amber-100 dark:bg-sa-amber-950/30'
                  : 'hover:bg-sa-stone-200 dark:hover:bg-sa-stone-700',
              ].join(' ')}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={THUMB_STRIP_LABELS[key]}
                className={[
                  'h-14 w-auto rounded object-cover',
                  active ? 'ring-2 ring-sa-amber-500' : '',
                ].join(' ')}
              />
              <span className={[
                'text-[9px]',
                active
                  ? 'text-sa-amber-600 dark:text-sa-amber-400 font-semibold'
                  : 'text-sa-stone-400 dark:text-sa-stone-500',
              ].join(' ')}>
                {THUMB_STRIP_LABELS[key]}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function JobDetailPage({ params }: { params: { jobId: string } }) {
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [selection, setSelection] = useState<StepSelection>({ kind: 'job', stepKey: 'load' })
  // Tracks which photo index triggered a reprocess so only that photo shows the running indicator
  const [reprocessingPhotoIdx, setReprocessingPhotoIdx] = useState<number | null>(null)

  useEffect(() => {
    getJob(params.jobId)
      .then((j) => {
        setJob(j)
        // Auto-select first step that has a debug image
        for (const { stepKey, debugKey } of JOB_STEP_TREE) {
          if (j.debug_urls?.[debugKey]) {
            setSelection({ kind: 'job', stepKey })
            return
          }
        }
        // If no pre-split steps, try first per-photo step for photo 1
        for (const { stepKey, debugKeyFn } of PHOTO_STEP_TREE) {
          if (j.debug_urls?.[debugKeyFn('01')]) {
            setSelection({ kind: 'photo', photoIdx: 1, stepKey })
            return
          }
        }
        // Fall back to results if available
        if (j.output_urls?.length) {
          setSelection({ kind: 'results' })
        }
      })
      .catch(() => setFetchError('Could not load job'))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.jobId])

  // Poll while processing (initial run or reprocess)
  useEffect(() => {
    if (!job || job.status !== 'processing') return
    const id = setInterval(() => {
      getJob(params.jobId)
        .then((j) => {
          setJob(j)
          if (j.status !== 'processing') setReprocessingPhotoIdx(null)
        })
        .catch(() => { /* keep polling */ })
    }, POLLING_INTERVAL_MS)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status, params.jobId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 rounded-full border-2 border-sa-amber-500 border-t-transparent animate-spin" />
      </div>
    )
  }

  if (fetchError || !job) {
    return (
      <div className="flex flex-col items-center py-20 gap-4 text-center">
        <p className="text-sa-error text-sm">{fetchError ?? 'Job not found'}</p>
        <Link href="/library" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline text-sm">
          ← Back to Library
        </Link>
      </div>
    )
  }

  const currentLabel = selectionLabel(selection)

  function renderCanvas() {
    if (!job) return null

    if (selection.kind === 'results') {
      return <ResultsView job={job} />
    }

    if (selection.kind === 'photo') {
      if (selection.stepKey === 'glare_remove') {
        const n = photoNum(selection.photoIdx)
        return (
          <GlareRemovalView
            afterUrl={job.debug_urls?.[`07_photo_${n}_deglared`]}
            photoIdx={selection.photoIdx}
            jobId={job.job_id}
            onStarted={() => { setReprocessingPhotoIdx(selection.photoIdx); setJob((j) => j ? { ...j, status: 'processing' } : j) }}
          />
        )
      }
      if (selection.stepKey === 'ai_orient') {
        return (
          <OrientationView
            job={job}
            photoIdx={selection.photoIdx}
            onStarted={() => { setReprocessingPhotoIdx(selection.photoIdx); setJob((j) => j ? { ...j, status: 'processing' } : j) }}
          />
        )
      }
      if (selection.stepKey === 'color_restore') {
        return (
          <ColorRestoreView
            job={job}
            photoIdx={selection.photoIdx}
            onStarted={() => { setReprocessingPhotoIdx(selection.photoIdx); setJob((j) => j ? { ...j, status: 'processing' } : j) }}
          />
        )
      }
    }

    // Photo Split step gets the interactive boundary editor
    if (selection.kind === 'job' && selection.stepKey === 'photo_split') {
      return (
        <PhotoSplitView
          job={job}
          onStarted={() => setJob((j) => j ? { ...j, status: 'processing' } : j)}
        />
      )
    }

    return <DebugImageCanvas url={getDebugUrl(job, selection)} label={currentLabel} />
  }

  return (
    // -mx-4 -my-8 escapes the (app)/layout.tsx's px-4 py-8 on <main>
    // so the step-detail chrome can be flush edge-to-edge within max-w-6xl
    <div className="-mx-4 -my-8 flex flex-col" style={{ minHeight: 'calc(100vh - 56px)' }}>
      {/* Processing indicator — lean top strip */}
      {job.status === 'processing' && (
        <div className="flex items-center gap-2 px-6 py-2 bg-sa-amber-50 dark:bg-sa-amber-950/20 border-b border-sa-amber-200 dark:border-sa-amber-900/40 text-[11px] text-sa-amber-700 dark:text-sa-amber-400 flex-shrink-0">
          <div className="w-2.5 h-2.5 rounded-full border-[1.5px] border-sa-amber-500 border-t-transparent animate-spin flex-shrink-0" />
          Processing — results will update automatically when complete.
        </div>
      )}

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 px-6 py-3.5 border-b border-sa-stone-200 dark:border-sa-stone-800 text-[13px] flex-shrink-0">
        <Link
          href="/library"
          className="text-sa-stone-500 dark:text-sa-stone-400 hover:text-sa-stone-700 dark:hover:text-sa-stone-200 transition-colors duration-[200ms]"
        >
          Library
        </Link>
        <span className="text-sa-stone-300 dark:text-sa-stone-600">/</span>
        <span
          className="text-sa-stone-600 dark:text-sa-stone-300 truncate max-w-[200px]"
          title={job.input_filename}
        >
          {job.input_filename}
        </span>
        <span className="text-sa-stone-300 dark:text-sa-stone-600 ml-auto" aria-hidden="true">·</span>
        <Link
          href={`/pipeline?jobId=${job.job_id}`}
          className="ml-1 text-sa-amber-600 dark:text-sa-amber-400 hover:underline flex-shrink-0"
        >
          View in Pipeline
        </Link>
        <span className="text-sa-stone-300 dark:text-sa-stone-600">/</span>
        <span className="text-sa-stone-900 dark:text-sa-stone-100 font-semibold">{currentLabel}</span>
      </div>

      {/* Step thumbnail strip — single-photo jobs only */}
      {job.photo_count === 1 && job.thumbnail_urls && Object.keys(job.thumbnail_urls).length > 0 && (
        <StepThumbnailStrip
          thumbnailUrls={job.thumbnail_urls}
          selection={selection}
          onSelect={setSelection}
        />
      )}

      {/* 3-pane body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar — 196px, independently scrollable */}
        <div className="border-r border-sa-stone-200 dark:border-sa-stone-800 overflow-y-auto flex-shrink-0">
          <StepTree job={job} selection={selection} onSelect={setSelection} reprocessingPhotoIdx={reprocessingPhotoIdx} />
        </div>

        {/* Right canvas — relative wrapper for bottom progress overlay */}
        <div className="flex-1 flex flex-col overflow-hidden relative min-w-0">
          {/* Canvas — switches between views with a fade */}
          <AnimatePresence mode="wait">
            <motion.div
              key={JSON.stringify(selection)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="flex-1 flex overflow-auto min-w-0"
            >
              {renderCanvas()}
            </motion.div>
          </AnimatePresence>

          {/* Bottom progress banner — shown while pipeline is running */}
          {job.status === 'processing' && (() => {
            const fraction = STEP_PROGRESS[job.current_step] ?? 0
            const stepNum = (BACKEND_TO_VISUAL[job.current_step] ?? 0) + 1
            const stepLabel = job.step_detail || STEP_LABELS[job.current_step] || job.current_step
            return (
              <div className="absolute bottom-0 inset-x-0 flex items-center gap-3 px-5 py-3 border-t border-sa-amber-200 dark:border-sa-amber-900/40 bg-white/90 dark:bg-sa-stone-950/90 backdrop-blur-sm">
                <div className="w-4 h-4 rounded-full border-2 border-sa-amber-500 border-t-transparent animate-spin flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[12px] font-semibold text-sa-stone-700 dark:text-sa-stone-200 truncate">
                      Step {stepNum} of {TOTAL_VISUAL_STEPS}: {stepLabel}
                    </span>
                    <span className="text-[11px] tabular-nums text-sa-stone-400 dark:text-sa-stone-500 flex-shrink-0 ml-3">
                      {Math.round(fraction * 100)}%
                    </span>
                  </div>
                  <div className="h-0.5 rounded-full bg-sa-stone-200 dark:bg-sa-stone-700 overflow-hidden">
                    <div
                      className="h-full bg-sa-amber-500 rounded-full transition-[width] duration-500 ease-out"
                      style={{ width: `${Math.round(fraction * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}
