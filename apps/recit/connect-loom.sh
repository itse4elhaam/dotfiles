#!/bin/bash
set -euo pipefail

cli_path="$HOME/.local/share/glint/twg"
if command -v twg >/dev/null; then
    cli_path="$(command -v twg)"
fi
if [[ ! -x "$cli_path" ]]; then
    echo 'Install Atlassian TWG CLI first: https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/'
    read -r -p 'Press Enter to close.'
    exit 1
fi
echo 'Connect RecIt to Loom'
echo 'Review Atlassian consent below. RecIt does not accept it on your behalf.'
"$cli_path" consent
"$cli_path" login
echo 'Connection finished. Return to RecIt to upload your recording.'
read -r -p 'Press Enter to close.'
