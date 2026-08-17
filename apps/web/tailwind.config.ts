import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'sa-amber': {
          50: '#FFF8F0',
          100: '#FEF0DC',
          200: '#FDE0C0',
          400: '#FBBF24',
          500: '#D97706',
          600: '#B45309',
          700: '#92400E',
        },
        'sa-stone': {
          50: '#FAFAF9',
          100: '#F5F5F4',
          200: '#E7E5E4',
          300: '#D1CFC9',
          400: '#A8A29E',
          500: '#78716C',
          600: '#57534E',
          700: '#44403C',
          800: '#292524',
          900: '#1C1917',
          950: '#0C0A09',
        },
        'sa-success': '#16A34A',
        'sa-error': '#DC2626',
        /* Semantic adaptive tokens — reference CSS variables set in globals.css */
        'sa-card': 'rgb(var(--sa-card) / <alpha-value>)',
        'sa-surface': 'rgb(var(--sa-surface) / <alpha-value>)',
        'sa-border-card': 'rgb(var(--sa-border-card) / <alpha-value>)',
      },
      fontFamily: {
        display: ['var(--font-fraunces)', 'Georgia', 'serif'],
        sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      transitionTimingFunction: {
        'sa-spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      transitionDuration: {
        'sa-standard': '200ms',
        'sa-slide': '350ms',
        'sa-reveal': '600ms',
      },
      animation: {
        'sa-standard': 'sa-standard 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        'sa-slide': 'sa-slide 350ms cubic-bezier(0.16, 1, 0.3, 1)',
        'sa-reveal': 'sa-reveal 600ms cubic-bezier(0.16, 1, 0.3, 1)',
        'spin-slow': 'spin 1.2s linear infinite',
      },
      keyframes: {
        'sa-standard': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'sa-slide': {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'sa-reveal': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

export default config
