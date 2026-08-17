'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import clsx from 'clsx'

interface BeforeAfterSliderProps {
  beforeSrc?: string
  afterSrc?: string
  beforeLabel?: string
  afterLabel?: string
  beforeAlt?: string
  afterAlt?: string
  className?: string
  style?: React.CSSProperties
  /** Render slot for 'before' pane when no beforeSrc is supplied */
  beforeSlot?: React.ReactNode
  /** Render slot for 'after' pane when no afterSrc is supplied */
  afterSlot?: React.ReactNode
  /**
   * Starting handle position as a percentage (0–100).
   * 0 = handle at left, showing full "before".
   * 100 = handle at right, showing full "after".
   * Defaults to 0.
   */
  initialPosition?: number
}

export default function BeforeAfterSlider({
  beforeSrc,
  afterSrc,
  beforeLabel = 'Before',
  afterLabel = 'After',
  beforeAlt = 'Before image',
  afterAlt = 'After image',
  className,
  beforeSlot,
  afterSlot,
  initialPosition = 0,
  style,
}: BeforeAfterSliderProps) {
  const [position, setPosition] = useState(initialPosition)
  const containerRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)
  const hinted = useRef(false)

  // One-time hint: nudge handle right then back to show it's draggable
  useEffect(() => {
    if (hinted.current) return
    hinted.current = true
    const t1 = setTimeout(() => setPosition(18), 600)
    const t2 = setTimeout(() => setPosition(initialPosition), 1200)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [initialPosition])

  const updatePosition = useCallback((clientX: number) => {
    const el = containerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width))
    setPosition((x / rect.width) * 100)
  }, [])

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      isDragging.current = true
      updatePosition(e.clientX)
      e.preventDefault()
    },
    [updatePosition],
  )

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      isDragging.current = true
      updatePosition(e.touches[0].clientX)
    },
    [updatePosition],
  )

  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (isDragging.current) updatePosition(e.clientX) }
    const onTouchMove = (e: TouchEvent) => { if (isDragging.current) updatePosition(e.touches[0].clientX) }
    const onUp = () => { isDragging.current = false }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    window.addEventListener('touchmove', onTouchMove, { passive: true })
    window.addEventListener('touchend', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', onUp)
    }
  }, [updatePosition])

  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative overflow-hidden rounded-2xl select-none cursor-ew-resize',
        'border border-sa-stone-200 dark:border-sa-stone-700',
        className,
      )}
      style={style}
      onMouseDown={onMouseDown}
      onTouchStart={onTouchStart}
      role="img"
      aria-label={`Before/after comparison: ${beforeLabel} and ${afterLabel}`}
    >
      {/* Base layer: "before" — always full width */}
      <div className="w-full h-full">
        {beforeSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={beforeSrc} alt={beforeAlt} className="w-full h-full object-cover" draggable={false} />
        ) : (
          beforeSlot
        )}
      </div>

      {/* Overlay: "after" — revealed from left as handle moves right */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
      >
        {afterSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={afterSrc} alt={afterAlt} className="w-full h-full object-cover" draggable={false} />
        ) : (
          afterSlot
        )}
      </div>

      {/* Divider line */}
      <div
        className="absolute inset-y-0 w-0.5 bg-white shadow-[0_0_6px_rgba(0,0,0,0.4)] pointer-events-none transition-[left] duration-[200ms]"
        style={{ left: `${position}%`, transform: 'translateX(-50%)' }}
      />

      {/* Handle knob */}
      <div
        className="absolute top-1/2 w-9 h-9 rounded-full bg-white shadow-[0_2px_12px_rgba(0,0,0,0.35)] flex items-center justify-center pointer-events-none transition-[left] duration-[200ms]"
        style={{ left: `${position}%`, transform: 'translate(-50%, -50%)' }}
      >
        <svg
          viewBox="0 0 20 20"
          className="w-5 h-5 text-sa-stone-600"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M7 4l-4 6 4 6M13 4l4 6-4 6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* Labels */}
      <span className="absolute bottom-3 left-3 text-xs font-medium text-white bg-black/50 px-2 py-1 rounded-full pointer-events-none">
        {beforeLabel}
      </span>
      <span className="absolute bottom-3 right-3 text-xs font-medium text-white bg-black/50 px-2 py-1 rounded-full pointer-events-none">
        {afterLabel}
      </span>
    </div>
  )
}
