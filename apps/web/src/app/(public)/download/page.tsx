import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Download',
  description:
    'Download Sunday Album for Mac — free, unlimited, runs locally. Or use the web app in your browser with no download required.',
}

export default function DownloadPage() {
  return (
    <div className="py-20 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            Download
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            Get Sunday Album
          </h1>
          <p className="text-lg text-sa-stone-500 dark:text-sa-stone-400 max-w-xl mx-auto">
            Choose the version that works for you — a native Mac app or the web app in your browser.
          </p>
        </div>

        {/* Download options */}
        <div className="grid md:grid-cols-2 gap-8 mb-20">
          {/* Mac App */}
          <div className="p-8 rounded-2xl border-2 border-sa-stone-200 dark:border-sa-stone-700 bg-white dark:bg-sa-stone-900 flex flex-col">
            {/* macOS icon */}
            <div className="mb-6 p-4 bg-sa-stone-50 dark:bg-sa-stone-800 rounded-2xl w-fit">
              <svg viewBox="0 0 48 48" className="w-12 h-12 text-sa-stone-700 dark:text-sa-stone-200" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="6" y="8" width="36" height="26" rx="3" />
                <path d="M2 34h44" strokeLinecap="round" />
                <path d="M18 34l-2 6h16l-2-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <h2 className="font-display text-2xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
              Sunday Album for Mac
            </h2>
            <p className="text-sa-stone-500 dark:text-sa-stone-400 text-sm mb-6 leading-relaxed">
              Native macOS app. Full processing pipeline runs locally on your Mac — no internet connection required for processing. Free, with no account or subscription needed.
            </p>

            <ul className="flex flex-col gap-2.5 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-8 flex-1">
              {[
                'Apple Silicon (M1 / M2 / M3 / M4)',
                'macOS 13 Ventura or later',
                'Drag-and-drop or file picker input',
                'Export to Photos.app or Finder',
                'API keys stored in macOS Keychain',
                'Free — no account, no subscription',
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <svg viewBox="0 0 16 16" className="w-4 h-4 text-sa-success flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>

            {/* CTA — placeholder until real download link exists */}
            <div className="flex flex-col gap-3">
              <a
                href="#"
                className="block w-full px-4 py-3 rounded-xl text-sm font-medium text-center bg-sa-stone-900 dark:bg-sa-stone-50 text-white dark:text-sa-stone-900 hover:bg-sa-stone-700 dark:hover:bg-sa-stone-200 transition-colors duration-[200ms]"
              >
                {/* Apple-style download icon */}
                <span className="flex items-center justify-center gap-2">
                  <svg viewBox="0 0 20 20" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M10 3v10M6 10l4 5 4-5" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M3 16h14" strokeLinecap="round" />
                  </svg>
                  Download for Mac — Free
                </span>
              </a>
              <p className="text-xs text-center text-sa-stone-400 dark:text-sa-stone-500">
                Requires macOS 13+, Apple Silicon
              </p>
            </div>
          </div>

          {/* Web App */}
          <div className="p-8 rounded-2xl border-2 border-sa-amber-300 dark:border-sa-amber-700 bg-sa-amber-50/50 dark:bg-sa-amber-950/20 flex flex-col">
            {/* Browser icon */}
            <div className="mb-6 p-4 bg-sa-amber-100 dark:bg-sa-amber-900/40 rounded-2xl w-fit">
              <svg viewBox="0 0 48 48" className="w-12 h-12 text-sa-amber-700 dark:text-sa-amber-300" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="4" y="8" width="40" height="32" rx="3" />
                <path d="M4 16h40" />
                <circle cx="11" cy="12" r="1.5" fill="currentColor" stroke="none" />
                <circle cx="18" cy="12" r="1.5" fill="currentColor" stroke="none" />
                <circle cx="25" cy="12" r="1.5" fill="currentColor" stroke="none" />
              </svg>
            </div>

            <h2 className="font-display text-2xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
              Sunday Album Web App
            </h2>
            <p className="text-sa-stone-500 dark:text-sa-stone-400 text-sm mb-6 leading-relaxed">
              No download needed. Works in any modern browser on any device. Email login, live processing progress, download photos instantly. Free with 20 pages per day.
            </p>

            <ul className="flex flex-col gap-2.5 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-8 flex-1">
              {[
                'Works on Mac, Windows, Linux, iOS, Android',
                'Any modern browser',
                'No download, no install',
                'Email login — no password needed',
                'Live processing updates via WebSocket',
                '20 pages/day free · Unlimited with BYOK',
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <svg viewBox="0 0 16 16" className="w-4 h-4 text-sa-success flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>

            <div className="flex flex-col gap-3">
              <Link
                href="/login"
                className="block w-full px-4 py-3 rounded-xl text-sm font-medium text-center bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]"
              >
                Open Web App →
              </Link>
              <p className="text-xs text-center text-sa-stone-400 dark:text-sa-stone-500">
                No download required · Works in any browser
              </p>
            </div>
          </div>
        </div>

        {/* Comparison note */}
        <div className="max-w-2xl mx-auto text-center p-6 rounded-2xl bg-sa-stone-50 dark:bg-sa-stone-900 border border-sa-stone-100 dark:border-sa-stone-800">
          <h3 className="font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-2">
            Which should I choose?
          </h3>
          <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">
            Both run the same processing pipeline and produce identical output quality. The Mac app
            is great if you have lots of albums to digitize and want to process everything offline.
            The web app is perfect if you want to try it first or are on a non-Mac device.
          </p>
          <p className="mt-3 text-sm">
            <Link href="/pricing" className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline">
              See full pricing details →
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
