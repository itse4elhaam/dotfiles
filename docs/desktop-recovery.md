# Desktop recovery

Click the refresh icon in the system tray, then **Recover**, or press **Super+Alt+R**.
The app launcher also has **Recover Desktop**. Login starts the tray and waits for
one of these actions before opening or moving applications.

| Application | Workspace | Display with two displays |
| --- | --- | --- |
| Edge window with more Upwork tabs | 2 | Primary |
| Other Edge window | 1 | Primary |
| Ghostty running tmux | 1 | Secondary |
| Zoho Mail PWA | 3 | Primary |
| Discord | 4 | Primary |
| T3 Code | 5 | Primary |
| WhatsApp PWA | 6 | Secondary |

Other application windows keep their current display and workspace.
With one display, everything uses that display. Recovery enables workspaces on
both displays so Ghostty and WhatsApp can occupy different workspaces there.
It uses six or more fixed workspaces and maximizes the windows it places.

## Quiet recovery

Recovery places Edge on workspace 1 first, then the Upwork Edge on workspace 2,
before launching the remaining apps. Existing windows are reused. New windows
start on the secondary display on their intended workspace, settle, then move to
their final display. With one display, they use that display instead.

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

The script reads the newest saved `Session_*` file to count each tab's current
Upwork URL, excluding navigation history and closed tabs. It matches the saved
windows to open window titles and saved workspace positions. The window with the
higher count goes to workspace 2. A tie favors the window already on workspace 2.
If the saved session has not caught up with the open windows, recovery reports
an error; wait a few seconds and click Recover again.

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
never saved. It does not replace tmux session persistence across reboots.

## Installation and checks

Run `./scripts/setup-desktop-recovery` after checking out these dotfiles. It
registers the launcher, shortcut, and tray autostart, then starts the tray. It
replaces the old startup entry so there is only one login action.
`./scripts/startup-setup.sh` remains a compatible command for direct recovery.

Requires GNOME on X11, `wmctrl`, `xrandr`, `systemd-run`, `bluetoothctl`, Python Xlib,
Python GI with GTK 3 and AyatanaAppIndicator3, and the installed applications.
T3 Code uses the existing `t3code.desktop` launcher. Zoho and WhatsApp use the
existing Edge Default-profile PWA IDs in `scripts/desktop-recovery`.

Run `./scripts/test-desktop-recovery.py` for offline checks without touching the
desktop. Logs for recovery actions started from the tray are available through
`journalctl --user -g desktop-recovery`. Application errors also produce a desktop
notification. A failed recovery can leave some applications placed; another
Recover click reuses those windows and retries.

Use `./scripts/test-desktop-recovery.py --x11-staging` to additionally check real
X11 staging with invisible, unmapped probe windows. It never launches apps or
changes the visible desktop.

Disable the tray on login in Startup Applications, or set
`X-GNOME-Autostart-enabled=false` in
`~/.config/autostart/startup-workspaces.desktop`. Quit in the tray menu stops it
for the current login only.
