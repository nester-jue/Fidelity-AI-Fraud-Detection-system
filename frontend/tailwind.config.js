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
      },
      // ── NEXA Central Typography Standard ──
      // Unified size scale (px) mirroring the CSS variables in src/index.css.
      fontSize: {
        // Main page headings — target 28–32px
        nexaDisplay:    ['30px', { lineHeight: '1.2', fontWeight: '800' }],
        // Section headings — target 22–24px
        nexaSection:    ['23px', { lineHeight: '1.3', fontWeight: '700' }],
        // Dashboard card headings — target 15–17px
        nexaCard:       ['16px', { lineHeight: '1.4', fontWeight: '600' }],
        // Financial figures — target 26–32px
        nexaFigure:     ['30px', { lineHeight: '1.2', fontWeight: '800' }],
        // Sidebar navigation — target 15–17px
        nexaSidebar:    ['16px', { lineHeight: '1.4', fontWeight: '600' }],
        // Tables — target 14–16px
        nexaTable:      ['15px', { lineHeight: '1.5', fontWeight: '500' }],
        // Forms/inputs/buttons — target 15–16px
        nexaForm:       ['16px', { lineHeight: '1.5', fontWeight: '600' }],
        // Body text — target 15–16px
        nexaBody:       ['16px', { lineHeight: '1.55', fontWeight: '400' }],
        // Secondary info — target 13–14px
        nexaSecondary:  ['13.5px', { lineHeight: '1.4', fontWeight: '400' }],
      },
      fontFamily: {
        display: ["'Inter', 'Plus Jakarta Sans', -apple-system, Arial, sans-serif"],
        formal:  ["'Times New Roman', Times, serif"],
      },
    },
  },
  plugins: [],
};
