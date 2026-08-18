'use client'

import {
  useEffect,
  useState,
  useCallback,
  useRef,
  type DragEvent,
  type ChangeEvent,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useJobsStore } from '@/stores/jobs-store'
import { listJobs, createJob, s3Upload, startJob } from '@/lib/api'
import { ALLOWED_EXTENSIONS } from '@/lib/constants'
import AlbumPageCard from '@/components/library/AlbumPageCard'
import DropZone from '@/components/library/DropZone'
import ExpandedCard from '@/components/library/ExpandedCard'
import type { Job } from '@/lib/types'

export default function LibraryPage() {
  const { jobs, setJobs, upsertJob } = useJobsStore()
  const [loading, setLoading] = useState(true)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Track drag enter/leave across child elements
  const dragCounter = useRef(0)

  useEffect(() => {
    listJobs()
      .then((res) => setJobs(res.jobs))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [setJobs])

  // Close expanded overlay if the job gets removed
  useEffect(() => {
    if (expandedJobId && !jobs.find((j) => j.job_id === expandedJobId)) {
      setExpandedJobId(null)
    }
  }, [jobs, expandedJobId])

  // ── File handling ──────────────────────────────────────────────────────────

  const handleFiles = useCallback(
    async (files: FileList) => {
      setUploadError(null)

      for (const file of Array.from(files)) {
        const ext = '.' + (file.name.split('.').pop()?.toLowerCase() ?? '')
        if (!ALLOWED_EXTENSIONS.has(ext)) {
          setUploadError(`Unsupported file type: ${ext}. Allowed: HEIC, JPG, PNG.`)
          continue
        }

        // Optimistic placeholder — preview_url gives immediate before-thumbnail
        const previewUrl = URL.createObjectURL(file)
        const optimistic: Job = {
          job_id: `uploading-${Date.now()}`,
          status: 'uploading',
          current_step: '',
          step_detail: '',
          input_filename: file.name,
          input_stem: file.name.replace(/\.[^.]+$/, ''),
          photo_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          error_message: '',
          processing_time: 0,
          output_keys: [],
          preview_url: previewUrl,
        }
        upsertJob(optimistic)

        try {
          const created = await createJob(file.name, file.size)
          await s3Upload(created.upload_url, file)
          await startJob(created.job_id)

          // Fetch real job and replace optimistic — preserve preview_url as fallback
          const res = await listJobs()
          const realJob = res.jobs.find((j) => j.job_id === created.job_id)
          if (realJob) {
            upsertJob({ ...realJob, preview_url: previewUrl })
            setJobs([
              { ...realJob, preview_url: previewUrl },
              ...res.jobs.filter((j) => j.job_id !== created.job_id),
            ])
          } else {
            setJobs(res.jobs)
          }
        } catch (err) {
          URL.revokeObjectURL(previewUrl)
          upsertJob({
            ...optimistic,
            status: 'failed',
            error_message: err instanceof Error ? err.message : 'Upload failed',
          })
          setUploadError(err instanceof Error ? err.message : 'Upload failed. Try again.')
        }
      }
    },
    [upsertJob, setJobs],
  )

  const handleFileInput = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files)
        e.target.value = ''
      }
    },
    [handleFiles],
  )

  // ── Full-page drag handlers (active even when grid is populated) ───────────

  const handleDragEnter = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    dragCounter.current++
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    dragCounter.current--
    if (dragCounter.current === 0) setIsDragOver(false)
  }, [])

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      dragCounter.current = 0
      setIsDragOver(false)
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files)
      }
    },
    [handleFiles],
  )

  // ── Derived state ──────────────────────────────────────────────────────────

  const expandedJob = expandedJobId
    ? (jobs.find((j) => j.job_id === expandedJobId) ?? null)
    : null

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-sa-amber-500 border-t-transparent animate-spin" />
      </div>
    )
  }

  return (
    <div
      className="relative min-h-full"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Full-page drag-over amber border overlay */}
      {isDragOver && (
        <div className="pointer-events-none fixed inset-0 z-30 border-[3px] border-sa-amber-500" />
      )}

      {/* Page content — blurred when a card is expanded */}
      <div
        className="transition-[filter] duration-[200ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
        style={{ filter: expandedJobId ? 'blur(3px)' : 'none' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-8 pt-6 sm:pt-8 pb-6">
          <h1 className="font-display text-[32px] font-semibold text-sa-stone-700 dark:text-sa-stone-100 leading-tight">
            Library
          </h1>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium text-white bg-sa-amber-500 hover:bg-sa-amber-600 transition-colors duration-[200ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
          >
            <svg viewBox="0 0 12 12" width="12" height="12" fill="currentColor">
              <path d="M6.5 1H5.5v4.5H1v1h4.5V11h1V6.5H11v-1H6.5V1z" />
            </svg>
            Add Photos
          </button>
        </div>

        {/* Hidden file input for "Add Photos" button */}
        <input
          ref={fileInputRef}
          type="file"
          accept={Array.from(ALLOWED_EXTENSIONS).join(',')}
          multiple
          onChange={handleFileInput}
          className="sr-only"
        />

        {/* Error banner */}
        {uploadError && (
          <div className="mx-4 sm:mx-8 mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950 border border-sa-error text-sa-error text-sm">
            {uploadError}
          </div>
        )}

        {/* Empty state: DropZone at 320px height */}
        {jobs.length === 0 ? (
          <div className="px-4 sm:px-8" style={{ height: 320 }}>
            <DropZone onFiles={handleFiles} />
          </div>
        ) : (
          <>
            {/* Compact drop zone — always visible above the grid when jobs exist */}
            <div className="px-4 sm:px-8 pb-4">
              <DropZone onFiles={handleFiles} compact />
            </div>

            {/* Adaptive grid — min 240px, max 400px columns, 16px gap */}
            <div
              data-testid="library-grid"
              className="px-4 sm:px-8 pb-10"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(min(240px, 100%), 400px))',
                gap: 16,
              }}
            >
              {jobs.map((job) => (
                <AlbumPageCard
                  key={job.job_id}
                  job={job}
                  isOtherExpanded={expandedJobId !== null && expandedJobId !== job.job_id}
                  onExpand={() =>
                    setExpandedJobId((prev) => (prev === job.job_id ? null : job.job_id))
                  }
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Expanded card overlay — rendered outside the blurred container */}
      <AnimatePresence>
        {expandedJob && (
          <ExpandedCard
            key={expandedJob.job_id}
            job={expandedJob}
            onClose={() => setExpandedJobId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
