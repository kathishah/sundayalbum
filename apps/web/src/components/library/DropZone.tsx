'use client'

import { useRef, useState, useCallback, type DragEvent, type ChangeEvent } from 'react'
import clsx from 'clsx'
import { ALLOWED_EXTENSIONS } from '@/lib/constants'
import Button from '@/components/ui/Button'

interface DropZoneProps {
  onFiles: (files: FileList) => void
  compact?: boolean
}

function CloudUploadIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
    </svg>
  )
}

export default function DropZone({ onFiles, compact = false }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setDragActive(false)
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onFiles(e.dataTransfer.files)
      }
    },
    [onFiles],
  )

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onFiles(e.target.files)
        e.target.value = ''
      }
    },
    [onFiles],
  )

  const acceptedExtensions = Array.from(ALLOWED_EXTENSIONS).join(',')

  if (compact) {
    return (
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={clsx(
          'flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-dashed transition-all duration-[200ms]',
          dragActive
            ? 'border-sa-amber-400 bg-sa-amber-50 dark:bg-sa-amber-950'
            : 'border-sa-stone-300 dark:border-sa-stone-700 hover:border-sa-amber-400 dark:hover:border-sa-amber-500',
        )}
      >
        <CloudUploadIcon className="w-5 h-5 text-sa-stone-400 dark:text-sa-stone-500 flex-shrink-0" />
        <span className="text-sm text-sa-stone-500 dark:text-sa-stone-400 flex-1">
          Drop more pages here
        </span>
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          Choose Files
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={acceptedExtensions}
          multiple
          onChange={handleChange}
          className="sr-only"
        />
      </div>
    )
  }

  return (
    <div
      data-testid="drop-zone"
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      className={clsx(
        'flex flex-col items-center justify-center gap-5 px-8 py-16 rounded-2xl border-2 border-dashed transition-all duration-[350ms]',
        dragActive
          ? 'border-sa-amber-400 bg-sa-amber-50 dark:bg-sa-amber-950 scale-[1.01]'
          : 'border-sa-stone-300 dark:border-sa-stone-700 hover:border-sa-amber-400 dark:hover:border-sa-amber-500 bg-white dark:bg-sa-stone-900',
      )}
    >
      <CloudUploadIcon
        className={clsx(
          'w-16 h-16 transition-colors duration-[200ms]',
          dragActive
            ? 'text-sa-amber-500'
            : 'text-sa-stone-300 dark:text-sa-stone-600',
        )}
      />

      <div className="text-center">
        <p className="font-display text-xl font-semibold text-sa-stone-800 dark:text-sa-stone-100 mb-1">
          Drop album pages here
        </p>
        <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400">
          HEIC, JPG, or PNG · up to multiple files at once
        </p>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-sa-stone-400 dark:text-sa-stone-600">or</span>
        <Button
          variant="primary"
          size="md"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          Choose Files
        </Button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={acceptedExtensions}
        multiple
        onChange={handleChange}
        className="sr-only"
      />
    </div>
  )
}
