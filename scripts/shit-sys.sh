#!/usr/bin/env bash
set -u

OUT="/tmp/popos_diagnose_$(date +%Y%m%d_%H%M%S).txt"

have() {
  command -v "$1" >/dev/null 2>&1
}

section() {
  printf "\n============================================================\n" >> "$OUT"
  printf "%s\n" "$1" >> "$OUT"
  printf "============================================================\n" >> "$OUT"
}

run_cmd() {
  local title="$1"
  shift
  section "$title"
  {
    echo "\$ $*"
    "$@"
  } >> "$OUT" 2>&1 || true
}

run_shell() {
  local title="$1"
  local cmd="$2"
  section "$title"
  {
    echo "\$ $cmd"
    bash -lc "$cmd"
  } >> "$OUT" 2>&1 || true
}

copy_to_clipboard() {
  if have wl-copy; then
    wl-copy < "$OUT"
    return 0
  elif have xclip; then
    xclip -selection clipboard < "$OUT"
    return 0
  elif have xsel; then
    xsel --clipboard --input < "$OUT"
    return 0
  fi
  return 1
}

echo "Pop!_OS diagnostic report" > "$OUT"
echo "Generated: $(date)" >> "$OUT"
echo "Host: $(hostname)" >> "$OUT"
echo "User: $(whoami)" >> "$OUT"
echo "Kernel: $(uname -a)" >> "$OUT"

run_cmd "UPTIME" uptime
run_cmd "TOP SNAPSHOT" top -b -n 1
run_shell "TOP 25 PROCESSES BY CPU" "ps aux --sort=-%cpu | head -n 25"
run_shell "TOP 25 PROCESSES BY MEMORY" "ps aux --sort=-%mem | head -n 25"
run_shell "PROCESSES IN D STATE" "ps -eo user,pid,ppid,stat,ni,comm,args | awk '\$4 ~ /D/ {print}'"
run_cmd "DISK USAGE" df -h
run_shell "INODE USAGE" "df -ih"
run_shell "ROOT MOUNT OPTIONS" "mount | grep ' on / '"
run_shell "BLOCK DEVICES" "lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL"
run_shell "SWAPS" "swapon --show"

run_shell "RECENT KERNEL STORAGE ERRORS" "journalctl -k -b | grep -Ei 'nvme|ext4|i/o|error|timeout|reset|blk|buffer|journal|jbd2' | tail -n 300"
run_shell "RECENT SYSTEM ERRORS PRIORITY<=3" "journalctl -p 3 -xb | tail -n 300"

run_shell "RUNNING SERVICES" "systemctl list-units --type=service --state=running"
run_shell "PACKAGEKIT / TRACKER / APPCENTER PROCESSES" "ps aux | grep -Ei 'packagekit|tracker|miner|appcenter|fwupd|snapd' | grep -v grep"

if have sensors; then
  run_cmd "TEMPERATURES" sensors
else
  section "TEMPERATURES"
  echo "sensors not installed" >> "$OUT"
fi

if have iostat; then
  run_shell "IOSTAT 3 SAMPLES" "iostat -xz 1 3"
else
  section "IOSTAT 3 SAMPLES"
  echo "iostat not installed. Install with: sudo apt install sysstat" >> "$OUT"
fi

if have iotop; then
  run_shell "IOTOP SNAPSHOT" "sudo -n iotop -oPa -b -n 3 || echo 'sudo without password required or iotop unavailable to current user'"
else
  section "IOTOP SNAPSHOT"
  echo "iotop not installed. Install with: sudo apt install iotop" >> "$OUT"
fi

if have smartctl; then
  run_shell "NVME SMART" "sudo -n smartctl -a /dev/nvme0n1 || sudo -n smartctl -a /dev/nvme0 || echo 'sudo without password required or smartctl could not read NVMe device'"
else
  section "NVME SMART"
  echo "smartctl not installed. Install with: sudo apt install smartmontools" >> "$OUT"
fi

run_shell "OPEN DELETED FILES" "sudo -n lsof +L1 || echo 'sudo without password required or lsof unavailable'"
run_shell "POSTGRES / DOCKER / OLLAMA / REDIS / MONGO PROCESSES" "ps aux | grep -Ei 'postgres|docker|containerd|ollama|redis|mongod' | grep -v grep"
run_shell "TRACKER STATUS" "tracker3 status 2>/dev/null || tracker status 2>/dev/null || echo 'tracker tool not installed'"
run_shell "APT / DPKG LOCK HOLDERS" "ps aux | grep -Ei 'apt|dpkg|packagekit' | grep -v grep"

section "SUMMARY HINTS"
{
  echo "- High wa in top means disk or filesystem wait."
  echo "- Many D-state processes means blocked I/O."
  echo "- jbd2/ext4 lines point to filesystem/journal issues."
  echo "- High await or %util in iostat points to storage saturation."
  echo "- SMART critical warnings or media errors point to NVMe health problems."
} >> "$OUT"

if copy_to_clipboard; then
  echo "Saved report to: $OUT"
  echo "Copied report to clipboard."
else
  echo "Saved report to: $OUT"
  echo "Clipboard tool not found. Install one of: wl-clipboard, xclip, or xsel"
fi
