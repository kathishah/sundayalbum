'use client'

import { type ButtonHTMLAttributes } from 'react'
import clsx from 'clsx'
import Spinner from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-sa-amber-500 hover:bg-sa-amber-600 text-white border border-transparent focus-visible:ring-sa-amber-500',
  secondary:
    'bg-sa-stone-200 hover:bg-sa-stone-300 dark:bg-sa-stone-700 dark:hover:bg-sa-stone-600 text-sa-stone-800 dark:text-sa-stone-100 border border-transparent focus-visible:ring-sa-stone-400',
  ghost:
    'bg-transparent hover:bg-sa-stone-100 dark:hover:bg-sa-stone-800 text-sa-stone-700 dark:text-sa-stone-300 border border-transparent focus-visible:ring-sa-stone-400',
}

const sizeClasses: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm rounded-lg gap-1.5',
  md: 'px-4 py-2 text-sm rounded-xl gap-2',
  lg: 'px-6 py-3 text-base rounded-xl gap-2',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  className,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading

  return (
    <button
      disabled={isDisabled}
      className={clsx(
        'inline-flex items-center justify-center font-medium',
        'transition-all duration-[200ms] cubic-bezier(0.16,1,0.3,1)',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading && <Spinner size={size === 'lg' ? 'md' : 'sm'} />}
      {children}
    </button>
  )
}
