#!/bin/bash

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

filter="$1"

echo "$script_dir -- $filter"

# what does this do
cd "$script_dir" || exit
runs_dir="./runs"

if [ ! -d "$runs_dir" ]; then
  echo "$runs_dir does not exist"
  exit 1
fi

scripts="$(find $runs_dir -maxdepth 1 -mindepth 1 -type f)"

for script in $scripts; do
  # v here inverts it and says if it does not contain it
  if echo "$script" | grep -qv "$filter"; then
    echo "filtering $script"
    continue 
  fi

  ./"$script"
done
