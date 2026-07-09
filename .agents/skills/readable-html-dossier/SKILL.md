---
name: readable-html-dossier
description: Use when creating a standalone HTML report, dossier, investigation brief, review findings document, or human-readable context page from agent research.
---

# Readable HTML Dossier

Create a self-contained HTML document optimized for humans reading dense context. Default to dark theme; support light mode through CSS variables and add a visible toggle only when the report is meant for interactive theme switching.

## Design contract

- **Reading first:** body text targets `65ch`, line-height `1.6–1.75`, 16–18px equivalent via `rem`/`clamp()`.
- **Responsive by default:** no horizontal scrolling at normal zoom, 200% zoom, or laptop widths.
- **Dark default:** use softened dark colors, not pure black/white. Light mode must be available through CSS variables and `data-theme="light"`; visible toggles are optional unless interactivity is required.
- **Standalone:** inline CSS; no build step. Only use CDN scripts when diagrams genuinely need Mermaid.
- **Semantic:** `main`, `section`, `article`, headings in order, tables only for tabular data.
- **Context-rich:** include background, evidence, uncertainty, and domain links when those help a human make a decision.

## Workflow

1. **Choose the reader job.** Decide whether the dossier is for decision, review, onboarding, debugging, or audit.
   Completion: the title and first paragraph say what a human can decide after reading.

2. **Shape the document.** Use this default order:
   - Executive summary
   - Background context
   - Findings or evidence cards
   - Recommended actions
   - Open questions / stale items
   - Source links and domain documents
   Completion: every major section has a clear reader purpose.

3. **Write the HTML.** Save where the caller asks; use `/tmp` only for explicitly one-off reports and always report the path.
   Completion: the file opens directly in a browser without a server.

4. **Verify readability.** Check line length, heading order, contrast, zoom/reflow, and print behavior.
   Completion: the document remains readable on a laptop, large monitor, and browser zoom.

5. **Open in browser (default).** Detect which browser is open (Chrome, Firefox, Brave, Edge, etc.), collect the absolute path of the HTML document, and open it as a new tab in that browser. Skip this step only if the user explicitly asks not to open it.
   Completion: the dossier is open in the user's browser for immediate reading.
   See [REFERENCES.md](REFERENCES.md) for the exact detection and opening process per browser.

## Minimal scaffold

```html
<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dossier</title>
  <style>
    :root{color-scheme:dark light;--bg:#121212;--panel:#1b1b1b;--text:#e6e1d9;--muted:#aaa39a;--accent:#8ab4ff;--border:#333}
    [data-theme="light"]{--bg:#fafafa;--panel:#fff;--text:#1f1f1f;--muted:#5f5f5f;--accent:#0057b3;--border:#ddd}
    body{margin:0;background:var(--bg);color:var(--text);font:clamp(1rem,.94rem+.21vw,1.125rem)/1.7 system-ui,-apple-system,Segoe UI,sans-serif}
    main{max-width:min(72rem,100% - 2rem);margin:auto;padding:clamp(1.5rem,4vw,4rem) 0}
    .prose{max-width:65ch}.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:1.25rem;margin:1rem 0}
    h1,h2,h3{line-height:1.2} a{color:var(--accent)} code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
    @media print{body{background:#fff!important;color:#000!important;font-size:11pt}.card{break-inside:avoid}a[href^="http"]::after{content:" (" attr(href) ")";font-size:.85em}}
  </style>
</head>
<body><main><article class="prose"><h1>Dossier title</h1></article></main></body>
</html>
```

## Evidence writing

Each finding should answer:
- What happened?
- Why does it matter?
- What evidence supports it?
- What should a human or agent do next?
- What could make this stale?

Use tables for comparisons, cards for findings, and callouts for uncertainty. Do not bury actions inside prose.

## Quality checks

- Body text column stays near 45–75 characters.
- Contrast meets WCAG AA; aim higher for long reading.
- Links are underlined or otherwise not color-only.
- Print stylesheet forces light background and exposes URLs.
- Empty sections are removed.
