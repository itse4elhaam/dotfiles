#!/bin/bash
set -euo pipefail

app_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data_dir="$HOME/.local/share/glint"
command -v uv >/dev/null || { echo 'Install uv before running this installer.' >&2; exit 1; }
command -v obs >/dev/null || { echo 'RecIt needs OBS Studio 27 and its plugins.' >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg before running this installer.' >&2; exit 1; }
mkdir -p "$data_dir" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
if [[ ! -x "$data_dir/venv/bin/python" ]]; then
    uv venv "$data_dir/venv"
fi
uv pip install --python "$data_dir/venv/bin/python" -r "$app_dir/requirements.txt"
ln -sfn "$app_dir/recit" "$HOME/.local/bin/recit"
ln -sfn "$app_dir/assets/recit-mark.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/tech.truedevs.RecIt.svg"
cat > "$HOME/.local/share/applications/tech.truedevs.RecIt.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=RecIt
GenericName=Screen and Camera Recorder
Comment=Record an explanation. Share it with Loom.
Exec="$HOME/.local/bin/recit"
Icon=tech.truedevs.RecIt
Terminal=false
Categories=AudioVideo;Video;Recorder;
Keywords=record;screen;camera;loom;video;explainer;
StartupNotify=true
StartupWMClass=RecIt
EOF
if command -v update-desktop-database >/dev/null; then
    update-desktop-database "$HOME/.local/share/applications"
fi
echo 'RecIt is installed. Find it in your app launcher, or run recit.'
