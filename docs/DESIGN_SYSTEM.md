# Design system (contract for the Nov 2026 redesign)

Goal: a calm, credible, clinical-but-warm product for Indian college students and counsellors. It should look like a well-run health service, not a landing-page template. This file is the contract between the shell (`base.html`, `static/css/site.css`) and every page template.

## Hard bans (checked by `tests/test_design_rules.py`)

- No purple, violet, indigo or pink gradients. No gradients on text. Avoid gradients entirely; flat surfaces only.
- No pill-shaped buttons or badges (`rounded-full` / `border-radius: 9999px` / 999px). Radius is 6px (`--radius`), 8px for cards (`--radius-lg`). Circles are allowed only for avatars and status dots.
- No emoji anywhere (templates, JS strings, flash messages, AI prompt examples). Use the SVG icon macro.
- No em dashes (U+2014) and no en dashes used as punctuation. Use a comma, colon, full stop or a plain hyphen.
- No fake reviews, testimonials, customer logos, "trusted by", user counters, "10,000+ users", ratings, star rows or invented statistics. Numbers on screen must come from the database or be absent. Empty data shows `n/a` or an empty state.
- No vague hero text ("Transform your journey", "Unlock your potential", "Your AI-powered wellness companion", "Revolutionize"). Say what the product does in plain words.
- No "Made with AI", "Powered by AI", "AI-generated" badges or marketing sparkles. The AI companion keeps its functional disclosure inside the chat ("Anya is an AI assistant, not a therapist"); that stays.
- No stock or AI-generated photos, no decorative blobs. Use no photography; use real UI, simple SVG diagrams or plain typography.
- No cursor effects, parallax, scroll-jacking, scroll-triggered reveal choreography, auto-playing carousels, typewriter text, floating particles, bouncing arrows. Allowed motion: 120-200ms colour/opacity/transform transitions on hover and focus, the progress bar, toast fade. Everything off under `prefers-reduced-motion`.
- No fake "encrypted", "HIPAA compliant", "clinically proven" claims.

## Palette (CSS custom properties; dark values under `[data-theme="dark"]`)

| Token | Light | Dark |
|-------|-------|------|
| `--bg` | `#F3F5F6` | `#13171C` |
| `--surface` | `#FFFFFF` | `#1A1F26` |
| `--surface-2` | `#E9EEF0` | `#232A33` |
| `--surface-raised` (menus, toasts, dialogs) | `#FFFFFF` | `#29313B` |
| `--text` | `#1E2A33` | `#DCE2E8` |
| `--text-muted` | `#4A5B67` | `#9FABB7` |
| `--border` | `#D4DBDF` | `#333C47` |
| `--input-border` | `#6C7C87` | `#6B7885` |
| `--primary` | `#0F6B7B` | `#62B0BF` |
| `--primary-hover` | `#0A5563` | `#7CC1CE` |
| `--primary-contrast` | `#FFFFFF` | `#0C1A1F` |
| `--danger` | `#B3261E` | `#EE8B84` |
| `--warning` | `#8A4B08` | `#E0B068` |
| `--success` | `#1A6B44` | `#6FC79E` |
| `--info` | `#1D5CA6` | `#8DB3E6` |
| `--focus` | `#0F6B7B` | `#8BC9D5` |
| `--on-danger` | `#FFFFFF` | `#2A0E0C` |

Never use pure `#000` or `#FFF` for a page background or body text (halation and glare); dark surfaces step lighter with elevation and carry no shadow. Do not hard-code colours in CSS or templates: use tokens (`--scrim` for dialog backdrops, `--shadow-pop` for floating layers). Rationale and sources: [research/color-theme.md](research/color-theme.md). Check with `python scripts/check_contrast.py`; `tests/test_theme_contrast.py` enforces it.

All text/background pairs meet WCAG AA (4.5:1). Focus ring: 2px solid `--focus`, 2px offset, never removed. Shadows: none, or a hairline on cards (none in dark).

Typography: system UI stack (`system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Noto Sans Devanagari", sans-serif`), no web font download. Base 16px, line-height 1.6. Scale: h1 1.875rem, h2 1.5rem, h3 1.125rem, small 0.875rem. Headings weight 600, never uppercase-tracked.

## Layout and classes

Use Tailwind utilities for **layout only** (flex, grid, gap, margin, padding, width, text-size, hidden/md:block). Never use Tailwind colour utilities (`bg-*`, `text-<colour>-*`, `border-<colour>-*`, `from-*`, `to-*`, `shadow-*` colours): they break dark mode. Colour comes from these semantic classes, defined in `static/css/site.css`:

- Containers: `.container` (max 72rem, 16px gutters), `.section` (vertical rhythm), `.page-header` (h1 + `.lead` + `.page-actions`).
- Buttons: `.btn` + one of `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`; size `.btn-sm`. Min height 40px (44px on touch). Disabled and loading (`aria-busy="true"`) states exist.
- Surfaces: `.card`, `.card-header`, `.card-body`, `.panel-muted`.
- Forms: `.field`, `.label`, `.input`, `.select`, `.textarea`, `.help`, `.error-text`; invalid state via `aria-invalid="true"`; success note `.success-text`; checkbox row `.check`.
- Feedback: `.alert` + `.alert-info|success|warning|danger`, `.badge` + `.badge-neutral|success|warning|danger|info`, `.empty-state` (icon, title, text, action), `.skeleton` (shimmer block; no shimmer under reduced motion), `.stat` (`.stat-label`, `.stat-value`, `.stat-note`), `.table` (+ `.table-wrap` for horizontal scroll), `.tabs`, `.accordion`.
- Text helpers: `.muted`, `.text-danger`, `.text-success`, `.prose` (long-form pages: privacy, terms, blog).
- Crisis banner: `.crisis-banner` (always readable, high contrast, links `tel:`). Helplines come from `utils/helplines.py`, never typed in templates.

## Glass (structural chrome only)

The owner has asked for Apple-style translucency on a handful of structural surfaces: the sticky header (`.site-header`), the desktop dropdown menu (`.menu-popover`), the confirm/delete modal (`.mfh-modal` and its `::backdrop`), and dashboard stat tiles (`.stat`). This is a deliberate, narrow addition, not a reversal of "flat surfaces only" above: everywhere else in the product (cards, forms, journal and assessment text, chat, body content) stays flat with the hairline border and no shadow, exactly as before. Glass goes on chrome you look past, never on anything you read or write.

Implementation (`static/css/components.css`, gated by `@supports (backdrop-filter: blur(1px))`):
- `backdrop-filter: blur(...) saturate(...)` (10-20px blur depending on how much the surface overlaps content; 130-150% saturation so colour behind the glass does not wash out).
- A translucent background built from existing tokens only, never a new colour: `--glass-tint` (`color-mix(in srgb, var(--surface) 68%, transparent)`) for lighter chrome (header, stat tiles), `--glass-tint-strong` (`color-mix(in srgb, var(--surface-raised) 90%, transparent)`) where text needs to stay legible over arbitrary page content (menu, modal). Both tokens are defined once in `site.css` from the theme-aware `--surface`/`--surface-raised`, so they resolve correctly in light and dark mode without a second definition.
- A 1px edge, `--glass-border` (`color-mix(in srgb, var(--border) 65%, var(--text) 25%)`), slightly more visible than the normal hairline so the glass surface still reads as a bounded panel.
- No `@supports not` override is needed: every glass rule only replaces a background/border that is already solid elsewhere in the same stylesheet, so a browser without `backdrop-filter` (or with it disabled) simply keeps that solid surface and stays fully readable.

The crisis/helpline banner stays flat and opaque on purpose: it must read as unambiguous and urgent, not decorative, so it was left out of this pass.

## Icons

Inline SVG sprite at `static/img/icons.svg`, 24px grid, 1.75 stroke, `currentColor`. Use the macro:

```jinja
{% from 'partials/icons.html' import icon %}
{{ icon('heart') }}              {# decorative, aria-hidden #}
{{ icon('alert', label='Warning') }}   {# meaningful, role="img" #}
```

Icon names: home, chart, calendar, chat, heart, book, user, users, settings, bell, check, alert, info, x, menu, search, sun, moon, arrow-right, arrow-left, play, pause, clock, pill, video, music, leaf, lock, mail, phone, edit, trash, copy, external, shield, mood, journal, mic, target, logout, plus, filter, download, eye, eye-off, wind, activity, file, help, chevron-down, chevron-up.

## Shell contract (`templates/base.html`)

Blocks every page may override: `title`, `meta_description`, `canonical`, `robots` (default `noindex, nofollow`; public pages set `index, follow`), `og_image`, `breadcrumbs`, `head_extra`, `content`, `scripts`. Breadcrumb macro: `{% from 'partials/breadcrumbs.html' import breadcrumb %}{{ breadcrumb([('Home','/'),('Blog',None)]) }}` (renders the nav and BreadcrumbList JSON-LD).

JavaScript API from `static/js/shell.js` (loaded `defer`): `MFH.toast(message, type)` where type is `info|success|error`; `MFH.confirm({title, message, confirmText, danger})` returns a Promise of boolean (from `static/js/components.js`); flashed Flask messages become toasts. Pages never include their own `<html>`, theme code or fonts.

Template flags available everywhere (context processor): `prescriptions_enabled` (bool), `site_url`, `contact_email`, `helplines`. Wrap any prescription links or sections in `{% if prescriptions_enabled %}`.

## Copy rules

Plain, specific, second person, sentence case, short sentences. Say what a feature does and who it is for. Examples:
- Hero: "Track your mood, take PHQ-9 and GAD-7 screenings, and book a session with your college counsellor." Not: "Transform your mental wellness journey."
- Empty state: "No mood entries yet. Log how you feel today to start your history."
- Safety: "This is a screening tool, not a diagnosis. If you are in crisis call Tele-MANAS 14416."
No exclamation marks in UI copy except genuine confirmations (rare). No second-guessing language ("Oops!"). Error text says what happened and what to do.
