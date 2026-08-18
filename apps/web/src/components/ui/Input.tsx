'use client'

import { type InputHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, className, id, ...props },
  ref,
) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          htmlFor={inputId}
          className="text-sm font-medium text-sa-stone-700 dark:text-sa-stone-300"
        >
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={clsx(
          'w-full px-3 py-2 rounded-xl text-sm',
          'bg-white dark:bg-sa-stone-800',
          'text-sa-stone-900 dark:text-sa-stone-50',
          'border transition-all duration-[200ms]',
          'placeholder:text-sa-stone-400 dark:placeholder:text-sa-stone-600',
          'focus:outline-none focus:ring-2 focus:ring-sa-amber-500 focus:border-transparent',
          error
            ? 'border-sa-error focus:ring-sa-error'
            : 'border-sa-stone-300 dark:border-sa-stone-700',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          className,
        )}
        {...props}
      />
      {error && (
        <p className="text-xs text-sa-error">{error}</p>
      )}
      {hint && !error && (
        <p className="text-xs text-sa-stone-500 dark:text-sa-stone-400">{hint}</p>
      )}
    </div>
  )
})

export default Input
