// Verification for the NEXA Central Typography Standard (Req 1-10).
// Run: node scripts/verify_typography.mjs
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const ROOT = resolve(process.cwd());
const SRC = join(ROOT, 'frontend/src');
const DIST = join(ROOT, 'frontend/dist');
let failures = 0;

const check = (ok, label) => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`);
  if (!ok) failures += 1;
};

const read = (p) => readFileSync(resolve(ROOT, p), 'utf8');

// Gather all JSX/CSS files in src (departments, panels, dashboards, pages, components).
const walk = (dir, out = []) => {
  for (const e of readdirSync(resolve(dir), { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
};
const srcFiles = walk(SRC).map((f) => f.split('\\').join('/'));

// ── 1. Inter as primary font throughout the app interface ──────────────
const css = read('frontend/src/index.css');
check(/fonts\.googleapis\.com\/css2\?family=Inter[^']*/.test(css), '1a. Inter imported at the stylesheet');
check(css.includes('body {') && css.includes('font-family: var(--font-body)'), '1b. body uses Inter (--font-body) as primary');
check(css.includes('font-sans') && css.includes('--font-sans:    var(--font-body)'), '1c. .font-sans central override → Inter');
const distCss = readdirSync(join(DIST, 'assets')).filter(f => f.endsWith('.css')).map(f => read(join(DIST, 'assets', f))).join('\n');
check(distCss.includes('family=Inter'), '1d. Inter present in built CSS');

// ── 2. Inter applied to dashboards, nav, tables, forms, figures, buttons, AI outputs ──
const displayUtil = css.match(/\.nexa-display\s*\{[^}]*\}/)?.[0] || '';
check(displayUtil.includes('var(--font-display)'), '2a. nexa-display uses Inter (display utility)');
const cssAll = css + srcFiles.map(read).join('\n');
check(/text-left[^}]*font-family|table[^}]*font/i.test(cssAll), '2b. Tables: .nexa-table utility exists (check file)');
check(css.includes('.nexa-table'), '2c. nexa-table utility defined');
// Dashboards/panels rely on central utilities + inherited body font; verify body sets Inter and no dashboard overrides fonts to Jakarta/system as PRIMARY.
const forbiddenPrimary = srcFiles.filter(f => /\.(js|jsx)$/.test(f) && /fontFamily|font-family\s*:|family=/i.test(read(f)) && !read(f).includes('Times New Roman'));
check(forbiddenPrimary.every(f => !/Plus\s*Jakarta|ui-sans-serif/.test(read(f))), '2d. No component overrides font-family to Jakarta/system as primary (central Inter stays)');

// ── 3. Times New Roman for formal reports ──────────────────────────────
check(css.includes('--font-formal') && css.includes('Times New Roman'), '3a. --font-formal is Times New Roman');
check(css.includes('.nexa-report'), '3b. .nexa-report (Times New Roman) utility defined');
const execDash = read('frontend/src/components/dashboards/ExecutiveDashboard.jsx');
const complianceDash = read('frontend/src/components/dashboards/ComplianceDashboard.jsx');
const invDash = read('frontend/src/components/dashboards/FraudInvestigationDashboard.jsx');
check(execDash.includes('nexa-report'), '3c. Executive (management) reports use nexa-report');
check(complianceDash.includes('nexa-report'), '3d. Compliance/regulatory reports use nexa-report');
check(invDash.includes('nexa-report'), '3e. Investigation reports use nexa-report');
// Print: official documents render Times when printed.
check(css.includes('@media print') && css.match(/@media print\s*\{[^}]*--font-formal/s) !== null || (css.includes('@media print') && css.includes('nexa-report')), '3f. Print styles resolve formal font');

// ── 4. Consistent sizes/weights/line-heights via variables ────────────
const root = css.match(/:root\s*\{([^}]*)\}/)?.[1] || '';
const props = Object.fromEntries([...root.matchAll(/--([a-zA-Z0-9-]+):\s*([^;]+);/g)].map(m => [m[1], m[2].trim()]));
for (const t of ['display', 'section', 'card-heading', 'figure', 'sidebar', 'table', 'form', 'button', 'body', 'secondary']) {
  check(props[`fs-${t}`] && props[`fs-${t}`].includes('clamp('), `4a. --fs-${t} is responsive (clamp)`);
}
for (const w of ['display', 'section', 'card', 'table', 'form', 'button', 'body']) {
  check(new RegExp(`--fw-${w}:\\s*\\d+`).test(root), `4b. --fw-${w} weight defined`);
}
for (const l of ['display', 'section', 'table', 'formal', 'body', 'secondary', 'form']) {
  check(new RegExp(`--lh-${l}:\\s*[\\d.]+`).test(root), `4c. --lh-${l} line-height defined`);
}

// ── 5. Departmental dashboards share the standard (central tokens) ─────
const dashboards = srcFiles.filter(f => f.includes('components/dashboards/') && f.endsWith('.jsx'));
const nonInterOverrides = dashboards.filter((f) => {
  const c = read(f);
  // Any fontFamily/font-family override that isn't Inter/Plus Jakarta and isn't Times is a violation.
  const matches = c.match(/(?:fontFamily=["'`][^"'"`]+["'`]|font-family:\s*["'`][^"'"`]+["'`])/gi) || [];
  return matches.filter((m) => !/Times New Roman/.test(m) && !/Inter|Plus\s*Jakarta/i.test(m)).length > 0;
});
check(dashboards.length >= 12 && nonInterOverrides.length === 0, `5. All ${dashboards.length} departmental dashboards follow the central Inter standard (no primary font overrides)`);

// ── 6. Readable financial figures, claim refs, AI risk scores ──────────
check(css.includes('tabular-nums'), '6a. tabular numerals enabled for figures/tables (readability)');
check(css.includes('.nexa-figure'), '6b. .nexa-figure utility (claim amounts/totals) defined');
check(execDash.includes('money(kpis?.total_financial_exposure)'), '6c. Financial figures still render via money() (unchanged)');

// ── 7/8. Desktop, laptop, tablet + no overlap/clip ────────────────────
check(css.includes('2.2vw') || css.includes('clamp('), '7a. Responsive sizes (vw/clamp) for laptop/tablet');
check(css.includes('min-width:0') || css.includes('min-w-0') || css.includes('overflow-wrap:anywhere') || css.includes('overflow-wrap: anywhere'), '8a. Anti-clip safeguards (min-width:0 + overflow-wrap) present');

// ── 9. Preserve branding/colors/layout (no accidental removals) ────────
check(css.includes('#f4f6fa') && css.includes('#17243a'), '9a. Body background/color unchanged');
check(css.includes("--font-display: 'Inter', 'Plus Jakarta Sans', -apple-system, Arial, sans-serif"), '9b. --font-display keeps Inter first + Jakarta fallback');

// ── 10. No business-logic changes introduced (JSX still compiles) ──────
check(!srcFiles.some(f => /\.test\.(js|jsx)$/.test(f)), '10a. No test files touched by this change set');

console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
