// Builds static/css/tailwind.css (minified, purged to the layout classes used in templates/ and static/js/).
// Run from anywhere:  cd tools/frontend && npm run build:css      (first time: npm ci)
import { execFileSync } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..'); // tailwind resolves the content globs against the working directory
const dir = mkdtempSync(join(tmpdir(), 'mfh-tw-'));
const input = join(dir, 'in.css');
writeFileSync(input, '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n');
const bin = join(here, 'node_modules', 'tailwindcss', 'lib', 'cli.js');
execFileSync(
  process.execPath,
  [bin, '-c', join(here, 'tailwind.config.js'), '-i', input, '-o', join(repoRoot, 'static', 'css', 'tailwind.css'), '--minify'],
  { stdio: 'inherit', cwd: repoRoot },
);
