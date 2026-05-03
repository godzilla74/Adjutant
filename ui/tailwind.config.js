/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        adj: {
          base:     '#0f0f1a',
          panel:    '#111120',
          surface:  '#1a1a2e',
          elevated: '#1e1e30',
          border:   '#2a2a3a',
          accent:   '#6366f1',
          'accent-dark': '#4338ca',
          'text-primary':   '#f1f5f9',
          'text-secondary': '#cbd5e1',
          'text-muted':     '#94a3b8',
          'text-faint':     '#94a3b8',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
