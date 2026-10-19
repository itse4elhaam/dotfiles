# ELAN touchpad recording and recovery

This laptop's `ELAN07AC:00 04F3:31EC Touchpad` intermittently reports erratic
movement. Xorg reports discarded touch jumps, but the specific firmware,
transport or driver cause is still unproven. The previous periodic X11 reset
loop was ineffective and has been removed. No upgrades are required here.

## Install once

```bash
sudo /home/elhaam/dotfiles/scripts/install-touchpad-watch
```

The installer copies the recorder and reset helper into root-owned locations,
validates the systemd unit and sudoers rule, starts recording at boot, and
checks that both ELAN input nodes opened. Root access is needed to read raw
touch events and rebind the I2C driver. The restricted sudoers rule permits
only `/usr/local/sbin/reset-touchpad-driver` with no arguments. It never grants
password-free execution of a script in this user-writable repository.

This session configured **Ctrl+Alt+Shift+F12** to record an incident and then
reset the hardware driver, with a desktop notification showing the result.
Existing shortcuts were preserved. The shortcut needs the installation above.

## When movement goes wrong

Press **Ctrl+Alt+Shift+F12**, or run:

```bash
fixtouchpad --hardware
```

This first asks the recorder to save up to the preceding minute, waits for its
acknowledgment, and then unbinds/rebinds only `i2c-ELAN07AC:00` from
`i2c_hid_acpi`. Success requires a new HID and input identity; an evdev event
number can legitimately be reused. Interrupted resets attempt to restore the
binding. The command also checks that X11 lists an enabled touchpad before
reporting completion. This manual recovery enables the touchpad.

If recording fails, manual recovery still proceeds with an explicit warning.
A successful rebind proves recreation, not that erratic movement is cured.
Please report whether it feels normal and how quickly the problem returns.

`fixtouchpad --mark` saves a failure trace without resetting. Plain `fixtouchpad`
keeps the earlier soft X11 workaround available. `fixtouchpad --check` reports
its X11 enabled state and current device node.

## What runs automatically

`touchpad-watch.service` observes the touchpad and its sibling ELAN Mouse
input node without grabbing them. It opens only devices whose names, bus,
vendor and product match this hardware. It keeps up to 60 seconds or 50,000
events in memory and retains at most 20 manual incident files and 20 candidate
files under
`/var/lib/touchpad-watch/`. Traces include slot state preceding the saved window
and explicitly flag capacity truncation. A separate writer saves each trace
while the monitor keeps reading events. Marker acknowledgments use unique tokens.
The service uses Python's standard library in isolated mode.

The candidate detector logs repeated large coordinate jumps within the same
finger's track. It distinguishes slots and new tracking IDs, ignores reported
palms, handles lost events conservatively, and suppresses stale contact motion
after long gaps. Missing axis resolution means capture only. Candidate saves
are limited to one every two minutes and three per hour, including across device
reconnections. The thresholds are
hypotheses tested against synthetic traces; they have not been validated
against an actual fault recording from this laptop.

**Automatic driver resets are off.** Before enabling them, a labeled real
incident must be detected, a verified manual rebind must clear the symptoms,
and normal use must show acceptable false-positive rates. No-event freezes
cannot be distinguished reliably from an idle hand by this monitor.

## Inspect and replay

```bash
systemctl status touchpad-watch.service
journalctl -u touchpad-watch.service -n 40
cat /run/touchpad-watch/status
ls -lt /var/lib/touchpad-watch/
python3 -I scripts/touchpad-watch.py --replay /var/lib/touchpad-watch/touchpad-RECORDING.json
```

Each live finding explicitly includes `automatic_reset: false`. The status
file lists connected sources; a service being active alone does not prove
that recording is working. Hardware reconnection is logged with its identity.

## Tests and checks

```bash
python3 -m unittest discover -s tests -p 'test_*touchpad*.py' -v
bash -n scripts/fixtouchpad scripts/reset-touchpad-driver scripts/install-touchpad-watch scripts/touchpad-recover-shortcut
```

Tests use the replay CLI and a non-root fake sysfs boundary. They cover contact
lifecycle, slots, palms, lost events, resume gaps, cooldowns, hourly limits,
recording retention of earlier contact state, unknown resolution, wrong
drivers, unchanged identity, event-number reuse, and restoration after
interruption. Synthetic and fake-kernel tests do not establish physical
recovery effectiveness. Actual device reads and rebinding require live admin
installation and an incident.

## Disable or remove

```bash
sudo systemctl disable --now touchpad-watch.service
```

To also revoke password-free manual resets, remove
`/etc/sudoers.d/touchpad-recovery`. To remove the recorder, remove the installed
`/etc/systemd/system/touchpad-watch.service`, `/usr/local/libexec/touchpad-watch.py`
and `/usr/local/sbin/reset-touchpad-driver`, then run `sudo systemctl daemon-reload`.
The incident files remain until explicitly removed. The keyboard shortcut can
be removed in GNOME Settings → Keyboard → Custom Shortcuts.
