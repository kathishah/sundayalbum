import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Use',
  description: 'Terms of Use for Sunday Album, a product of ArjunTech LLC.',
}

export default function TermsPage() {
  return (
    <div className="py-20 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-12">
          <p className="text-sm font-semibold uppercase tracking-wider text-sa-amber-600 dark:text-sa-amber-400 mb-3">
            Legal
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-6 leading-tight">
            Terms of Use
          </h1>
          <p className="text-sm text-sa-stone-400 dark:text-sa-stone-500">
            Effective date: April 14, 2026 &mdash; ArjunTech LLC
          </p>
        </div>

        <div className="flex flex-col gap-10 text-sa-stone-600 dark:text-sa-stone-300 leading-relaxed">
          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Agreement
            </h2>
            <p className="text-sm">
              Sunday Album is operated by{' '}
              <a
                href="https://arjuntech.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
              >
                ArjunTech LLC
              </a>
              . By using the Sunday
              Album website, web app, or Mac app, you agree to these Terms of Use. If you do not
              agree, do not use the service.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Your content
            </h2>
            <p className="text-sm">
              You retain ownership of all photos you upload. By uploading photos, you grant
              ArjunTech LLC a limited license to process them for the purpose of providing the
              service. We do not claim any ownership over your photos and do not use them for
              advertising or training AI models.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Acceptable use
            </h2>
            <p className="text-sm mb-3">You agree not to:</p>
            <ul className="text-sm flex flex-col gap-2 list-disc list-inside">
              <li>Upload content that is illegal, harmful, or violates the rights of others.</li>
              <li>
                Use the service to circumvent rate limits or abuse the processing pipeline.
              </li>
              <li>
                Reverse-engineer, decompile, or attempt to extract the source code of the service.
              </li>
              <li>Use the service in any way that violates applicable laws or regulations.</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Free tier and paid plans
            </h2>
            <p className="text-sm">
              The Mac app is free to use with no account required. The web app offers a free tier
              with usage limits and paid plans for higher volume. Pricing details are on the{' '}
              <a
                href="/pricing"
                className="text-sa-amber-600 dark:text-sa-amber-400 hover:underline"
              >
                Pricing page
              </a>
              . ArjunTech LLC reserves the right to change pricing with reasonable notice.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Disclaimer of warranties
            </h2>
            <p className="text-sm">
              Sunday Album is provided &ldquo;as is&rdquo; without warranties of any kind. We do
              not guarantee that the service will be uninterrupted, error-free, or that processing
              results will meet your expectations. Use the service at your own discretion.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Limitation of liability
            </h2>
            <p className="text-sm">
              To the maximum extent permitted by law, ArjunTech LLC shall not be liable for any
              indirect, incidental, or consequential damages arising from your use of Sunday
              Album. Our total liability for any claim shall not exceed the amount you paid us in
              the 12 months preceding the claim.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Changes to these terms
            </h2>
            <p className="text-sm">
              We may update these Terms from time to time. Continued use of the service after
              changes are posted constitutes acceptance of the updated terms. Material changes
              will be communicated by email or an in-app notice.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-3">
              Contact
            </h2>
            <p className="text-sm">
              Questions about these terms? Email us at{' '}
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
