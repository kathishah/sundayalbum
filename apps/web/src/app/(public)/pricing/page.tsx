import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Pricing',
  description:
    'Sunday Album is free for Mac and free on the web (20 pages/day). Bring your own API keys to remove all limits.',
}

function Check() {
  return (
    <svg viewBox="0 0 16 16" className="w-4 h-4 text-sa-success flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const faqs = [
  {
    q: 'What counts as one "page"?',
    a: 'One uploaded image = one page. If your album page has 3 photos, that\'s 1 page and produces 3 output photos.',
  },
  {
    q: 'Why is it free?',
    a: 'The Mac app runs locally — there\'s no server cost. The web app uses AI APIs (Anthropic and OpenAI) that cost money per call, so the free tier is rate-limited to keep costs sustainable.',
  },
  {
    q: 'What does BYOK mean?',
    a: '"Bring Your Own Keys." You create accounts at anthropic.com and openai.com, generate API keys, and paste them into Sunday Album\'s Settings page. The AI calls then bill directly to your accounts instead of ours, so there\'s no reason for a daily limit.',
  },
  {
    q: 'Is there a paid plan?',
    a: 'Not currently. The free tier with BYOK covers all features. If demand grows, a paid tier may be added to cover API costs without requiring BYOK.',
  },
  {
    q: 'Are my API keys safe?',
    a: 'Yes. Your keys are stored encrypted in DynamoDB and are never logged or shared. You can delete them from Settings at any time.',
  },
  {
    q: 'Do I need an account for the Mac app?',
    a: 'No. The Mac app runs entirely locally. No account, no login, no internet connection required for processing. API keys (for AI orientation and glare removal) are stored in the macOS Keychain.',
  },
]

export default function PricingPage() {
  return (
    <div className="py-20 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            Pricing
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-4">
            Simple, honest pricing
          </h1>
          <p className="text-lg text-sa-stone-500 dark:text-sa-stone-400 max-w-xl mx-auto">
            Start free. No credit card. No subscription.
          </p>
        </div>

        {/* Pricing cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-20">
          {/* Mac App */}
          <div className="p-6 rounded-2xl border-2 border-sa-stone-200 dark:border-sa-stone-700 bg-white dark:bg-sa-stone-900 flex flex-col">
            <div className="mb-6">
              <span className="text-xs font-bold uppercase tracking-wider text-sa-stone-400 dark:text-sa-stone-500">Mac App</span>
              <div className="mt-3 flex items-end gap-2">
                <span className="font-display text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50">Free</span>
              </div>
              <p className="mt-2 text-sm text-sa-stone-500 dark:text-sa-stone-400">Unlimited, runs locally</p>
            </div>
            <ul className="flex flex-col gap-3 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-8 flex-1">
              {[
                'Full 10-step processing pipeline',
                'Runs entirely on your Mac',
                'No account, no login, no subscription',
                'API keys stored in macOS Keychain',
                'Drag-and-drop input',
                'Export to Photos.app or Finder',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/download"
              className="block w-full px-4 py-3 rounded-xl text-sm font-medium text-center border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]"
            >
              Download for Mac
            </Link>
          </div>

          {/* Web App — Free tier */}
          <div className="p-6 rounded-2xl border-2 border-sa-amber-400 dark:border-sa-amber-600 bg-sa-amber-50 dark:bg-sa-amber-950/30 flex flex-col relative overflow-hidden">
            <div className="absolute top-4 right-4 px-2.5 py-1 rounded-full bg-sa-amber-500 text-white text-xs font-medium">
              Most popular
            </div>
            <div className="mb-6">
              <span className="text-xs font-bold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400">Web App</span>
              <div className="mt-3 flex items-end gap-2">
                <span className="font-display text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50">Free</span>
              </div>
              <p className="mt-2 text-sm text-sa-stone-500 dark:text-sa-stone-400">20 pages / day</p>
            </div>
            <ul className="flex flex-col gap-3 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-8 flex-1">
              {[
                '20 album pages per day (resets midnight UTC)',
                'Email-based login — no password needed',
                '7-day sessions',
                'Live progress via WebSocket',
                'Download individual or all photos',
                'Works on any device, any browser',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/login"
              className="block w-full px-4 py-3 rounded-xl text-sm font-medium text-center bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]"
            >
              Get started free
            </Link>
          </div>

          {/* Web App — BYOK */}
          <div className="p-6 rounded-2xl border-2 border-sa-stone-200 dark:border-sa-stone-700 bg-white dark:bg-sa-stone-900 flex flex-col">
            <div className="mb-6">
              <span className="text-xs font-bold uppercase tracking-wider text-sa-stone-400 dark:text-sa-stone-500">Web App + BYOK</span>
              <div className="mt-3 flex items-end gap-2">
                <span className="font-display text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50">Free</span>
              </div>
              <p className="mt-2 text-sm text-sa-stone-500 dark:text-sa-stone-400">Unlimited, pay API costs directly</p>
            </div>
            <ul className="flex flex-col gap-3 text-sm text-sa-stone-600 dark:text-sa-stone-300 mb-8 flex-1">
              {[
                'Everything in Web App free tier',
                'No daily page limit',
                'Supply your own Anthropic + OpenAI keys',
                'Keys stored encrypted in DynamoDB',
                'You pay API providers directly',
                'Never logged or shared',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/settings"
              className="block w-full px-4 py-3 rounded-xl text-sm font-medium text-center border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-200 hover:bg-sa-stone-50 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]"
            >
              Add your keys in Settings
            </Link>
          </div>
        </div>

        {/* FAQ */}
        <div className="max-w-2xl mx-auto">
          <h2 className="font-display text-2xl md:text-3xl font-bold text-sa-stone-900 dark:text-sa-stone-50 text-center mb-10">
            Frequently asked questions
          </h2>
          <div className="flex flex-col divide-y divide-sa-stone-100 dark:divide-sa-stone-800">
            {faqs.map((faq) => (
              <div key={faq.q} className="py-5">
                <h3 className="font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-2">{faq.q}</h3>
                <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 leading-relaxed">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
