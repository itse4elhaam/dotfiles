#!/usr/bin/env bash

OUT="power_report_$(date +%F_%H-%M).txt"

{
echo "===== BASIC SYSTEM ====="
inxi -Fxxxza

echo -e "\n===== KERNEL ====="
uname -a
cat /proc/cmdline

echo -e "\n===== CPU INFO ====="
lscpu

echo -e "\n===== PCI DEVICES (important for ACPI) ====="
lspci -nnk

echo -e "\n===== USB DEVICES ====="
lsusb

echo -e "\n===== POWER SUPPLY ====="
upower -d

echo -e "\n===== ACPI SUPPORT ====="
cat /sys/power/state
cat /sys/power/mem_sleep

echo -e "\n===== SWAP (required for hibernate) ====="
swapon --show
free -h

echo -e "\n===== TLP STATUS ====="
sudo tlp-stat -s || true

echo -e "\n===== POWERTOP SUGGESTIONS ====="
sudo powertop --time=5 --html=powertop.html >/dev/null 2>&1 || true
echo "Powertop HTML generated as powertop.html"

echo -e "\n===== SYSTEMD SLEEP CONF ====="
cat /etc/systemd/sleep.conf 2>/dev/null || true

echo -e "\n===== LOGIND CONF ====="
cat /etc/systemd/logind.conf 2>/dev/null || true

echo -e "\n===== LAST BOOT POWER LOGS ====="
journalctl -b | grep -iE "acpi|sleep|suspend|hibernate|power" | tail -n 200

} > "$OUT"

echo "Report saved to $OUT"

