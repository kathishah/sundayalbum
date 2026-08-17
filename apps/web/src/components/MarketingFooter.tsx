import Link from 'next/link'

const footerLinks = [
  {
    heading: 'Product',
    links: [
      { href: '/pipeline', label: 'Pipeline' },
      { href: '/pricing', label: 'Pricing' },
      { href: '/download', label: 'Download for Mac' },
      { href: '/login', label: 'Web App' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { href: '/about', label: 'About' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { href: '/privacy', label: 'Privacy Policy' },
      { href: '/terms', label: 'Terms of Use' },
    ],
  },
]

export default function MarketingFooter() {
  return (
    <footer className="border-t border-sa-stone-200 dark:border-sa-stone-800 bg-white dark:bg-sa-stone-950">
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-10">
          {/* Brand */}
          <div className="col-span-2">
            <Link
              href="/"
              className="font-display text-lg font-bold text-sa-stone-900 dark:text-sa-stone-50 hover:text-sa-amber-600 dark:hover:text-sa-amber-400 transition-colors duration-[200ms]"
            >
              Sunday Album
            </Link>
            <p className="mt-3 text-sm text-sa-stone-500 dark:text-sa-stone-400 max-w-xs leading-relaxed">
              Digitize your physical photo albums. AI-powered page scanning, glare removal, and color restoration.
            </p>
          </div>

          {footerLinks.map((group) => (
            <div key={group.heading}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-sa-stone-400 dark:text-sa-stone-500 mb-4">
                {group.heading}
              </h3>
              <ul className="space-y-3">
                {group.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-sa-stone-600 dark:text-sa-stone-400 hover:text-sa-stone-900 dark:hover:text-sa-stone-50 transition-colors duration-[200ms]"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-sa-stone-100 dark:border-sa-stone-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-sa-stone-400 dark:text-sa-stone-600">
            © {new Date().getFullYear()} ArjunTech LLC. All rights reserved.
          </p>
          <p className="text-xs text-sa-stone-400 dark:text-sa-stone-600">
            Sunday Album is a product of{' '}
            <a
              href="https://arjuntech.com"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-sa-stone-900 dark:hover:text-sa-stone-400 transition-colors duration-[200ms]"
            >
              ArjunTech LLC
            </a>
            .
          </p>
        </div>
      </div>
    </footer>
  )
}
