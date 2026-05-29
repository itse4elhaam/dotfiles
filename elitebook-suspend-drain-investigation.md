# HP EliteBook 840 G10 — Suspend Battery Drain Investigation

## 1. The Problem

When you close the lid, your laptop enters **s2idle** (also called S0ix or Modern Standby). Instead of staying asleep, it repeatedly wakes every ~20-40 seconds, reconnects to Wi-Fi, then suspends again — cycling endlessly until the battery dies. Closed-lid drain is actually **worse** than open-lid because the EC firmware behaves differently in each state.

## 2. Your System

| Component | Detail |
|-----------|--------|
| **Model** | HP EliteBook 840 G10 — 13th Gen Intel i7-1370P (Raptor Lake) |
| **Kernel** | Pop!_OS 6.17.9-generic (Ubuntu-based) |
| **Sleep modes** | `s2idle` (active) / `deep` (available but unused) |
| **BIOS** | V70 01.11.00 (Nov 2025) — latest |
| **Wake sources** | 23 enabled — USB, keyboard, lid, EC, Thunderbolt, WiFi |

## 3. Key Concepts (TL;DR)

- **s2idle / S0ix / Modern Standby**: System looks off but CPU stays powered in low-power mode. Resume is instant (~1s). Draws 0.5–1.0W minimum on 13th-gen Intel.
- **deep / S3**: Actual suspend-to-RAM. CPU powers off, DRAM self-refreshes. Resume takes ~3-5s. Draws near zero. This is what "suspend" used to mean before 2020.
- **EC (Embedded Controller)**: A separate microcontroller that handles lid switch, keyboard, power button, thermals. HP's EC firmware sends spurious wake signals during s2idle.
- **GPE (General Purpose Event)**: ACPI's interrupt mechanism. The EC fires GPEs to signal events. On Linux, these get interpreted as wake requests.

**Why Intel killed S3**: Starting with 11th-gen CPUs, Intel pushed OEMs to validate only s2idle. S3 still exists in ACPI tables for backward compatibility, but OEMs don't test it. The firmware and drivers (especially Thunderbolt) may not save/restore state correctly across S3 cycles.

## 4. Root Causes (Ranked)

| # | Cause | Confidence | Why |
|---|-------|------------|-----|
| **1** | **HP EC firmware spurious GPEs** | 80% | Bug 218939 (open since 2022): G7/G8/G9/G10 all affected. EC sends false wake events during s2idle. Not reproducible on Windows — HP's Windows driver handles them correctly. |
| **2** | **Kernel 6.17.x s2idle regression** | 85% | Ubuntu kernel ML (March 2026): user got 45,773 wakeups in 9 hours after upgrading to 6.17.0-19. Same kernel series as yours. Sources: XHCI, PS2K, RP08. |
| **3** | **Raptor Lake S0ix platform bugs** | 70% | Bug 218750: S0ix broken on 13th-gen Lenovo (same CPU as yours) after a MSFT LPS0 UUID commit. The patch changed how Low Power S0 Idle is negotiated with firmware. |
| **4** | **acpi_osi=\"Windows 2020\" interaction** | 65% | Your cmdline already uses this to enable HP thermal/fan support. It also tells ACPI to expose Windows Modern Standby behavior, which may put the EC into a mode that produces more frequent GPEs. |

## 5. Fixes (Least → Most Invasive)

### Fix A — Update Pop!_OS kernel (zero risk, 2 min)
Your kernel has an available point-release update. The newer build may include s2idle backports.
```bash
sudo apt update && sudo apt upgrade
```
**Confidence**: 40% | **Rollback**: Boot old kernel from GRUB

### Fix B — Test deep sleep at runtime (~reversible, 5 min)
Force one sleep cycle into S3. If it works, deep sleep is a viable option.
```bash
echo deep | sudo tee /sys/power/mem_sleep
sudo systemctl suspend
```
**What to watch for**: Does it stay asleep? Does resume work cleanly? Any Thunderbolt/USB-C issues after resume?
**Confidence**: 70% | **Rollback**: Reboot restores s2idle

### Fix C — Disable EC wake events (runtime reversible, 5 min)
Blocks the EC from generating wake GPEs. Most commonly reported fix for HP EliteBooks.
```bash
echo 1 | sudo tee /sys/module/acpi/parameters/ec_no_wakeup
sudo systemctl suspend
```
**Trade-off**: Lid-close will no longer wake the laptop. Use power button.
**Confidence**: 75% | **Rollback**: `echo 0 | sudo tee ...`

### Fix D — Identify the exact wake device (systematic, 10 min)
Disable wake sources one by one (USB, WiFi, keyboard) to find the culprit:
```bash
echo disabled | sudo tee /sys/bus/usb/devices/usb*/power/wakeup
```
**Confidence**: 65% | **Rollback**: Reboot

### Fix E — suspend-then-hibernate (permanent workaround, 10 min)
Enter s2idle for instant resume, then auto-hibernate after N minutes — zero drain.
```bash
sudo mkdir -p /etc/systemd/sleep.conf.d/
echo -e "[Sleep]\nHibernateDelaySec=1800" | sudo tee /etc/systemd/sleep.conf.d/90-suspend-hibernate.conf
```
**Requires**: Swap partition equal to or larger than RAM.
**Confidence**: 90% | **Rollback**: Delete the config file

### Fix F — Force deep sleep permanently (after Fix B confirmation)
```bash
sudo kernelstub -a "mem_sleep_default=deep"
```
**Confidence**: 70% (contingent on Fix B) | **Rollback**: `sudo kernelstub -d "mem_sleep_default=deep"`

## 6. Recommended Path

| Step | Action | Time |
|------|--------|------|
| **1** | Update kernel (Fix A) | 2 min |
| **2** | Runtime deep test (Fix B) | 5 min |
| **3** | If deep works → permanent deep (Fix F) OR if deep fails → ec_no_wakeup (Fix C) | 5 min |
| **4** | Configure suspend-then-hibernate (Fix E) as backup for long unattended periods | 10 min |

**Want me to execute any of these?** I'll pause before each system change and explain exactly what's happening.
