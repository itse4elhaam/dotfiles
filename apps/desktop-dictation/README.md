# Desktop dictation

On Pop!_OS/X11, place the caret in an editable field, hold **F9**, speak, and release. A blue waveform follows the microphone on the active window’s monitor. The adjacent text is a live hypothesis and can change before release. Press **Esc while holding the key** to discard the recording.

Run `apps/desktop-dictation/install.sh` from this checkout to install or update the user service. It uses the system Python 3.10 with GTK 3, PyGObject, pycairo and python-xlib, PulseAudio-compatible `parec`, and the Linux x64 T3 Code Nightly AppImage in `~/Applications`. Download **Parakeet Unified English 0.6B** and the Silero silence filter through T3 once. T3 can be closed during dictation.

The worker reads T3’s installed Q8_0 GGUF and Silero v6.2, streams locally, and applies the filler-word, silence-filter and preferred spelling/alias settings from `~/.t3/userdata/client-settings.json`. The model supplies punctuation. No cloud text-generation pass runs. Audio stays in process memory. Release loads the finished text onto the system clipboard and pastes it once. Clipboard managers can retain that text.

Clicking or typing during finalization, switching windows, or changing fields with the mouse keeps the result on the clipboard for manual paste. Applications can move their own caret or switch internal fields without notifying X11. Keep the caret in place until the overlay finishes. Auto-paste uses Ctrl+V in GUI applications and Ctrl+Shift+V in common terminal emulators. The recording limit is five minutes.

Set `DICTATION_KEY=F8` (or another single X11 keysym) in `~/.config/desktop-dictation.env` to change the shortcut. Set `T3_DICTATION_APPIMAGE=/absolute/path/to/T3.AppImage` there if T3 moves. Restart with `systemctl --user restart desktop-dictation`. For diagnostics use `journalctl --user -u desktop-dictation`. Disable with `systemctl --user disable --now desktop-dictation`.
