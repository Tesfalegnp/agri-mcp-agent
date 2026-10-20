/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#f2f8f3',
          100: '#e1efe4',
          200: '#c5e0cb',
          300: '#9ec9a7',
          400: '#71ab7e',
          500: '#4e8f5d',
          600: '#3a7247',
          700: '#305b3a',
          800: '#294931',
          900: '#233d2a',
          950: '#102115',
        },
        earth: {
          50: '#faf6f1',
          100: '#f3ece0',
          200: '#e5d7c0',
          300: '#d4be9b',
          400: '#c1a176',
          500: '#b08759',
          600: '#9a704a',
          700: '#7c573d',
          800: '#674837',
          900: '#563d30',
        }
      }
    },
  },
  plugins: [],
}
