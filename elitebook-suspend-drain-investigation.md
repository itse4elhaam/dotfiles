# HP EliteBook 840 G10 — Suspend Battery Drain Investigation

## 1. The Problem

When you close the lid, your laptop enters **s2idle** (also called S0ix or Modern Standby). Instead of staying asleep, it repeatedly wakes every ~20-40 seconds, reconnects to Wi-Fi, then suspends again — cycling endlessly until the battery dies. Closed-lid drain is actually **worse** than open-lid because the EC firmware behaves differently in each state.

### Is this harmful for battery health?

Yes — but not catastrophically. Three mechanisms:
- **Thermal cycling**: Each resume powers up CPU, fans may spin. Repeated heat/cool cycles stress components more than staying steadily asleep.
- **Write amplification**: Each resume triggers journal writes, Discord/network reconnects, disk cache flushes. Extra SSD wear over months/years.
- **Deep discharge risk**: Worst case — battery hits 0% and system dies hard. Li-ion cells degrade faster when repeatedly deep-discharged.

Your battery is at 76% health. This won't cause a fire or hardware failure, but **left unfixed, it accelerates degradation**. Fixing it means each battery cycle lasts longer per charge.

### Performance reminder

Once suspend is resolved, we need to benchmark/optimize this machine for parallel OpenCode development.

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

### Sleep mode comparison

| Aspect | s2idle (current) | deep (S3) | hibernation (S4) |
|--------|------------------|-----------|-----------------|
| **Power draw** | 0.5-2W (varies) | ~0.1W | 0W (powered off) |
| **Resume time** | ~1s | ~3-5s | ~15-30s |
| **Battery drain** | Moderate | Minimal | Zero |
| **Data safety** | RAM powered | RAM powered | Saved to disk |
| **Your laptop** | Broken (cycling) | Available, untested | Depends on swap |

**Most ideal**: deep (S3) if it works. Next: suspend-then-hibernate. Fallback: s2idle with ec_no_wakeup.

## 4. Root Causes (Ranked)

| # | Cause | Confidence | Why |
|---|-------|------------|-----|
| **1** | **HP EC firmware spurious GPEs** | 80% | Bug 218939 (open since 2022): G7/G8/G9/G10 all affected. EC sends false wake events during s2idle. Not reproducible on Windows — HP's Windows driver handles them correctly. |
| **2** | **Kernel 6.17.x s2idle regression** | 85% | Ubuntu kernel ML (March 2026): user got 45,773 wakeups in 9 hours after upgrading to 6.17.0-19. Same kernel series as yours. Sources: XHCI, PS2K, RP08. |
| **3** | **Raptor Lake S0ix platform bugs** | 70% | Bug 218750: S0ix broken on 13th-gen Lenovo (same CPU as yours) after a MSFT LPS0 UUID commit. The patch changed how Low Power S0 Idle is negotiated with firmware. |
| **4** | **acpi_osi=\"Windows 2020\" interaction** | 65% | Your cmdline already uses this to enable HP thermal/fan support. It also tells ACPI to expose Windows Modern Standby behavior, which may put the EC into a mode that produces more frequent GPEs. |

## 5. Fixes (Least → Most Invasive)

### Fix A — Update Pop!_OS kernel (SKIP — researched, no benefit)
The available kernel is the **same 6.17.9 base** — just a newer build timestamp. Reviewed the 6.17.9 changelog and Pop!_OS GitHub — **zero s2idle fixes** in this release. The 6.17.9 Pop kernel also has a known BTF validation bug that sent systems to emergency mode (#3949, #3961).

**Verdict**: Skip. Risk (boot failure) outweighs benefit (none).

### Fix B — Test deep sleep at runtime (~reversible, 5 min)
Force one sleep cycle into S3. If it works, deep sleep is a viable option.
```bash
echo deep | sudo tee /sys/power/mem_sleep
sudo systemctl suspend
```
**What to watch for**: Does it stay asleep? Does resume work cleanly? Any Thunderbolt/USB-C issues after resume?
**Confidence**: 70% | **Rollback**: Reboot restores s2idle

**Why you got a kernel panic before**: This is a known issue on HP EliteBooks. S3 exists in ACPI for backward compat, but Intel stopped validating it starting 11th-gen. On resume, Thunderbolt/USB-C controllers and the EC may fail to restore state. The panic was most likely a **resume failure** — system entered S3 fine, but couldn't come back. This is firmware-level, not driver-level.

**Safe test procedure**: Save all work first. Have power button ready (lid may not wake from deep). If it panics: long-press power 10s to force shutdown, then reboot. The runtime test (`echo deep | tee ...`) only affects one cycle — reboot resets to s2idle.

### Fix C — Disable EC wake events (runtime reversible, 5 min)
Blocks the EC from generating wake GPEs. Most commonly reported fix for HP EliteBooks.
```bash
echo 1 | sudo tee /sys/module/acpi/parameters/ec_no_wakeup
sudo systemctl suspend
```
**Trade-off**: Lid-close will no longer wake the laptop. Use power button.
**Confidence**: 75% | **Rollback**: `echo 0 | sudo tee ...`

**Researched downsides**:
- **Lid-close stops waking** — you'll need power button (certainty). Not a problem for most — just a behavior change.
- **Power button still works** (separate from EC GPE path)
- **Rare reports** on Arch forums: some X1 Carbon Gen6 users had trackpad/trackpoint unresponsive after wake. Not common on HP. The kernel upstream has been adding DMI quirks for this exact fix on Lenovo, TUXEDO, and HP ZHAN Pro models — it's a recognized, kernel-supported mitigation.
- **Runtime toggle is zero-risk**: `echo 0` undoes it. Next reboot resets to default.

### Fix D — Identify the exact wake device (systematic, 10 min)
Read wakeup counters and /proc/acpi/wakeup to find which device is the primary culprit:
```bash
# Check current wakeup counters on all devices
for f in /sys/bus/*/devices/*/power/wakeup_count; do
  c=$(cat "$f" 2>/dev/null) || continue
  [ "$c" -gt 0 ] 2>/dev/null && echo "$f: $c"
done
```
**Confidence**: 65% | **Rollback**: Read-only — no changes

Can proceed on this.

### Fix E — suspend-then-hibernate (permanent workaround, 10 min)
Enter s2idle for instant resume, then auto-hibernate after N minutes — zero drain.
```bash
sudo mkdir -p /etc/systemd/sleep.conf.d/
echo -e "[Sleep]\nHibernateDelaySec=1800" | sudo tee /etc/systemd/sleep.conf.d/90-suspend-hibernate.conf
```
**Requires**: Swap partition equal to or larger than RAM.
**Confidence**: 90% | **Rollback**: Delete the config file

**Researched risks**:
- **Requires swap ≥ RAM** — Pop!_OS default does not configure this. Need to check.
- **systemd bug #38193**: Timer sometimes misfires on some hardware (Framework 13), causing the system to miss the s2idle→hibernate transition window and stay awake.
- **Battery estimation bug #33843**: systemd's discharge rate estimation can be wrong, causing 0% battery on wake. Mitigation: set explicit HibernateDelaySec instead of relying on estimation.
- **User.slice freeze**: Freezes all user processes during transition. Can cause issues with nvidia (not relevant — Intel GPU).
- Mitigation: set a conservative HibernateDelaySec (e.g., 30 min). This avoids the estimation bugs entirely.

### Fix F — Force deep sleep permanently (after Fix B confirmation)
```bash
sudo kernelstub -a "mem_sleep_default=deep"
```
**Confidence**: 70% (contingent on Fix B) | **Rollback**: `sudo kernelstub -d "mem_sleep_default=deep"`

## 6. Recommended Path

| Step | Action | Time |
|------|--------|------|
| **1** | ~~Update kernel (Fix A)~~ **SKIP — no s2idle fixes, known BTF bug** | — |
| **2** | Identify wake devices (Fix D — read-only) | 5 min |
| **3** | Safe deep sleep test (Fix B) — save work, power button ready | 5 min |
| **4** | If deep works → permanent deep (Fix F) |
| | If deep panics → ec_no_wakeup runtime (Fix C) | 5 min |
| **5** | Configure suspend-then-hibernate (Fix E) as backup for long unattended periods | 10 min |

**Want me to execute any of these?** I'll pause before each system change and explain exactly what's happening.
