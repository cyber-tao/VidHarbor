/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        surface: 'rgb(24 24 27)',      // zinc-900
        panel: 'rgb(30 30 35)',
        accent: 'rgb(129 140 248)',    // indigo-400
      },
    },
  },
  plugins: [],
}
