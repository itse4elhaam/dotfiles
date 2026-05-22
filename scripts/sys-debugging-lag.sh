#!/bin/bash
set -u

OUT="/tmp/system-lag-snapshot-$(date +%Y%m%d-%H%M%S).txt"

section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

run() {
  local title="$1"
  shift

  section "$title"
  echo "\$ $*"
  echo

  timeout 12s "$@" 2>&1 || true
}

{
  section "SYSTEM LAG SNAPSHOT"
  echo "Generated: $(date)"
  echo "Hostname: $(hostname)"
  echo "User: $(whoami)"
  echo "Kernel: $(uname -a)"
  echo "Session: ${XDG_SESSION_TYPE:-unknown}"
  echo "Desktop: ${XDG_CURRENT_DESKTOP:-unknown}"
  echo "Shell: ${SHELL:-unknown}"

  run "OS RELEASE" bash -lc 'cat /etc/os-release'

  run "UPTIME AND LOAD" bash -lc 'uptime'

  run "MEMORY" bash -lc 'free -h'

  run "SWAP" bash -lc 'swapon --show; echo; cat /proc/sys/vm/swappiness'

  run "VMSTAT 10 SECOND SAMPLE" bash -lc 'vmstat 1 10'

  run "CPU TOP PROCESSES" bash -lc 'ps -eo pid,ppid,comm,cmd,%mem,%cpu --sort=-%cpu | head -50'

  run "MEMORY TOP PROCESSES" bash -lc 'ps -eo pid,ppid,comm,cmd,%mem,%cpu --sort=-%mem | head -50'

  run "NODE / LSP / EDITOR RELATED PROCESSES" bash -lc 'ps -eo pid,ppid,comm,cmd,%mem,%cpu --sort=-%cpu | grep -Ei "node|typescript|tsserver|eslint|prettier|biome|tailwind|next|turbo|opencode|nvim|vim|edge|chrome|chromium" | grep -v grep | head -80'

  run "DISK SPACE" bash -lc 'df -hT'

  run "DISK INODES" bash -lc 'df -ih'

  run "DISK IO SAMPLE" bash -lc 'if command -v iostat >/dev/null 2>&1; then iostat -xz 1 5; else echo "iostat not installed. Install with: sudo apt install sysstat"; fi'

  run "IO TOP SNAPSHOT" bash -lc 'if command -v iotop >/dev/null 2>&1; then sudo iotop -b -o -n 3 -P 2>/dev/null; else echo "iotop not installed. Install with: sudo apt install iotop"; fi'

  run "INOTIFY LIMITS" bash -lc 'cat /proc/sys/fs/inotify/max_user_watches; cat /proc/sys/fs/inotify/max_user_instances; cat /proc/sys/fs/inotify/max_queued_events'

  run "INOTIFY USAGE BY PROCESS" bash -lc '
    for pid in /proc/[0-9]*; do
      p="${pid##*/}"
      count=$(find "$pid/fd" -lname "anon_inode:inotify" 2>/dev/null | wc -l)
      if [ "$count" -gt 0 ]; then
        cmd=$(tr "\0" " " < "$pid/cmdline" 2>/dev/null)
        printf "%6s  %4s  %s\n" "$p" "$count" "${cmd:-unknown}"
      fi
    done | sort -k2 -nr | head -50
  '

  run "OPEN FILE COUNT BY PROCESS" bash -lc '
    for pid in /proc/[0-9]*; do
      p="${pid##*/}"
      count=$(ls "$pid/fd" 2>/dev/null | wc -l)
      if [ "$count" -gt 100 ]; then
        cmd=$(tr "\0" " " < "$pid/cmdline" 2>/dev/null)
        printf "%6s  %5s  %s\n" "$p" "$count" "${cmd:-unknown}"
      fi
    done | sort -k2 -nr | head -50
  '

  run "THERMALS" bash -lc 'if command -v sensors >/dev/null 2>&1; then sensors; else echo "sensors not installed. Install with: sudo apt install lm-sensors"; fi'

  run "CPU FREQUENCY" bash -lc 'grep "cpu MHz" /proc/cpuinfo | head -20'

  run "POWER PROFILE" bash -lc 'if command -v powerprofilesctl >/dev/null 2>&1; then powerprofilesctl get; powerprofilesctl list; else echo "powerprofilesctl not available"; fi'

  run "GPU / DISPLAY WARNINGS" bash -lc 'journalctl -b -p warning..err --no-pager | grep -iE "gpu|drm|i915|nvidia|amdgpu|wayland|xorg|gnome|mutter|mesa" | tail -120'

  run "SYSTEM WARNINGS / ERRORS" bash -lc 'journalctl -b -p warning..err --no-pager | tail -200'

  run "USER SERVICES THAT OFTEN CAUSE LAG" bash -lc '
    systemctl --user --no-pager --type=service --state=running | grep -Ei "tracker|evolution|gnome|portal|pipewire|wireplumber|dbus" || true
  '

  run "SYSTEM SERVICES THAT OFTEN CAUSE LAG" bash -lc '
    systemctl --no-pager --type=service --state=running | grep -Ei "packagekit|snapd|docker|containerd|tracker|updatedb|apt|fwupd|fprint|bluetooth" || true
  '

  run "RECENT OOM / KILL EVENTS" bash -lc 'journalctl -b --no-pager | grep -Ei "out of memory|oom|killed process|oom-killer" | tail -80'

  run "NVME / SMART BASIC INFO" bash -lc '
    if command -v nvme >/dev/null 2>&1; then
      sudo nvme list 2>/dev/null
      for d in /dev/nvme*n1; do
        [ -e "$d" ] && sudo nvme smart-log "$d" 2>/dev/null
      done
    else
      echo "nvme-cli not installed. Install with: sudo apt install nvme-cli"
    fi
  '

  section "END"
} > "$OUT"

echo "Snapshot saved to: $OUT"

if command -v xclip >/dev/null 2>&1; then
  xclip -selection clipboard < "$OUT"
  echo "Copied to clipboard using xclip."
elif command -v xsel >/dev/null 2>&1; then
  xsel --clipboard --input < "$OUT"
  echo "Copied to clipboard using xsel."
elif command -v wl-copy >/dev/null 2>&1; then
  wl-copy < "$OUT"
  echo "Copied to clipboard using wl-copy."
else
  echo "Could not copy to clipboard because xclip/xsel/wl-copy is not installed."
  echo "Install one with:"
  echo "  sudo apt install xclip"
fi

echo
echo "Done."
