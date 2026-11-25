// Builds static/css/tailwind.css (minified, purged to the layout classes used in templates/ and static/js/).
// Run from anywhere:  cd tools/frontend && npm run build:css      (first time: npm ci)
// Tailwind v4: config is CSS-based (tailwind.config.css), CLI moved to @tailwindcss/cli.
import { execFileSync } from 'node:child_process';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const input = join(here, 'tailwind.config.css'); // lives in-repo so its @source paths resolve
const bin = join(here, 'node_modules', '@tailwindcss', 'cli', 'dist', 'index.mjs');
execFileSync(
  process.execPath,
  [bin, '-i', input, '-o', join(repoRoot, 'static', 'css', 'tailwind.css'), '--minify'],
  { stdio: 'inherit', cwd: repoRoot },
);
