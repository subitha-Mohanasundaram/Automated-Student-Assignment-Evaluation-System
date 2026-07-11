/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        brand: {
          50:  '#f0fdfb',
          100: '#ccfbf4',
          200: '#99f6e8',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#00b8a3',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
        accent: {
          400: '#fb923c',
          500: '#ffa116',
          600: '#ea580c',
        },
        dark: {
          900: '#0a0a0f',
          800: '#111118',
          700: '#1a1a2e',
          600: '#16213e',
          500: '#1e2a3a',
          400: '#253447',
        }
      },
    },
  },
  plugins: [],
}
