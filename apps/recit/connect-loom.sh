#!/bin/bash
set -euo pipefail

cli_path="${1:-$HOME/.local/share/glint/twg}"
if [[ $# -eq 0 ]] && command -v twg >/dev/null; then
    cli_path="$(command -v twg)"
fi
if [[ ! -x "$cli_path" ]]; then
    echo 'Install Atlassian TWG CLI first: https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/'
    read -r -p 'Press Enter to close.'
    exit 1
fi
echo 'Connect RecIt to Loom'
echo 'Review Atlassian consent below. RecIt does not accept it on your behalf.'
if ! "$cli_path" consent || ! "$cli_path" login; then
    echo 'Connection did not finish. No video was uploaded. Review the error above and try Connect Loom again.'
    read -r -p 'Press Enter to close.'
    exit 1
fi
echo 'Connection finished. Return to RecIt to upload your recording.'
read -r -p 'Press Enter to close.'
