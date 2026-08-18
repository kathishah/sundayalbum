'use client'

import { useThemeStore, type ThemePreference } from '@/stores/theme-store'

function SunIcon() {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="3.5" />
      <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.5 11.5A7.5 7.5 0 1 1 8.5 2.5a5.5 5.5 0 0 0 9 9z" />
    </svg>
  )
}

function SystemIcon() {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="16" height="11" rx="2" />
      <path d="M7 17h6M10 14v3" />
    </svg>
  )
}

const OPTIONS: { value: ThemePreference; label: string; icon: React.ReactNode }[] = [
  { value: 'system', label: 'System', icon: <SystemIcon /> },
  { value: 'light',  label: 'Light',  icon: <SunIcon /> },
  { value: 'dark',   label: 'Dark',   icon: <MoonIcon /> },
]

export default function AppearanceSettings() {
  const { preference, setPreference } = useThemeStore()

  return (
    <div className="bg-white dark:bg-sa-stone-900 rounded-2xl border border-sa-stone-200 dark:border-sa-stone-800 shadow-sm p-6 max-w-xl">
      <h2 className="font-display text-lg font-semibold text-sa-stone-900 dark:text-sa-stone-50 mb-1">
        Appearance
      </h2>
      <p className="text-sm text-sa-stone-500 dark:text-sa-stone-400 mb-5">
        Choose how Sunday Album looks. System follows your device setting.
      </p>

      <div className="flex rounded-xl overflow-hidden border border-sa-stone-200 dark:border-sa-stone-700 bg-sa-stone-100 dark:bg-sa-stone-800 p-1 gap-1">
        {OPTIONS.map(({ value, label, icon }) => {
          const active = preference === value
          return (
            <button
              key={value}
              type="button"
              onClick={() => setPreference(value)}
              className={[
                'flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all duration-[200ms]',
                active
                  ? 'bg-white dark:bg-sa-stone-700 text-sa-stone-900 dark:text-sa-stone-50 shadow-sm'
                  : 'text-sa-stone-500 dark:text-sa-stone-400 hover:text-sa-stone-700 dark:hover:text-sa-stone-200',
              ].join(' ')}
            >
              {icon}
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
