# HID capture, 2026-11-11

This is the first raw HID plus evdev recording of a labeled failure. It
answers the question left open in `center-test.md`: the bad data already
exists in the bytes the touchpad sends. The kernel passes it through
unchanged. Libinput then turns it into phantom taps, scrolls and jumps.

## Setup

- ELAN07AC:00 04F3:31EC on i2c_hid_acpi / hid-multitouch, firmware 0x0008.
  The wireless mouse receiver was unplugged. The laptop was on AC.
- Tool: `~/.local/state/touchpad-investigation/2026-11-05/captures/capture-next.py`.
  It runs `libinput-record --with-hidraw` as root and `xinput test-xi2 --root`
  as the user, for 90 s each. No grabs, no device writes.
- `capture-next.py` was edited in place to record only the touchpad node.
  `libinput-record` refuses to write two devices to stdout ("Recording
  multiple devices requires an output file"). hidraw is per HID device, so
  every report is still captured.
- An earlier attempt (23:23:55 to 23:25:25) recorded zero events. The user
  had started stroking late. **This was not a device fault.** A 4 s probe
  right afterwards caught 226 RawMotion events with 333 ELAN interrupts.

## Report 0x54 layout (from the report descriptor)

29 bytes: report ID; byte 1 = physical button (bit 0), 3 constant bits, and
contact count (high nibble); scan time u16 (100 us units); then 5 finger
slots of 5 bytes: flags (bit 0 Confidence, bit 1 Tip, high nibble Contact
ID), X u16 (0 to 3689, 32 units/mm), Y u16 (0 to 2410, 31 units/mm). The
first report decodes to X 1389, Y 1820, matching evdev exactly.

## Capture A: during the episode

Directory `.../captures/incident-_b94gx60/`, 23:28:05 to 23:29:35. Slow
one-finger strokes and circles through the middle. This followed a driver
reset at 23:21 that the user rated "worse". Whether a finger was on the pad
during that reset is unknown.

- 9,312 HID reports. The physical button bit was **never** set.
- X11 got 33 button events from the touchpad: 17 left, 1 middle (a
  three-finger tap), and 15 scroll-wheel steps (4 up, 11 down). All of
  them were synthesized from contact data. None was a physical click.
- 145 contacts started in 90 s; evdev shows 146 tracking IDs. Confidence
  was never 0 and there were no palm tool events. The kernel did not
  invent or drop contacts.
- 265 reports had a contact count of 2, and 2 had 3. The ghost second
  contact sat about 700 units (22 mm) from the real finger.
- **Dead vertical strip:** the single-contact X histogram (25-unit bins)
  has 300 to 470 reports per bin around X 1350 to 1575, but only 10 to 29
  per bin for X 1600 to 1750. Reports pile up at the edges (1550 to 1575:
  473; 1775: 218). Contacts end near X 1560 and restart near X 1975 (or
  the reverse) 20 to 100 ms later. X stayed frozen while Y moved in 7
  runs, and the reverse never happened. That matches the user's report
  that circles came out as up-and-down movement.
- Y = 1586 exactly appears 40 times, against 3 to 7 for each neighbouring
  value. It is also the most common start position of new contacts.

## Clean reset at 23:36:57

`sudo -n /usr/local/sbin/reset-touchpad-driver` ran after the user lifted
every finger. The ELAN interrupt count in `/proc/interrupts` stayed flat
for 1 s before and 2 s after the reset, so no touch was present during
recalibration. The user rated the result "a bit better".

## Capture B: after the clean reset

Directory `.../captures/incident-27ttjtf9/`, 23:42:25 to 23:43:55. Slow
one-finger side-to-side strokes across the full width.

| Measure | A | B |
|---|---|---|
| Reports with 2+ contacts | 267 | 16 |
| X11 scroll-wheel phantoms | 15 | 0 |
| X11 tap clicks | 17 left + 1 middle | 13 left |
| X frozen while Y moves | 7 runs | 0 |
| Drop and restart across the strip (<100 ms, far) | 26 | 2 |
| Reports per 25-unit bin at X 1600 to 1650 | 10 to 29 | about 100 |

The dead gap is gone, but the same column misbehaves the other way.
X 1675 to 1700 holds 291 and 408 reports, against about 80 in other
bins. The most common exact X values are 1702 and 1697, so the pointer
sticks there briefly as the finger passes. Y = 1586 still spikes: 11
reports, against 0 for each neighbour. Five of the 17 tap-like contacts
lie at X 1589 to 1690. Several are single 7 ms reports at Y 1586.

Side-to-side strokes naturally hold Y steady, so the 28 "Y frozen while X
moves" runs in B are not evidence of a fault.

A re-check by a second agent found that B also has a sparse band at
X 1000 to 1225 (5 to 22 reports per bin, against 30 to 85 beside it). Eleven
contacts end near X 860 to 923 and restart near X 1240 to 1363 within
14 ms. The Nov 5 watch-service windows had a dead band at X 1325 to 1600
and a full-width dead Y band near Y 825 to 1050. **The dead band moves with
every recalibration**, so it is not one fixed spot. Touch-down Y values in B
sit exactly 127 units apart (1332, 1459, 1586, 1713), which matches the
row-electrode pitch (about 4.1 mm). So the Y 1586 spike is most likely
centroid quantization at touch-down, not a defect mark.

## Capture C: battery, then charger

Directory `.../captures/incident-nch2tt7q/`, 23:49:31 to 23:51:01, side-to-
side strokes. The charger was unplugged at the start. `upower --monitor-detail`
logged it being plugged in at 23:50:14.021, which is t ≈ 43.0 s in the
recording (anchor: "Current time is 23:50:15" at t = 43.99 s). The battery
was at 96 %. upower reported "pending-charge" (plugged in, not charging) from 23:50:13, not "charging". The first 3 s after the plug-in are excluded.

| Measure | Battery (0 to 43 s) | AC, not charging (46 to 90 s) |
|---|---|---|
| Contacts per second | 0.53 | 0.64 |
| Reports with 2+ contacts | 0.9 % | 0.9 % |
| Tap-like contacts | 3 | 4 |
| Drop and restart (<100 ms, far) | 8 | 10 |
| evdev BTN_TOOL_DOUBLETAP | 2 | 2 |

The charger makes no measurable difference in this state. The user had
reported "better on battery" after a 20 s subjective test. That test came
after the clean reset, which already explains the improvement. A and B were
both on AC at about 98 % ("pending-charge") and still differed about
five-fold, so charge state cannot be the main driver. A specific
at-full-charge effect is not excluded. The charger is HP original and
ungrounded.

## Capture D: reset with a finger resting on the pad

At 23:55:28 `reset-touchpad-driver` ran while one finger rested still on
the middle (143 ELAN interrupts in the second before; 286 in 2 s after).
The laptop was on AC at 96 % in "pending-charge" (plugged in, not charging), the same upower state as during A. Capture
`.../captures/incident-skpyyyt0/`, 23:55:59 to 23:57:30, side-to-side strokes.

Result: no ghost contacts (0 reports with 2+ contacts), 3 tap-like
contacts, 2 X11 clicks, no frozen-X runs. **A touch during reset does not
cause the ghost-contact episode.** D is not clean, though. It still has
18 fast drop/restart pairs, ending mostly near X 2200, and the
single-contact X histogram dips to about 45 per 25-unit bin at X 2125 to
2200, against 100 to 156 on either side. A "below 30 % of median" test
misses a dip of about 50 %.

### The dead band drifts on its own

Fast drop/restart crossings by capture, from a second agent's lone-contact
analysis, confirmed against the histograms here:

| Capture | Calibration | Charger | Band crossed |
|---|---|---|---|
| A, 23:28 | .0029 (23:21) | AC full | X 1560 to 1975 |
| B, 23:42 | .002A (23:36:57) | AC full | X 920 to 1240 |
| C, 23:49 | .002A | battery, then AC pending-charge | X 1960 to 2390, both before and after the plug-in at 43 s |
| D, 23:56 | .002B (23:55:28) | AC pending-charge | X 1940 to 2390 |

The band moved between B and C within one calibration, with no reset.
The charger was unplugged at 23:47:45, in between. It stayed put across the
C to D reset and across the plug-in inside C. So resets do not place the
band. Something time-varying does: adaptive-baseline drift, noise, or a
thermal factor. The two phenomena should be tracked separately:

1. A moving dead band that drops the finger and jumps it. It was present in
   every capture.
2. Ghost second contacts with phantom taps and scrolls. These were severe in
   A, rare in B, and absent in D.

Where the finger rested during D's reset was not recorded. The user was
asked to rest it on "the middle".

## The 23:21 reset

The touchpad-watch incident saved just before it
(`/var/lib/touchpad-watch/touchpad-manual-1794421279095654424.json`, copied
privately for analysis) holds 20.4 s of evdev. That window already had 6.9 %
of touched frames with 2+ contacts. The last contact ended about 40 s
before the reset, so that reset was untouched. The episode predates it.

## Charger state at each incident

Source: upowerd's own history, `/var/lib/upower/history-rate-Primary-51-02568_2023_09_08.dat`
(world-readable; not a `power_supply` sysfs read). It covers Nov 5 01:04 to
now. With gaps capped at 10 min, awake time splits as AC charging 43 %,
AC full ("pending-charge"/"fully-charged") 30 %, battery 26 %.

| Event | State |
|---|---|
| Manual incidents Nov 5 16:29, 16:31, 18:45, 18:47 | AC full |
| Manual incidents Nov 5 19:39, 19:43 (the center test) | battery, but last calibrated at 18:45 on AC full |
| Manual incident Nov 11 23:21; the whole 21:55 to 23:47 interval | AC full |
| Xorg touch-jump bursts Nov 5 13:39, Nov 9 15:50, Nov 11 15:27 | AC charging |
| Capture D calibration (23:55, no ghosts) | AC, pending-charge |

All three independent episodes in the covered period started on AC full,
or ran on a calibration made on AC full. By chance that is about 0.3^3, or
3 %. The 23:36:57 clean reset was also made on AC full and gave a better
but imperfect result (B still had a sparse band at X 1000 to 1225). That
fits an intermittent noise source at calibration time. The touch-jump
warnings follow a different pattern and may be a separate signature.
Earlier history files (`Primary-51-01739`, `Primary-51-25491`, last written in
June) belong to other batteries, likely the user's other laptop of the
same model.

### Exact shares since charger history began

No charger-state record exists before Nov 5 01:05. The journal logs the
battery only at boot. The system76-power profile is always "Balanced". TLP
does not log AC switches. Nightwatch status lines begin on Nov 5. For
Nov 5 01:05 to Nov 12 00:02, awake time was computed from boot ranges minus
the six kernel `PM: suspend entry/exit` intervals: 141.2 h in total.

| State | Awake hours | Share | Problem episodes | Per 10 awake h |
|---|---|---|---|---|
| Battery | 58.4 | 41.4 % | 1 (Nov 5 19:39, calibrated on AC full at 18:45) | 0.17 |
| AC, full | 53.6 | 38.0 % | 3 (Nov 5 16:29, Nov 5 18:45, Nov 11 23:21) | 0.56 |
| AC, charging | 29.1 | 20.6 % | 3 (Xorg touch-jump bursts only) | 1.03 |

Episodes merge user or agent marks and Xorg touch-jump warnings less than
30 min apart. Six of seven episodes started on AC, against 59 % of awake
time on AC. By chance that is about 15 %; counting the battery episode's
AC-full calibration, 7 of 7 is about 2.5 %. Limits: the sample is
seven episodes; awake time is not touchpad-use time (Nightwatch keeps the
machine awake on battery while idle); and marks cluster around
investigation sessions. A persistent per-minute log with touchpad-use time
is needed for real rates.

The user reports that the charger is plugged in about 99 % of the time
whenever power is available. The battery runs since Nov 5 are mostly long
overnight or morning blocks (Nov 5 05:35 to 13:39, Nov 6 03:38 to 12:16,
Nov 9 01:49 to 13:56, Nov 8 16:32 to 23:41), which suggests idle awake
time or power outages rather than active use. If active use is almost
all on AC, then 6 or 7 of 7 episodes on AC is what chance predicts, and
**this correlation carries little evidence either way**. The decisive test
is within an episode: mark it, unplug, then mark again about 30 s later.
That comparison does not depend on how often the laptop is plugged in.

The user reports that the fault is charger-linked and intermittent, and
suspected it happens only when the battery is full. Capture C ran on a
calibration that was already mostly healthy, and on AC in the same
"pending-charge" state as A. In that state it showed no ghost episode.

## Interpretation

- Layer: firmware or sensor. The coordinates, contact counts and Contact
  IDs are already wrong in the HID bytes. Libinput settings cannot repair
  that. Tap-to-click off would remove only the tap half of the phantom
  input, not the ghost-contact scrolling or the jumps.
- The largest measured effect is the reset itself: A (after a 23:21 reset,
  touch state unknown) against B and C (after a reset verified untouched).
  The leading hypothesis is a poisoned firmware baseline: the controller
  captures its no-touch reference at reset or resume. If a finger or palm
  is present then, the reference is wrong in a band that varies each time,
  until the next clean reset. This fits a moving strip, a same-model
  second laptop with the same symptoms, and no physical damage history.
- Not supported: a fixed physical defect (the band moves) and charger
  noise (C shows no difference).
- Battery health from upower is 96.6 % of design. The user saw nothing
  raised. The centre clicks slightly softer, which is normal for a hinged
  clickpad.

## Open checks

1. Decisive test of the baseline hypothesis: reset deliberately with one
   finger resting in the middle, capture, then reset cleanly and capture.
   A dead band where the finger rested, gone after a clean reset, proves it.
2. Check whether a contact was active at the 23:21 reset. The touchpad-
   watch incident `/var/lib/touchpad-watch/touchpad-manual-1794421279095654424.json`
   (root-only) holds the evdev ring right before that reset.
3. Check whether episodes begin at resume (the lid opened with a hand on
   the pad).
4. `acpi_osi="Windows 2020"` is ruled out: the user confirmed the
   touchpad problems predate it (2026-11-12). Its sleep-drain purpose is
   already solved; leave it alone.
