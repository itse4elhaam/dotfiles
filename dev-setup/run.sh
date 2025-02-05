#!/bin/bash

if ! command -v apt-get &> /dev/null && ! command -v dpkg &> /dev/null; then
  echo "This script is intended for apt-based systems. Exiting..."
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

filter=""

dry=0

while [[ $# -gt 1 ]]; do
  if [[ $1 == "--dry" ]]; then
    dry=1
  else 
    filter="$1"
  fi
  # what does this do? this is probably not working
  shift
done


log(){
  if [[ $dry == 1 ]]; then
    echo "[DRY_RUN]: $*"
    return
  fi

  echo "$@"
}

execute(){
  log "execute $*"
  if [[ $dry == 1 ]]; then
    return
  fi

  # this will just execute it
  "$@"
}

log "$script_dir -- $filter"

# what does this do
cd "$script_dir" || exit
runs_dir="./runs"

if [ ! -d "$runs_dir" ]; then
  log "$runs_dir does not exist"
  exit 1
fi

scripts="$(find $runs_dir -maxdepth 1 -mindepth 1 -type f)"

for script in $scripts; do
  # v here inverts it and says if it does not contain it
  if echo "$script" | grep -qv "$filter"; then
    log "filtering $script"
    continue 
  fi

  execute ./"$script"
done
