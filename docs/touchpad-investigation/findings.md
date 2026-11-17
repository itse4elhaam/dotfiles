# Touchpad investigation, 2026-11-05

## Decision

The input anomalies are real, but their cause is not established. No driver
upgrade, firmware flash or repair patch has been installed. The unsuccessful
speed/tap-drag settings trial was reverted. The source audit does not justify
calling this physical hardware failure or claiming a permanent software fix.

The user reports identical symptoms on two laptops of the same model with
the same software/configuration. This increases the value of investigating a
shared cause. It does not separate shared software, common firmware and a
model-specific hardware behavior. Device IDs, firmware versions and recordings
from the second laptop have not been independently compared.

## Evidence

The [historical audit](log-audit.md) examined 1,023,421 journal records and
retained text logs. General input/system records cover October 3 through
November 5. The requested August 5 through early October interval is missing
because those records are no longer retained.

There are 17 paired Xorg/Touchégg jump warnings, 58 scheduling warnings,
and two kernel incomplete I2C-HID reports during resume. The incomplete
reports are not within 60 seconds of a logged jump. Other desktop and kernel
anomalies and their correlations are catalogued in the historical audit.
Neither proximity nor a log label is treated as proof of causation.

The [exact-source audit](source-audit.md) verified the installed Ubuntu
libinput source/patches and the relevant files in the exact Pop kernel
source. Libinput's jump warning is emitted before pointer acceleration and
tapping. Both Xorg and Touchégg consume that same upstream event stream.
Their paired warnings do not represent two separate hardware faults.

The host-side drivers are open source. The kernel maps firmware Contact IDs
to slots; it does not assign these contacts by nearest coordinates. None of
the retained raw-event recordings overlaps a logged jump warning. Their
absence of jump candidates is not proof that the reported interactions were
normal. They also lack the HID bytes and generated pointer/button events
needed to locate the first incorrect transition.

The [release audit](release-comparison.md) inspected newer fixes and built
isolated libinput 1.32.0 diagnostic tools. No reviewed fix has a demonstrated
match to this failure. The compatible repository update is a security
backport, not a touch-motion fix. Newer foreign-distribution binaries require
unrelated dependency upgrades. Matching SONAMEs alone do not make a live
library replacement disruption-free. Current and rollback packages are staged,
but none was installed.

## Concrete next experiment (done 2026-11-11; see below)

A bounded capture helper is prepared at
`~/.local/state/touchpad-investigation/2026-11-05/captures/capture-next.py`.
It validates the two ELAN nodes by name and I2C/vendor/product IDs and checks
that both belong to the same HID device. It runs the installed standard
`libinput-record --with-hidraw` for 90 seconds and simultaneously records
the X11 master pointer, including source IDs. It records no keyboard device,
does not grab or inject events, and changes no system configuration. Private
capture directories contain device properties and wall/monotonic clock anchors.

Only the installed recorder runs through sudo. Syntax, help and live node
identity checks passed. The capture has not run: raw input requires root,
and the private credential request timed out. No credential was supplied or
logged. The helper's full recording path is therefore still unverified.

During capture, label the actual failing action: one finger held still,
slow stroke, contact/lift, or unexpected click/drag. This distinguishes
unintended events from intentional taps and movement. Preserve baseline
settings and avoid resets before the failure is captured.

The required source change depends on the first incorrect boundary:

- Correct HID contacts but incorrect kernel slots/releases require a
  trace-backed fix in HID frame/contact handling or input-mt.
- Correct evdev contacts but incorrect libinput output require a lifecycle,
  history or tapping correction in libinput, reproduced from that sequence.
- Correct processed motion with incorrect desktop action requires checking
  Xorg, gestures or the receiving application before changing kernel code.
- Bad coordinates already present in HID reports locate the fault before
  libinput, but still do not distinguish firmware, sensor and electrical
  transport. Physical hardware failure needs additional controlled evidence.

Any repair must first fail on the captured sequence, pass after the change,
and preserve normal contact/release/multifinger behavior. Only then can an
existing release or a minimal packaged backport be selected with rollback.
Disabling jump detection or resetting on a timer would hide evidence without
establishing a repair.

# Update, 2026-11-11/12

The labeled HID captures A to D are written up in
[2026-11-11-hid-capture.md](2026-11-11-hid-capture.md). The fault is already
in the HID bytes the firmware sends. The kernel and libinput pass it on, so
no libinput setting can fix it. These findings come from replaying the
captures' evdev streams (`touchpad-watch.py --replay TRACE --health`).

## Two separate signatures

1. **Moving dead band.** A finger moving on its own is dropped at one side of
   a band, and a new contact starts 0 to 60 ms later on the far side. The
   pointer skips the band or sticks at its edge, and short fragments become
   tap clicks. This happened on almost every crossing in captures A, B, C and
   D and in the Nov 5 center test.
2. **Ghost contacts.** Second contacts appear, often on the real finger's
   own row or column, and turn into scrolling and clicks. Captures A
   (3.9% of frames had 2+ contacts in its first minute) and Nov 5 (5.1%),
   and the 23:21 pre-reset window (6.9%), show it. B (0.1%) and D (0%) do
   not.

## Where the dead band was

| Recording | HID calibration | Charger at that time | Band (device units) |
|---|---|---|---|
| Nov 5 19:43 center test | .0019, rebind 18:45:26 on AC | battery since 19:14 | X 1325–1600 and a full-width Y band 825–1050 |
| A, 23:28 | .0029, rebind 23:21 | AC full | X 1600–1750 (Y 1325–1500 sparse) |
| B, 23:42 | .002A, hands-off rebind 23:36:57 | AC full | X ≈ 920–1240 |
| C, 23:49 | .002A (same as B) | battery, then AC pending-charge | X ≈ 1960–2390, before and after the plug-in |
| D, 23:56 | .002B, rebind 23:55:28 with a finger resting | AC pending-charge | X ≈ 1940–2390 |

The band moved within one calibration (B to C, 7 minutes, no reset) and
stayed put across a reset (C to D). So calibration events do not fix where
it sits. Something time-varying does: drift in the firmware's adaptive
baseline, electrical noise, or a thermal or mechanical factor. A purely
fixed physical defect is not supported, because the band moves. On Nov 5
the strongest bands ran on battery, but on a calibration made on AC.
Capture C showed no change at the plug-in.

Sources for the charger states: upowerd's own
`/var/lib/upower/history-{rate,charge}-*.dat` and the journal. The user keeps
the charger plugged in almost always, so episode counts per state carry
little evidence without touch-time denominators. That is why the health log
exists (see [touchpad-recovery.md](../touchpad-recovery.md)). Its event study
compares touched minutes just before and after each plug, unplug,
battery-state change, resume and rebind.

## Kernel facts that bound the workarounds

From the exact Pop 6.17.9 source (`drivers/hid/i2c-hid/i2c-hid-core.c`,
`i2c-hid-acpi.c`, `hid-multitouch.c`):

- ELAN matches `I2C_HID_QUIRK_NO_WAKEUP_AFTER_RESET | I2C_HID_QUIRK_BOGUS_IRQ`
  and not `RESET_ON_RESUME`.
- On s2idle suspend, `mt_suspend` sets high latency (and no reporting if
  wake is disabled), then `i2c_hid_core_suspend` sends SET_POWER SLEEP.
- On resume, the device gets only SET_POWER ON plus `mt_reset_resume`'s
  mode feature reports. No HID RESET is sent. The ACPI node has no power
  states, so the pad is not power-cycled. Whether the firmware takes a new
  baseline on wake is firmware-defined and undocumented.
- A driver unbind/bind runs probe, which sends HID RESET. This is the only
  recalibration Linux can trigger without vendor feature reports.

A post-resume "wait until untouched, then rebind" hook would be feasible as
an opt-in `/usr/lib/systemd/system-sleep/` script. It would reuse
`fixtouchpad`'s interrupt-counter wait and `/usr/local/sbin/reset-touchpad-driver`.
It is not built. The health log's `resume` lines will show first whether
episodes start at resume.

## Firmware and BIOS, as far as checked

- fwupd lists `ELAN07AC:00 04F3:31EC`: plugin `elantp`, IC type 0x11,
  module 0x1D, firmware 0x0008, bootloader 0x0001, updatable. LVFS offers
  no update.
- HP's V70 BIOS package for the 840 G10 (sp158083, 01.09.00, 2025-04-30)
  bundles EC, ME, GOP, PXE and USB-C PD firmware. It has no touchpad
  firmware and no touchpad fixes:
  <https://ftp.hp.com/pub/softpaq/sp158001-158500/sp158083.html>.
- HP does ship ELAN ClickPad firmware inside BIOS packages for other G10
  models. The 640/650/630 G10 V74/V75 package sp150010 bundles ClickPad 22.50.0.0
  (ELAN): <https://ftp.hp.com/pub/softpaq/sp150001-150500/sp150010.html>.
- The installed BIOS is 01.11.00 (2025-11-06). A later 01.12.01 for the 840 G10 is
  mentioned in a secondhand forum post. Its release notes were not retrieved.
- The fwupd elantp plugin needs `HIDIOCSFEATURE`/`HIDIOCGFEATURE` and
  documents no read-only diagnostic commands:
  <https://fwupd.github.io/libfwupdplugin/elantp-README.html>.
- The device's report descriptor declares undocumented vendor feature
  reports: 0x0B (130 bytes), 0x0C (1160 bytes), 0x0D and 0x0E (4 bytes), and
  0x06 (256 bytes). Never send them.

## Userspace filter (built 2026-11-12, opt-in, off by default)

`scripts/touchpad-filter.py` grabs the ELAN evdev node and re-emits it through a
uinput twin. Use, install, safety and the verification checklist are in
[touchpad-recovery.md](../touchpad-recovery.md#optional-touchpad-filter-off-by-default).
It makes two corrections and forwards everything else unchanged:

- **Bridge.** A lone contact's restart within 60 ms continues the old tracking
  ID. Replayed, it bridged 32 of A's 36 such restarts, 14 of 15 in B, 16 of 18
  in C, 18 of 19 in D and 38 of 39 on Nov 5. The rest followed a contact that
  could still have been a tap (under 200 ms, under 48 units of travel). The
  filter never holds such a release, because 60 ms more would push a 130 ms tap
  past libinput's 180 ms tap timeout.
- **Ghost hold.** A second contact that starts while the first has been down
  200 ms, at least 500 units away, waits up to 120 ms and is dropped if it ends.

Replaying every second-contact start changed the picture of the ghosts:

- A's ~700-unit second contacts, the likely source of its 15 phantom scroll
  steps, start 0 to 21 ms after the first finger (often in the same frame) and
  last 355 to 469 ms. They are indistinguishable from a real two-finger touch in
  the event stream. Nothing in the filter addresses them.
- Most "late second contacts" in A (7 of 9) and B (3 of 4) are dead-band
  crossings with overlap. A new contact appears 200 to 340 units away and the
  old one ends 1 to 4 frames later. The bridge needs a gap, so it misses these.
- The true short ghosts in A and B (28 to 57 ms) sit about 285 units from the
  finger, under the 500-unit floor. Ghosts in C and on Nov 5 sat 550 to 790
  units away. With the floor at 500 the filter dropped 0 ghosts in A, 0 in B, 1
  in C and 0 on Nov 5. At 200 it dropped 2, 1, 1 and 0.

The two Nov 5 ghosts that outlived the hold lasted 121 and 128 ms. The hold
length and the floor are constants (`GHOST_HOLD`, `GHOST_MIN_UNITS`) to revisit
once the health log shows how often ghosts occur in normal use.

Health metrics now come from the raw HID reports, so health.jsonl measures the
pad itself with the filter on or off. Its new fields `filter_on`,
`bridged_drops` and `suppressed_ghosts` record what the filter did each minute.
