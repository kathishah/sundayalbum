'use client'

/**
 * PhotoSplitView — interactive photo boundary editor.
 *
 * Displays the `04_photo_boundaries` debug image with an SVG overlay
 * containing four independently-draggable corner handles per detected region.
 * Corners move freely (not constrained to a rectangle), allowing the user to
 * match keystoned or rotated photo prints. Draw mode creates a new axis-aligned
 * rectangle which can then be fine-tuned corner by corner.
 *
 * On confirm, sends `corners` (4 × [x, y] in natural px) plus a derived `bbox`
 * as `forced_detections` to reprocess from `photo_detect`.
 */

import { useState, useRef, useEffect } from 'react'
import { reprocessJob } from '@/lib/api'
import type { Job } from '@/lib/types'

// ── Types ──────────────────────────────────────────────────────────────────────

type Pt = [number, number]  // [x, y] in natural image pixels

interface Region {
  id: number
  // Corners in clockwise order: [TL, TR, BR, BL]
  corners: [Pt, Pt, Pt, Pt]
}

type DragState =
  | { type: 'corner'; regionId: number; cornerIdx: number }
  | { type: 'draw'; startX: number; startY: number; curX: number; curY: number }
  | null

interface NaturalSize { w: number; h: number }

// ── Helpers ────────────────────────────────────────────────────────────────────

const COLOURS = ['#f59e0b', '#16a34a', '#3b82f6', '#dc2626', '#9333ea']
const colour = (idx: number) => COLOURS[idx % COLOURS.length]

/** Returns true if the 4-point quad is convex (all cross products same sign). */
function isConvex(pts: [Pt, Pt, Pt, Pt]): boolean {
  const n = pts.length
  let sign = 0
  for (let i = 0; i < n; i++) {
    const a = pts[i]
    const b = pts[(i + 1) % n]
    const c = pts[(i + 2) % n]
    const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
    if (Math.abs(cross) > 1e-9) {
      if (sign === 0) sign = cross > 0 ? 1 : -1
      else if ((cross > 0 ? 1 : -1) !== sign) return false
    }
  }
  return true
}

/** Convert a client-space point to SVG viewport coordinates. */
function clientToSvg(
  svg: SVGSVGElement,
  clientX: number,
  clientY: number,
): { x: number; y: number } {
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const inv = svg.getScreenCTM()?.inverse()
  if (!inv) return { x: clientX, y: clientY }
  const r = pt.matrixTransform(inv)
  return { x: r.x, y: r.y }
}

/** Derive axis-aligned bbox from free-form corners (for the API payload). */
function bboxFromCorners(corners: [Pt, Pt, Pt, Pt]): [number, number, number, number] {
  const xs = corners.map(c => c[0])
  const ys = corners.map(c => c[1])
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

// ── Component ──────────────────────────────────────────────────────────────────

interface PhotoSplitViewProps {
  job: Job
  onStarted: () => void
}

export default function PhotoSplitView({ job, onStarted }: PhotoSplitViewProps) {
  const imgRef = useRef<HTMLImageElement>(null)
  const svgRef  = useRef<SVGSVGElement>(null)

  const [size, setSize] = useState<NaturalSize | null>(null)
  const [regions, setRegions] = useState<Region[]>([])
  const [mode, setMode] = useState<'edit' | 'draw'>('edit')
  const [drag, setDrag] = useState<DragState>(null)
  const [nextId, setNextId] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const imageUrl      = job.debug_urls?.['04_photo_boundaries']
  const detectionsUrl = job.debug_urls?.['05_photo_detections_json']

  // Load detection JSON on mount — prefer corners, fall back to bbox
  useEffect(() => {
    if (!detectionsUrl) return
    fetch(detectionsUrl)
      .then((r) => r.json())
      .then((data: { detections?: Array<{ bbox: number[]; corners?: number[][] }> }) => {
        const list = (data.detections ?? []).map((d, i) => {
          let corners: [Pt, Pt, Pt, Pt]
          if (d.corners && d.corners.length === 4) {
            corners = d.corners.map(c => [c[0], c[1]] as Pt) as [Pt, Pt, Pt, Pt]
          } else {
            const [x1, y1, x2, y2] = d.bbox
            corners = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
          }
          return { id: i, corners }
        })
        setRegions(list)
        setNextId(list.length)
      })
      .catch(() => { /* no JSON yet — start empty */ })
  }, [detectionsUrl])

  // Capture natural image dimensions once loaded
  function handleImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const img = e.currentTarget
    setSize({ w: img.naturalWidth, h: img.naturalHeight })
  }

  // ── Pointer helpers ──────────────────────────────────────────────────────────

  function getSvgPt(e: React.MouseEvent) {
    if (!svgRef.current) return null
    return clientToSvg(svgRef.current, e.clientX, e.clientY)
  }

  // ── SVG-level events (draw mode + corner drag) ───────────────────────────────

  function handleSvgMouseDown(e: React.MouseEvent) {
    if (mode !== 'draw') return
    e.preventDefault()
    const pt = getSvgPt(e)
    if (!pt) return
    setDrag({ type: 'draw', startX: pt.x, startY: pt.y, curX: pt.x, curY: pt.y })
  }

  function handleSvgMouseMove(e: React.MouseEvent) {
    if (!drag) return
    const pt = getSvgPt(e)
    if (!pt) return

    if (drag.type === 'draw') {
      setDrag((d) => d && d.type === 'draw' ? { ...d, curX: pt.x, curY: pt.y } : d)
    } else if (drag.type === 'corner') {
      const { regionId, cornerIdx } = drag
      setRegions((rs) =>
        rs.map((r) => {
          if (r.id !== regionId) return r
          const newCorners = r.corners.map((c, i) =>
            i === cornerIdx ? [pt.x, pt.y] as Pt : c
          ) as [Pt, Pt, Pt, Pt]
          // Only apply if the result remains a convex quad
          return isConvex(newCorners) ? { ...r, corners: newCorners } : r
        }),
      )
    }
  }

  function handleSvgMouseUp(e: React.MouseEvent) {
    if (!drag) return
    if (drag.type === 'draw') {
      const pt = getSvgPt(e)
      if (pt) {
        const x1 = Math.min(drag.startX, pt.x)
        const y1 = Math.min(drag.startY, pt.y)
        const x2 = Math.max(drag.startX, pt.x)
        const y2 = Math.max(drag.startY, pt.y)
        if (x2 - x1 > 30 && y2 - y1 > 30) {
          const id = nextId
          const corners: [Pt, Pt, Pt, Pt] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
          setRegions((rs) => [...rs, { id, corners }])
          setNextId((n) => n + 1)
        }
      }
      setMode('edit')
    }
    setDrag(null)
  }

  // ── Corner handle events (edit mode only) ────────────────────────────────────

  function handleCornerDown(e: React.MouseEvent, regionId: number, cornerIdx: number) {
    e.preventDefault()
    e.stopPropagation()
    setDrag({ type: 'corner', regionId, cornerIdx })
  }

  // ── Delete ────────────────────────────────────────────────────────────────────

  function deleteRegion(id: number) {
    setRegions((rs) => rs.filter((r) => r.id !== id))
  }

  // ── Apply ─────────────────────────────────────────────────────────────────────

  async function handleApply() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      await reprocessJob(job.job_id, {
        from_step: 'photo_detect',
        config: {
          forced_detections: regions.map((r) => ({
            bbox: bboxFromCorners(r.corners),
            corners: r.corners,
            confidence: 1.0,
            region_type: 'photo',
            orientation: 'unknown',
          })),
        },
      })
      onStarted()
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start reprocessing')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Draw preview rect ─────────────────────────────────────────────────────────

  const preview = drag?.type === 'draw' ? {
    x: Math.min(drag.startX, drag.curX),
    y: Math.min(drag.startY, drag.curY),
    w: Math.abs(drag.curX - drag.startX),
    h: Math.abs(drag.curY - drag.startY),
  } : null

  // Handle size in natural image pixels — scales with the image
  const H = size ? Math.round(size.w * 0.012) : 14   // ~1.2% of image width

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="flex-1 flex flex-col overflow-hidden">

      {/* Canvas */}
      <div className="flex-1 flex justify-center items-start p-6 overflow-auto min-h-0 bg-sa-stone-900">
        {imageUrl ? (
          <div className="relative" style={{ display: 'inline-block', lineHeight: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={imageUrl}
              alt="Photo boundaries"
              className="max-w-full h-auto block rounded-xl shadow-lg"
              onLoad={handleImageLoad}
              draggable={false}
              style={{ userSelect: 'none' }}
            />

            {size && (
              <svg
                ref={svgRef}
                className="absolute inset-0 w-full h-full rounded-xl"
                viewBox={`0 0 ${size.w} ${size.h}`}
                preserveAspectRatio="none"
                style={{ cursor: mode === 'draw' ? 'crosshair' : 'default' }}
                onMouseDown={handleSvgMouseDown}
                onMouseMove={handleSvgMouseMove}
                onMouseUp={handleSvgMouseUp}
                onMouseLeave={() => { if (drag?.type === 'draw') { setDrag(null); setMode('edit') } }}
              >
                {/* Regions — pointer-events disabled during draw mode */}
                <g style={{ pointerEvents: mode === 'draw' ? 'none' : 'auto' }}>
                  {regions.map((r, idx) => {
                    const c = colour(idx)
                    const [tl, tr, br, bl] = r.corners
                    const polyPoints = r.corners.map(p => `${p[0]},${p[1]}`).join(' ')
                    return (
                      <g key={r.id}>
                        {/* Polygon border */}
                        <polygon
                          points={polyPoints}
                          fill="none" stroke={c} strokeWidth={3}
                          style={{ pointerEvents: 'none' }}
                        />
                        {/* Label — near TL corner */}
                        <text
                          x={tl[0] + H * 0.6} y={tl[1] + H * 1.8}
                          fontSize={H * 1.5} fontWeight="600"
                          fontFamily="var(--font-dm-sans)"
                          fill="white" stroke={c} strokeWidth={0.4}
                          style={{ pointerEvents: 'none' }}
                        >
                          Photo {idx + 1}
                        </text>
                        {/* Delete button — at TR corner */}
                        <g
                          style={{ cursor: 'pointer' }}
                          onClick={() => deleteRegion(r.id)}
                        >
                          <circle cx={tr[0]} cy={tr[1]} r={H} fill={c} />
                          <text
                            x={tr[0]} y={tr[1]} fontSize={H * 1.4}
                            textAnchor="middle" dominantBaseline="central"
                            fill="white" style={{ pointerEvents: 'none' }}
                          >×</text>
                        </g>
                        {/* 4 independent corner handles */}
                        {r.corners.map((corner, cornerIdx) => (
                          <circle
                            key={cornerIdx}
                            cx={corner[0]} cy={corner[1]} r={H}
                            fill={c} stroke="white" strokeWidth={2.5}
                            style={{
                              cursor: mode === 'edit' ? 'grab' : 'default',
                              filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.5))',
                            }}
                            onMouseDown={(e) => mode === 'edit' && handleCornerDown(e, r.id, cornerIdx)}
                          />
                        ))}
                      </g>
                    )
                  })}
                </g>

                {/* Draw preview */}
                {preview && preview.w > 5 && preview.h > 5 && (
                  <rect
                    x={preview.x} y={preview.y} width={preview.w} height={preview.h}
                    fill="rgba(245,158,11,0.12)" stroke="#f59e0b"
                    strokeWidth={3} strokeDasharray="12 6"
                    style={{ pointerEvents: 'none' }}
                  />
                )}
              </svg>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center w-full h-full text-sa-stone-500 text-sm">
            No photo boundaries image available
          </div>
        )}
      </div>

      {/* Footer controls */}
      <div className="flex-shrink-0 border-t border-sa-amber-200 dark:border-sa-stone-700 bg-sa-amber-50 dark:bg-sa-stone-900 px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Region count */}
          <span className="text-[12px] text-sa-stone-500 dark:text-sa-stone-400 flex-shrink-0">
            {regions.length} region{regions.length !== 1 ? 's' : ''}
          </span>

          {/* Toggle draw mode */}
          <button
            onClick={() => setMode((m) => m === 'draw' ? 'edit' : 'draw')}
            className={[
              'px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors duration-[200ms] flex-shrink-0',
              mode === 'draw'
                ? 'bg-sa-amber-500 text-white'
                : 'bg-white dark:bg-sa-stone-800 border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-600 dark:text-sa-stone-300 hover:bg-sa-stone-100 dark:hover:bg-sa-stone-700',
            ].join(' ')}
          >
            {mode === 'draw' ? '✕  Cancel Draw' : '+ Add Region'}
          </button>

          <p className="text-[11px] text-sa-stone-400 dark:text-sa-stone-500 flex-shrink-0">
            {mode === 'draw'
              ? 'Click and drag to draw a new region'
              : 'Drag any corner freely to adjust shape · × to delete'}
          </p>

          <div className="flex-1" />

          {submitError && (
            <span className="text-[11px] text-sa-error flex-shrink-0">{submitError}</span>
          )}

          <button
            onClick={handleApply}
            disabled={submitting || regions.length === 0}
            className="px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-sa-amber-500 hover:bg-sa-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-[200ms] flex-shrink-0"
          >
            {submitting ? 'Starting…' : 'Confirm & Re-run'}
          </button>
        </div>
      </div>
    </div>
  )
}
