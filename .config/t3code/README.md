# T3 configuration

The permanent `~/dotfiles` checkout owns the themes, embedded wallpapers,
keybindings, client preferences, and CSS. T3 reads them through these links:

```text
~/.t3/userdata/themes/              -> ~/dotfiles/.config/t3code/themes/
~/.t3/userdata/keybindings.json      -> ~/dotfiles/.config/t3code/keybindings.json
~/.t3/userdata/client-settings.json  -> ~/dotfiles/.config/t3code/client-settings.json
~/.local/bin/t3-zen                 -> ~/dotfiles/scripts/t3-zen
~/.local/bin/t3-wallpaper-layout     -> ~/dotfiles/scripts/t3-wallpaper-layout
~/.local/bin/t3-double-ctrl          -> ~/dotfiles/scripts/t3-double-ctrl
~/.config/systemd/user/t3-double-ctrl.service -> ~/dotfiles/scripts/t3-double-ctrl.service
```

Install or verify the links:

```bash
~/dotfiles/scripts/setup-t3-config
~/dotfiles/scripts/setup-t3-config --check
```

Use `--repo /path/to/permanent/dotfiles` if the permanent checkout is elsewhere.
Never point live links at a temporary worktree. `--dry-run` shows the link plan.
Existing files, directories, and launcher links are preserved under
`~/.local/state/t3-config/backups/` before replacement. Re-running is safe.
The setup is also available as `dev-setup/runs/t3-config.sh`.

Setup registers the GNOME X11 shortcut and selects the theme in `defaults.json`.
If T3 has not installed its CLI yet, open T3 once and re-run setup. On a headless
machine, setup skips shortcut registration; run `t3-zen install` from the desktop
later. `--skip-shortcut` and `--skip-theme` install only the links.

T3's atomic config writer resolves symlink targets before replacement. Changes
made in T3 settings therefore update the tracked files; inspect and commit them
when wanted. Themes use a directory link so publishing new themes also reaches
the repository. T3's directory watcher may need a theme re-selection or restart
to notice a config file edited externally in the repository.

`settings.json` stays app-owned: it also contains provider configuration and
runtime timestamps. Setup applies the selected theme through T3's CLI rather
than replacing that file. Credentials, sessions, databases, browser data,
backups, and transient toggle state stay outside Git. Logging in is not the
backup mechanism for this configuration.

## Wallpaper and top-bar controls

- **Ctrl+Alt+Z** shows or hides the top bar by switching the theme preset.
- **Ctrl+Tab** toggles the left sidebar independently.
- **Ctrl+Alt+L** opens or closes the right panel, including from its browser.
- **Ctrl+Alt+A** opens T3's theme picker if the desktop shortcut is unavailable.

The default `zen-mode` theme hides the title row and keeps the floating left
sidebar toggle visible. It hides the panel buttons while the right panel is
closed. While the panel is open, its terminal and close buttons stay in the
panel header beside maximize. **Ctrl+Shift+B** toggles thread
details in Zen as usual, including its popover on narrow windows. Panels retain
their native shortcuts, open states, and sizes. `t3-zen on`, `off`, and `status` also
work from a terminal. The previous theme is remembered in
`~/.local/state/t3-zen/restore.json`; setup seeds it from `restoreThemeId` only
when absent. Theme switching affects browser clients served by the same T3
environment as well as this machine's desktop app.

Run `t3-wallpaper-layout` to refresh the shared wallpaper CSS on normal themes.
It preserves backups and supports `--dry-run`. Re-select the theme afterward.
Themes must fit T3's 50,000-character CSS limit. The largest deer wallpaper may
use the app's default corner radii to fit that limit. Deer is the tightest
theme, so check its size after adding shared rules. The shared CSS also does the
following:

- Adds glass reflections to the sidebar and the right panel, including the panel
  in the narrow-window sheet. Browser pages, diffs, PR details and terminals
  keep their opaque content.
- Shows the wallpaper behind the PR and issue lists.
- Lets the PR list fill its available pane.

The script paints the wallpaper as the page body's fixed background. Do not
isolate `[data-slot=sidebar-wrapper]` or give it a negative-z layer. Desktop
browser views are fixed layers mounted outside that wrapper. An isolated
wrapper puts the right panel's resize edge and the floating preview's close
and resize controls beneath the page. For the same reason, blur the panel's
content (`[data-preview-panel-mode]>:last-child`), never the panel root that
holds the resize edge.

## Voice dictation shortcuts

**Ctrl+Shift+D** and a **double tap of Ctrl** both start dictation, and stop it
while it records. T3's keybindings need a non-modifier key, so the double tap
comes from the `t3-double-ctrl` user service. It watches X11 key events without
grabbing any. When a T3 window is focused, it sends the existing Ctrl+Shift+D
shortcut, which T3 handles as usual outside the terminal.

Both taps must be on the same Ctrl key, each held under 250 ms, with the second
ending within 400 ms of the first. Any other key or mouse button in between
cancels, so Ctrl+C, Ctrl+click and a held Ctrl never trigger it. It works on
X11 only. Setup enables the service; `--skip-shortcut` leaves it alone.

```bash
systemctl --user status t3-double-ctrl.service
journalctl --user -u t3-double-ctrl.service -n 20   # one line per trigger
systemctl --user disable --now t3-double-ctrl.service
```

## Verification

```bash
python3 -m unittest discover -s tests -p test_t3_config.py -v
python3 -m unittest discover -s tests -p test_t3_double_ctrl.py -v
~/dotfiles/scripts/setup-t3-config --check
```

## Native close button

The dotfiles `t3` launcher hides Electron's native caption buttons only in T3.
It builds `.config/t3code/no-close.c` with the system C compiler on first launch
and caches the GTK module under `~/.cache/t3code/`. Other applications keep
GNOME's normal button layout, including editors and browsers started by T3.
If compilation fails, T3 launches with normal controls and prints a warning.

Setup links `~/.local/bin/t3` and the desktop launcher into this checkout.
The launcher also sets `T3CODE_DESKTOP_LAUNCHER_PATH`, so T3 registers its URL
handler through the same launcher. This applies after quitting and reopening
T3; setup does not interrupt running work. Alt+F4 and the app's Quit command
remain available. Launching an AppImage directly bypasses this setting.

Check the launcher without opening T3:

```bash
python3 -m unittest discover -s tests -p test_t3_launcher.py -v
```
