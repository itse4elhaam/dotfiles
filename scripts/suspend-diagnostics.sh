#!/bin/bash
# Suspend Battery Drain Diagnostics for HP EliteBook 840 G10
# Usage: sudo ./suspend-diagnostics.sh          # Pre-suspend diagnostics
#        sudo ./suspend-diagnostics.sh --post   # Post-suspend extraction
set -euo pipefail

TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
PRESUSPEND_LOG="/tmp/suspend-diagnostics-presuspend-${TIMESTAMP}.log"
POSTSUSPEND_LOG="/tmp/suspend-diagnostics-postsuspend-${TIMESTAMP}.log"

pre_suspend() {
    exec > >(tee "$PRESUSPEND_LOG") 2>&1
    echo "============================================"
    echo " PRE-SUSPEND DIAGNOSTICS — $(date)"
    echo "============================================"

    # 1. Enable PM debug messages
    echo 1 | tee /sys/power/pm_debug_messages
    echo "[OK] pm_debug_messages=1"

    # 2. Dump sleep states
    echo ""
    echo "--- Sleep States ---"
    cat /sys/power/mem_sleep

    # 3. ACPI wake devices
    echo ""
    echo "--- ACPI Wake Devices (/proc/acpi/wakeup) ---"
    cat /proc/acpi/wakeup

    # 4. Last wakeup IRQ
    echo ""
    echo "--- PM Wakeup IRQ ---"
    cat /sys/power/pm_wakeup_irq

    # 5. Wakeup counters on all devices
    echo ""
    echo "--- Wakeup Counters (non-zero) ---"
    for f in /sys/bus/*/devices/*/power/wakeup_count; do
        c=$(cat "$f" 2>/dev/null) || continue
        [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c"
    done

    # 6. USB device wakeup state
    echo ""
    echo "--- USB Device Wakeup State ---"
    for f in /sys/bus/usb/devices/*/power/wakeup; do
        state=$(cat "$f" 2>/dev/null) || continue
        name=$(cat "${f%/power/wakeup}/product" 2>/dev/null || echo "unknown")
        echo "  ${f}: ${state} (${name})"
    done

    # 7. Interrupts for key lines
    echo ""
    echo "--- Key Interrupt Counts ---"
    grep -E "ACPI|i8042|rtc0" /proc/interrupts

    # 8. EC no_wakeup state
    echo ""
    echo "--- EC No Wakeup (0=disabled, 1=enabled) ---"
    cat /sys/module/acpi/parameters/ec_no_wakeup

    # 9. Storage of this boot's suspend events so far
    echo ""
    echo "--- Current Boot Suspend Events So Far ---"
    journalctl -b 0 -p info --no-pager 2>/dev/null | grep -E "PM:|suspend|wake|GPE|ec_no_wake|wakeup" | tail -60 || echo "  (none yet)"

    # 10. Previous boot for comparison
    echo ""
    echo "--- Previous Boot Suspend Events ---"
    journalctl -b -1 -p info --no-pager 2>/dev/null | grep -E "PM:|suspend|wake|GPE" | tail -60 || echo "  (no previous boot logs)"

    # 11. Total wakeup events from /sys/power
    echo ""
    echo "--- Wakeup Events Summary ---"
    for f in /sys/power/wakeup_* 2>/dev/null; do
        echo "  $(basename $f): $(cat $f 2>/dev/null)"
    done

    # 12. s2idle/residency counters if available
    echo ""
    echo "--- S0ix Residency (intel_pmc_core) ---"
    if [ -d /sys/kernel/debug/pmc_core ] 2>/dev/null; then
        cat /sys/kernel/debug/pmc_core/slp_s0_residency_usec 2>/dev/null || echo "  slp_s0_residency_usec: unavailable"
    else
        echo "  debugfs not available (kernel lockdown)"
    fi
    # Try via PM QoS
    cat /sys/power/pm_debug_messages 2>/dev/null

    echo ""
    echo "============================================"
    echo " PRE-SUSPEND DIAGNOSTICS COMPLETE"
    echo "============================================"
    echo ""
    echo "Log saved to: $PRESUSPEND_LOG"
    echo ""
    echo "NEXT STEPS:"
    echo "  1. Unplug external USB devices (mouse/keyboard) to isolate variables"
    echo "  2. Close the lid and let it suspend"
    echo "  3. Wait 5-10 minutes (or until it wakes)"
    echo "  4. Open lid and run: sudo $0 --post"
    echo ""
}

post_suspend() {
    exec > >(tee "$POSTSUSPEND_LOG") 2>&1
    echo "============================================"
    echo " POST-SUSPEND DIAGNOSTICS — $(date)"
    echo "============================================"

    # 1. Check pm_debug_messages is still set
    echo "--- pm_debug_messages ---"
    cat /sys/power/pm_debug_messages

    # 2. Wakeup IRQ
    echo ""
    echo "--- PM Wakeup IRQ (last wake source) ---"
    cat /sys/power/pm_wakeup_irq

    # 3. Extract THIS boot's full suspend/resume log
    echo ""
    echo "--- Full Suspend/Resume Journal (current boot) ---"
    journalctl -b 0 -p info --no-pager 2>/dev/null \
        | grep -E "PM:|suspend|wake|GPE|ec_no_wake|wakeup|IRQ|i8042|ACPI" \
        | tail -100

    # 4. Wakeup counters now
    echo ""
    echo "--- Wakeup Counters After Suspend ---"
    for f in /sys/bus/*/devices/*/power/wakeup_count; do
        c=$(cat "$f" 2>/dev/null) || continue
        [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c"
    done

    # 5. ACPI wake devices after
    echo ""
    echo "--- ACPI Wake Devices Now ---"
    cat /proc/acpi/wakeup

    # 6. Interrupt deltas
    echo ""
    echo "--- Key Interrupt Counts (compare with pre-suspend) ---"
    grep -E "ACPI|i8042|rtc0" /proc/interrupts

    # 7. Check systemd sleep state
    echo ""
    echo "--- systemd sleep status ---"
    systemctl is-system-running 2>/dev/null || echo "  unknown"

    # 8. Network reconnection events (indirect wake marker)
    echo ""
    echo "--- Network Reconnection Events ---"
    journalctl -b 0 --no-pager 2>/dev/null \
        | grep -E "NetworkManager.*(wake|sleep|reconnect|link)" \
        | tail -20

    echo ""
    echo "============================================"
    echo " POST-SUSPEND DIAGNOSTICS COMPLETE"
    echo "============================================"
    echo "Log saved to: $POSTSUSPEND_LOG"
    echo ""
    echo "Share the contents of these files for analysis:"
    echo "  $PRESUSPEND_LOG"
    echo "  $POSTSUSPEND_LOG"
}

deep_sleep_test() {
    echo "============================================"
    echo " DEEP SLEEP (S3) TEST"
    echo "============================================"
    echo ""
    echo "What will happen:"
    echo "  1. Saves all work (you should save first)"
    echo "  2. Forces ONE sleep cycle into deep/S3"
    echo "  3. System will power off more aggressively"
    echo "  4. Resume takes ~3-5 seconds (vs ~1s for s2idle)"
    echo ""
    echo "Risks:"
    echo "  - Known issue: HP EliteBook S3 resume may panic"
    echo "  - If so: long-press power 10s, reboot"
    echo "  - Deep only affects this cycle (reboot resets)"
    echo ""
    echo "Ready? Sleeping in 5 seconds..."
    sleep 5

    echo ""
    echo "[$(date)] Setting deep sleep..."
    echo deep | tee /sys/power/mem_sleep
    echo "[OK] mem_sleep=$(cat /sys/power/mem_sleep)"

    echo ""
    echo "[$(date)] Entering S3 deep sleep now..."
    systemctl suspend

    # If we get here, resume succeeded
    echo ""
    echo "[OK] Resume successful!"
    echo ""

    # Check if deep actually took effect
    echo "--- PM Wakeup IRQ (post-deep) ---"
    cat /sys/power/pm_wakeup_irq

    echo ""
    echo "--- Wakeup Counters ---"
    for f in /sys/bus/*/devices/*/power/wakeup_count; do
        c=$(cat "$f" 2>/dev/null) || continue
        [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c"
    done

    echo ""
    echo "--- Journalctl Suspend Events (post-deep) ---"
    journalctl -b 0 -p info --no-pager 2>/dev/null \
        | grep -E "PM:|suspend|wake|GPE" | tail -20

    echo ""
    echo "============================================"
    echo " DEEP SLEEP TEST COMPLETE"
    echo "============================================"
    echo "If this worked: deep sleep is safe on your system."
    echo "Next step: sudo kernelstub -a \"mem_sleep_default=deep\""
}

case "${1:-}" in
    --post|-p)
        post_suspend
        ;;
    --deep|-d)
        deep_sleep_test
        ;;
    --help|-h)
        echo "Usage: sudo $0 [--post | --deep | --help]"
        echo ""
        echo "  (no args)     Run pre-suspend diagnostics + enable pm_debug_messages"
        echo "  --post, -p    Run post-suspend diagnostics after waking"
        echo "  --deep, -d    Run deep sleep (S3) test (save work first!)"
        echo "  --help, -h    Show this help"
        ;;
    *)
        pre_suspend
        ;;
esac
