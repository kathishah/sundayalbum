'use client'

import { TOTAL_VISUAL_STEPS } from '@/lib/constants'

interface PipelineProgressWheelProps {
  completedCount: number
  size?: number
  /** When true, the next (unfilled) segment pulses amber to indicate active processing */
  isRunning?: boolean
}

/** Builds an SVG path string for one pie segment */
function pieSegmentPath(
  index: number,
  total: number,
  size: number,
  gapDeg: number,
): string {
  const cx = size / 2
  const cy = size / 2
  const r = size / 2
  const slice = 360 / total
  const startDeg = index * slice - 90 + gapDeg / 2
  const endDeg = (index + 1) * slice - 90 - gapDeg / 2
  const startRad = (startDeg * Math.PI) / 180
  const endRad = (endDeg * Math.PI) / 180
  const sx = cx + r * Math.cos(startRad)
  const sy = cy + r * Math.sin(startRad)
  const ex = cx + r * Math.cos(endRad)
  const ey = cy + r * Math.sin(endRad)
  // Each slice is 60° minus 3° gap = 57°, always < 180° → large-arc-flag = 0
  return `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 0 1 ${ex} ${ey} Z`
}

/**
 * Pie-chart progress wheel matching macOS PipelineProgressWheel.
 * 6 segments (one per visual pipeline step), amber fill for completed,
 * stone fill for pending. Donut hole uses saCard background.
 */
export default function PipelineProgressWheel({
  completedCount,
  size = 88,
  isRunning = false,
}: PipelineProgressWheelProps) {
  const total = TOTAL_VISUAL_STEPS
  const clamped = Math.max(0, Math.min(total, completedCount))
  const cx = size / 2
  const cy = size / 2
  // Donut hole radius: size * 0.28 matches macOS .padding(size * 0.22)
  const holeR = size * 0.28
  const countFontSize = Math.round(size * 0.22)
  const labelFontSize = Math.round(size * 0.12)

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-label={`${clamped} of ${total} steps complete`}
    >
      {/* Pie segments */}
      {Array.from({ length: total }, (_, i) => {
        const d = pieSegmentPath(i, total, size, 3)
        const isNext = isRunning && i === clamped
        return (
          <g key={i}>
            {/* Base segment */}
            <path
              d={d}
              className={
                i < clamped
                  ? 'fill-sa-amber-500 transition-opacity duration-[200ms]'
                  : 'fill-sa-stone-200 dark:fill-sa-stone-700'
              }
            />
            {/* Amber overlay on the next-to-fill segment — pulses while processing */}
            {isNext && (
              <path
                d={d}
                className="fill-sa-amber-400"
                style={{ animation: 'sa-segment-pulse 1.3s ease-in-out infinite' }}
              />
            )}
          </g>
        )
      })}

      {/* Donut hole — saCard color to blend with card background */}
      <circle
        cx={cx}
        cy={cy}
        r={holeR}
        className="fill-sa-card"
      />

      {/* Center label */}
      <text
        x={cx}
        y={cy - labelFontSize * 0.6}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={countFontSize}
        fontWeight="700"
        fontFamily="var(--font-dm-sans)"
        className="fill-sa-stone-700 dark:fill-sa-stone-100"
      >
        {clamped}
      </text>
      <text
        x={cx}
        y={cy + countFontSize * 0.6}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={labelFontSize}
        fontFamily="var(--font-dm-sans)"
        className="fill-sa-stone-400 dark:fill-sa-stone-500"
      >
        of {total}
      </text>
    </svg>
  )
}
