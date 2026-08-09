#!/bin/bash
# Dump the clipboard image to a file so opencode can reference it with @path.
#
# Why this exists: opencode TUI image paste (Ctrl+V) silently fails when the
# terminal doesn't pipe image bytes through bracketed paste — Ghostty, Kitty,
# WezTerm, tmux are all text-only by design. The opencode keyboard-paste path
# never reads the X11/Wayland clipboard itself (upstream issues #4077, #25806).
# This script is the in-band workaround: it reads the image directly from the
# clipboard and the /paste-image command attaches the resulting file.
set -euo pipefail

OUT="/tmp/opencode-clipboard-image.png"

# Wayland
if command -v wl-paste >/dev/null 2>&1 && [ -n "${WAYLAND_DISPLAY:-}" ]; then
  if wl-paste --type image/png > "$OUT" 2>/dev/null && [ -s "$OUT" ]; then
    echo "Image saved to $OUT"
    exit 0
  fi
fi

# X11 via xclip
if command -v xclip >/dev/null 2>&1; then
  if xclip -selection clipboard -t image/png -o > "$OUT" 2>/dev/null && [ -s "$OUT" ]; then
    echo "Image saved to $OUT"
    exit 0
  fi
fi

# X11 via xsel (fallback)
if command -v xsel >/dev/null 2>&1; then
  if xsel --clipboard --target image/png --output > "$OUT" 2>/dev/null && [ -s "$OUT" ]; then
    echo "Image saved to $OUT"
    exit 0
  fi
fi

echo "ERROR: No image found in clipboard" >&2
exit 1
