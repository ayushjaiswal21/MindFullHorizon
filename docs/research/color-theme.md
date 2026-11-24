# Colour theme research (light and dark)

Agent U4, access date for every URL below: 2026-11-24. Trigger: the owner found the old palette (white-on-near-black-green dark mode, near-white light mode, saturated teal) harsh in both modes, and the dark mode unprofessional.

Status labels: FETCHED means the page was opened and read. UNVERIFIED means only a search snippet or a secondary summary was seen; do not rely on it for a decision without reading the source.

## 1. Questions and short answers

1. Do pure white pages and pure black pages cause eye strain? Both extremes are discouraged by most practitioner guidance. The scientific evidence is thin and mixed, so the decision rests on legibility and comfort, not on a proven effect.
2. How much contrast is enough? WCAG 2.2 sets floors (4.5:1 text, 3:1 non-text). There is no WCAG ceiling, but very high contrast in dark mode is where halation (glow around light text) is reported.
3. What do mature design systems do for dark? Dark grey, not black; lighter surfaces for elevation; desaturated, lighter accents; off-white text at reduced emphasis.
4. Does colour change mood in health settings? Weak evidence. A review of healthcare colour research found no strong support for colour prescriptions. Legibility and consistency matter more.
5. What should a counselling service look like? Calm, plain and credible, like the NHS and GOV.UK systems, not like a pastel consumer wellness app.

## 2. Eye strain, glare and halation

- NN/g, "Dark mode vs light mode" (FETCHED): https://www.nngroup.com/articles/dark-mode/ . Light text on dark (negative polarity) generally performs worse for people with typical vision ("light mode leads to better performance most of the time"); the explanation offered is that brighter screens constrict the pupil, which reduces blur. Some low-vision users (for example with cataracts, which scatter light) read better in dark mode. A 7-person study linking long-term light-mode reading to choroid thinning is mentioned; too small to act on. Conclusion for us: offer both modes, follow the system setting, and make neither one extreme.
- Smashing Magazine, "Inclusive dark mode" (FETCHED): https://smashingmagazine.com/2025/04/inclusive-dark-mode-designing-accessible-dark-themes/ . Advises dark greys such as #121212 instead of pure black, warns that light text on dark can produce halo effects and that dark mode "can actually compromise readability" for people with astigmatism or low contrast sensitivity (it cites a BOIA post that was not opened by us: that attribution is UNVERIFIED), and advises avoiding overly saturated colours in dark UIs. Several of its other citations (bounce-rate claims) are marketing-grade and were ignored.
- Search results on halation and astigmatism (UNVERIFIED, snippets only): Android Authority, All About Vision (https://www.allaboutvision.com/conditions/computer-vision-syndrome/digital-eye-strain/is-dark-mode-better-for-eyes), Icons8, Bustle. They repeat that halation affects a large share of people with astigmatism (one source says about half; the number is not traceable to a primary study in what we saw) and that white-on-black is the worst case. Treat as plausible practitioner consensus, not measured fact.
- Pure white pages: no primary evidence was found that a white page damages eyes. The reasoning for an off-white page is glare control in dim rooms and a visible difference between page and white cards. GOV.UK itself uses a white body and a tinted template background (#f4f8fb) (FETCHED, see section 5). NHS uses a grey-tinted page (#f0f4f5).

Decision: never use #000 or #FFF as the page or text colour in either mode; keep dark body text below about 15:1 against its background.

## 3. Contrast standards

- WCAG 2.2 SC 1.4.3 Contrast (Minimum) (FETCHED): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html . 4.5:1 for text, 3:1 for large text (18 pt, or 14 pt bold). Ratios are not rounded. The page notes that some people with cognitive disabilities need lower-contrast combinations and encourages author-provided colour adjustment; it does not set an upper limit.
- WCAG 2.2 SC 1.4.11 Non-text Contrast and 2.4.7 Focus Visible (FETCHED): https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html . 3:1 against adjacent colours for UI component boundaries needed to identify a control, for state indicators and for focus indicators.
- WCAG 2.2 SC 1.4.1 Use of Color (FETCHED): https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html . Colour must not be the only means of conveying information; add text, shape or icon.
- APCA (UNVERIFIED, search snippets of the Myndex repository and the ARC site): body text Lc 75 minimum and Lc 90 preferred; other content text Lc 60. APCA is a draft for WCAG 3, not a legal standard, and the sources say it asks for more contrast than WCAG 2 for body text. We still use WCAG 2.x ratios because that is what regulators and the existing tests use, but our body text sits at 12-14:1, which lands near or above APCA Lc 75 territory for normal weights. A tool check of Lc values was not run.
- NHS and GOV.UK aim for AA and prefer AAA where possible (FETCHED, NHS). NHS notes that its own border colour (#d8dde0) does not meet contrast on the page background: decorative card borders may be soft, but borders that identify a control (inputs) must be 3:1.

Decision: body 12:1 or better but under 15:1 (comfortable, not extreme); muted text 6:1 or better (floor 4.5:1); every status colour 4.5:1 on its tinted background; focus and input borders 3:1 or better.

## 4. Dark theme guidance from design systems

- Material Design dark theme codelab (FETCHED): https://codelabs.developers.google.com/codelabs/design-material-darktheme/ . Base surface "a dark grey with the hex value #121212"; elevation shown by overlaying white at higher opacity (cards about 2%, app bar about 12%) because shadows are hard to see on dark; saturated colours "shimmer" against dark backgrounds so lighter tonal variants are used; text uses white at 87 percent (high emphasis), 60 (medium) and 38 (disabled), avoiding pure white. The m2.material.io dark-theme page itself would not load for the fetch tool, so statements about the 200 tone and the 15.8:1 figure in other pages are UNVERIFIED.
- Apple Human Interface Guidelines, Dark Mode (UNVERIFIED; the page is script-rendered and the fetch returned only a title; search snippets of the .md export were read): https://developer.apple.com/design/human-interface-guidelines/dark-mode . It describes "base" (dimmer) and "elevated" (brighter) background sets so foreground layers come forward, and recommends system semantic colours. Apple also uses true black as base on OLED iPhones; we deliberately do not copy that, because we serve web users on LCD laptops and shared screens, and halation is the reported risk.
- NHS and GOV.UK publish no dark theme (as far as the fetched colour pages show). We take their light palettes as the credibility reference and Material and Apple as the dark-mode technique reference.

Decision: dark page #13171C (blue-slate, not black, not green), surfaces step lighter bg < surface < surface-2 < raised, shadows removed in dark, accents lighter and less saturated, text about 87 percent feel (#DCE2E8).

## 5. Healthcare and public-service palettes

- NHS design system colour page (FETCHED): https://service-manual.nhs.uk/design-system/styles/colour . Text #212b32, secondary text #4c6272, link #005eb8, border #d8dde0, input border #4c6272, page background grey-5 #f0f4f5, focus #ffeb3b with dark text, error #d5281b. Blue link on a cool grey page: the reference for "clinical".
- GOV.UK design system colour page (FETCHED): https://design-system.service.gov.uk/styles/colour/ . Text #0b0c0c, secondary #484949, link #1a65a6, border #cecece, template background #f4f8fb, error #ca3535, success #0f7a52. Neither system uses a pastel brand colour for large areas.
- Smashing Magazine, "Designing for distressed users" (2026) (UNVERIFIED, snippet): https://smashingmagazine.com/2026/07/designing-distressed-users-mental-health-apps-ui/ . Argues mental-health UIs should offer refuge and trust, not follow UI fashion. Another snippet (arounda.agency) reports de-saturated blues and greens as common, and a third warns that "blues and purples" are now a cliché default. These are opinion pieces, not studies.
- Clinical software versus consumer wellness apps: no source found that compares palettes directly (UNVERIFIED gap). Our inference: clinical tools use neutral greys, one restrained accent, dense tables and plain borders; wellness apps use large pastel fields, gradients and rounded illustration. A college counselling service sits between: warm copy, clinical surfaces.

Decision: cool-grey page (NHS-like), white cards, a deep blue-teal accent between the old teal and the NHS blue, slate text (not black), and text-labelled status colours.

## 6. Does colour affect mood? (say plainly)

The evidence is weak.

- Summary of a critical review, Healthcare Design magazine (UNVERIFIED, summary only): https://healthcaredesignmagazine.com/?p=592 . Reports no direct link between particular colours and health outcomes, no one-to-one colour-emotion pairing, and that universal colour guidelines are not supported by strong evidence.
- Elliot and Maier, "Color psychology" (PubMed 23808916, UNVERIFIED, abstract snippet): https://pubmed.ncbi.nlm.nih.gov/23808916/ . Colour can influence affect and behaviour, mostly shown in achievement, affiliation and consumer contexts, not in treatment settings.
- Mental Health America and RMIT pages (UNVERIFIED, snippets) call most online colour-mood claims anecdotal or inconclusive.

So "blue-green is calming" is plausible but not established, and individuals differ. We choose a cool teal-blue because it reads clinical and credible and is familiar from health services, not because it heals. Legibility, consistent use and a stable layout are the things that reduce strain and anxiety. We make no claim in UI copy about colour and mood.

## 7. Colour blindness

WCAG 1.4.1 (see section 3). In this app status colours are always paired with text or an icon: `.alert` carries an icon and a heading or message, `.badge` carries a word, `.error-text` carries a sentence, risk levels are written. Danger and success use different lightness and the danger red is on the warm side while success is a blue-leaning green, but the rule is that colour is never the only signal. Not simulated with a CVD tool in this pass (UNVERIFIED).

## 8. Seasonal and student audiences

Searches found no research on seasonal palette changes in student mental-health services and we do not build any (UNVERIFIED gap; a seasonal palette would add inconsistency, which works against the consistency goal).

A 2024 survey of university students (arXiv 2409.10895, UNVERIFIED, snippet only; the paper was not opened): https://arxiv.org/pdf/2409.10895 . It reports most students preferred dark mode on their phones but a sizeable minority did not want it on learning sites, and recommends a user toggle. A Lithuanian study (CEUR-WS Vol-3575 Paper15, UNVERIFIED) found theme choice did not significantly change programmers' performance, so the theme is mostly comfort and aesthetics. Conclusion: students will use both themes, often at night; keep the system-preference default and the header toggle (already present), and make dark mode quiet instead of striking.

## 9. Token sets (defended)

Contrast computed with `scripts/check_contrast.py` (WCAG 2.x relative luminance). "soft" is the status colour mixed 10 percent over `--surface`.

| Token | Light | Dark | Reason |
|-------|-------|------|--------|
| `--bg` | #F3F5F6 | #13171C | Cool grey page (NHS-like), blue-slate dark (not black, not green) |
| `--surface` | #FFFFFF | #1A1F26 | White only for raised cards; dark steps lighter |
| `--surface-2` | #E9EEF0 | #232A33 | Table heads, hover, panels |
| `--surface-raised` | #FFFFFF | #29313B | Menus, toasts, dialogs: elevation by lightness in dark |
| `--text` | #1E2A33 | #DCE2E8 | Slate, not black; off-white about 87 percent feel |
| `--text-muted` | #4A5B67 | #9FABB7 | 6:1 or better in both |
| `--border` | #D4DBDF | #333C47 | Soft card edges (decorative) |
| `--input-border` | #6C7C87 | #6B7885 | 3:1 or better, identifies controls |
| `--primary` | #0F6B7B | #62B0BF | Deeper blue-teal; lighter, calmer in dark |
| `--primary-hover` | #0A5563 | #7CC1CE | |
| `--primary-contrast` | #FFFFFF | #0C1A1F | Text on primary buttons |
| `--danger` | #B3261E | #EE8B84 | Desaturated, lighter in dark |
| `--warning` | #8A4B08 | #E0B068 | Brown-amber in light so text passes AA |
| `--success` | #1A6B44 | #6FC79E | |
| `--info` | #1D5CA6 | #8DB3E6 | |
| `--focus` | #0F6B7B | #8BC9D5 | 2px ring plus 2px offset, 5:1 or better |
| `--on-danger` | #FFFFFF | #2A0E0C | Crisis banner text |

Results (full table: run the script): lowest text pair in light is muted text on surface-2 at 6.0:1; lowest status text on its soft background is 5.5:1 (danger, light); lowest in dark is danger on danger-soft at 5.8:1; focus 5.3:1 or better in light and 7.9:1 or better in dark; input border 3.9:1 (light on page) and 3.7:1 (dark on surface). Body text on page: 13.4:1 light, 13.8:1 dark.

Enforced by `tests/test_theme_contrast.py`.

## 10. What was not verified

- Primary studies on halation, astigmatism and polarity were not read; only secondary summaries.
- APCA Lc values were not computed with an APCA tool.
- Apple HIG page text and the Material 2 dark theme page did not load; Material claims come from the codelab.
- No colour-vision-deficiency simulation was run.
- No user testing with students, people with astigmatism or counsellors.
