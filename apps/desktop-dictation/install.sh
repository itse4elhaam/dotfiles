#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
install -d "$HOME/.local/share/desktop-dictation" "$HOME/.config/systemd/user"
for file in dictate.py overlay.py glow.py literal.py selection.py forest.jpg transcribe.cjs; do
    install -m 644 "$here/$file" "$HOME/.local/share/desktop-dictation/$file"
done
install -d "$HOME/.local/share/desktop-dictation/fonts"
install -m 644 "$here/fonts/Inter-latin-variable.ttf" "$here/fonts/OFL.txt" "$HOME/.local/share/desktop-dictation/fonts/"
install -Dm644 "$here/last-dictation.desktop" "$HOME/.local/share/applications/last-dictation.desktop"
unit="desktop-dictation.service"
source_unit="$here/../../.config/systemd/user/$unit"
destination="$HOME/.config/systemd/user/$unit"
if [[ ! "$source_unit" -ef "$destination" ]]; then
    install -m 644 "$source_unit" "$destination"
fi
systemctl --user daemon-reload
systemctl --user enable "$unit"
systemctl --user restart "$unit"
