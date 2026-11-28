# Desktop dictation for Pop!_OS

Place the caret in a text field and hold **Super + Left Alt**. A blue and lavender outline marks the window that was active when recording began. Its lower edge and the waveform on the bottom card follow the microphone. The card shows the words as Parakeet recognizes them. Release either key to finish, then let both keys up for insertion. Press **Esc** during a hold to cancel it.

Speech recognition runs locally. The service uses the English Parakeet Unified 0.6B Q8_0 model, Silero voice detection, a native CPU speech engine and a microphone accessible through PulseAudio or PipeWire’s PulseAudio service. Audio stays in memory. The recognizer stays warm for 15 minutes between holds.

## Install

On a Pop!_OS X11 desktop, run:

```sh
apps/desktop-dictation/install.sh
```

The installer downloads pinned engine and model files, verifies their hashes, and starts the user service. To reuse model files you already have, pass the directory containing both GGUF files to `install.sh`. The installer makes independent copies in `${XDG_DATA_HOME:-$HOME/.local/share}/desktop-dictation/models`. For model provenance and terms, see the [Parakeet model card](https://huggingface.co/handy-computer/parakeet-unified-en-0.6b-gguf) and the [Silero model card](https://huggingface.co/handy-computer/silero-vad-v6.2-gguf).

The desktop overlay uses system Python 3, GTK 3, PyGObject, pycairo, python-xlib and `parec`. It registers its bundled Inter typeface inside its own process. Use `systemctl --user status desktop-dictation` to check the service and `journalctl --user -u desktop-dictation` for diagnostics. Disable it with `systemctl --user disable --now desktop-dictation`.

## Insertion and recovery

Keep the caret in the original field until insertion finishes. If you move to another field or change windows while the transcript is finishing, the overlay holds the text and offers **Copy**. If recognition stops early, it offers the last available partial. A read-only target or an application that cannot consume a paste may also require Copy. X11 exposes the focused window. An application can move its own caret without sending a separate desktop focus event.

The clipboard delivery path preserves supported existing formats. If text reaches the application's clipboard handler, **Sent to app** offers Copy for four seconds. Open **Last Dictation** in the application launcher to recall the latest acknowledged transcript. A clipboard read alone cannot confirm what an editor kept. Unhandled transcripts remain available until copied, dismissed or cleared when the session locks.

## Testing

Run `/usr/bin/python3 apps/desktop-dictation/test_x11.py` with Xvfb and xdotool on PATH. The fixture creates a private X server, supplies audio and verifies input, focus, clipboard and overlay behavior. Pass `--chrome` for a real browser field in a throwaway profile, or `--real-model` to transcribe recorded speech with the installed local engine.
