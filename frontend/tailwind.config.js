/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        sage: {
          50: '#faf8ff',
          100: '#f0ecfe',
          200: '#c8a8e9',
          300: '#afa9ec',
          400: '#7f77dd',
          500: '#534ab7',
          600: '#3c3489',
          700: '#26215c',
        },
        rose: {
          sage: '#f9c4d2',
          deep: '#d4537e',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
