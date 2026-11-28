#!/bin/bash
set -euo pipefail

if (( $# > 1 )); then
    echo "Usage: $0 [directory-containing-model-files]" >&2
    exit 2
fi
source_dir="${1:-}"
model_dir="${XDG_DATA_HOME:-$HOME/.local/share}/desktop-dictation/models"
install -d "$model_dir"
exec 9>"$model_dir/.install.lock"
flock 9
staged=""
trap '[[ -z "$staged" ]] || rm -f -- "$staged"' EXIT

install_model() {
    local repo="$1" revision="$2" name="$3" sha="$4"
    local destination="$model_dir/$name"
    if [[ -f "$destination" && ! -L "$destination" ]] &&
       [[ "$(sha256sum < "$destination")" == "$sha  -" ]]; then
        echo "Model ready: $name"
        return
    fi
    staged="$(mktemp --tmpdir="$model_dir" ".$name.XXXXXX")"
    if [[ -n "$source_dir" ]]; then
        cp --reflink=auto -- "$source_dir/$name" "$staged"
    else
        curl --fail --location --retry 2 --proto '=https' --proto-redir '=https' \
             --output "$staged" "https://huggingface.co/$repo/resolve/$revision/$name"
    fi
    if [[ "$(sha256sum < "$staged")" != "$sha  -" ]]; then
        echo "Checksum mismatch for $name" >&2
        return 1
    fi
    mv -T -- "$staged" "$destination"
    staged=""
    echo "Installed $name"
}

install_model handy-computer/parakeet-unified-en-0.6b-gguf 7e948f21b7bdbac698d3318db9d350f1096f3b6c \
    parakeet-unified-en-0.6b-Q8_0.gguf 4b50b6dd862bf6e346929aaf4f5eaacec003bfa3f56462d6c874b41ef2f38795
install_model handy-computer/silero-vad-v6.2-gguf 97bbd75179f535e4708bccdf61e9278b8b60dfc7 \
    silero-vad-v6.2-F32.gguf 0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6
