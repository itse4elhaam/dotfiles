#!/usr/bin/env bash
set -u

OUT="/tmp/pop_sleep_keyring_diag_$(date +%Y%m%d_%H%M%S).txt"

have() {
  command -v "$1" >/dev/null 2>&1
}

section() {
  {
    printf "\n============================================================\n"
    printf "%s\n" "$1"
    printf "============================================================\n"
  } >> "$OUT"
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

{
  echo "Pop!_OS Sleep / Hibernate / Lid / Keyring Diagnostic"
  echo "Generated: $(date)"
  echo "Host: $(hostname)"
  echo "User: $(whoami)"
  echo "Kernel: $(uname -a)"
} > "$OUT"

run_cmd "UPTIME" uptime
run_shell "OS RELEASE" "cat /etc/os-release"
run_shell "DESKTOP SESSION" "echo XDG_CURRENT_DESKTOP=\$XDG_CURRENT_DESKTOP; echo DESKTOP_SESSION=\$DESKTOP_SESSION; echo XDG_SESSION_TYPE=\$XDG_SESSION_TYPE"
run_shell "HARDWARE MODEL" "cat /sys/devices/virtual/dmi/id/{sys_vendor,product_name,product_version,board_name,bios_version,bios_date} 2>/dev/null"

run_shell "LID STATE" "find /proc/acpi/button/lid -type f 2>/dev/null -name state -exec sh -c 'echo FILE:{}; cat {}' \\; || echo 'No /proc/acpi/button/lid state found'"
run_shell "UPOWER DEVICES" "upower -e 2>/dev/null | while read -r d; do echo '---'; echo \$d; upower -i \$d; done"

run_shell "SUPPORTED POWER STATES" "echo '/sys/power/state:'; cat /sys/power/state; echo; echo '/sys/power/mem_sleep:'; cat /sys/power/mem_sleep 2>/dev/null || true; echo; echo '/sys/power/disk:'; cat /sys/power/disk 2>/dev/null || true"

run_shell "SYSTEMD SLEEP TARGETS" "systemctl status sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target --no-pager || true"
run_shell "CAN SYSTEM HIBERNATE" "systemctl hibernate --help >/dev/null 2>&1; echo 'systemctl hibernate command exists'; loginctl show-session \$XDG_SESSION_ID -p IdleHint 2>/dev/null || true"

run_shell "SWAP / RESUME SETUP" "swapon --show; echo; echo 'Resume parameters from kernel cmdline:'; cat /proc/cmdline; echo; echo '/etc/initramfs-tools/conf.d/resume:'; cat /etc/initramfs-tools/conf.d/resume 2>/dev/null || echo 'missing'; echo; echo 'findmnt /:'; findmnt / -o SOURCE,FSTYPE,OPTIONS; echo; echo 'findmnt swap:'; findmnt -t swap -o SOURCE,FSTYPE,SIZE,USED,OPTIONS || true"

run_shell "LOGIND CONFIG" "grep -nE '^(HandleLidSwitch|HandleLidSwitchExternalPower|HandleLidSwitchDocked|LidSwitchIgnoreInhibited|IdleAction|IdleActionSec)=' /etc/systemd/logind.conf /etc/systemd/logind.conf.d/* 2>/dev/null || echo 'No explicit lid settings found'"
run_shell "LOGINCTL LID SETTINGS (if exposed)" "loginctl show-logind 2>/dev/null | grep -Ei 'HandleLidSwitch|LidSwitchIgnoreInhibited|IdleAction|IdleActionUSec' || true"

run_shell "SYSTEMD INHIBITORS" "systemd-inhibit --list || true"

run_shell "RECENT SUSPEND / HIBERNATE JOURNAL" "journalctl -b --no-pager | grep -Ei 'suspend|resume|hibernate|sleep|PM:|ACPI: button/lid|lid closed|lid open|systemd-sleep|failed to suspend|failed to hibernate' | tail -n 400"
run_shell "KERNEL POWER JOURNAL" "journalctl -k -b --no-pager | grep -Ei 'suspend|resume|hibernate|sleep|s2idle|deep|ACPI|PM:|LID|button/lid|freeze' | tail -n 400"

run_shell "GNOME POWER SETTINGS" "gsettings list-recursively org.gnome.settings-daemon.plugins.power 2>/dev/null || echo 'No GNOME power schema available'"
run_shell "GNOME SESSION / SCREENSAVER SETTINGS" "gsettings list-recursively org.gnome.desktop.screensaver 2>/dev/null; echo; gsettings list-recursively org.gnome.desktop.session 2>/dev/null || true"

run_shell "GDM / PAM KEYRING HOOKS" "grep -n 'pam_gnome_keyring.so' /etc/pam.d/gdm-password /etc/pam.d/login /etc/pam.d/passwd /etc/pam.d/common-auth /etc/pam.d/common-session 2>/dev/null || true"
run_shell "GNOME KEYRING PACKAGES" "dpkg -l | grep -Ei 'gnome-keyring|libpam-gnome-keyring|seahorse' || true"
run_shell "GNOME KEYRING USER SERVICES" "systemctl --user --no-pager --all | grep -Ei 'keyring|secret|gnome-keyring' || true"
run_shell "SECRET SERVICE ENV" "env | grep -Ei 'keyring|ssh_auth_sock|gnome' || true"

run_shell "KEYRING FILES" "ls -la ~/.local/share/keyrings 2>/dev/null || echo 'No local keyrings dir'; echo; find ~/.local/share/keyrings -maxdepth 1 -type f 2>/dev/null -printf '%f\n' || true"

run_shell "LAST BOOT ERRORS RELATED TO KEYRING / GDM / PAM" "journalctl -b --no-pager | grep -Ei 'keyring|gnome-keyring|pam_gnome_keyring|gdm-password|seahorse|secret service' | tail -n 300"

run_shell "TOP SNAPSHOT" "top -b -n 1 | head -n 80"

section "SUMMARY HINTS"
{
  echo "- If /sys/power/mem_sleep shows [s2idle] only, deep sleep may not be available."
  echo "- Hibernate needs working swap plus a valid resume= kernel/initramfs setup."
  echo "- systemd-inhibit can reveal GNOME or apps blocking lid-close suspend."
  echo "- HandleLidSwitch in logind.conf is the main lid-close action source."
  echo "- If keyring prompts appear after unlock, login and keyring passwords may be mismatched, or PAM/keyring unlock on login/resume is failing."
} >> "$OUT"

if copy_to_clipboard; then
  echo "Saved report to: $OUT"
  echo "Copied report to clipboard."
else
  echo "Saved report to: $OUT"
  echo "Clipboard tool not found. Install one of: wl-clipboard, xclip, or xsel"
fi
