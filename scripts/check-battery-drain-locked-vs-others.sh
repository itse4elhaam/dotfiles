#!/bin/bash

OUT="/tmp/popos-battery-suspend-report.txt"

{
  echo "===== SYSTEM ====="
  date
  hostnamectl
  uname -a

  echo
  echo "===== BATTERY ====="
  upower -i /org/freedesktop/UPower/devices/battery_BAT0 2>&1
  upower --dump 2>&1

  echo
  echo "===== SLEEP MODE ====="
  cat /sys/power/mem_sleep 2>&1

  echo
  echo "===== LID CONFIG ====="
  grep -R "HandleLidSwitch" /etc/systemd/logind.conf /etc/systemd/logind.conf.d/* 2>&1

  echo
  echo "===== SUSPEND / RESUME LOGS: LAST 30 DAYS ====="
  journalctl --since "30 days ago" | grep -Ei "suspend|resume|sleep|lid|PM:" 2>&1

  echo
  echo "===== PREVIOUS BOOT SUSPEND LOGS ====="
  journalctl -b -1 | grep -Ei "suspend|resume|sleep|lid|PM:" 2>&1

  echo
  echo "===== CURRENT POWER-RELATED PROCESSES ====="
  ps aux --sort=-%cpu | head -40
  ps aux --sort=-%mem | head -40

  echo
  echo "===== UPOWER HISTORY FILES ====="
  ls -lah /var/lib/upower/ 2>&1
  cat /var/lib/upower/* 2>&1

} > "$OUT"

if command -v wl-copy >/dev/null 2>&1; then
  cat "$OUT" | wl-copy
  echo "Copied report to clipboard using wl-copy."
elif command -v xclip >/dev/null 2>&1; then
  cat "$OUT" | xclip -selection clipboard
  echo "Copied report to clipboard using xclip."
elif command -v xsel >/dev/null 2>&1; then
  cat "$OUT" | xsel --clipboard --input
  echo "Copied report to clipboard using xsel."
else
  echo "Clipboard tool not found. Report saved at:"
  echo "$OUT"
fi
