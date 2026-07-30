# Readable HTML dossier reference

Load the section named by `SKILL.md` only when that step is active.

## Visual contract

Use this normative presentation contract:

- Body: system sans-serif stack, `1.125rem/1.7`, prose width `min(65ch, 100% - 2rem)`.
- Headings: system sans-serif stack, weight `650`, line height `1.2`, letter spacing `-.02em`.
- Code: system monospace stack, `.875rem/1.6`, with horizontal overflow contained by the code block.
- Theme: softened dark colors by default; define light mode through CSS variables and `data-theme="light"`.
- Layout: semantic landmarks and ordered headings; tables only for tabular data; no page-level horizontal overflow at narrow widths or 200% zoom.
- Links: visibly underlined and distinguishable without color alone.
- Print: force a light palette and expose external URLs.
- Dependencies: inline required CSS and JavaScript. Use a CDN only when a diagram genuinely requires Mermaid; the report remains readable when that resource is unavailable.
- Text size floors: body text minimum effective rendered size 18px; secondary, label, and metadata text minimum 14px. When a control's text would fall below the minimum, enlarge the control rather than shrinking the text.
- Responsive layout: above 768px viewport width use the full width with sidebar or columnar hierarchy as the dossier structure requires. At or below 768px, switch to single-column with no sidebar; search and filter controls appear inline at section tops.

Minimal scaffold:

```html
<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dossier</title>
  <style>
    :root{color-scheme:dark light;--bg:#121212;--panel:#1b1b1b;--text:#e6e1d9;--muted:#aaa39a;--accent:#8ab4ff;--border:#333;--font-body:system-ui,-apple-system,"Segoe UI",sans-serif;--font-code:ui-monospace,"SFMono-Regular",Consolas,monospace}
    [data-theme="light"]{--bg:#fafafa;--panel:#fff;--text:#1f1f1f;--muted:#5f5f5f;--accent:#0057b3;--border:#ddd}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:400 1.125rem/1.7 var(--font-body)}
    main{max-width:min(65ch,100% - 2rem);margin:auto;padding:clamp(1.5rem,4vw,4rem) 0}
    .card{background:var(--panel);border:1px solid var(--border);border-radius:1rem;padding:1.25rem;margin:1rem 0}
    h1,h2,h3{font-weight:650;line-height:1.2;letter-spacing:-.02em} a{color:var(--accent);text-decoration:underline}
    code{font-family:var(--font-code);font-size:.9em} pre{font:400 .875rem/1.6 var(--font-code);overflow-x:auto;max-width:100%}
    button,input,select,textarea,progress{font:inherit;max-width:100%} button,input,select,textarea{padding:.5em .75em} input,select,textarea{width:min(100%,30rem)} progress,input[type="range"]{width:min(100%,24rem);min-height:1em}
    :focus-visible{outline:3px solid var(--accent);outline-offset:3px}
    @media (prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
    @media print{body{background:#fff!important;color:#000!important;font-size:11pt}.card{break-inside:avoid}a[href^="http"]::after{content:" (" attr(href) ")";font-size:.85em}}
  </style>
</head>
<body><main><article><h1>Dossier title</h1></article></main></body>
</html>
```

## Reading progress tracker

The dossier reports reading progress to its opener window via `postMessage` when one exists. A directly opened dossier without an opener uses manual fallback progress.

Serialize the complete metadata object, then replace HTML-sensitive characters before inserting that complete result as the metadata block's text:

```javascript
const serializedMetadata = JSON.stringify({ documentId })
  .replace(/</g, "\\u003c")
  .replace(/>/g, "\\u003e")
  .replace(/&/g, "\\u0026")
  .replace(/\u2028/g, "\\u2028")
  .replace(/\u2029/g, "\\u2029");
```

This is data serialization, not HTML escaping. Do not wrap `serializedMetadata` in additional quotes.

```html
<script id="dossier-metadata" type="application/json">SERIALIZED_METADATA_OBJECT</script>
<script>
(() => {
  const metadata = document.getElementById("dossier-metadata");
  const headings = [...document.querySelectorAll("main h2[id], main h3[id]")];
  let documentId;
  let shortDocumentTimer;
  let greatestReported = -1;
  let lastReportedHeadingId = null;

  try {
    ({ documentId } = JSON.parse(metadata.textContent));
  } catch (error) {
    console.warn("Read tracking metadata is invalid", error);
    return;
  }

  const currentHeadingId = () => {
    const readingLine = Math.min(window.innerHeight * 0.35, 240);
    let current = null;
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top > readingLine) break;
      current = heading.id;
    }
    return current;
  };

  const reportProgress = (progress) => {
    if (!window.opener || window.opener.closed) return;
    const milestone = progress === 100 ? 100 : Math.floor(progress / 5) * 5;
    const lastHeadingId = currentHeadingId();
    if (milestone <= greatestReported && lastHeadingId === lastReportedHeadingId) return;
    greatestReported = Math.max(greatestReported, milestone);
    lastReportedHeadingId = lastHeadingId;
    window.opener.postMessage({
      type: "dossier:progress",
      documentId,
      progress: greatestReported,
      lastHeadingId
    }, "*");
  };

  const measureProgress = () => {
    const root = document.documentElement;
    const maximum = root.scrollHeight - root.clientHeight;
    if (maximum <= 1) return null;
    const atEnd = Math.abs(maximum - root.scrollTop) <= 1;
    return atEnd ? 100 : Math.min(99, Math.floor((root.scrollTop / maximum) * 100));
  };

  const updateProgress = () => {
    const progress = measureProgress();
    if (progress !== null) reportProgress(progress);
  };

  const scheduleShortDocument = () => {
    window.clearTimeout(shortDocumentTimer);
    if (measureProgress() !== null || document.visibilityState !== "visible") return;
    shortDocumentTimer = window.setTimeout(() => reportProgress(100), 3000);
  };

  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("resize", () => {
    updateProgress();
    scheduleShortDocument();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") scheduleShortDocument();
    else window.clearTimeout(shortDocumentTimer);
  });
  updateProgress();
  scheduleShortDocument();
})();
</script>
```

Local-file origins may be opaque, so this sender must use `"*"` as the target origin. This sender emits milestone changes rather than every scroll event.

## Browser opening

Open local output directly; no server or browser automation is part of delivery.

1. Resolve and serialize the file URI safely with an installed Python executable:

   ```bash
   python_cmd="$(command -v python3 || command -v python)"
   file_url="$("$python_cmd" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$html_path")"
   ```

2. Detect a running browser in this order: Edge, Chrome/Chromium, Brave, Firefox, and resolve its matching installed executable.
3. Open a new tab with that executable; use `xdg-open "$file_url"` on Linux or `open "$file_url"` on macOS when no matching executable is available.

```bash
browser_cmd=""
if pgrep -x msedge >/dev/null 2>&1 || pgrep -x microsoft-edge >/dev/null 2>&1; then
  browser_cmd="$(command -v microsoft-edge || command -v msedge || true)"
elif pgrep -x google-chrome >/dev/null 2>&1 || pgrep -x chrome >/dev/null 2>&1; then
  browser_cmd="$(command -v google-chrome || command -v google-chrome-stable || true)"
elif pgrep -x chromium >/dev/null 2>&1 || pgrep -x chromium-browser >/dev/null 2>&1; then
  browser_cmd="$(command -v chromium || command -v chromium-browser || true)"
elif pgrep -x brave >/dev/null 2>&1 || pgrep -x brave-browser >/dev/null 2>&1; then
  browser_cmd="$(command -v brave-browser || command -v brave || true)"
elif pgrep -x firefox >/dev/null 2>&1 || pgrep -x firefox-esr >/dev/null 2>&1; then
  browser_cmd="$(command -v firefox || command -v firefox-esr || true)"
fi

if [[ -n "$browser_cmd" ]]; then
  "$browser_cmd" --new-tab "$file_url"
elif [[ "$(uname -s)" == "Darwin" ]]; then
  open "$file_url"
else
  xdg-open "$file_url"
fi
```

Do not use Playwright, Puppeteer, Selenium, or any visible automated browser. Do not take screenshots or perform exhaustive interaction testing. The single verification pass in Step 6 is the only check needed.
