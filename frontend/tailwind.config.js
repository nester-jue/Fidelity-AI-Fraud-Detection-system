/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#0A192F',
          primary: '#0F2744',
          secondary: '#1B3A57',
          accent: '#C59B27',
          accentLight: '#DFB743',
        }
      }
    },
  },
  plugins: [],
};
