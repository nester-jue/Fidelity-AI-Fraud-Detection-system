/** @type {import('tailwindcss').Config} */

/* ══════════════════════════════════════════════════════════════════════════
   FIDE AI FRAUD DETECTION — FIDELITY LIFE ASSURANCE ZIMBABWE
   CENTRAL CORPORATE COLOUR THEME (single source of truth)

   Official Fidelity palette (per corporate identity):
     Fidelity Red : #C8102E
     White        : #FFFFFF
     Dark Red     : #8B0000
     Light Red    : #FCEBED
     Dark Text    : #222222
     Subtle Border: #EEEEEE

   Policy enforced here for EVERY module:
     • Interface is predominantly WHITE and RED.
     • Headings are BLACK / DARK CHARCOAL — never red.
     • Table headers: white text on Fidelity-red backgrounds (CSS layer).
     • Primary buttons: Fidelity red + white; secondary: white + red border.
     • NO blue, purple, green, orange, or multicoloured gradients.
   Every legacy Tailwind hue family (blue/indigo/purple/violet/sky/cyan/teal,
   green/emerald/lime, orange/amber/yellow, pink/rose/fuchsia, …) is remapped
   onto the Fidelity red scale; every legacy gray family is remapped onto a
   neutral charcoal/gray scale. Components keep working unchanged; the output
   colour is always on-brand.
   ══════════════════════════════════════════════════════════════════════════ */

const FIDELITY_RED = '#C8102E';   // Fidelity Red
const FIDELITY_RED_DARK = '#8B0000';   // Dark Red
const FIDELITY_RED_LIGHT = '#FCEBED';  // Light Red
const FIDELITY_WHITE = '#FFFFFF';
const FIDELITY_TEXT = '#222222';       // Dark Text
const FIDELITY_BORDER = '#EEEEEE';     // Subtle Borders

/** Fidelity-red scale (50 → 950) — only approved corporate red values. */
const fidelityRed = {
  50: FIDELITY_RED_LIGHT,   // #FCEBED  light-red tint / highlight
  100: FIDELITY_RED_LIGHT,
  200: FIDELITY_RED_LIGHT,
  300: FIDELITY_RED_LIGHT,
  400: FIDELITY_RED,        // #C8102E  Fidelity Red
  500: FIDELITY_RED,        // #C8102E  Fidelity Red (primary)
  600: FIDELITY_RED,        // #C8102E  Fidelity Red (primary)
  700: FIDELITY_RED_DARK,   // #8B0000  Dark Red (hover / darker)
  800: FIDELITY_RED_DARK,   // #8B0000  Dark Red
  900: FIDELITY_RED_DARK,
  950: FIDELITY_RED_DARK,
};

/** Neutral scale — only white, subtle borders and dark text. */
const charcoal = {
  50: FIDELITY_WHITE,
  100: FIDELITY_WHITE,
  200: FIDELITY_BORDER,     // #EEEEEE  subtle borders
  300: FIDELITY_BORDER,
  400: FIDELITY_TEXT,
  500: FIDELITY_TEXT,
  600: FIDELITY_TEXT,
  700: FIDELITY_TEXT,
  800: FIDELITY_TEXT,
  900: FIDELITY_TEXT,       // #222222  dark text
  950: FIDELITY_TEXT,
};

/** Every legacy coloured hue collapses onto the Fidelity-red scale. */
const redAliases = {};
for (const name of [
  'red', 'rose', 'pink', 'fuchsia',
  'orange', 'amber', 'yellow', 'lime',
  'green', 'emerald', 'teal', 'cyan', 'sky',
  'blue', 'indigo', 'violet', 'purple',
]) {
  redAliases[name] = fidelityRed;
}

/** `amber` historically meant "warning gold"; in Fidelity it becomes red. */
const amber = {
  50: FIDELITY_RED_LIGHT,
  100: FIDELITY_RED_LIGHT,
  200: FIDELITY_RED_LIGHT,
  300: FIDELITY_RED,
  400: FIDELITY_RED,
  500: FIDELITY_RED,
  600: FIDELITY_RED_DARK,
  700: FIDELITY_RED_DARK,
  800: FIDELITY_RED_DARK,
  900: FIDELITY_RED_DARK,
  950: FIDELITY_RED_DARK,
};

/** Every legacy gray hue collapses onto the neutral charcoal scale. */
const grayAliases = {};
for (const name of ['slate', 'gray', 'grey', 'zinc', 'neutral', 'stone']) {
  grayAliases[name] = charcoal;
}

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    // legacy backups are not part of the shipped UI; don't scan them
    '!./src/**/*-backup.*',
    '!./index-backup.html',
    '!./src/index-backup.css',
  ],
  theme: {
    extend: {
      colors: {
        // ── Fidelity corporate brand tokens ──────────────────────────────
        fidelity: {
          red: FIDELITY_RED,
          'red-dark': FIDELITY_RED_DARK,
          'red-light': FIDELITY_RED_LIGHT,
          white: FIDELITY_WHITE,
          text: FIDELITY_TEXT,
          border: FIDELITY_BORDER,
          ...fidelityRed,
        },
        'fidelity-red': FIDELITY_RED,
        'fidelity-red-dark': FIDELITY_RED_DARK,
        'fidelity-red-light': FIDELITY_RED_LIGHT,

        // ── Legacy `brand` namespace re-pointed at Fidelity Life ─────────
        brand: {
          dark: FIDELITY_TEXT,            // was navy #0A192F → charcoal
          primary: FIDELITY_RED,          // was navy → Fidelity Red
          secondary: FIDELITY_RED_DARK,   // was navy → Dark Red
          accent: FIDELITY_RED,           // was gold #C59B27 → Fidelity Red
          accentLight: FIDELITY_RED_LIGHT, // was gold → Light Red
          white: FIDELITY_WHITE,
          text: FIDELITY_TEXT,
          border: FIDELITY_BORDER,
        },

        // ── Remapped legacy hue families (nothing blue/green/purple/…) ──
        ...redAliases,
        amber,   // legacy "gold/amber" → Fidelity red treatment
        ...grayAliases,

        black: '#000000',
        white: FIDELITY_WHITE,
      },

      // ── NEXA Central Typography Standard ── (unchanged scale; on-brand)
      fontSize: {
        nexaDisplay:    ['30px', { lineHeight: '1.2', fontWeight: '800' }],
        nexaSection:    ['23px', { lineHeight: '1.3', fontWeight: '700' }],
        nexaCard:       ['16px', { lineHeight: '1.4', fontWeight: '600' }],
        nexaFigure:     ['30px', { lineHeight: '1.2', fontWeight: '800' }],
        nexaSidebar:    ['16px', { lineHeight: '1.4', fontWeight: '600' }],
        nexaTable:      ['15px', { lineHeight: '1.5', fontWeight: '500' }],
        nexaForm:       ['16px', { lineHeight: '1.5', fontWeight: '600' }],
        nexaBody:       ['16px', { lineHeight: '1.55', fontWeight: '400' }],
        nexaSecondary:  ['13.5px', { lineHeight: '1.4', fontWeight: '400' }],
      },
      fontFamily: {
        display: ["'Inter', 'Montserrat', -apple-system, Arial, sans-serif"],
        formal:  ["'Times New Roman', Times, serif"],
      },
    },
  },
  plugins: [],
};
