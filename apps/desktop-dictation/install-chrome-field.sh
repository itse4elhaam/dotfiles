#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.local/share/desktop-dictation"
hosts="${XDG_CONFIG_HOME:-$HOME/.config}/google-chrome/NativeMessagingHosts"
install -d "$dest/chrome-field" "$hosts"
install -m 644 "$here/browser_field.py" "$dest/"
install -m 755 "$here/field_host.py" "$dest/"
install -m 644 "$here/chrome-field/"{manifest.json,arm.js,field.js} "$dest/chrome-field/"
python3 - "$here/chrome-field/host.json" "$dest/field_host.py" "$hosts" <<'PY'
import json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
manifest["path"] = sys.argv[2]
(Path(sys.argv[3]) / (manifest["name"] + ".json")).write_text(json.dumps(manifest))
PY
echo "In chrome://extensions, enable Developer mode and Load unpacked: $dest/chrome-field"
