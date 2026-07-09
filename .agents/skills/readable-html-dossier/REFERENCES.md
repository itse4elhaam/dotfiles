# Browser detection & tab opening

## Overview

After creating the HTML dossier, open it in the user's browser by: (1) detecting which browser is running, (2) converting the file path to a `file://` URL, (3) opening it as a new tab.

## Step by step

### 1. Detect which browser is running

Check for running browser processes using `pgrep`. Order by likelihood:

```bash
pgrep -x chrome >/dev/null 2>&1 && echo "chrome"
pgrep -x firefox >/dev/null 2>&1 && echo "firefox"
pgrep -x brave >/dev/null 2>&1 && echo "brave"
pgrep -x msedge >/dev/null 2>&1 && echo "edge"
```

Common process names per browser:

| Browser | Process name(s) | Command |
|---------|----------------|---------|
| Chrome  | `chrome`, `google-chrome`, `chromium`, `chromium-browser` | `google-chrome`, `google-chrome-stable`, `chromium` |
| Firefox | `firefox`, `firefox-esr` | `firefox` |
| Brave   | `brave` | `brave-browser` |
| Edge    | `msedge`, `microsoft-edge` | `microsoft-edge`, `msedge` |

> **Multiple browsers open?** Prefer Chrome, then Brave, then Edge, then Firefox (most-to-least likely for this user). Or use the one specified by the user if they mentioned one.

> **No browser open?** Fall back to `xdg-open` (Linux) or `open` (macOS). These use the OS default browser.

### 2. Convert path to file:// URL

```bash
# Absolute path from the write step, e.g. /tmp/dossier.html
# Convert to file:// URL
file_url="file://$(realpath "$html_path")"
```

`realpath` resolves symlinks and normalises the path. The `file://` prefix lets browsers open local files.

### 3. Open as new tab

For each browser, use the `--new-tab` flag with the file URL:

```bash
# Chrome / Chromium
google-chrome --new-tab "$file_url"
google-chrome-stable --new-tab "$file_url"

# Firefox
firefox --new-tab "$file_url"

# Brave
brave-browser --new-tab "$file_url"

# Edge
microsoft-edge --new-tab "$file_url"
# or
msedge --new-tab "$file_url"

# Fallback (OS default browser)
xdg-open "$file_url"   # Linux
open "$file_url"        # macOS
```

### 4. Complete script pattern

```bash
html_path="/path/to/dossier.html"
file_url="file://$(realpath "$html_path")"

if pgrep -x google-chrome >/dev/null 2>&1 || pgrep -x chrome >/dev/null 2>&1; then
  google-chrome --new-tab "$file_url"
elif pgrep -x brave >/dev/null 2>&1; then
  brave-browser --new-tab "$file_url"
elif pgrep -x msedge >/dev/null 2>&1 || pgrep -x microsoft-edge >/dev/null 2>&1; then
  microsoft-edge --new-tab "$file_url"
elif pgrep -x firefox >/dev/null 2>&1 || pgrep -x firefox-esr >/dev/null 2>&1; then
  firefox --new-tab "$file_url"
else
  xdg-open "$file_url"
fi
```

## Notes

- `--new-tab` may fail if no browser window is open; some browsers open a new window instead. That's acceptable.
- `realpath` requires `coreutils`. On macOS, use `grealpath` from `brew install coreutils`, or construct the URL manually.
- Prefer `pgrep` over `ps | grep` — it's cleaner and avoids false matches.

---

# Typography

## Font pairing

| Use case | Font | Weight | CSS |
|----------|------|-------:|-----|
| Body text / prose | **Source Sans 3** | 400 | `1.125rem/1.7 "Source Sans 3", system-ui, sans-serif` |
| Headings | **Inter** | 650 | `family: Inter; weight: 650; letter-spacing: -0.02em` |
| Key concepts / labels | **Source Sans 3** | 600 | `weight: 600` in body font |
| Code blocks | **JetBrains Mono** | 400 | `font: .875rem/1.6 "JetBrains Mono", monospace` |
| Inline code / identifiers | **JetBrains Mono** | 400 | `font-size: 0.9em` of body |

## Design rationale

- **Source Sans 3** was designed for UI environments — open, calm letterforms that make long paragraphs feel airy rather than dense. It is the primary reading face.
- **Inter** has a high x-height and geometric clarity suited for headings, callouts, navigation, and interface-like labels. Avoid using Inter for body paragraphs — it projects a "software UI" personality.
- **JetBrains Mono** was designed specifically for developer readability: wide characters, obvious punctuation, deliberate letterforms that remain crisp at small sizes. Use exclusively for code, terminal output, filenames, paths, and identifiers.
- The font switch itself is semantic punctuation: *this is explanation → now this is executable thought.*

## Loading from Google Fonts

Use a single `@import` in the `<style>` block:

```css
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Inter:wght@400;650&family=JetBrains+Mono:wght@400;500&display=swap');
```

`@import` must appear before any other CSS rules in the `<style>` block.

## Spacing

- **Body text:** 18px (1.125rem), line-height 1.7
- **Code blocks:** 14px (0.875rem), line-height 1.6, horizontal scroll instead of wrapping
- **Inline code:** 0.9em of body size
- **Main prose column:** 760px max-width (not 65ch — at 18px that would be ~1170px)
- **Vertical spacing:** generous between conceptual sections; use margins on headings and cards

## Config reference

```css
:root {
  --font-body: "Source Sans 3", system-ui, sans-serif;
  --font-heading: "Inter", "Source Sans 3", system-ui, sans-serif;
  --font-code: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}

body {
  font-family: var(--font-body);
  font-size: 18px;
  line-height: 1.7;
  font-weight: 400;
}

h1, h2, h3, h4 {
  font-family: var(--font-heading);
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

p, li {
  line-height: 1.7;
}

code, pre {
  font-family: var(--font-code);
}

pre {
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
}

:not(pre) > code {
  font-size: 0.9em;
}
```

## Anti-patterns

- ❌ Do not render explanatory prose in monospace.
- ❌ Do not use decorative/display fonts.
- ❌ Do not use thin font weights (< 400) for body text.
- ❌ Do not make the prose column wider than 780px.
- ❌ Do not wrap long code lines — use horizontal scrolling instead.
