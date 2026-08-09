#!/bin/bash
# Send SIGUSR2 to the opencode process to reload config without quitting.
#
# opencode registers an undocumented SIGUSR2 handler that invalidates the
# config cache and disposes all instances, forcing the TUI to re-bootstrap
# and re-read config/commands/agents from disk.
# See docs/opencode-reload-restart.md for the source-level evidence.
#
# Caveat: this disposes in-memory instance state; sessions reload from storage.
set -euo pipefail

pid=$$
while [ -n "$pid" ] && [ "$pid" -ne 1 ]; do
  name=$(ps -o comm= -p "$pid" 2>/dev/null | tr -d ' ')
  if [ "$name" = "opencode" ]; then
    kill -USR2 "$pid"
    echo "SIGUSR2 sent to opencode (pid $pid) - config reloaded, TUI re-bootstrapping."
    exit 0
  fi
  pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
done

echo "ERROR: could not locate the opencode process in the ancestor chain" >&2
exit 1
