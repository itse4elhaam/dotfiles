#!/bin/bash
set -euo pipefail

# GNOME shortcuts require a logged-in X11 desktop session.
if [[ "${XDG_SESSION_TYPE:-}" != "x11" ]]; then
  echo 'Skipping Neovim anywhere shortcuts outside X11. Run scripts/setup-nvim-anywhere from your GNOME desktop later.'
  exit 0
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for command in xdotool wmctrl xclip; do
  if ! command -v "$command" >/dev/null 2>&1; then
    sudo apt-get install -y xdotool wmctrl xclip python3-gi
    break
  fi
done
"$script_dir/../../scripts/setup-nvim-anywhere"
