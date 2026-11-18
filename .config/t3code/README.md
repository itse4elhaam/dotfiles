# T3 configuration

The permanent `~/dotfiles` checkout owns the themes, embedded wallpapers,
keybindings, client preferences, and CSS. T3 reads them through these links:

```text
~/.t3/userdata/themes/              -> ~/dotfiles/.config/t3code/themes/
~/.t3/userdata/keybindings.json      -> ~/dotfiles/.config/t3code/keybindings.json
~/.t3/userdata/client-settings.json  -> ~/dotfiles/.config/t3code/client-settings.json
~/.local/bin/t3-zen                 -> ~/dotfiles/scripts/t3-zen
~/.local/bin/t3-wallpaper-layout     -> ~/dotfiles/scripts/t3-wallpaper-layout
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

The default `zen-mode` theme hides the title row and the three panel buttons,
and keeps the floating left sidebar toggle visible. **Ctrl+Shift+B** toggles thread
details in Zen as usual, including its popover on narrow windows. Panels retain
their native shortcuts, open states, and sizes. `t3-zen on`, `off`, and `status` also
work from a terminal. The previous theme is remembered in
`~/.local/state/t3-zen/restore.json`; setup seeds it from `restoreThemeId` only
when absent. Theme switching affects browser clients served by the same T3
environment as well as this machine's desktop app.

Run `t3-wallpaper-layout` to refresh the shared wallpaper CSS on normal themes.
It preserves backups and supports `--dry-run`. Re-select the theme afterward.
Themes must fit T3's 50,000-character CSS limit. The largest deer wallpaper may
use the app's default corner radii to fit that limit. The shared CSS also adds
sidebar glass reflections and lets the PR list fill its available pane.

The script paints the wallpaper as the page body's fixed background. Do not
isolate `[data-slot=sidebar-wrapper]` or give it a negative-z layer. Desktop
browser views are fixed layers mounted outside that wrapper. An isolated
wrapper puts the right panel's resize edge and the floating preview's close
and resize controls beneath the page.

## Verification

```bash
python3 -m unittest discover -s tests -p test_t3_config.py -v
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
