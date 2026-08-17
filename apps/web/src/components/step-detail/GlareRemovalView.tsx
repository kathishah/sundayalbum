'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { reprocessJob } from '@/lib/api'

// The static part of the prompt sent to OpenAI gpt-image-1.5.
// Source: src/glare/remover_openai.py _build_prompt()
const PROMPT_STATIC =
  'We used an iPhone camera to photograph a picture printed on glossy paper for digitization. ' +
  'Remove glare/reflections caused by the glossy surface. ' +
  'Preserve the original composition, geometry, textures, and colors. ' +
  'Only modify pixels necessary to remove glare/reflections; do not change framing. ' +
  'Description of the printed photo: '

interface GlareRemovalViewProps {
  afterUrl: string | undefined
  photoIdx: number
  jobId: string
  onStarted: () => void
}

export default function GlareRemovalView({
  afterUrl,
  photoIdx,
  jobId,
  onStarted,
}: GlareRemovalViewProps) {
  const [revealed, setRevealed] = useState(false)
  const [sceneDesc, setSceneDesc] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const dirty = sceneDesc.trim() !== ''

  // Re-trigger reveal animation each time the photo changes
  useEffect(() => {
    setRevealed(false)
    setSceneDesc('')
    setSubmitError(null)
    const raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => setRevealed(true))
      return () => cancelAnimationFrame(raf2)
    })
    return () => cancelAnimationFrame(raf1)
  }, [photoIdx])

  async function handleApply() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      await reprocessJob(jobId, {
        from_step: 'glare_remove',
        photo_index: photoIdx,
        config: sceneDesc.trim()
          ? { forced_scene_description: sceneDesc.trim() }
          : {},
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
      {/* Image canvas — saReveal: 600ms cubic-bezier(0.16,1,0.3,1); amber glow delay 400ms */}
      <div className="flex-1 flex justify-center p-6 overflow-auto min-h-0">
        <motion.div
          className="rounded-xl overflow-hidden bg-sa-surface self-start"
          animate={{ opacity: revealed ? 1 : 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {afterUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={afterUrl} alt="Glare removed" className="max-h-full w-auto object-contain" />
          ) : (
            <div className="w-64 h-64 flex items-center justify-center text-sa-stone-400 dark:text-sa-stone-500 text-sm">
              No image available
            </div>
          )}
        </motion.div>
      </div>

      {/* Prompt + reprocess footer */}
      <div className="flex-shrink-0 border-t border-sa-amber-200 bg-sa-amber-50 px-6 py-4 flex flex-col gap-3">
        {/* Prompt template display */}
        <div className="flex flex-col gap-1.5">
          <p className="text-[11px] font-semibold text-sa-stone-400 dark:text-sa-stone-500 uppercase tracking-wider">
            Prompt sent to OpenAI
          </p>
          <p className="text-[11px] text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed font-mono bg-white dark:bg-sa-stone-800 rounded-lg px-3 py-2 border border-sa-stone-200 dark:border-sa-stone-700">
            {PROMPT_STATIC}
            <span className="text-sa-amber-600 dark:text-sa-amber-400 italic">
              {sceneDesc.trim() || '[AI auto-detected scene description]'}
            </span>
          </p>
        </div>

        {/* Scene description override + actions row */}
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px] flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-sa-stone-400 dark:text-sa-stone-500 uppercase tracking-wider">
              Override scene description
            </label>
            <input
              type="text"
              value={sceneDesc}
              onChange={(e) => setSceneDesc(e.target.value)}
              placeholder="Leave blank to use AI auto-detected description"
              className="text-[12px] px-3 py-1.5 rounded-lg border border-sa-stone-200 dark:border-sa-stone-700 bg-white dark:bg-sa-stone-800 text-sa-stone-700 dark:text-sa-stone-200 placeholder:text-sa-stone-300 dark:placeholder:text-sa-stone-600 focus:outline-none focus:ring-1 focus:ring-sa-amber-500"
            />
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {submitError && (
              <span className="text-[11px] text-sa-error">{submitError}</span>
            )}
            {dirty && !submitting && (
              <button
                onClick={() => { setSceneDesc(''); setSubmitError(null) }}
                className="px-3 py-1.5 rounded-lg text-[12px] text-sa-stone-500 dark:text-sa-stone-400 hover:text-sa-stone-700 dark:hover:text-sa-stone-200 transition-colors duration-[200ms]"
              >
                Discard
              </button>
            )}
            <button
              onClick={handleApply}
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-[200ms]"
            >
              {submitting ? 'Starting…' : 'Re-run Glare Removal'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
