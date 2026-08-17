'use client'

import { useState } from 'react'
import type { Job } from '@/lib/types'

interface ResultsViewProps {
  job: Job
}

export default function ResultsView({ job }: ResultsViewProps) {
  const outputUrls = job.output_urls ?? []
  const [selected, setSelected] = useState(0)
  const total = outputUrls.length

  if (total === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sa-stone-400 dark:text-sa-stone-500 text-sm">
        No output photos available
      </div>
    )
  }

  function handleDownloadAll() {
    outputUrls.forEach((url, i) => {
      const a = document.createElement('a')
      a.href = url
      a.download = `photo_${String(i + 1).padStart(2, '0')}.jpg`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    })
  }

  const prev = () => setSelected((s) => Math.max(0, s - 1))
  const next = () => setSelected((s) => Math.min(total - 1, s + 1))

  return (
    <div data-testid="results-view" className="flex-1 flex flex-col overflow-hidden">
      {/* Single large image */}
      <div className="flex-1 flex justify-center p-6 overflow-auto min-h-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={selected}
          src={outputUrls[selected]}
          alt={`Photo ${selected + 1}`}
          className="max-h-full w-auto rounded-xl shadow-md object-contain self-start"
        />
      </div>

      {/* Navigation + download footer */}
      <div className="flex-shrink-0 border-t border-sa-amber-200 bg-sa-amber-50 px-6 py-3 flex items-center gap-4">
        {/* Prev/Next only if more than one photo */}
        {total > 1 && (
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={prev}
              disabled={selected === 0}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-sa-amber-200 text-sa-stone-600 hover:bg-sa-amber-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-[200ms]"
              aria-label="Previous photo"
            >
              <svg viewBox="0 0 8 12" width="8" height="12" fill="currentColor">
                <path d="M6.5 1L1.5 6l5 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span className="text-[13px] text-sa-stone-600 tabular-nums flex-shrink-0">
              {selected + 1} <span className="text-sa-stone-400">/ {total}</span>
            </span>
            <button
              onClick={next}
              disabled={selected === total - 1}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-sa-amber-200 text-sa-stone-600 hover:bg-sa-amber-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-[200ms]"
              aria-label="Next photo"
            >
              <svg viewBox="0 0 8 12" width="8" height="12" fill="currentColor">
                <path d="M1.5 1L6.5 6l-5 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        )}

        <div className="flex-1" />

        {/* Filename */}
        <span className="text-[11px] font-mono text-sa-stone-400 truncate hidden sm:block max-w-[200px]" title={job.input_filename}>
          {job.input_filename}
        </span>

        {/* Download */}
        <a
          href={outputUrls[selected]}
          download={`photo_${String(selected + 1).padStart(2, '0')}.jpg`}
          className="flex-shrink-0 px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 transition-colors duration-[200ms]"
        >
          {total > 1 ? `Download Photo ${selected + 1}` : 'Download'}
        </a>
        {total > 1 && (
          <button
            onClick={handleDownloadAll}
            className="flex-shrink-0 px-4 py-1.5 rounded-lg text-[12px] font-semibold text-sa-stone-600 bg-white border border-sa-amber-200 hover:bg-sa-amber-100 transition-colors duration-[200ms]"
          >
            Download All ({total})
          </button>
        )}
      </div>
    </div>
  )
}
