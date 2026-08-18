import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'Privacy Policy for Sunday Album, a product of ArjunTech LLC.',
}

export default function PrivacyPage() {
  return (
    <div className="py-20 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            Legal
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-6 leading-tight">
            Privacy Policy
          </h1>
          <p className="text-sm text-sa-stone-400 dark:text-sa-stone-500">
            Effective date: April 14, 2026 &mdash; ArjunTech LLC
          </p>
        </div>

        <div className="flex flex-col gap-10 text-sa-stone-600 dark:text-sa-stone-300 leading-relaxed">
          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Who we are
            </h2>
            <p className="text-sm">
              Sunday Album is a product of{' '}
              <a
                href="https://arjuntech.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
              >
                ArjunTech LLC
              </a>
              . References to
              &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo; in this policy refer to
              ArjunTech LLC. You can reach us at{' '}
              <a
                href="mailto:support@arjuntech.com"
                className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
              >
                support@arjuntech.com
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              What we collect
            </h2>
            <ul className="text-sm flex flex-col gap-2 list-disc list-inside">
              <li>
                <strong>Account information</strong> — your email address when you create an
                account.
              </li>
              <li>
                <strong>Photos you upload</strong> — images you submit for processing. These are
                used solely to run the Sunday Album pipeline and are not shared with third parties
                except as described below.
              </li>
              <li>
                <strong>Usage data</strong> — job history, processing results, and basic analytics
                (page views, feature usage) to improve the product.
              </li>
              <li>
                <strong>API keys you provide</strong> — if you choose to bring your own Anthropic
                or OpenAI keys, they are stored encrypted and used only to make API calls on your
                behalf.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              How we use it
            </h2>
            <ul className="text-sm flex flex-col gap-2 list-disc list-inside">
              <li>To run the photo processing pipeline and return results to you.</li>
              <li>To maintain your job history and library.</li>
              <li>To communicate with you about your account or service updates.</li>
              <li>To improve Sunday Album&apos;s accuracy and performance.</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Third-party services
            </h2>
            <p className="text-sm mb-3">
              Sunday Album uses AI services to process your photos:
            </p>
            <ul className="text-sm flex flex-col gap-2 list-disc list-inside">
              <li>
                <strong>Anthropic (Claude)</strong> — used for photo orientation detection.
                Images may be transmitted to Anthropic&apos;s API.
              </li>
              <li>
                <strong>OpenAI</strong> — used for glare removal via image inpainting. Images may
                be transmitted to OpenAI&apos;s API.
              </li>
            </ul>
            <p className="text-sm mt-3">
              Both services process data under their own privacy policies. If you use
              &ldquo;no-AI&rdquo; mode in the Mac app or disable AI steps, no images are sent to
              these services.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Data retention
            </h2>
            <p className="text-sm">
              Processed photos and job data are retained for as long as your account is active.
              You can delete your library at any time from the web app. Account deletion removes
              all associated data within 30 days.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Mac app
            </h2>
            <p className="text-sm">
              The Sunday Album Mac app processes photos locally on your device. No photos leave
              your computer unless you explicitly enable AI steps that require an API call.
              No account is required to use the Mac app.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Contact
            </h2>
            <p className="text-sm">
              Questions about this policy? Email us at{' '}
              <a
                href="mailto:support@arjuntech.com"
                className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
              >
                support@arjuntech.com
              </a>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
