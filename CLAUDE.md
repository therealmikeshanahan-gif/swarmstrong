# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository.

## What this is

**SwarmStrong** is the marketing landing page for an AI-powered marketing
agency ("We create leads so you don't have to"). It is a single, fully
self-contained static website — there is no application backend, no API, and no
data layer.

## Repository structure

The entire site is one file:

```
swarmstrong/
├── index.html   ← the whole website (markup + inline CSS)
└── CLAUDE.md    ← this file
```

`index.html` contains everything:

- **`<head>`** — meta tags, the Google Fonts link (Inter), and a single
  `<style>` block that holds *all* CSS for the site.
- **`<body>`** — the page sections, in order: `nav`, `.hero`, `.stats`,
  `#services`, `#how` (How It Works), `#contact` (CTA banner), and `footer`.

There is **no** build tooling, package manager, framework, bundler, or
JavaScript. Do not introduce one unless explicitly asked.

## Running / previewing

There is no build step. To view the site, open `index.html` in a browser:

```bash
# Quick: open the file directly
xdg-open index.html        # Linux
open index.html            # macOS

# Or serve it (useful for testing as a real URL)
python3 -m http.server 8000   # then visit http://localhost:8000
```

Because the page links Google Fonts over HTTPS, fonts require network access;
everything else works fully offline.

## Conventions

Follow the patterns already in `index.html`:

- **Single-file architecture.** Keep markup and styles together in
  `index.html`. Do not split CSS into separate files or add a JS bundle without
  a clear request to do so.
- **Design tokens via CSS variables.** Colors are defined once in `:root`
  (`--black`, `--dark`, `--card`, `--border`, `--accent`, `--accent2`,
  `--white`, `--muted`). Always reference these variables rather than
  hard-coding hex values, so the dark/purple theme stays consistent.
- **Accent gradient.** The brand gradient is
  `linear-gradient(135deg, var(--accent), var(--accent2))` (purple → cyan),
  used for the logo, headings, stat numbers, and primary buttons via the
  `-webkit-background-clip: text` technique. Reuse it for any new accent text.
- **Typography.** Inter, loaded from Google Fonts. Headings are heavy
  (`font-weight: 900`) with tight negative `letter-spacing`. Fluid sizes use
  `clamp()` (e.g. `h1` is `clamp(2.8rem, 7vw, 6rem)`).
- **Sections.** Content sits in `<section>` blocks capped at `max-width:
  1200px` and centered. Each section opens with a `.section-label` (uppercase
  accent kicker), then an `<h2>`, then a `.section-sub`.
- **Cards & grids.** Service cards use
  `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))` for responsive
  reflow; the steps grid uses `minmax(220px, 1fr)`. Match this auto-fit pattern
  for new grids.
- **Interactions.** Hover states use subtle `transform: translateY(...)`,
  border-color changes, and glow via `box-shadow`. Transitions are short
  (~0.2–0.3s). Keep motion restrained.
- **Responsive.** A single `@media (max-width: 768px)` block at the end of the
  `<style>` handles mobile (hides `.nav-links`, stacks the footer, tightens
  padding). Add mobile adjustments there.

## Content notes

- The site copy markets autonomous AI agents across marketing channels (social,
  Google Ads, email, SEO, lead nurturing, analytics).
- Contact / CTA links point to `mailto:hello@swarmstrong.com`. Keep contact
  details consistent if you change one (nav CTA, hero CTA, banner, footer).
- Footer copyright reads "© 2026 SwarmStrong."

## Git workflow

- Active development branch for AI-assisted changes: `claude/claude-md-docs-etapj7`.
- The default branch is `main`.
- Commit with clear, descriptive messages; push with
  `git push -u origin <branch-name>`; open a pull request for the pushed branch.

## When making changes

1. Edit `index.html` directly — there is nothing to compile.
2. Reuse existing CSS variables and the established gradient/typography system.
3. Verify visually by opening the file in a browser (and check the mobile
   breakpoint at ≤768px).
4. Keep the page a single self-contained file unless asked to restructure.
