'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'
import { isAuthenticated } from '@/lib/auth'

const navLinks = [
  { href: '/pipeline', label: 'Pipeline' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/download', label: 'Download' },
  { href: '/about', label: 'About' },
]

export default function MarketingNav() {
  const pathname = usePathname()
  const [authed, setAuthed] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setAuthed(isAuthenticated())
  }, [])

  return (
    <header className="sticky top-0 z-40 border-b border-sa-stone-200/80 dark:border-sa-stone-800/80 bg-white/90 dark:bg-sa-stone-950/90 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link
          href="/"
          className="font-display text-xl font-bold text-sa-stone-900 dark:text-sa-stone-50 hover:text-sa-amber-600 dark:hover:text-sa-amber-400 transition-colors duration-[200ms]"
        >
          Sunday Album
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={clsx(
                'text-sm transition-colors duration-[200ms]',
                pathname === link.href
                  ? 'text-sa-stone-900 dark:text-sa-stone-50 font-medium'
                  : 'text-sa-stone-600 dark:text-sa-stone-400 hover:text-sa-stone-900 dark:hover:text-sa-stone-50',
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Desktop CTAs */}
        <div className="hidden md:flex items-center gap-3">
          {authed ? (
            <Link
              href="/library"
              className="px-4 py-2 rounded-xl text-sm font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]"
            >
              Go to Library
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="text-sm text-sa-stone-600 dark:text-sa-stone-400 hover:text-sa-stone-900 dark:hover:text-sa-stone-50 transition-colors duration-[200ms]"
              >
                Sign in
              </Link>
              <Link
                href="/login"
                className="px-4 py-2 rounded-xl text-sm font-medium bg-sa-amber-500 hover:bg-sa-amber-600 text-white transition-colors duration-[200ms]"
              >
                Try it free
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu button */}
        <button
          className="md:hidden p-2 rounded-lg text-sa-stone-600 dark:text-sa-stone-400 hover:bg-sa-stone-100 dark:hover:bg-sa-stone-800 transition-colors duration-[200ms]"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Toggle menu"
          aria-expanded={menuOpen}
        >
          {menuOpen ? (
            <svg viewBox="0 0 20 20" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M4 4l12 12M16 4L4 16" />
            </svg>
          ) : (
            <svg viewBox="0 0 20 20" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M2 5h16M2 10h16M2 15h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden border-t border-sa-stone-200 dark:border-sa-stone-800 bg-white dark:bg-sa-stone-950 px-4 py-4 flex flex-col gap-3">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className={clsx(
                'text-sm py-2 transition-colors duration-[200ms]',
                pathname === link.href
                  ? 'text-sa-stone-900 dark:text-sa-stone-50 font-medium'
                  : 'text-sa-stone-600 dark:text-sa-stone-400',
              )}
            >
              {link.label}
            </Link>
          ))}
          <div className="pt-2 border-t border-sa-stone-100 dark:border-sa-stone-800 flex flex-col gap-2">
            {authed ? (
              <Link
                href="/library"
                onClick={() => setMenuOpen(false)}
                className="px-4 py-2 rounded-xl text-sm font-medium bg-sa-amber-500 text-white text-center"
              >
                Go to Library
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setMenuOpen(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium border border-sa-stone-200 dark:border-sa-stone-700 text-sa-stone-700 dark:text-sa-stone-300 text-center"
                >
                  Sign in
                </Link>
                <Link
                  href="/login"
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-sa-amber-500 text-white text-center"
                >
                  Try it free
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  )
}
