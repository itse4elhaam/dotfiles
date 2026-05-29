#!/bin/bash
# Suspend Battery Drain Diagnostics — HP EliteBook 840 G10
# Usage: sudo ./suspend-diagnostics.sh         # One-shot: pre → suspend → post
#        sudo ./suspend-diagnostics.sh --deep   # Test deep sleep (S3)
set -euo pipefail

LOGPATH="/tmp/suspend-diagnostics-$(date "+%Y%m%d_%H%M%S").log"
exec > >(tee "$LOGPATH") 2>&1

echo "============================================"
echo " SUSPEND DIAGNOSTICS — $(date)"
echo " Source: $(basename "$0")"
echo "============================================"

# ---------- PRE-SUSPEND ----------
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PRE-SUSPEND DIAGNOSTICS                 ║"
echo "╚══════════════════════════════════════════╝"

echo 1 | tee /sys/power/pm_debug_messages >/dev/null
echo "[OK] pm_debug_messages=1"

# ec_no_wakeup intentionally disabled — causes HP EliteBook G10 to abort s2idle entry

echo ""
echo "--- Sleep States ---"
cat /sys/power/mem_sleep

echo ""
echo "--- ACPI Wake Devices ---"
cat /proc/acpi/wakeup

echo ""
echo "--- PM Wakeup IRQ (last wake source) ---"
cat /sys/power/pm_wakeup_irq

echo ""
echo "--- EC No Wakeup ---"
cat /sys/module/acpi/parameters/ec_no_wakeup

echo ""
echo "--- Wakeup Counters (non-zero) ---"
found=0
for f in /sys/bus/*/devices/*/power/wakeup_count; do
    c=$(cat "$f" 2>/dev/null) || continue
    [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c" && found=1
done
[ "$found" -eq 0 ] && echo "  (none)"

echo ""
echo "--- USB Device Wakeup State ---"
for f in /sys/bus/usb/devices/[0-9]-[0-9]*/power/wakeup; do
    state=$(cat "$f" 2>/dev/null) || continue
    name=$(cat "${f%/power/wakeup}/product" 2>/dev/null || echo "unknown")
    echo "  ${f}: ${state} (${name})"
done

echo ""
echo "--- Key Interrupt Counts ---"
grep -E "ACPI|i8042|rtc0" /proc/interrupts || echo "  (not found in /proc/interrupts)"

echo ""
echo "--- Wakeup Events Total ---"
cat /sys/power/wakeup_count 2>/dev/null || echo "  unavailable"

echo ""
echo "--- S0ix Residency ---"
if [ -f /sys/kernel/debug/pmc_core/slp_s0_residency_usec ]; then
    val=$(cat /sys/kernel/debug/pmc_core/slp_s0_residency_usec 2>/dev/null)
    echo "  slp_s0_residency_usec: $val"
else
    echo "  debugfs not available (kernel lockdown)"
fi

echo ""
echo "--- Current Boot Suspend Events ---"
journalctl -b 0 -p info --no-pager 2>/dev/null \
    | grep -E "(PM:|suspend|wake|GPE)" \
    | grep -v "hibernation.*Registered nosave" \
    | grep -v "PM:.*genpd" \
    | grep -v "PM:.*Magic number" \
    | grep -v "PM:.*RTC time" \
    | grep -v "ACPI:.*PM: Registering" \
    | grep -v "ACPI: PM:" \
    | tail -40

echo ""
echo "--- Previous Boot Suspend Events ---"
journalctl -b -1 -p info --no-pager 2>/dev/null \
    | grep -E "(PM:|suspend|wake|GPE)" \
    | grep -v "hibernation.*Registered nosave" \
    | grep -v "PM:.*genpd" \
    | grep -v "PM:.*Magic number" \
    | grep -v "PM:.*RTC time" \
    | grep -v "ACPI:.*PM: Registering" \
    | grep -v "ACPI: PM:" \
    | tail -40

SUSPEND_START=$(date +%s)

# ---------- SUSPEND ----------
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  SUSPENDING...                           ║"
echo "║                                          ║"
echo "║  Close the lid now, or press power btn   ║"
echo "║  System will enter s2idle.               ║"
echo "║  When you open the lid, diagnostics      ║"
echo "║  will continue automatically.            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

systemctl suspend

# ---------- POST-SUSPEND (continues after resume) ----------
SUSPEND_END=$(date +%s)
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  POST-SUSPEND DIAGNOSTICS                ║"
echo "╚══════════════════════════════════════════╝"
echo "[OK] Resume detected. Suspend duration: $((SUSPEND_END - SUSPEND_START))s"

echo ""
echo "--- PM Wakeup IRQ (last wake source) ---"
cat /sys/power/pm_wakeup_irq

echo ""
echo "--- Wakeup Counters (non-zero after resume) ---"
found=0
for f in /sys/bus/*/devices/*/power/wakeup_count; do
    c=$(cat "$f" 2>/dev/null) || continue
    [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c" && found=1
done
[ "$found" -eq 0 ] && echo "  (none)"

echo ""
echo "--- ACPI Wake Devices ---"
cat /proc/acpi/wakeup

echo ""
echo "--- Key Interrupt Counts ---"
grep -E "ACPI|i8042|rtc0" /proc/interrupts || echo "  (not found)"

echo ""
echo "--- Wakeup Events Total ---"
cat /sys/power/wakeup_count 2>/dev/null || echo "  unavailable"

echo ""
echo "--- Suspend/Resume Journal (this cycle) ---"
journalctl -b 0 --since "@${SUSPEND_START}" -p info --no-pager 2>/dev/null \
    | grep -E "(PM:|suspend|wake|GPE|wakeup|printk: Suspending)" \
    | tail -40

echo ""
echo "--- Network Manager Sleep/Wake Events ---"
journalctl -b 0 --since "@${SUSPEND_START}" --no-pager 2>/dev/null \
    | grep -i "NetworkManager.*\(sleep\|wake\|reconnect\)" \
    | tail -20

echo ""
echo "--- systemd Sleep Transactions (this boot) ---"
journalctl -b 0 --no-pager 2>/dev/null \
    | grep -E "systemd-sleep|systemd.*(suspend|resume)" \
    | tail -20

echo ""
echo "============================================"
echo " DIAGNOSTICS COMPLETE"
echo "============================================"
echo "Full log: $LOGPATH"
echo ""


# ---------- DEEP SLEEP TEST ----------
deep_sleep_test() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║  DEEP SLEEP (S3) TEST                    ║"
    echo "╚══════════════════════════════════════════╝"
    echo "Save all work first. Power button ready."
    echo "Entering deep sleep in 5s..."
    sleep 5

    DEEP_START=$(date +%s)
    echo deep | tee /sys/power/mem_sleep >/dev/null
    echo "[OK] mem_sleep=$(cat /sys/power/mem_sleep)"
    echo "[$(date)] Entering S3..."
    systemctl suspend

    DEEP_END=$(date +%s)
    echo "[OK] Resume! Duration: $((DEEP_END - DEEP_START))s"
    echo ""
    echo "--- PM Wakeup IRQ (post-deep) ---"
    cat /sys/power/pm_wakeup_irq

    echo ""
    echo "--- Wakeup Counters ---"
    found=0
    for f in /sys/bus/*/devices/*/power/wakeup_count; do
        c=$(cat "$f" 2>/dev/null) || continue
        [ "$c" -gt 0 ] 2>/dev/null && echo "  $f: $c" && found=1
    done
    [ "$found" -eq 0 ] && echo "  (none)"

    echo ""
    echo "--- Journal (post-deep) ---"
    journalctl -b 0 --since "@${DEEP_START}" --no-pager 2>/dev/null \
        | grep -E "(PM:|suspend|wake|GPE)" | tail -20

    echo ""
    echo "--- Network Events (post-deep) ---"
    journalctl -b 0 --since "@${DEEP_START}" --no-pager 2>/dev/null \
        | grep -i "NetworkManager.*\(sleep\|wake\|reconnect\)" | tail -10

    echo ""
    echo "============================================"
    echo " DEEP SLEEP TEST COMPLETE"
    echo "============================================"
    echo "If resume worked: deep sleep is safe."
    echo "To make permanent: sudo kernelstub -a \"mem_sleep_default=deep\""
    echo "Full log: $LOGPATH"
}

case "${1:-}" in
    --deep|-d) deep_sleep_test ;;
    --help|-h)
        echo "Usage: sudo $0 [--deep | --help]"
        echo "  (no args)  One-shot: pre-diagnostics → suspend → post-diagnostics"
        echo "  --deep     Test deep sleep (S3) — save work first"
        ;;
    *) ;;  # default runs main flow above
esac
