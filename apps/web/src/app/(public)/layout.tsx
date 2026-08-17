import type { Metadata } from 'next'
import MarketingNav from '@/components/MarketingNav'
import MarketingFooter from '@/components/MarketingFooter'

export const metadata: Metadata = {
  title: {
    default: 'Sunday Album — Digitize Your Photo Albums',
    template: '%s | Sunday Album',
  },
  description:
    'Snap a photo of your album page. Sunday Album finds every photo, removes glare, restores faded colors, and delivers clean digital photos — automatically.',
  openGraph: {
    siteName: 'Sunday Album',
    url: 'https://www.sundayalbum.com',
  },
}

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-white dark:bg-sa-stone-950">
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  )
}
