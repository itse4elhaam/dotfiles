#!/bin/bash

set -u

OUT="/tmp/hardware-vs-workload-diagnosis-$(date +%Y%m%d-%H%M%S).txt"

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

  timeout 20s "$@" 2>&1 || true
}

copy_to_clipboard() {
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
    echo "Could not copy to clipboard."
    echo "Install one of these:"
    echo "  sudo apt install xclip"
    echo "  sudo apt install xsel"
    echo "  sudo apt install wl-clipboard"
  fi
}

{
  section "CONTEXT FOR CHATGPT"

  cat <<'CTX'
Problem:
- System lag happens mostly when opencode is running actively and Neovim is open alongside it.
- RAM and CPU do not look fully exhausted at a high level, but the desktop, Neovim, Edge, and opencode feel laggy.
- There has been recurring disk I/O wait before.
- User suspects this may be a hardware/NVMe issue, but the pattern strongly correlates with opencode + Neovim workload.

Previous snapshot findings:
- Two opencode processes were active at the same time.
- opencode was consuming high CPU, roughly 50%+ and 30%+ in different snapshots.
- Neovim, tsserver/tsgo, biome, Edge, Discord, and GNOME were also active.
- Disk space was okay: root partition had around 59GB free.
- I/O wait was around 9 to 10%, with previous spikes higher.
- In one live snapshot, vmstat showed wa around 10%, but nvme %util was only around 1.3% at that exact moment.
- Swap/zram usage increased from around 1.8Gi to around 3Gi.
- swappiness was 180.
- System uses Pop!_OS 22.04, GNOME/X11, encrypted /dev/mapper root, zram swap, and NVMe.
- NVMe temperature previously showed composite around 60.9°C and one sensor around 84.8°C.
- The goal of this script is to prove whether this is:
  1. hardware/NVMe failure,
  2. NVMe thermal throttling,
  3. zram/swap pressure,
  4. dm-crypt/encrypted disk overhead,
  5. opencode + Neovim + TypeScript/Biome watcher contention,
  6. or background services causing disk noise.

Important interpretation target:
- If NVMe errors/warnings/resets exist, hardware becomes more likely.
- If lag appears only with opencode + Neovim and disappears when they are closed, workload contention is more likely.
- If iowait is high while nvme %util is low, investigate swap/zram, dm-crypt, small synchronous I/O, scheduler pressure, and blocked tasks.
- If NVMe temperature rises near throttle range during lag, thermal throttling becomes likely.
CTX

  section "SYSTEM SUMMARY"
  echo "Generated: $(date)"
  echo "Hostname: $(hostname)"
  echo "User: $(whoami)"
  echo "Kernel: $(uname -a)"
  echo "Session: ${XDG_SESSION_TYPE:-unknown}"
  echo "Desktop: ${XDG_CURRENT_DESKTOP:-unknown}"
  echo "Shell: ${SHELL:-unknown}"

  run "OS RELEASE" bash -lc 'cat /etc/os-release'

  run "UPTIME / LOAD" bash -lc 'uptime'

  run "MEMORY / SWAP / SWAPPINESS" bash -lc '
    free -h
    echo
    swapon --show
    echo
    echo "vm.swappiness=$(cat /proc/sys/vm/swappiness)"
    echo "zswap enabled:"
    cat /sys/module/zswap/parameters/enabled 2>/dev/null || true
  '

  run "VMSTAT BASELINE 15 SECOND SAMPLE" bash -lc 'vmstat 1 15'

  run "PSI PRESSURE STALL INFO" bash -lc '
    echo "--- CPU pressure ---"
    cat /proc/pressure/cpu 2>/dev/null || echo "No CPU PSI available"
    echo
    echo "--- Memory pressure ---"
    cat /proc/pressure/memory 2>/dev/null || echo "No memory PSI available"
    echo
    echo "--- IO pressure ---"
    cat /proc/pressure/io 2>/dev/null || echo "No IO PSI available"
  '

  run "TOP CPU PROCESSES" bash -lc '
    ps -eo pid,ppid,comm,%mem,%cpu,stat,wchan:32,cmd --sort=-%cpu | head -40
  '

  run "TOP MEMORY PROCESSES" bash -lc '
    ps -eo pid,ppid,comm,%mem,%cpu,stat,wchan:32,cmd --sort=-%mem | head -40
  '

  run "DEV WORKLOAD PROCESSES" bash -lc '
    ps -eo pid,ppid,comm,%mem,%cpu,stat,wchan:32,cmd --sort=-%cpu \
      | grep -Ei "opencode|nvim|node|tsserver|tsgo|typescript|biome|eslint|prettier|prettierd|next|turbo|tailwind|vite|webpack|edge|chrome|chromium|discord|gdu" \
      | grep -v grep \
      | head -100
  '

  run "PROCESS TREE FOR OPENCODE / NVIM / TYPESCRIPT / BIOME" bash -lc '
    if command -v pstree >/dev/null 2>&1; then
      for p in $(pgrep -f "opencode|nvim|tsserver|tsgo|biome" | head -20); do
        echo
        echo "--- pstree for PID $p ---"
        pstree -asp "$p" 2>/dev/null || true
      done
    else
      echo "pstree missing. Install with: sudo apt install psmisc"
    fi
  '

  run "DISK SPACE" bash -lc 'df -hT'

  run "INODE USAGE" bash -lc 'df -ih'

  run "BLOCK DEVICES / MOUNTS" bash -lc '
    lsblk -o NAME,TYPE,SIZE,FSTYPE,FSVER,MOUNTPOINTS,MODEL,SERIAL,ROTA,SCHED
    echo
    findmnt -R /
  '

  run "DISK IO BASELINE 15 SECOND SAMPLE" bash -lc '
    if command -v iostat >/dev/null 2>&1; then
      iostat -xz 1 15
    else
      echo "iostat missing. Install with: sudo apt install sysstat"
    fi
  '

  run "IOTOP SAMPLE" bash -lc '
    if command -v iotop >/dev/null 2>&1; then
      sudo iotop -b -o -n 5 -P 2>/dev/null
    else
      echo "iotop missing. Install with: sudo apt install iotop"
    fi
  '

  run "IO BY PROCESS FROM /PROC" bash -lc '
    for pid in /proc/[0-9]*; do
      p="${pid##*/}"
      cmd=$(tr "\0" " " < "$pid/cmdline" 2>/dev/null)
      [ -z "$cmd" ] && continue

      read_bytes=$(awk "/read_bytes/ {print \$2}" "$pid/io" 2>/dev/null)
      write_bytes=$(awk "/write_bytes/ {print \$2}" "$pid/io" 2>/dev/null)

      if [ "${read_bytes:-0}" -gt 0 ] || [ "${write_bytes:-0}" -gt 0 ]; then
        printf "%10s %15s %15s %s\n" "$p" "${read_bytes:-0}" "${write_bytes:-0}" "$cmd"
      fi
    done | sort -k3 -nr | head -50
  '

  run "INOTIFY LIMITS" bash -lc '
    echo "max_user_watches=$(cat /proc/sys/fs/inotify/max_user_watches)"
    echo "max_user_instances=$(cat /proc/sys/fs/inotify/max_user_instances)"
    echo "max_queued_events=$(cat /proc/sys/fs/inotify/max_queued_events)"
  '

  run "INOTIFY USAGE BY PROCESS" bash -lc '
    for pid in /proc/[0-9]*; do
      p="${pid##*/}"
      count=$(find "$pid/fd" -lname "anon_inode:inotify" 2>/dev/null | wc -l)
      if [ "$count" -gt 0 ]; then
        cmd=$(tr "\0" " " < "$pid/cmdline" 2>/dev/null)
        printf "%6s  %4s  %s\n" "$p" "$count" "${cmd:-unknown}"
      fi
    done | sort -k2 -nr | head -80
  '

  run "OPEN FILE COUNT BY PROCESS" bash -lc '
    for pid in /proc/[0-9]*; do
      p="${pid##*/}"
      count=$(ls "$pid/fd" 2>/dev/null | wc -l)
      if [ "$count" -gt 100 ]; then
        cmd=$(tr "\0" " " < "$pid/cmdline" 2>/dev/null)
        printf "%6s  %5s  %s\n" "$p" "$count" "${cmd:-unknown}"
      fi
    done | sort -k2 -nr | head -80
  '

  run "NVME LIST" bash -lc '
    if command -v nvme >/dev/null 2>&1; then
      sudo nvme list
    else
      echo "nvme-cli missing. Install with: sudo apt install nvme-cli"
    fi
  '

  run "NVME SMART LOG" bash -lc '
    if command -v nvme >/dev/null 2>&1; then
      for d in /dev/nvme*n1; do
        [ -e "$d" ] || continue
        echo
        echo "--- $d ---"
        sudo nvme smart-log "$d" 2>/dev/null || true
      done
    else
      echo "nvme-cli missing. Install with: sudo apt install nvme-cli"
    fi
  '

  run "SMARTCTL NVME DETAILS" bash -lc '
    if command -v smartctl >/dev/null 2>&1; then
      for d in /dev/nvme*n1; do
        [ -e "$d" ] || continue
        echo
        echo "--- $d ---"
        sudo smartctl -a "$d" 2>/dev/null || true
      done
    else
      echo "smartmontools missing. Install with: sudo apt install smartmontools"
    fi
  '

  run "NVME / DISK / FILESYSTEM KERNEL WARNINGS" bash -lc '
    journalctl -b --no-pager \
      | grep -Ei "nvme|i/o error|reset|timeout|blk_update_request|buffer i/o|ext4|dm-crypt|crypt|filesystem|journal" \
      | tail -200
  '

  run "BLOCKED TASK / HUNG TASK / OOM EVENTS" bash -lc '
    journalctl -b --no-pager \
      | grep -Ei "blocked for more than|hung task|out of memory|oom|killed process|oom-killer|page allocation failure" \
      | tail -200
  '

  run "THERMALS" bash -lc '
    if command -v sensors >/dev/null 2>&1; then
      sensors
    else
      echo "sensors missing. Install with: sudo apt install lm-sensors"
    fi
  '

  run "CPU FREQUENCY SAMPLE" bash -lc '
    echo "--- cpu MHz ---"
    grep "cpu MHz" /proc/cpuinfo | head -40
    echo
    echo "--- scaling governors ---"
    for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
      [ -e "$f" ] && echo "$f: $(cat "$f")"
    done | head -40
  '

  run "POWER / PERFORMANCE TOOLS" bash -lc '
    if command -v powerprofilesctl >/dev/null 2>&1; then
      powerprofilesctl get
      powerprofilesctl list
    else
      echo "powerprofilesctl not available"
    fi

    echo
    if command -v system76-power >/dev/null 2>&1; then
      system76-power profile 2>/dev/null || true
      system76-power graphics 2>/dev/null || true
    else
      echo "system76-power not available"
    fi
  '

  run "GPU / DISPLAY WARNINGS" bash -lc '
    journalctl -b -p warning..err --no-pager \
      | grep -iE "gpu|drm|i915|nvidia|amdgpu|wayland|xorg|gnome|mutter|mesa|hang|reset" \
      | tail -200
  '

  run "SYSTEM SERVICES THAT MAY CAUSE BACKGROUND IO" bash -lc '
    systemctl --no-pager --type=service --state=running \
      | grep -Ei "packagekit|snapd|docker|containerd|tracker|updatedb|apt|fwupd|fprint|bluetooth|appstream|flatpak" || true
  '

  run "USER SERVICES THAT MAY CAUSE BACKGROUND IO" bash -lc '
    systemctl --user --no-pager --type=service --state=running \
      | grep -Ei "tracker|evolution|gnome|portal|pipewire|wireplumber|dbus|appcenter" || true
  '

  section "CONTROLLED TEST INSTRUCTIONS"

  cat <<'TESTS'
To diagnose hardware vs workload, run these manually and paste the results:

Test A: Baseline with opencode and Neovim closed
-----------------------------------------------
pkill -f opencode
pkill -f "nvim --embed"
pkill -f gdu
sleep 10
vmstat 1 10
iostat -xz 1 10

Expected:
- wa should ideally be near 0 to 2%.
- nvme %util should be low.
- si/so should usually be 0.

Test B: Neovim only
-------------------
cd into the real project.
Open Neovim only.
Wait 30 to 60 seconds for LSP to settle.
Then run:
vmstat 1 10
iostat -xz 1 10

If iowait rises here, Neovim/LSP/tsserver/tsgo/biome is a major contributor.

Test C: opencode only
---------------------
Close Neovim.
Start one opencode session only:
nice -n 10 ionice -c2 -n7 opencode

Then run:
vmstat 1 10
iostat -xz 1 10
sudo iotop -b -o -n 5 -P

If iowait rises here, opencode indexing/scanning/writing is a major contributor.

Test D: opencode + Neovim together
----------------------------------
Run one Neovim and one low-priority opencode session together:
nice -n 10 ionice -c2 -n7 opencode

Then run:
vmstat 1 10
iostat -xz 1 10
sudo iotop -b -o -n 5 -P

If lag only appears in this test, the issue is workload contention, not necessarily bad hardware.

Hardware suspicion threshold
----------------------------
Hardware/NVMe becomes likely if any of these are true:
- nvme smart-log shows critical_warning != 0
- media_errors > 0
- num_err_log_entries is high or increasing
- journalctl shows nvme reset, timeout, I/O error, ext4 error, or blk_update_request errors
- NVMe temperature hits throttle range during lag
- high iowait happens even when opencode/Neovim are closed
- fio latency is terrible on an otherwise idle system

Workload suspicion threshold
----------------------------
Workload contention is more likely if:
- opencode is high CPU or doing disk writes during lag
- Neovim starts multiple tsserver/tsgo instances
- biome watcher is active alongside opencode
- wa rises only when opencode + Neovim are both running
- nvme %util is low but wa is high, especially with swap/zram activity
TESTS

  section "RECOMMENDED FIXES TO TRY AFTER CAPTURING THIS SNAPSHOT"

  cat <<'FIXES'
1. Avoid duplicate opencode sessions:
   pgrep -af opencode
   pkill -f opencode

2. Start opencode with lower CPU and disk priority:
   nice -n 10 ionice -c2 -n7 opencode

3. Create useful aliases:
   alias opc='nice -n 10 ionice -c2 -n7 opencode'
   alias opc-kill='pkill -f opencode'
   alias dev-calm='pkill -f opencode; pkill -f gdu; pkill -f biome; sudo systemctl stop packagekit.service'

4. Reduce swappiness from 180 to a safer zram-friendly value:
   echo 'vm.swappiness=60' | sudo tee /etc/sysctl.d/99-swappiness.conf
   sudo sysctl --system

5. Clear swap only after closing heavy apps:
   sudo swapoff -a
   sudo swapon -a

6. Avoid running gdu during lag diagnostics:
   pkill -f gdu

7. Make sure these are ignored by tools where possible:
   node_modules
   .next
   .turbo
   .vercel
   dist
   build
   coverage
   .cache
   .git
   playwright-report
   test-results

8. Watch live pressure:
   watch -n 1 'echo "=== CPU ==="; ps -eo pid,ppid,comm,%mem,%cpu,cmd --sort=-%cpu | head -20; echo; echo "=== VMSTAT ==="; vmstat 1 2 | tail -1; echo; echo "=== PSI IO ==="; cat /proc/pressure/io; echo; echo "=== DISK ==="; iostat -xz 1 2 | tail -25'
FIXES

  section "END OF SNAPSHOT"
} > "$OUT"

echo "Snapshot saved to: $OUT"
copy_to_clipboard
echo
echo "Done."
