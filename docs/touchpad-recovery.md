# ELAN touchpad recording and recovery

This laptop's `ELAN07AC:00 04F3:31EC Touchpad` intermittently reports erratic
movement. Xorg reports discarded touch jumps, but the specific firmware,
transport or driver cause is still unproven. The previous periodic X11 reset
loop was ineffective and has been removed.

## Settings trial on 2026-11-05, reverted

The user reported that the settings trial below made behavior worse. Both
changes were reverted in the same session: speed is again
`0.73529411764705888` and tap-and-drag is enabled. This was not a successful
fix. The investigation continues at the input-stack and driver-source level.

Movement was unpredictable during finger contact. The journal contained
`Touch jump detected and discarded` at 13:39:44, reported by both Xorg and
Touchégg. The incident recordings captured during investigation contained no
lost-event markers or jumps caught by the recorder. Its large-jump detector
does not rule out smaller movement errors or unintended generated clicks.

The touchpad speed was `0.73529411764705888` and tap-and-drag was enabled.
These settings were temporarily changed in the user's GNOME session:

```bash
gsettings set org.gnome.desktop.peripherals.touchpad speed 0.0
gsettings set org.gnome.desktop.peripherals.touchpad tap-and-drag false
```

GNOME saves these settings across logins. During the trial, tap-to-click
remained enabled and dragging required holding the physical click.
X11 confirmed `libinput Accel Speed = 0` and
`libinput Tapping Drag Enabled = 0` after applying the changes.

The original values were saved in
`~/.local/state/touchpad-settings/20261105-163236.json`. To restore these two
settings:

```bash
gsettings set org.gnome.desktop.peripherals.touchpad speed 0.73529411764705888
gsettings set org.gnome.desktop.peripherals.touchpad tap-and-drag true
```

These changes address excessive speed and unintended tap-drag gestures, but
are not a confirmed repair for intermittent bad device coordinates. User
verification is still required. The ELAN firmware reports version `0x0008`;
`fwupdmgr get-updates` returned no update for this device using the available
metadata. No firmware was installed.

## Install once

```bash
sudo /home/elhaam/dotfiles/scripts/install-touchpad-watch
```

The installer copies the recorder and reset helper into root-owned locations,
validates the systemd unit and sudoers rule, and starts recording at boot.
It then checks three things: the touchpad and mouse input nodes and the
hidraw node are open, and `/var/log/touchpad-watch/health.jsonl` is being
written with mode 0644. Root access is needed to read raw touch events and
HID reports and to rebind the I2C driver. The restricted sudoers rule permits
only `/usr/local/sbin/reset-touchpad-driver` with no arguments. It never grants
password-free execution of a script in this user-writable repository.
Re-run the installer after changing `scripts/touchpad-watch.py`: the service
runs the installed copy.

**Ctrl+Alt+Shift+F12** runs `scripts/touchpad-recover-shortcut`, which runs
`fixtouchpad --hardware` and shows its progress as desktop notifications.

Optional dead-strip notifications need no sudo. They are **not recommended
yet**: the detector also fires on capture D, which the user felt was fine,
and a reset did not move D's band. Enable them only once the health log
shows the dead band tracks the user's bad periods:

```bash
systemctl --user link /home/elhaam/dotfiles/scripts/touchpad-alert.service \
    /home/elhaam/dotfiles/scripts/touchpad-alert.path
systemctl --user enable --now touchpad-alert.path
```

## When movement goes wrong: hands-off recalibration

Lift every finger and palm off the pad, then press **Ctrl+Alt+Shift+F12**, or run:

```bash
fixtouchpad --hardware
```

1. The recorder saves the preceding minute of evdev events and raw HID
   reports, and acknowledges the save.
2. The script asks you to lift your fingers (a desktop notification when it
   is started from the shortcut). It waits until the `ELAN07AC:00` interrupt
   counter in `/proc/interrupts` has not moved for 1 s. The counter only
   moves while the firmware reports contacts, so a flat counter means nothing
   is touching the pad. If touches keep coming for 20 s, it gives up and
   exits 3 without resetting. If the counter is missing (the driver is
   unbound), it warns and resets after 2 s.
3. It unbinds and rebinds only `i2c-ELAN07AC:00`. The rebind sends a HID
   RESET, which is expected to make the firmware take a new baseline. That
   is ELAN-internal and undocumented. Success requires a new HID and input
   identity.
4. It checks that X11 lists an enabled touchpad. It then watches the counter
   for 2 s more and reports whether the pad stayed quiet. Touches right after
   a hands-off reset suggest phantom contacts; run it again with nothing on
   the pad.

The reset itself happens about 1 s after quiet is confirmed, so keep your
hands off until the result notification appears. A flat counter cannot
detect an object the firmware has stopped reporting, such as a finger
resting inside a dead band.

`fixtouchpad --mark` saves a failure trace without resetting. Plain `fixtouchpad`
keeps the earlier soft X11 workaround available. `fixtouchpad --check` reports
the X11 state, the device node, the recorder status and the latest dead-strip
alert. Both also cover the filtered device below when it exists.

## Optional touchpad filter (off by default)

**Status 2026-11-12: built and tested, not installed.** The user chose to wait.
Open decision: the ghost-hold minimum distance. It is 500 units as first
specified, which catches almost nothing because short ghosts in captures A and
B sit about 285 units away. 200 is recommended: the hold only drops a second
contact that disappears within 120 ms, so a real finger is never dropped.
Installing also needs the repo `touchpad-watch.py` reinstalled first. Until then,
the installed recorder measures health from evdev, not hidraw. Replay results
are in `findings.md`.

`scripts/touchpad-filter.py` sits between the touchpad and libinput. It takes an
exclusive grab (`EVIOCGRAB`) on the touchpad's evdev node and re-emits every
event through a uinput device named `ELAN07AC:00 04F3:31EC Touchpad (filtered)`.
That device copies the real one's axis ranges, resolution, keys, five MT slots,
tool types, `MSC_TIMESTAMP`, ids (bus 0x18, 04f3:31ec) and its pointer and
buttonpad properties. Fuzz is 0, so the kernel never smooths what the filter
writes. GNOME finds touchpads by their libinput properties, not their names, so
it should apply the same speed, tapping and scrolling settings to it. Check this
the first time (see the checklist). Nothing starts the filter at boot.

It forwards the stream unchanged except in two places, and it never invents or
smooths a coordinate.

1. **Bridge.** A lone contact ends and a new lone contact starts within 60 ms.
   The new contact continues the old tracking ID with `BTN_TOUCH` held, so
   libinput sees no lift and no tap. Its real position goes through. To decide,
   the filter holds the release of a lone contact for up to 60 ms. It never
   holds the release of a contact younger than 200 ms that moved less than 48
   units, because that contact could still become a tap. libinput's tap limits
   are 180 ms and 1.3 mm.
2. **Ghost hold.** A second contact starts while the only other contact has
   been down for 200 ms or more, at least 500 units away. The filter withholds
   it for up to 120 ms. If it ends in that time, libinput never sees it. If it
   lasts, or the first finger lifts, a third finger lands or the pad clicks,
   the filter shows it at its current position first.

After a bridge, libinput 1.20 treats the step as motion when the gap was over
30 ms. With a shorter gap it usually discards the step as a jump and logs
"Touch jump detected and discarded" in the Xorg log. Either way there is no lift
and no phantom tap.

Replayed through the same code (`python3 -I scripts/touchpad-filter.py --replay TRACE`):

| Capture | Lone restarts within 60 ms | Bridged | Left alone by the tap rule | Ghosts dropped at 500 units | At 200 units |
|---|---|---|---|---|---|
| A | 36 | 32 | 4 | 0 | 2 |
| B | 15 | 14 | 1 | 0 | 1 |
| C | 18 | 16 | 2 | 1 | 1 |
| D | 19 | 18 | 1 | 0 | 0 |
| Nov 5 | 39 | 38 | 1 | 0 | 0 |

On Nov 5, three ghosts at 550 to 790 units were held. Two lasted 121 and 128 ms,
just past the hold, and ended within 20 ms of being shown.

What the filter does not fix:

- **A's phantom scrolls.** A's second contacts about 700 units away start 0 to
  21 ms after the first finger, often in the same frame, and last 355 to
  469 ms. A rule that needs the first finger down for 200 ms cannot see them,
  and they outlast the hold. In the event stream they look exactly like a real
  two-finger touch.
- **Overlapping crossings.** In A (7 of 9 late second contacts) and B (3 of 4),
  the dead band shows up as a new contact 200 to 340 units away, and the old
  contact ends 1 to 4 frames later. The bridge needs a gap, so these pass as
  they are. libinput sees two fingers for a frame or two.
- **The short ghosts in A and B.** They sit about 285 units from the finger,
  under the 500-unit floor. `GHOST_MIN_UNITS = 200` would drop them. Two real
  fingertips probably sit at least 12 mm (380 units) apart, but that is an
  estimate, not measured on the user's own gestures, so the floor stays at 500
  for now.

What it costs:

- The lift of every contact that is not a tap candidate reaches libinput up to
  60 ms late. A pointer stroke, long press or drag ends 60 ms after the finger
  leaves. Taps are never delayed.
- The bridge has no distance limit (`BRIDGE_MIN_UNITS = 0`). A real lift and
  re-touch within 60 ms after a stroke, such as a fast reposition, becomes one
  touch. If the gap was over 30 ms, libinput applies the whole jump as one
  accelerated motion and the pointer flicks. Taps are not affected.
- A second finger that lands 200 ms or more after the first, at least 500 units
  away, appears up to 120 ms late. A one-then-two-finger scroll starts that much
  later. A second-finger tap shorter than 120 ms in that situation is dropped.
- While the filter runs, Xorg's jump warnings include bridged drops, so they no
  longer measure the raw pad. The health log still does (see below).

### Install

Run once, from the normal account:

```bash
sudo /home/elhaam/dotfiles/scripts/install-touchpad-watch    # health from raw HID; do this first
sudo /home/elhaam/dotfiles/scripts/install-touchpad-filter
```

The filter installer copies the daemon to `/usr/local/libexec/touchpad-filter.py`
and installs `touchpad-filter.service` without enabling or starting it. It also
writes `/etc/sudoers.d/touchpad-filter`, which allows exactly
`/usr/bin/systemctl start touchpad-filter.service` and
`/usr/bin/systemctl stop touchpad-filter.service` without a password. It refuses
to run while the filter is on. Re-run it after changing `touchpad-filter.py`.

Before turning the filter on, check that the reinstalled recorder logs health
from HID. Use the pad normally for a minute, then:

```bash
tail -n 1 /var/log/touchpad-watch/health.jsonl   # "kind":"minute" ... "health_source":"hid"
journalctl -u touchpad-watch | grep health_error  # must print nothing
```

The recorder's own install check passes on its `service_start` line alone, and
it reports a health error only once, so a broken HID path would otherwise just
stop the minute lines.

### Turn it on and off

```bash
scripts/touchpad-filter on        # returns once it has grabbed the untouched pad
scripts/touchpad-filter off
scripts/touchpad-filter status
```

**Ctrl+Alt+Shift+F11** toggles it, with a notification, once registered:

```bash
path=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/touchpad-filter/
schema=org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path
gsettings set "$schema" name 'Toggle ELAN touchpad filter'
gsettings set "$schema" binding '<Control><Alt><Shift>F11'
gsettings set "$schema" command '/home/elhaam/dotfiles/scripts/touchpad-filter toggle --notify'
python3 -I -c 'import ast, subprocess, sys
key = ["org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]
paths = ast.literal_eval(subprocess.run(["gsettings", "get", *key], capture_output=True, text=True,
                                        check=True).stdout.replace("@as ", ""))
if sys.argv[1] not in paths:
    subprocess.run(["gsettings", "set", *key, str(paths + [sys.argv[1]])], check=True)' "$path"
```

After a reboot the filter is off.

### Why it fails safe

- It exits on any error, and systemd never restarts it (`Restart=no`). The kernel
  drops an evdev grab when the grabbing descriptor closes. Every exit closes it,
  SIGKILL included, so the raw pad then reaches libinput again.
- Each pass of the event loop re-arms a 1 s kernel interval timer. If the loop
  stalls, SIGALRM kills the process. systemd's `WatchdogSec=2s` is the backup.
- It grabs nothing but the event node under `/sys/bus/i2c/devices/i2c-ELAN07AC:00`
  named exactly `ELAN07AC:00 04F3:31EC Touchpad`, with bus 0x18, vendor 04f3,
  product 31ec and the buttonpad property. Anything else is refused before the
  grab and before it opens uinput.
- It grabs only while no finger is down, and on "off" it waits up to 2 s for the
  pad to be untouched before letting go. libinput therefore does not miss the
  lift of a touch it saw begin. If that happened anyway, libevdev 1.12 drops the
  unmatched tracking ID and logs "double tracking ID" instead of passing it on.
- Ctrl+Alt+Shift+F12 rebinds the driver, which removes the event node. The
  filter lifts every virtual touch, waits up to 15 s for the new node, checks
  that it has the same layout, and grabs it. Otherwise it exits and the pad is
  unfiltered. `fixtouchpad --hardware` reports which happened.
- The unit runs with no capabilities, read-only access to input devices,
  read-write access to `/dev/uinput` only, no network, and a read-only file
  system apart from `/run/touchpad-filter`.

### Check it the first time it is on

1. `scripts/touchpad-filter status` says `active`, and X11 lists the filtered device.
2. `xinput list-props "ELAN07AC:00 04F3:31EC Touchpad (filtered)"` shows
   Accel Speed 0.735294, Tapping Enabled 1, Tapping Drag Enabled 1, Natural
   Scrolling Enabled 1 and Disable While Typing Enabled 1. If any differ, turn
   the filter off. Do not change GNOME settings to make up for it.
3. The pointer moves. A tap clicks. Double-tap, tap-and-drag, two-finger scroll,
   two-finger tap (right click) and the physical click work. Touching right
   after typing is ignored, as before.
4. `sudo systemctl kill -s KILL touchpad-filter.service`, then move the pointer
   with the pad straight away. It must work. `touchpad-filter status` now says
   `failed` or `inactive`.
5. Turn it on again and press Ctrl+Alt+Shift+F12 with hands off. The
   notification says the filter reattached.
6. After a touched minute, `tail -n 1 /var/log/touchpad-watch/health.jsonl`
   shows `"health_source":"hid"` and `"filter_on":true`.

### If anything goes wrong

1. Press Ctrl+Alt+Shift+F11, or run `scripts/touchpad-filter off`.
2. If that does not respond, run `sudo systemctl kill -s KILL touchpad-filter.service`.
   The pad works again as soon as the process is gone.
3. Without a usable desktop, press Ctrl+Alt+F3, log in at the text console, run
   step 2, then go back with Ctrl+Alt+F2.
4. A reboot always leaves the filter off.

## What runs automatically

`touchpad-watch.service` observes the touchpad, its sibling ELAN Mouse input
node and the ELAN hidraw node, without grabbing them or writing to them. It
finds the nodes through `/sys/bus/i2c/devices/i2c-ELAN07AC:00` and checks
name, bus, vendor and product before opening. It follows driver rebinds by
rediscovering every 2 s.

- **Incident ring.** Up to 60 s or 50,000 evdev events, plus up to 60 s or
  9,000 raw HID reports with the report descriptor. A mark or a candidate
  saves both into one JSON file under `/var/lib/touchpad-watch/`. HID report
  times are when the service read them (`CLOCK_MONOTONIC`, a few ms after the
  matching evdev frame).
- **Retention.** At most 20 files in each category (manual, jump candidate,
  strip candidate) and 64 MiB in total. Automatic captures are removed
  before marked incidents.
- **Jump detector.** Logs repeated large coordinate jumps within one
  finger's track. Candidate saves are limited to one every two minutes and
  three per hour.
- **Dead-strip detector.** Flags the signature seen in captures A to D and on
  Nov 5. A lone finger is lost and a new contact starts within 60 ms at least
  8 mm away. It fires when at least 4 such restarts happen in 30 s, at least
  3 cross one band, and few reports land inside it. It writes
  `/run/touchpad-watch/alert` and saves a strip candidate. At most one alert
  per 10 min and three per hour. Its advice to recalibrate is unproven: the
  band in capture C stayed put across the reset before capture D.
- **Health log.** See below.

**Automatic driver resets are off.** No detector resets the pad.

## Health log

`/var/log/touchpad-watch/health.jsonl` (mode 0644, rotated at 20 MB, at most
three files) holds aggregates only, never coordinates of individual touches.

- One `minute` line per minute in which the pad was touched. A minute is cut
  short when the charger state changes, and at a resume or rebind.
- One line per event: `service_start`, `power_change` (plug, unplug or any
  UPower battery-state change), `resume` (detected as a jump of
  `CLOCK_BOOTTIME` against `CLOCK_MONOTONIC`, with `suspended_s`) and
  `rebind` (new HID device, with `previous_hid`).

Every line carries these fields:

- `ts` (wall clock), `boot_id` and `hid`.
- Charger state from UPower over D-Bus: `ac_online`, `battery_state`,
  `battery_pct`, `energy_rate_w` and `power_age_s`. The service polls
  `busctl` every 10 s as a child process with a 2 s D-Bus timeout, is killed
  at 5 s, and never blocks the input loop. Values are null with
  `power_error` when UPower does not answer.
- The calibration context: `calibration_kind` (rebind, resume or unknown),
  `seconds_since_calibration` and the charger state then. The same is logged
  separately for the last rebind and the last resume (`rebind_*`, `resume_*`).
  The charger state at an event is the first UPower poll started 2 to 30 s
  after it, because UPower can be stale right after resume. Otherwise it is
  the last state known before the event.
- `cpu_pkg_temp_c` from the `x86_pkg_temp` zone, read from a CPU register.

The service never reads `/sys/class/power_supply` or ACPI thermal zones,
because ACPI battery reads have hung this laptop.

Minute metrics. Since 2026-11-12 the service counts them from the raw HID
reports (input report 0x54) instead of evdev, because touchpad-filter's grab
hides the evdev stream. They describe the touchpad itself whether or not the
filter is on. On captures A to D the HID counts equal the evdev counts, with two
exceptions. `touched_seconds` is about 1% lower, because the firmware's scan
clock runs slower than the kernel's timestamps. One of A's 44 restarts sits on
the 100 ms edge. The evdev incident ring and the jump and dead-strip detectors
still read evdev, so they see nothing from the touchpad while the filter runs.
The HID ring in incident files keeps recording.

| Field | Meaning |
|---|---|
| `health_source` | `hid` (live service) or `evdev` (older lines, evdev replays) |
| `filter_on` | touchpad-filter was active at some point in the minute |
| `bridged_drops`, `suppressed_ghosts` | What the filter did since the previous minute line |
| `touched_seconds`, `touched_frames` | Time and frames with at least one contact; the denominator |
| `contact_starts` | New tracking IDs |
| `multi_contact_frames` | Frames with 2+ contacts (raised by real two-finger gestures too) |
| `late_second_contacts` | A contact starting while another has been down for 200 ms or more |
| `tap_like_contacts` | Contacts shorter than 180 ms that moved less than 100 units |
| `fast_drop_restarts` | A lone contact ends and the next starts within 100 ms, 150+ units away |
| `frozen_x_runs`, `frozen_y_runs` | 10+ frames with one axis unchanged while the other moved 150+ units |
| `sparse_x_score`, `sparse_x_at` (and `_y_`) | Over the last 120 touched seconds of one-finger frames: 0 = even, 1 = an empty 100-unit bin between busy neighbours, and that bin's centre |

Side-to-side strokes leave empty Y bins between stroke heights, and vertical
strokes do the same for X, so a high sparse score alone is not a fault.

Summarize without sudo:

```bash
scripts/touchpad-health-report                  # whole log
scripts/touchpad-health-report --since 2026-11-12
```

The report starts with an event study. For every plug, unplug,
battery-state change, resume and rebind, it compares up to 5 touched minutes
before with up to 5 after. The windows stop at the neighbouring events and
at 6 h. It then lists touch hours, the share of touch time, the dead-band and
ghost shares of touched time, and rates per touched minute. These are grouped
by the charger state now, at the last calibration, at the last rebind, and by
CPU temperature. Touched time is the only denominator, because the charger is
plugged in most of the time. Fault definitions, in the report's `--help`:

- **Dead band:** at least 3 `fast_drop_restarts`, and at least 5 per touched
  minute. Replayed through the meter, captures A to D gave 8 to 50 per touched
  minute in 7 of their 8 minute windows. D's last 17 touched seconds had none.
- **Ghost:** at least 2 `late_second_contacts`, and at least 4 per touched
  minute. Replayed: Nov 5 7.2/min, A 8.4/min, B 4.3/min, C 1.4/min, D 0.
  Healthy use that the user rated "perfect" (2026-11-12 00:24 to 00:28)
  gave 0. Tap-like contacts and multi-contact frames are logged but not
  used to classify. That healthy use had 11.2 taps/min and 3.0% multi-contact
  frames from tap-to-click and two-finger scrolling, more than capture A's 2.7%.
- Healthy use also gave 0 `fast_drop_restarts`. The dead band shows up
  mainly in deliberate full-width strokes.

## Battery and ghost reminders

`scripts/touchpad-notify` runs as the user service `touchpad-notify.service`
(linked from the repo and enabled 2026-11-12; no root). It reads charger state
from UPower over D-Bus, never from `/sys/class/power_supply`. It follows
`health.jsonl` and only shows desktop notifications:

- **Outage guard:** from 18:00 until the 19:00 outage, while on battery, "plug in"
  every 15 min. The user has a daily 19:00 to 21:00 power outage.
- **Low battery:** at or below 50 % on battery, outside 18:00 to 21:00, "plug in"
  every 20 min.
- **Ghost alert:** two minutes rated ghost by the report's rule within 3 min.
  Plugged in outside 18:00 to 21:00, it advises unplugging for about 5 minutes,
  then F12. Otherwise it advises F12. At most once per 30 min.

Times and the threshold can be overridden in `~/.config/touchpad-notify.ini`
under `[reminders]` (`prep_start`, `outage_start`, `outage_end`,
`plug_in_percent`, `outage_repeat_min`, `low_repeat_min`, `ghost_cooldown_min`).
Then run `systemctl --user restart touchpad-notify`. `scripts/touchpad-notify --status`
prints the power state it sees, and `--test` shows a sample notification.

An unplug reminder whenever the laptop is plugged in and not charging was
rejected: since Nov 5 it would have fired about 8.5 times a day.

## Inspect and replay

```bash
systemctl status touchpad-watch.service
journalctl -u touchpad-watch.service -n 40
cat /run/touchpad-watch/status        # sources: hid, mouse, touchpad
tail -n 3 /var/log/touchpad-watch/health.jsonl
ls -lt /var/lib/touchpad-watch/
python3 -I scripts/touchpad-watch.py --replay /var/lib/touchpad-watch/touchpad-RECORDING.json
python3 -I scripts/touchpad-watch.py --replay TRACE.json --health   # per-minute metrics
python3 -I scripts/touchpad-watch.py --replay TRACE.json --health --hid   # from HID, as the service does
python3 -I scripts/touchpad-filter.py --replay TRACE.json   # what the filter would correct
```

Each live finding explicitly includes `automatic_reset: false`. The status
file lists connected sources; a service being active alone does not prove
that recording is working. Hardware reconnection is logged with its identity.

## Tests and checks

```bash
python3 -m unittest tests.test_fixtouchpad tests.test_touchpad_health tests.test_touchpad_watch \
    tests.test_reset_touchpad_driver tests.test_touchpad_filter tests.test_touchpad_notify
bash -n scripts/fixtouchpad scripts/reset-touchpad-driver scripts/install-touchpad-watch \
    scripts/touchpad-recover-shortcut scripts/touchpad-filter scripts/install-touchpad-filter
systemd-analyze verify scripts/touchpad-filter.service
```

Tests use the replay CLI, a non-root fake sysfs, fake `/proc/interrupts`
counters, stub `sudo`, `systemctl`, `xinput` and `notify-send` (the PATH holds no
real `sudo`), fake UPower replies, and a smoke run of the service loop as a normal
user against an empty fake sysfs. The filter tests feed the correction logic
frames from a model of hid-multitouch's slot and tracking-ID rules, and check
what libinput would receive. They run the real filter service in a child process
with fake ioctls, socket-pair devices and a fake uinput, then kill it, stall it,
stop it and remove its device. Tests that replay captures A to D read them from
`~/.local/state/touchpad-investigation/2026-11-05/captures` (or
`TOUCHPAD_CAPTURES`) and skip when they are absent. Synthetic and fake-kernel
tests do not establish physical recovery effectiveness, and no test touches a
real grab or uinput device.

## Disable or remove

```bash
sudo systemctl disable --now touchpad-watch.service
systemctl --user disable --now touchpad-alert.path
systemctl --user disable --now touchpad-notify.service
scripts/touchpad-filter off
```

To remove the filter:

```bash
sudo systemctl stop touchpad-filter.service
sudo rm /etc/systemd/system/touchpad-filter.service /usr/local/libexec/touchpad-filter.py \
    /etc/sudoers.d/touchpad-filter
sudo systemctl daemon-reload
```

To also revoke password-free manual resets, remove
`/etc/sudoers.d/touchpad-recovery`. To remove the recorder, remove the installed
`/etc/systemd/system/touchpad-watch.service`, `/usr/local/libexec/touchpad-watch.py`
and `/usr/local/sbin/reset-touchpad-driver`, then run `sudo systemctl daemon-reload`.
Incident files under `/var/lib/touchpad-watch/` and the health log under
`/var/log/touchpad-watch/` remain until explicitly removed. The keyboard shortcut can
be removed in GNOME Settings → Keyboard → Custom Shortcuts.
