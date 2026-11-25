# SEO, discovery and analytics

Code: `routes/seo.py`, `utils/seo.py`, `templates/search.html`, tests in `tests/test_seo.py`.

## What is indexed

`utils/seo.py::PUBLIC_PAGES` lists the pages a guest can open without a login redirect: `/`, `/login`, `/signup`, `/about`, `/faq`, `/contact`, `/privacy`, `/terms`, `/ai`, `/blog/` plus every published blog post (`/blog/<id>`). `/blog` is only a redirect, so the registry uses `/blog/`. Everything else is `noindex, nofollow`: signed-in pages, `/admin/*` (including `/admin/login`), `/consent`, `/role_selection`, `/search`, error pages, drafts and all JSON and operational endpoints. The signed-in home at `/` is a private page, so its robots tag is `noindex` for a logged-in visitor and `index, follow` for a guest.

A registry path appears in `robots.txt` and `sitemap.xml` only if the URL map resolves it (`app.url_map.bind('').match`). The sitemap lists the registry pages (with `<lastmod>` from `SITE_LAST_UPDATED` in `utils/site_context.py`, bump it when public content changes) and published posts only (`<lastmod>` from `updated_at`, else `created_at`). Drafts and private paths never enter it.

`PRIVATE_PREFIXES` are disallowed in `robots.txt`. Every noindex page path must start with one of them (`tests/test_meta_tags.py` enforces this), and no public path may. `robots.txt` is advisory; real protection is `@login_required`.

- `/robots.txt`: `text/plain`, cached 1 day.
- `/sitemap.xml`: sitemap protocol 0.9, max 5000 URLs, cached 1 hour in a per-process memo (skipped under `TESTING`).
- `/favicon.ico` is served by `app.py`.
- `X-Robots-Tag: noindex, nofollow`: one `after_app_request` in `routes/seo.py` adds it to every response whose path is not public (`is_indexable_path`), except `/robots.txt`, `/sitemap.xml`, `/favicon.ico` and static files. Public pages are left to their meta tag so a draft post stays noindex there. A route that sets its own header keeps it.

## Rules for every page

Per-page tags come from the `base.html` blocks in `docs/DESIGN_SYSTEM.md`. `base.html` appends ` | MindFull Horizon` to the title, so:

- `title`: the page part only, at most 41 characters (60 with the suffix), unique. Never write the brand in it. Dynamic pages cut data with `truncate(41, True, '...')`.
- `meta_description`: 50 to 160 characters, written for that page, plain, no emoji, no em dash, no claim the app cannot back. Public pages must differ from each other.
- `canonical`: the default is `site_url + request.path` (no query string), which is right for almost every page. Override only if the path differs.
- `robots`: default `noindex, nofollow`. A public page sets `index, follow`.
- `og_image`: default is `static/img/og-default.png` (1200x630, WebP twin beside it), made absolute with `site_url`. A blog post uses the default image.
- Exactly one `<h1>` per page.
- `breadcrumbs`: every public page below the home page uses the `breadcrumb` macro (nav plus BreadcrumbList JSON-LD). Private pages do not need it.
- JSON-LD: `Organization` and `WebSite` come from `base.html`. `FAQPage` is built from `routes/pages.py::build_faqs`. Blog posts emit `Article` (headline, datePublished, dateModified, author name) from `blog_detail.html` through `tojson`, never `|safe`, so user text cannot close the script tag. Published posts only.
- Dynamic pages: the blog post sets title and description from the post (description is the body text, whitespace collapsed, padded to 50 characters when the post is short). Search uses the query in title and description and is noindex.
- Clinical templates (`admin/_base.html`, `provider_rx/_base.html`) derive a default description from the page title, so a new page there only needs a `title`.

### Add a page

1. Route in a blueprint (`routes/pages.py` for static pages). Public and indexable: add one entry to `PUBLIC_PAGES` (path, title, description, changefreq, priority). Private: do nothing, but add its prefix to `PRIVATE_PREFIXES` if it is a new top-level path.
2. Template: set `title`, `meta_description`, and for a public page `robots` plus `breadcrumbs`.
3. Run `pytest tests/test_meta_tags.py tests/test_seo.py`. The crawl test visits every parameter-free GET route as guest, patient, provider, doctor, admin and pharmacy-desk admin and fails on a missing, long or duplicate title, a bad description, a wrong canonical or robots value, a second h1, broken JSON-LD, or a sitemap URL that is not indexable.

## Behind a proxy

`site_url()` (one function, `utils/site_context.py`, re-exported by `utils/seo.py`) returns `SITE_URL` when set, else the request root. In production ProxyFix (`utils/proxy.py`) makes that root use the forwarded scheme and host. Set `SITE_URL` anyway: then no canonical, Open Graph URL, sitemap entry or JSON-LD id can contain `localhost` or an internal host name.

## Titles, meta, canonical, OG: summary of files

`templates/base.html` (shell and defaults), `templates/partials/breadcrumbs.html`, `tests/test_meta_tags.py` (crawl), `tests/test_seo.py` (sitemap, robots, search, events).

## Custom domain

Set `SITE_URL=https://yourdomain.in` (no trailing slash needed). Without it the origin is taken from the request, which depends on the `Host` header and the proxy scheme, so set it in production. It feeds `Sitemap:` in `robots.txt`, every sitemap `<loc>`, every canonical and og:image URL.

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
