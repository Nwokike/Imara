/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        'imara-deep': '#2D1B36',      // Deep Purple/Brown (Premium Dark)
        'imara-gold': '#C8A165',      // Aged Gold (Accents)
        'imara-cream': '#F5F5F0',     // Warm Cream (Background)
        'imara-text': '#1A1A1A',      // Near Black
        'imara-dark-bg': '#121212',   // Dark Mode BG
        'imara-dark-surface': '#1E1E1E', // Dark Mode Surface
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
      },
      backdropBlur: {
        'xs': '2px',
      }
    },
  },
  plugins: [],
  darkMode: ['class', '[data-theme="dark"]'],
}
