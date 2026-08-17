import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'About',
  description:
    'Sunday Album is a tool for digitizing physical photo albums — built for families who want to preserve their memories.',
}

export default function AboutPage() {
  return (
    <div className="py-20 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            About
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-6 leading-tight">
            Why Sunday Album?
          </h1>
          <p className="text-lg text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
            Every family has a box of albums. Pages of yellowed, glare-covered prints slowly
            fading behind plastic sleeves. Sunday Album was built to fix that.
          </p>
        </div>

        {/* Story */}
        <div className="prose-like flex flex-col gap-6 text-sa-stone-600 dark:text-sa-stone-300 leading-relaxed mb-16">
          <p>
            The problem isn&apos;t just that old photos fade — it&apos;s that digitizing them is
            genuinely hard. A phone camera pointed at an album page produces one photo: a wide
            shot of 3 or 4 smaller photos, all behind plastic that throws glare everywhere,
            with yellowed colors and slightly crooked compositions.
          </p>
          <p>
            Existing tools solve part of it. Google PhotoScan reduces glare by combining
            multiple shots. Mobile scanning apps straighten documents. AI upscalers sharpen
            individual photos. But nobody built the full pipeline — take one photo of the album
            page, get clean individual digital photos out the other end.
          </p>
          <p>
            Sunday Album does exactly that. Page detection, perspective correction, multi-photo
            splitting, AI glare removal via OpenAI diffusion inpainting, color restoration, and
            auto-orientation — all in sequence, all automated. The same pipeline runs locally
            on the Mac app and in the cloud on the web app.
          </p>
          <p>
            It&apos;s not a subscription service. The Mac app is free and runs offline. The web
            app has a free tier and supports BYOK (bring your own API keys) for unlimited usage.
          </p>
        </div>

        {/* Pipeline callout */}
        <div className="p-6 rounded-2xl bg-sa-stone-50 dark:bg-sa-stone-900 border border-sa-stone-100 dark:border-sa-stone-800 mb-16">
          <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            The processing pipeline
          </h2>
          <ol className="flex flex-col gap-3 text-sm text-sa-stone-600 dark:text-sa-stone-300">
            {[
              ['Load', 'Decode HEIC, JPEG, PNG, or DNG — apply EXIF orientation'],
              ['Normalize', 'Resize to working resolution; generate thumbnail'],
              ['Page detect', 'GrabCut segmentation finds the album page boundary'],
              ['Perspective', 'Homographic warp to fronto-parallel view'],
              ['Photo detect', 'Contour detection finds individual photo boundaries'],
              ['Photo split', 'Extract each photo as its own crop'],
              ['AI orient', 'Claude Haiku detects rotation and gets a scene description'],
              ['Glare remove', 'OpenAI diffusion inpainting removes glare; OpenCV fallback available'],
              ['Color restore', 'White-balance → deyellow → adaptive brightness lift → sharpen'],
            ].map(([step, desc], i) => (
              <li key={step} className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-sa-amber-100 dark:bg-sa-amber-900/40 text-sa-amber-600 dark:text-sa-amber-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span>
                  <strong className="font-medium text-sa-stone-800 dark:text-sa-stone-200">{step}</strong>
                  {' — '}
                  {desc}
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* Tech stack note */}
        <div className="mb-16">
          <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            Open, inspectable stack
          </h2>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed mb-4">
            The processing engine is Python — OpenCV for computer vision, Pillow for image I/O,
            NumPy for array operations. The web app is Next.js on AWS (App Runner + Step Functions
            + Lambda). The Mac app is SwiftUI wrapping the same Python CLI.
          </p>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
            AI steps use Claude Haiku (Anthropic) for orientation and GPT-image-1.5 (OpenAI) for
            glare removal. Both steps degrade gracefully when keys are absent — pass-through for
            orientation, OpenCV fallback for glare.
          </p>
        </div>

        {/* ArjunTech */}
        <div className="mb-16">
          <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            Made by ArjunTech LLC
          </h2>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed mb-4">
            Sunday Album is a product of{' '}
            <a
              href="https://arjuntech.com"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-sa-stone-700 dark:text-sa-stone-200 hover:text-sa-amber-600 dark:hover:text-sa-amber-400 transition-colors duration-[200ms]"
            >
              ArjunTech LLC
            </a>{' '}
            —
            a small, independent software company building tools for everyday life. We make things
            we&apos;d use ourselves: practical, well-crafted software that solves real problems
            without unnecessary complexity.
          </p>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
            Built by Chintan &mdash;{' '}
            <a
              href="mailto:chintan@arjuntech.com"
              className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
            >
              chintan@arjuntech.com
            </a>
          </p>
        </div>

        {/* Other products */}
        <div className="mb-16">
          <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            Other ArjunTech products
          </h2>
          <a
            href="https://www.delicioustrades.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-col gap-1.5 p-5 rounded-2xl border border-sa-stone-100 dark:border-sa-stone-800 hover:border-sa-amber-300 dark:hover:border-sa-amber-700 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-900 transition-colors duration-[200ms] group"
          >
            <span className="font-display font-bold text-sa-stone-900 dark:text-sa-stone-50 group-hover:text-sa-amber-600 dark:group-hover:text-sa-amber-400 transition-colors duration-[200ms]">
              Delicious Trades
            </span>
            <span className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
              A learning platform for people who want to understand investing before putting real
              money on the line. Chart reading, options basics, paper trading — designed for
              beginners who want to go slow and get it right.
            </span>
            <span className="text-xs text-sa-amber-600 dark:text-sa-amber-400 mt-1">
              delicioustrades.com →
            </span>
          </a>
        </div>

        {/* Contact / CTA */}
        <div className="p-6 rounded-2xl bg-sa-amber-50 dark:bg-sa-amber-950/30 border border-sa-amber-200 dark:border-sa-amber-800">
          <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
            Questions or feedback?
          </h2>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed mb-4">
            Sunday Album is a small project. Feedback on what works and what doesn&apos;t is
            genuinely helpful.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/login"
              className="px-4 py-2.5 rounded-xl text-sm font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]"
            >
              Try it free
            </Link>
            <Link
              href="/download"
              className="px-4 py-2.5 rounded-xl text-sm font-medium border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-white dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]"
            >
              Download for Mac
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
