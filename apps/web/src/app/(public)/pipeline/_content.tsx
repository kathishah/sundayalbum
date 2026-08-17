'use client'

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { isAuthenticated } from '@/lib/auth'
import { getJob, reprocessJob } from '@/lib/api'
import type { Job } from '@/lib/types'

// ── Step definitions ──────────────────────────────────────────────────────────

interface ConfigOption {
  key: string
  label: string
  description: string
  type: 'boolean'
  defaultValue: boolean
}

interface PipelineStepDef {
  id: string
  rerunId: string
  label: string
  phase: 'page' | 'photo'
  description: string
  detail: string
  /** src relative to /demo/pipeline/ — null = no image for this step */
  imageSrc: string | null
  configOptions: ConfigOption[]
}

const STEPS: PipelineStepDef[] = [
  {
    id: 'load',
    rerunId: 'load',
    label: 'Load',
    phase: 'page',
    description: 'Decode the uploaded image and apply EXIF orientation.',
    detail: 'Supports HEIC (iPhone), JPEG, PNG, and DNG (ProRAW). Normalises to float32 RGB [0,1]. EXIF rotation is applied so the image always enters the pipeline right-side up.',
    imageSrc: '/demo/pipeline/01_loaded.jpg',
    configOptions: [],
  },
  {
    id: 'page_detect',
    rerunId: 'page_detect',
    label: 'Page Detect',
    phase: 'page',
    description: 'Find the album page boundary using GrabCut segmentation.',
    detail: 'OpenCV GrabCut seeds from an inset rectangle, segments foreground from background, then fits a quadrilateral to the largest contour. The four corner points define the album page in the original photo.',
    imageSrc: '/demo/pipeline/02_page_detected.jpg',
    configOptions: [],
  },
  {
    id: 'perspective',
    rerunId: 'perspective',
    label: 'Perspective',
    phase: 'page',
    description: 'Warp the page to a flat, top-down view.',
    detail: 'Computes a homography from the detected page corners to a rectangle of equivalent area. The result looks as if you had placed the album flat on a table and photographed it directly overhead.',
    imageSrc: '/demo/pipeline/03_page_warped.jpg',
    configOptions: [],
  },
  {
    id: 'photo_detect',
    rerunId: 'photo_detect',
    label: 'Photo Detect',
    phase: 'page',
    description: 'Find individual photo boundaries within the corrected page.',
    detail: 'Converts to LAB colour space, applies edge detection and contour finding, then filters by aspect ratio and minimum area. Photos are sorted top-to-bottom, left-to-right.',
    imageSrc: '/demo/pipeline/04_photo_bounds.jpg',
    configOptions: [],
  },
  {
    id: 'photo_split',
    rerunId: 'photo_split',
    label: 'Photo Split',
    phase: 'page',
    description: 'Extract each detected photo as its own crop.',
    detail: 'Applies a per-photo homography to extract a clean rectangular crop from the perspective-corrected page. Each crop enters the per-photo stages independently.',
    imageSrc: '/demo/pipeline/05_raw.jpg',
    configOptions: [],
  },
  {
    id: 'ai_orient',
    rerunId: 'ai_orient',
    label: 'AI Orient',
    phase: 'photo',
    description: 'Detect and correct rotation using Claude AI.',
    detail: 'Sends the photo to Claude Haiku asking for rotation (0/90/180/270°), flip flag, and a scene description. The scene description is reused by the glare removal model as inpainting context. Runs before glare removal so the model sees a correctly-oriented image.',
    imageSrc: '/demo/pipeline/06_oriented.jpg',
    configOptions: [
      {
        key: 'skip_ai_orient',
        label: 'Skip AI orientation',
        description: 'Pass through without rotation correction. Use if the photo is already correctly oriented.',
        type: 'boolean',
        defaultValue: false,
      },
    ],
  },
  {
    id: 'glare_remove',
    rerunId: 'glare_remove',
    label: 'Glare Remove',
    phase: 'photo',
    description: 'Erase glare using AI diffusion inpainting.',
    detail: 'Detects bright saturated highlights and creates a glare mask. OpenAI gpt-image-1 receives the photo, mask, and scene description and reconstructs the masked area using context from surrounding pixels. OpenCV Telea inpainting is available as a fallback.',
    imageSrc: '/demo/pipeline/07_deglared.jpg',
    configOptions: [
      {
        key: 'use_openai',
        label: 'Use AI inpainting (OpenAI)',
        description: 'Enabled: use OpenAI diffusion inpainting. Disabled: fall back to OpenCV (faster, lower quality on large patches).',
        type: 'boolean',
        defaultValue: true,
      },
    ],
  },
  {
    id: 'color_restore',
    rerunId: 'color_restore',
    label: 'Color Restore',
    phase: 'photo',
    description: 'Restore natural colours: white balance, deyellow, brightness, sharpen.',
    detail: 'Four stages: (1) white-point stretch, (2) deyellow to remove amber cast, (3) adaptive brightness lift on shadows/midtones, (4) vibrance to recover undersaturated hues. Finished with unsharp-mask sharpening.',
    imageSrc: '/demo/pipeline/08_enhanced.jpg',
    configOptions: [],
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
}
const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } }

const PHASE_COLORS = {
  page: 'bg-sa-stone-100 dark:bg-sa-stone-700 text-sa-stone-600 dark:text-sa-stone-300',
  photo: 'bg-sa-amber-100 dark:bg-sa-amber-900/40 text-sa-amber-700 dark:text-sa-amber-300',
}

// ── Step row ─────────────────────────────────────────────────────────────────

interface StepRowProps {
  step: PipelineStepDef
  index: number
  job: Job | null
  onRerun: (stepId: string, config: Record<string, unknown>) => void
  rerunning: string | null
}

function StepRow({ step, index, job, onRerun, rerunning }: StepRowProps) {
  const [config, setConfig] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(step.configOptions.map((o) => [o.key, o.defaultValue])),
  )
  const canRerun = !!job && job.status !== 'processing'
  const flip = index % 2 === 1

  const imageBlock = (
    <div className="relative rounded-2xl overflow-hidden shadow-md border border-sa-stone-200 dark:border-sa-stone-700 bg-sa-stone-100 dark:bg-sa-stone-800">
      {step.imageSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={step.imageSrc}
          alt={`${step.label} output`}
          className="w-full object-cover"
          draggable={false}
        />
      ) : (
        <div className="aspect-[3/2] flex items-center justify-center text-sa-stone-400 text-sm">
          No visual output for this step
        </div>
      )}
    </div>
  )

  const textBlock = (
    <div className="flex flex-col gap-4 justify-center py-2">
      <div className="flex items-center gap-3">
        <span className="w-8 h-8 rounded-full bg-sa-amber-100 dark:bg-sa-amber-900/40 text-sa-amber-600 dark:text-sa-amber-400 text-sm font-bold flex items-center justify-center flex-shrink-0">
          {index + 1}
        </span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${PHASE_COLORS[step.phase]}`}>
          {step.phase === 'page' ? 'page-level' : 'per-photo'}
        </span>
      </div>

      <div>
        <h3 className="font-display text-2xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
          {step.label}
        </h3>
        <p className="text-sa-stone-600 dark:text-sa-stone-300 leading-relaxed">
          {step.description}
        </p>
      </div>

      <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
        {step.detail}
      </p>

      {/* Config options */}
      {step.configOptions.length > 0 && (
        <div className="flex flex-col gap-3 pt-2 border-t border-sa-stone-100 dark:border-sa-stone-800">
          {step.configOptions.map((opt) => (
            <label key={opt.key} className="flex items-start gap-3 cursor-pointer">
              <div className="relative mt-0.5 flex-shrink-0">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={config[opt.key]}
                  onChange={(e) => setConfig((c) => ({ ...c, [opt.key]: e.target.checked }))}
                  disabled={!canRerun}
                />
                <div className="w-9 h-5 rounded-full bg-sa-stone-200 dark:bg-sa-stone-700 peer-checked:bg-sa-amber-500 transition-colors duration-[200ms] peer-disabled:opacity-50" />
                <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-[200ms] peer-checked:translate-x-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-sa-stone-800 dark:text-sa-stone-200">{opt.label}</p>
                <p className="text-xs text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed mt-0.5">{opt.description}</p>
              </div>
            </label>
          ))}
        </div>
      )}

      {/* Re-run button */}
      {canRerun && (
        <button
          onClick={() => onRerun(step.rerunId, config)}
          disabled={rerunning === step.rerunId}
          className="self-start flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-sa-amber-500 hover:bg-sa-amber-600 disabled:opacity-60 text-white transition-colors duration-[200ms]"
        >
          {rerunning === step.rerunId ? (
            <>
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" strokeOpacity="0.25" /><path d="M12 3a9 9 0 0 1 9 9" /></svg>
              Re-running…
            </>
          ) : (
            <>
              <svg viewBox="0 0 16 16" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8a5 5 0 1 1 10 0" /><path d="M13 5v3h-3" /></svg>
              Re-run from here
            </>
          )}
        </button>
      )}
    </div>
  )

  return (
    <motion.div
      variants={fadeUp}
      className={`grid md:grid-cols-2 gap-8 md:gap-12 items-center ${flip ? 'md:[&>*:first-child]:order-last' : ''}`}
    >
      {imageBlock}
      {textBlock}
    </motion.div>
  )
}

// ── Phase divider ─────────────────────────────────────────────────────────────

function PhaseDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-4 my-4">
      <div className="flex-1 h-px bg-sa-stone-200 dark:bg-sa-stone-700" />
      <span className="text-xs font-semibold uppercase tracking-wider text-sa-stone-400 dark:text-sa-stone-500 px-2">
        {label}
      </span>
      <div className="flex-1 h-px bg-sa-stone-200 dark:bg-sa-stone-700" />
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PipelinePageContent() {
  const searchParams = useSearchParams()
  const jobId = searchParams.get('jobId')

  const [authed, setAuthed] = useState(false)
  const [job, setJob] = useState<Job | null>(null)
  const [jobError, setJobError] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState<string | null>(null)
  const [rerunMsg, setRerunMsg] = useState<string | null>(null)

  useEffect(() => { setAuthed(isAuthenticated()) }, [])

  useEffect(() => {
    if (!jobId || !isAuthenticated()) return
    getJob(jobId).then(setJob).catch((e: Error) => setJobError(e.message))
  }, [jobId])

  const handleRerun = useCallback(async (fromStep: string, config: Record<string, unknown>) => {
    if (!job) return
    setRerunning(fromStep)
    setRerunMsg(null)
    try {
      await reprocessJob(job.job_id, { from_step: fromStep, config })
      setRerunMsg(`Re-running from "${fromStep}" — check your Library for progress.`)
      setJob((j) => (j ? { ...j, status: 'processing' } : j))
    } catch (e: unknown) {
      setRerunMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRerunning(null)
    }
  }, [job])

  // Split steps at the phase boundary
  const pageSteps = STEPS.filter((s) => s.phase === 'page')
  const photoSteps = STEPS.filter((s) => s.phase === 'photo')

  return (
    <div className="py-16 px-4">
      <div className="max-w-4xl mx-auto">

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <motion.div initial="hidden" animate="show" variants={stagger} className="mb-14">
          <motion.p variants={fadeUp} className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            Pipeline
          </motion.p>
          <motion.h1 variants={fadeUp} className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            From one snap to finished photos
          </motion.h1>
          <motion.p variants={fadeUp} className="text-lg text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed max-w-2xl">
            Every image below is real output from a single phone photo of an album page.
            Drag any before/after slider to compare the transformation at that step.
          </motion.p>
        </motion.div>

        {/* ── Final output hero ────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="mb-16"
        >
          <div className="relative rounded-2xl overflow-hidden shadow-xl border border-sa-stone-200 dark:border-sa-stone-700">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/demo/pipeline/09_final.jpg"
              alt="Final pipeline output"
              className="w-full object-cover"
              draggable={false}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            <div className="absolute bottom-0 left-0 right-0 p-6">
              <p className="text-white/70 text-xs font-medium uppercase tracking-wider mb-1">Final output</p>
              <p className="text-white font-display text-2xl font-bold">The finished photo</p>
              <p className="text-white/70 text-sm mt-1">Glare removed · Colors restored · Ready to share</p>
            </div>
          </div>
          <p className="mt-3 text-xs text-center text-sa-stone-400 dark:text-sa-stone-500">
            All images on this page are real output from IMG_1268.HEIC — a single iPhone photo of an album page.
          </p>
        </motion.div>

        {/* ── Job context ─────────────────────────────────────────────────── */}
        {jobId && (
          <div className={`mb-10 p-4 rounded-xl border text-sm ${
            job
              ? 'bg-sa-amber-50 dark:bg-sa-amber-950/30 border-sa-amber-200 dark:border-sa-amber-800 text-sa-amber-800 dark:text-sa-amber-200'
              : jobError
                ? 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                : 'bg-sa-stone-50 dark:bg-sa-stone-800 border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-500'
          }`}>
            {job ? (
              <span>
                Job <code className="font-mono text-xs bg-black/10 px-1 py-0.5 rounded">{job.job_id.slice(0, 8)}…</code>{' '}
                loaded — <strong>{job.input_filename}</strong> · {job.photo_count} photo{job.photo_count !== 1 ? 's' : ''} · status: <strong>{job.status}</strong>.
                Expand any step to re-run from that point.
              </span>
            ) : jobError ? (
              <span>Could not load job: {jobError}</span>
            ) : (
              <span>Loading job…</span>
            )}
          </div>
        )}

        {rerunMsg && (
          <div className="mb-8 p-4 rounded-xl bg-sa-stone-50 dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700 text-sm text-sa-stone-700 dark:text-sa-stone-200">
            {rerunMsg}{' '}
            {rerunMsg.startsWith('Re-running') && (
              <Link href="/library" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline">View in Library →</Link>
            )}
          </div>
        )}

        {!authed && (
          <div className="mb-10 p-4 rounded-xl bg-sa-stone-50 dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700 text-sm text-sa-stone-500 dark:text-sa-stone-400">
            <strong className="text-sa-stone-700 dark:text-sa-stone-200">Want to re-run steps on your own images?</strong>{' '}
            <Link href="/login" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline">Sign in</Link>{' '}
            then open a job and click "View in Pipeline."
          </div>
        )}

        {authed && !jobId && (
          <div className="mb-10 p-4 rounded-xl bg-sa-stone-50 dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700 text-sm text-sa-stone-500 dark:text-sa-stone-400">
            <strong className="text-sa-stone-700 dark:text-sa-stone-200">Re-run mode:</strong>{' '}
            open a completed job from your{' '}
            <Link href="/library" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline">Library</Link>{' '}
            and click "View in Pipeline" to load re-run controls.
          </div>
        )}

        {/* ── Page-level steps ─────────────────────────────────────────────── */}
        <PhaseDivider label="Page-level steps — run once per image" />

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-60px' }}
          variants={stagger}
          className="flex flex-col gap-16 mt-12"
        >
          {pageSteps.map((step, i) => (
            <StepRow
              key={step.id}
              step={step}
              index={i}
              job={job}
              onRerun={handleRerun}
              rerunning={rerunning}
            />
          ))}
        </motion.div>

        {/* ── Per-photo steps ──────────────────────────────────────────────── */}
        <PhaseDivider label="Per-photo steps — run once per detected photo" />

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-60px' }}
          variants={stagger}
          className="flex flex-col gap-16 mt-12"
        >
          {photoSteps.map((step, i) => (
            <StepRow
              key={step.id}
              step={step}
              index={pageSteps.length + i}
              job={job}
              onRerun={handleRerun}
              rerunning={rerunning}
            />
          ))}
        </motion.div>

        {/* ── CTA ─────────────────────────────────────────────────────────── */}
        <div className="mt-20 p-8 rounded-2xl bg-sa-amber-50 dark:bg-sa-amber-950/30 border border-sa-amber-200 dark:border-sa-amber-800 text-center">
          <h2 className="font-display text-2xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
            Try the full pipeline on your own photos
          </h2>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 mb-5">
            Upload a photo of an album page and watch every step run in real time.
          </p>
          <div className="flex justify-center gap-3">
            <Link href="/login" className="px-5 py-2.5 rounded-xl text-sm font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]">
              Try it free
            </Link>
            <Link href="/download" className="px-5 py-2.5 rounded-xl text-sm font-medium border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-white dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]">
              Download for Mac
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
