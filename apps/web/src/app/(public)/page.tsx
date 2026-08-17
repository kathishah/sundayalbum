'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import { isAuthenticated } from '@/lib/auth'
import BeforeAfterSlider from '@/components/BeforeAfterSlider'

// ── Animation helpers ─────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
}

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.1 } } }

// ── Hero: auto-cycling cave animation ─────────────────────────────────────────

const HERO_STAGES = [
  { src: '/demo/cave-stage-0.jpg', label: 'Raw scan' },
  { src: '/demo/cave-stage-1.jpg', label: 'Glare removed' },
  { src: '/demo/cave-stage-2.jpg', label: 'Color restored' },
]

function HeroCycler() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setStage((s) => (s + 1) % HERO_STAGES.length), 2800)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="relative w-full aspect-[3/2] rounded-2xl overflow-hidden shadow-2xl border border-sa-stone-200/60 dark:border-sa-stone-700/60">
      <AnimatePresence mode="sync">
        <motion.div
          key={stage}
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.9, ease: 'easeInOut' }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={HERO_STAGES[stage].src}
            alt={HERO_STAGES[stage].label}
            className="w-full h-full object-cover"
            draggable={false}
          />
        </motion.div>
      </AnimatePresence>

      {/* Stage label pill */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5 items-center bg-black/50 backdrop-blur-sm px-3 py-1.5 rounded-full">
        {HERO_STAGES.map((s, i) => (
          <button
            key={s.label}
            onClick={() => setStage(i)}
            className={`text-xs font-medium transition-colors duration-[200ms] ${
              i === stage ? 'text-white' : 'text-white/50 hover:text-white/80'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Features ─────────────────────────────────────────────────────────────────

interface Feature {
  icon: React.ReactNode
  title: string
  description: string
}

function FeatureIcon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 20 20" className="w-4 h-4 flex-shrink-0 text-sa-amber-500 dark:text-sa-amber-400" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}

const leftFeatures: Feature[] = [
  {
    icon: <FeatureIcon d="M4 4h5v5H4zM4 11h5v5H4zM11 4h5v5h-5zM11 11h5v5h-5z" />,
    title: 'Multi-photo detection',
    description: 'Finds every photo on the album page — 1, 2, 3 or more.',
  },
  {
    icon: <FeatureIcon d="M10 2v4M10 14v4M2 10h4M14 10h4M3.9 3.9l2.8 2.8M13.3 13.3l2.8 2.8M3.9 16.1l2.8-2.8M13.3 6.7l2.8-2.8" />,
    title: 'AI glare removal',
    description: 'Diffusion-based inpainting removes sleeve and print glare.',
  },
  {
    icon: <FeatureIcon d="M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16M6.5 10a3.5 3.5 0 0 1 7 0" />,
    title: 'Color restoration',
    description: 'Reverses yellowing and fading, restoring natural tones.',
  },
]

const rightFeatures: Feature[] = [
  {
    icon: <FeatureIcon d="M10 2v4M10 14v4M4.9 4.9l2.8 2.8M12.3 12.3l2.8 2.8M2 10h4M14 10h4" />,
    title: 'Auto-orientation',
    description: 'Detects and corrects rotation using AI scene understanding.',
  },
  {
    icon: <FeatureIcon d="M3 7l3-3h8l3 3v8l-3 3H6l-3-3V7zM3 7h14M14 3v4" />,
    title: 'Perspective correction',
    description: 'Straightens keystoned shots taken at an angle.',
  },
  {
    icon: <FeatureIcon d="M2 4h7v12H2zM11 4h7v7h-7zM11 13h7" />,
    title: 'Web + Mac',
    description: 'Process in the browser or use the free native Mac app.',
  },
]

function FeatureList({ features, align }: { features: Feature[]; align: 'left' | 'right' }) {
  return (
    <div className={`flex flex-col gap-6 ${align === 'right' ? 'md:text-right' : ''}`}>
      {features.map((f) => (
        <div key={f.title} className={`flex gap-3 ${align === 'right' ? 'md:flex-row-reverse' : ''}`}>
          <div className="mt-0.5">{f.icon}</div>
          <div>
            <p className="text-sm font-semibold text-sa-stone-800 dark:text-sa-stone-100 mb-0.5">{f.title}</p>
            <p className="text-xs text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">{f.description}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Pair B: stacked after slot ────────────────────────────────────────────────

function PairBAfterSlot() {
  return (
    <div className="w-full h-full flex flex-col gap-0.5 bg-sa-stone-100 dark:bg-sa-stone-800">
      {[1, 2, 3].map((n) => (
        <div key={n} className="flex-1 min-h-0 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/demo/pair-b-after-${n}.jpg`}
            alt={`Extracted photo ${n}`}
            className="w-full h-full object-cover"
            draggable={false}
          />
        </div>
      ))}
    </div>
  )
}

// ── Pipeline steps (for the "Under the hood" section) ────────────────────────

const pipelineSteps = [
  { id: 'snap',  label: 'Snap',        detail: 'Take a photo of your album page with any phone camera.' },
  { id: 'page',  label: 'Page Detect', detail: 'Finds and perspective-corrects the album page boundary.' },
  { id: 'split', label: 'Split Photos',detail: 'Detects each individual photo on the page and extracts it.' },
  { id: 'glare', label: 'Remove Glare',detail: 'AI inpainting erases sleeve and print glare completely.' },
  { id: 'color', label: 'Restore Color',detail: 'Reverses yellowing, lifts shadows, and sharpens detail.' },
  { id: 'done',  label: 'Done',        detail: 'Download your clean, individually restored digital photos.' },
]

// ── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [authed, setAuthed] = useState(false)
  const [activeStep, setActiveStep] = useState<string | null>(null)
  // Measure Pair A's rendered width so Pair B can use it as its height
  const pairARef = useRef<HTMLDivElement>(null)
  const [pairBHeight, setPairBHeight] = useState(0)

  useEffect(() => {
    setAuthed(isAuthenticated())
  }, [])

  useEffect(() => {
    const el = pairARef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      setPairBHeight(entry.contentRect.width)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const primaryCta = authed
    ? { href: '/library', label: 'Go to Library' }
    : { href: '/login', label: 'Try it free' }

  return (
    <div className="overflow-x-hidden">

      {/* ── 1. Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative py-14 md:py-20 px-4 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-sa-amber-50 to-white dark:from-sa-stone-900 dark:to-sa-stone-950 pointer-events-none" />

        <div className="relative max-w-6xl mx-auto grid md:grid-cols-2 gap-10 items-center">
          {/* Text */}
          <motion.div initial="hidden" animate="show" variants={stagger} className="flex flex-col gap-6">
            <motion.div variants={fadeUp}>
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sa-amber-100 dark:bg-sa-amber-900/40 text-sa-amber-700 dark:text-sa-amber-300 text-xs font-medium border border-sa-amber-200 dark:border-sa-amber-800">
                <span className="w-1.5 h-1.5 rounded-full bg-sa-amber-500 animate-pulse" />
                Free for Mac · Free tier for web
              </span>
            </motion.div>

            <motion.h1 variants={fadeUp} className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 leading-[1.1] tracking-tight">
              Your print photos,{' '}
              <span className="text-sa-amber-600 dark:text-sa-amber-400">beautifully</span>{' '}
              digitized.
            </motion.h1>

            <motion.p variants={fadeUp} className="text-lg text-sa-stone-600 dark:text-sa-stone-300 leading-relaxed">
              Snap a photo of a single print or an entire album page. Sunday Album finds
              every photo, removes glare, restores faded colors, and delivers clean digital
              photos — automatically.
            </motion.p>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
              <Link href={primaryCta.href} className="px-6 py-3 rounded-xl text-base font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms] shadow-sm">
                {primaryCta.label}
              </Link>
              <Link href="/download" className="px-6 py-3 rounded-xl text-base font-medium border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]">
                Download for Mac
              </Link>
            </motion.div>
          </motion.div>

          {/* Auto-cycling image */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <HeroCycler />
          </motion.div>
        </div>
      </section>

      {/* ── 2. How It Works (cards, no heading) ─────────────────────────────── */}
      <section className="py-16 px-4 bg-white dark:bg-sa-stone-950">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
            className="grid md:grid-cols-3 gap-6"
          >
            {[
              {
                step: '01', title: 'Snap',
                desc: 'Take a photo of your album page with any phone. One shot captures 1, 2, 3 or more prints at once.',
                icon: <svg viewBox="0 0 40 40" className="w-9 h-9" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="6" y="11" width="28" height="22" rx="3" /><circle cx="20" cy="22" r="6" /><circle cx="20" cy="22" r="3" fill="currentColor" stroke="none" /><path d="M15 11V9h10v2" strokeLinecap="round" /></svg>,
              },
              {
                step: '02', title: 'Process',
                desc: 'Sunday Album detects every photo on the page, removes glare, restores colors, and corrects orientation.',
                icon: <svg viewBox="0 0 40 40" className="w-9 h-9" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="20" cy="20" r="13" /><path d="M20 10v4M20 26v4M10 20h4M26 20h4" strokeLinecap="round" /><circle cx="20" cy="20" r="4" /></svg>,
              },
              {
                step: '03', title: 'Download',
                desc: 'Get clean, individually restored digital photos ready to share, print, or archive forever.',
                icon: <svg viewBox="0 0 40 40" className="w-9 h-9" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 8v16M13 18l7 7 7-7" strokeLinecap="round" strokeLinejoin="round" /><path d="M8 30h24" strokeLinecap="round" /></svg>,
              },
            ].map((item) => (
              <motion.div
                key={item.step}
                variants={fadeUp}
                className="flex flex-col items-center text-center p-6 rounded-2xl bg-sa-stone-50 dark:bg-sa-stone-900 border border-sa-stone-100 dark:border-sa-stone-800"
              >
                <div className="mb-4 p-3 rounded-xl bg-sa-amber-50 dark:bg-sa-amber-900/30 text-sa-amber-600 dark:text-sa-amber-400">
                  {item.icon}
                </div>
                <span className="text-xs font-bold text-sa-amber-500 tracking-widest mb-2">{item.step}</span>
                <h3 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">{item.title}</h3>
                <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">{item.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── 3. See the results — features flanking sliders ──────────────────── */}
      <section className="py-16 px-4 bg-sa-stone-50 dark:bg-sa-stone-900">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-80px' }}
            variants={stagger}
            className="text-center mb-12"
          >
            <motion.p variants={fadeUp} className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
              See the results
            </motion.p>
            <motion.h2 variants={fadeUp} className="font-display text-3xl md:text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50">
              Real pipeline output
            </motion.h2>
            <motion.p variants={fadeUp} className="mt-3 text-sa-stone-500 dark:text-sa-stone-400 max-w-xl mx-auto">
              Drag the slider to compare. Every photo below is actual output from the Sunday Album pipeline.
            </motion.p>
          </motion.div>

          {/* 3-column: features | sliders | features */}
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
            className="grid grid-cols-1 md:grid-cols-[220px_1fr_220px] gap-8 items-start"
          >
            {/* Left features */}
            <motion.div variants={fadeUp} className="flex flex-col justify-center md:pt-8">
              <FeatureList features={leftFeatures} align="left" />
            </motion.div>

            {/* Center: both sliders */}
            <motion.div variants={fadeUp} className="flex flex-col gap-6">
              {/* Pair A: single print quality — landscape, full column width × h-72 */}
              <div ref={pairARef} className="flex flex-col gap-2">
                <BeforeAfterSlider
                  beforeSrc="/demo/pair-a-before.jpg"
                  afterSrc="/demo/pair-a-after.jpg"
                  beforeLabel="Raw extract"
                  afterLabel="Restored"
                  beforeAlt="Photo before processing — yellowed, with glare"
                  afterAlt="Photo after processing — glare removed, colors restored"
                  initialPosition={0}
                  className="h-72 w-full"
                />
                <p className="text-xs text-center text-sa-stone-400 dark:text-sa-stone-500">
                  Single print — drag right to reveal restored
                </p>
              </div>

              {/* Pair B: album page → 3 photos
                  Width  = Pair A's height (h-72 = 18rem = 288px)
                  Height = Pair A's rendered width (measured via ResizeObserver) */}
              <div className="flex flex-col gap-2 items-center">
                <BeforeAfterSlider
                  beforeSrc="/demo/pair-b-before.jpg"
                  afterSlot={<PairBAfterSlot />}
                  beforeLabel="Album page"
                  afterLabel="3 photos"
                  beforeAlt="Album page with three prints"
                  afterAlt="Three individually extracted and restored photos"
                  initialPosition={0}
                  className="w-72 flex-shrink-0"
                  style={pairBHeight ? { height: pairBHeight } : { aspectRatio: '3/4' }}
                />
                <p className="text-xs text-center text-sa-stone-400 dark:text-sa-stone-500">
                  Album page — drag right to see 3 individual photos
                </p>
              </div>
            </motion.div>

            {/* Right features */}
            <motion.div variants={fadeUp} className="flex flex-col justify-center md:pt-8">
              <FeatureList features={rightFeatures} align="right" />
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ── 4. Under the hood — pipeline viz + link ──────────────────────────── */}
      <section className="py-16 px-4 bg-white dark:bg-sa-stone-950">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-80px' }}
            variants={stagger}
            className="text-center mb-10"
          >
            <motion.p variants={fadeUp} className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
              Under the hood
            </motion.p>
            <motion.h2 variants={fadeUp} className="font-display text-3xl md:text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50">
              A full processing pipeline
            </motion.h2>
            <motion.p variants={fadeUp} className="mt-3 text-sa-stone-500 dark:text-sa-stone-400">
              Hover any step to learn what it does.{' '}
              <Link href="/pipeline" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline">
                See the full pipeline →
              </Link>
            </motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
            className="flex flex-wrap justify-center gap-3 md:gap-0 items-center mb-8"
          >
            {pipelineSteps.map((step, i) => (
              <motion.div key={step.id} variants={fadeUp} className="flex items-center">
                <div
                  className="relative group"
                  onMouseEnter={() => setActiveStep(step.id)}
                  onMouseLeave={() => setActiveStep(null)}
                  onFocus={() => setActiveStep(step.id)}
                  onBlur={() => setActiveStep(null)}
                  tabIndex={0}
                >
                  <div className={`
                    px-4 py-2.5 rounded-xl text-sm font-medium cursor-default
                    transition-all duration-[200ms]
                    ${activeStep === step.id
                      ? 'bg-sa-amber-500 text-white shadow-md scale-105'
                      : 'bg-sa-stone-50 dark:bg-sa-stone-800 text-sa-stone-700 dark:text-sa-stone-200 border border-sa-stone-200 dark:border-sa-stone-700 hover:border-sa-amber-300 dark:hover:border-sa-amber-700'
                    }
                  `}>
                    {step.label}
                  </div>
                  <div className={`
                    absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 p-3
                    rounded-xl bg-sa-stone-900 dark:bg-sa-stone-50 text-sa-stone-50 dark:text-sa-stone-900
                    text-xs leading-relaxed shadow-lg z-10
                    transition-all duration-[200ms]
                    ${activeStep === step.id ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1 pointer-events-none'}
                  `}>
                    {step.detail}
                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-sa-stone-900 dark:border-t-sa-stone-50" />
                  </div>
                </div>
                {i < pipelineSteps.length - 1 && (
                  <svg viewBox="0 0 24 24" className="w-5 h-5 text-sa-stone-300 dark:text-sa-stone-600 mx-1 flex-shrink-0 hidden md:block" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M14 7l5 5-5 5" />
                  </svg>
                )}
              </motion.div>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <Link
              href="/pipeline"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]"
            >
              Explore the full pipeline
              <svg viewBox="0 0 16 16" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ── 5. Pricing Summary ───────────────────────────────────────────────── */}
      <section className="py-16 px-4 bg-sa-stone-50 dark:bg-sa-stone-900">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-80px' }}
            variants={stagger}
            className="text-center mb-12"
          >
            <motion.p variants={fadeUp} className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
              Pricing
            </motion.p>
            <motion.h2 variants={fadeUp} className="font-display text-3xl md:text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50">
              Simple, honest pricing
            </motion.h2>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            variants={stagger}
            className="grid sm:grid-cols-2 gap-6"
          >
            <motion.div variants={fadeUp} className="p-6 rounded-2xl border-2 border-sa-stone-200 dark:border-sa-stone-700 bg-white dark:bg-sa-stone-900 flex flex-col">
              <div className="mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-sa-stone-400 dark:text-sa-stone-500">Mac App</span>
                <div className="mt-2 flex items-end gap-1">
                  <span className="font-display text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50">Free</span>
                  <span className="text-sa-stone-400 mb-1">forever</span>
                </div>
              </div>
              <ul className="flex flex-col gap-2 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-6 flex-1">
                {['Full 10-step pipeline', 'Runs locally on your Mac', 'No account, no login', 'No internet required'].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <svg viewBox="0 0 16 16" className="w-4 h-4 text-sa-success flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link href="/download" className="block w-full px-4 py-2.5 rounded-xl text-sm font-medium text-center border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]">
                Download for Mac
              </Link>
            </motion.div>

            <motion.div variants={fadeUp} className="p-6 rounded-2xl border-2 border-sa-amber-400 dark:border-sa-amber-600 bg-sa-amber-50 dark:bg-sa-amber-950/30 flex flex-col relative overflow-hidden">
              <div className="absolute top-4 right-4 px-2 py-0.5 rounded-full bg-sa-amber-500 text-white text-xs font-medium">Popular</div>
              <div className="mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400">Web App</span>
                <div className="mt-2 flex items-end gap-1">
                  <span className="font-display text-4xl font-bold text-sa-stone-900 dark:text-sa-stone-50">Free</span>
                  <span className="text-sa-stone-400 mb-1">20 pages/day</span>
                </div>
              </div>
              <ul className="flex flex-col gap-2 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-6 flex-1">
                {['Email login, no password', 'Live processing progress', 'Unlimited with your own API keys', 'Download photos instantly'].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <svg viewBox="0 0 16 16" className="w-4 h-4 text-sa-success flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link href="/login" className="block w-full px-4 py-2.5 rounded-xl text-sm font-medium text-center bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]">
                Get started free
              </Link>
            </motion.div>
          </motion.div>

          <motion.p initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center text-sm text-sa-stone-400 dark:text-sa-stone-500 mt-5">
            <Link href="/pricing" className="hover:text-sa-amber-600 dark:hover:text-sa-amber-400 transition-colors duration-[200ms]">
              See full pricing details →
            </Link>
          </motion.p>
        </div>
      </section>

      {/* ── 6. Final CTA ─────────────────────────────────────────────────────── */}
      <section className="py-20 px-4 bg-gradient-to-b from-sa-amber-50 to-sa-amber-100 dark:from-sa-stone-900 dark:to-sa-stone-800 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-sa-amber-200/40 via-transparent to-transparent dark:from-sa-amber-900/20 pointer-events-none" />
        <div className="relative max-w-2xl mx-auto text-center">
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: '-80px' }} variants={stagger} className="flex flex-col items-center gap-6">
            <motion.h2 variants={fadeUp} className="font-display text-3xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 leading-tight">
              Give your memories a second life.
            </motion.h2>
            <motion.p variants={fadeUp} className="text-lg text-sa-stone-600 dark:text-sa-stone-300 max-w-lg leading-relaxed">
              Your family's best moments deserve better than a faded album. Start digitizing today.
            </motion.p>
            <motion.div variants={fadeUp} className="flex flex-wrap justify-center gap-3">
              <Link href={primaryCta.href} className="px-7 py-3.5 rounded-xl text-base font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms] shadow-sm">
                {primaryCta.label}
              </Link>
              <Link href="/download" className="px-7 py-3.5 rounded-xl text-base font-medium border border-sa-stone-300 dark:border-sa-stone-600 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-white/60 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]">
                Download for Mac
              </Link>
            </motion.div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
