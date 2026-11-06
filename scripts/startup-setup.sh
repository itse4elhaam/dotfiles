#!/bin/bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
exec /usr/bin/python3 "$script_dir/desktop-recovery" recover
