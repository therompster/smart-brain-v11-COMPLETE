/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js,ts}",
  ],
  theme: {
    extend: {
      colors: {
        'marriott': '#3b82f6',
        'mansour': '#10b981',
        'personal': '#8b5cf6',
        'learning': '#f59e0b',
        'admin': '#6b7280'
      }
    },
  },
  plugins: [],
}
