# SEO, discovery and analytics

Code: `routes/seo.py`, `utils/seo.py`, `templates/search.html`, tests in `tests/test_seo.py`.

## What is indexed

`utils/seo.py::PUBLIC_PAGES` lists the pages a guest can open without a login redirect: `/`, `/login`, `/signup`, `/about`, `/faq`, `/contact`, `/privacy`, `/terms`, `/blog/` plus every published blog post (`/blog/<id>`). `/blog` is only a redirect, so the registry uses `/blog/`. `/yoga/videos` is not listed: the real page is `/patient/yoga/videos` and needs a patient login.

A registry path appears in `robots.txt` and `sitemap.xml` only if the URL map resolves it (`app.url_map.bind('').match`), so pages that other agents have not built yet are skipped and appear on their own once the route exists. Add a new public page by adding one registry entry.

`PRIVATE_PREFIXES` (patient, provider, chat, `/api/`, profile, telehealth, music, `/search`, ...) are disallowed in `robots.txt`. `robots.txt` is advisory; real protection is `@login_required`. Drafts and private data never enter the sitemap.

- `/robots.txt`: `text/plain`, cached 1 day.
- `/sitemap.xml`: sitemap protocol 0.9, max 5000 URLs, `<lastmod>` for blog posts from `updated_at` (else `created_at`), cached 1 hour in a per-process memo (not Flask-Caching: that object lives in `app.py` and importing it from a blueprint is circular). The memo is skipped under `TESTING`.
- `/favicon.ico` is served by `app.py` (`favicon`, from `static/favicon.ico`); `seo.py` does not redefine it.

## Titles, meta, canonical, OG, JSON-LD

Per-page tags come from the `base.html` blocks in `docs/DESIGN_SYSTEM.md`: `title`, `meta_description`, `canonical`, `robots` (default `noindex, nofollow`; public pages set `index, follow`), `og_image`, `breadcrumbs` (macro also emits BreadcrumbList JSON-LD) and `head_extra` (for page-specific JSON-LD such as `Article` on blog posts). Public templates must override `robots` to `index, follow`, set a unique `title` and `meta_description`, and set `canonical` to `{{ site_url }}<path>`. `search.html` and every `/api/*` response also send `X-Robots-Tag: noindex`.

## Custom domain

Set `SITE_URL=https://yourdomain.in` (no trailing slash needed). Without it the origin is taken from the request, which depends on the `Host` header and the proxy scheme, so set it in production. It feeds `Sitemap:` in `robots.txt`, every sitemap `<loc>` and the search canonical.

## Verify

1. Open `/robots.txt` and `/sitemap.xml` on the live domain.
2. Search Console: add the domain property, verify (DNS TXT), submit `https://<domain>/sitemap.xml`.
3. Use URL Inspection on `/` and a blog post; check "Page is indexable" and the user-declared canonical.
4. Check that private pages (`/patient/dashboard`) are not in the coverage report.

## Search (`/search?q=`)

Guests search the public page registry and published blog posts (title and content, parameterised `LIKE` with `%`, `_` and `\` escaped, at most 20 results, query cut to 100 characters, up to 5 words that must all match). An empty query lists the page index. Logged-in patients and providers also see a static list of feature shortcuts for their role. Private data (journal, chat, notes, assessments) is never searched. Matches are highlighted by the `highlight` template filter, which escapes first and then wraps matches in `<mark>`. Rate limit: 60 per minute.

## First-party events (`POST /api/event`)

Body: JSON `{name, path, utm_source, utm_medium, utm_campaign}`. Stored in `AnalyticsEvent`: name, path, three UTM strings, timestamp. No user id, IP, user agent or free text.

- `name` must be one of `utils/seo.py::EVENT_NAMES` (page_view, signup_start, signup_complete, login, assessment_start, assessment_complete, chat_open, contact_submit, blog_read, cta_click, theme_toggle). Unknown names or fields give 400.
- `path` is required, must start with `/`, query string and fragment are removed, cut to 200 characters. UTM values lose characters outside `[A-Za-z0-9._~ +-]` and are cut to 100.
- Consent gate: the browser script must send the header `X-Analytics-Consent: granted` and only after the user has opted in. Without it, or with `DNT: 1`, the server returns 204 and stores nothing. The client script (not built yet) must not send anything before consent.
- Same-origin: `Origin` (else `Referer`) must match the request host, otherwise 403. A missing header is rejected.
- CSRF-exempt for this one endpoint, because it is a JSON beacon that may fire before a token exists. Compensation: same-origin check, the custom header (forces a CORS preflight cross-site), strict allowlist, and nothing it does depends on the session.
- Rate limit 120 per minute per IP. Success returns 204.
- Read side: `utils/seo.py::event_counts(days=30)` returns `{event name: count}`. No UI yet.
