# Desktop recovery

Click the refresh icon in the system tray, then **Recover**, or press **Super+Alt+R**.
The app launcher also has **Recover Desktop**. Login starts the tray and waits for
one of these actions before opening or moving applications.

| Application | Workspace | Display with two displays |
| --- | --- | --- |
| Edge | Existing or saved workspace numbers | Edge's placement |
| T3 Code | 1 | Primary |
| Ghostty running tmux | 4 | Secondary |
| Discord | 5 | Primary |
| Zoho Mail PWA | 5 | Primary |
| WhatsApp PWA | 6 | Secondary |

Other application windows keep their current display and workspace.
With one display, everything uses that display. Recovery enables workspaces on
both displays so Ghostty and WhatsApp can occupy different workspaces there.
It uses six or more fixed workspaces and maximizes the windows it places
except Ghostty, which keeps its existing window state.

## Quiet recovery

Recovery waits for Edge first, then handles T3 Code, Ghostty, Discord, Zoho
Mail, and WhatsApp in that order. Existing windows are reused. Each app after
Edge has its own wait and placement check. A failed app is reported by name
and the remaining apps still run.

Recovery never activates another workspace. It temporarily uses GNOME's strict
new-window focus policy and sets X11 launch properties to discourage focus
stealing, then restores the previous policy even if an app fails. These are
best-effort window-manager hints; an app that explicitly activates itself may
still interrupt. Windows already on the correct display avoid the visible
unmaximize/resize/maximize cycle. Sticky app windows are assigned to their
intended workspace. Unrelated windows are left alone.

After placement settles, recovery checks the paired **OnePlus Buds 4** and makes
one bounded connection attempt if disconnected. It does not scan or pair devices.
Unavailable earbuds are reported in the completion notification and do not fail
desktop recovery. Bluetooth and the audio system retain control of audio routing.

## Edge recovery

When no regular Edge window exists, the script backs up the Default profile's
`Sessions` directory, then starts Edge with `--restore-last-session`. Edge starts
before either PWA. Existing browser windows are reused. Recovery never sends
Ctrl+Shift+T, closes browser windows, or overwrites Edge's session files.

Before a cold launch, recovery records the saved window and tab counts by
workspace from the newest `Session_*` file. It waits for a fresh browser
session record with the same inventory and five seconds of stable X11 window
geometry. Recovery also checks that the restored windows match the recorded
workspaces. Edge places its own windows. A pending restore keeps its original
baseline across retries. Existing Edge sessions without a pending restore
keep their current workspaces and get a short settling check.

If recovery cannot verify a pending restore within 60 seconds, it stops
before launching the other apps. Check Edge and retry Recover. The browser
session inventory counts restored tabs, including tabs Edge defers loading.

The reader follows Chromium's [session command format](https://github.com/chromium/chromium/blob/main/components/sessions/core/session_service_commands.cc)
and [navigation record format](https://github.com/chromium/chromium/blob/main/components/sessions/core/serialized_navigation_entry.cc).
An Edge format change may require updating the reader.

Backups live in `~/.local/state/desktop-recovery/`. The last five automatic
`edge-session-*` backups are retained. `edge-before-first-recovery-20261106` is
the pre-launch backup from initial setup. `edge-reference-session` and
`reference-layout.json` capture the layout the user approved on November 6.
These are local private data, outside the dotfiles repository. Backups are for
manual recovery if Edge's own saved session is lost; they are never restored
over a running browser automatically. The script cannot recover tabs that Edge
never saved. Ghostty attaches to the most recently used tmux session. Recovery preserves
an existing Ghostty window's fullscreen and font settings. It checks for
an attached tmux client and verifies that pane zoom is retained. On a fresh
tmux server, Continuum and Resurrect restore the last saved layout and pane
zoom.

## Installation and checks

Run `./scripts/setup-desktop-recovery` after checking out these dotfiles. It
registers the launcher, shortcut, and tray autostart, then starts the tray. It
replaces the old startup entry so there is only one login action.
`./scripts/startup-setup.sh` remains a compatible command for direct recovery.

Requires GNOME on X11, `wmctrl`, `xprop`, `xrandr`, `systemd-run`, `bluetoothctl`, Python Xlib,
Python GI with GTK 3 and AyatanaAppIndicator3, and the installed applications.
T3 Code uses the installed `~/.local/bin/t3` launcher. Zoho and WhatsApp
use the existing Edge Default-profile PWA IDs in `scripts/desktop-recovery`.
Launches use transient user services. T3 Code runs in foreground mode so its
service tracks the AppImage for the lifetime of the application.

Run `./scripts/test-desktop-recovery.py` for checks without touching the
desktop. Recovery writes to `~/.local/state/desktop-recovery/recovery.log`
by default, with three 128 KiB rotated files and a 14-day age limit applied
on the next run. Search all retained files for the same `run=` value to
reconstruct a run. Launch events include systemd unit names, which can be
looked up with `journalctl --user -u <unit>`. Recovery can reuse existing app
windows on a retry.

Use `./scripts/test-desktop-recovery.py --x11-staging` to additionally check real
X11 staging with invisible, unmapped probe windows. It never launches apps or
changes the visible desktop.

Disable the tray on login in Startup Applications, or set
`X-GNOME-Autostart-enabled=false` in
`~/.config/autostart/startup-workspaces.desktop`. Quit in the tray menu stops it
for the current login only.
