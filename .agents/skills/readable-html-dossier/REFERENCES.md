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
