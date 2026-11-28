# Desktop dictation for Pop!_OS

Place the caret in a text field and hold **Super + Left Alt**. A blue and lavender outline marks the window that was active when recording began. Its lower edge and the waveform on the bottom card follow the microphone. The card shows the words as Parakeet recognizes them. Release either key to finish, then let both keys up for insertion. Press **Esc** during a hold to cancel it.

Speech recognition runs locally. The service uses the English Parakeet Unified 0.6B Q8_0 model, Silero voice detection, a native CPU speech engine and a microphone accessible through PulseAudio or PipeWire’s PulseAudio service. Each hold records up to five minutes. Audio stays in memory. The recognizer stays warm for 15 minutes between holds.

## Install

On a Pop!_OS X11 desktop, run:

```sh
apps/desktop-dictation/install.sh
```

The installer downloads pinned engine and model files, verifies their hashes, and starts the user service. To reuse model files you already have, pass the directory containing both GGUF files to `install.sh`. The installer makes independent copies in `${XDG_DATA_HOME:-$HOME/.local/share}/desktop-dictation/models`. For model provenance and terms, see the [Parakeet model card](https://huggingface.co/handy-computer/parakeet-unified-en-0.6b-gguf) and the [Silero model card](https://huggingface.co/handy-computer/silero-vad-v6.2-gguf).

The desktop overlay uses system Python 3, GTK 3, PyGObject, pycairo, python-xlib and `parec`. It registers its bundled Inter typeface inside its own process. Use `systemctl --user status desktop-dictation` to check the service and `journalctl --user -u desktop-dictation` for diagnostics. Disable it with `systemctl --user disable --now desktop-dictation`.

## Words and cleanup

The preview and final transcript use the same cleanup. Fillers and silence filtering are enabled by default. To set a preferred spelling, create `~/.config/desktop-dictation/settings.json`. Changes apply on the next hold.

```json
{
  "speechCustomWords": [{"term": "Pop!_OS", "aliases": ["pop os"]}],
  "speechRemoveFillerWords": true,
  "speechSilenceFiltering": true
}
```

## Insertion and recovery

Keep the caret in the original field until insertion finishes. If dictation detects a key press, a click, or a change of focus that could redirect the paste, the overlay holds the text and offers **Copy**. An application can move its own caret inside a window without sending a focus event that X11 can detect. If recognition stops early, the overlay offers the last available preview. A read-only field or an application that cannot consume a paste may also require Copy.

Dictation uses one normal desktop paste per utterance. Applications that request a paste with the original key-event timestamp receive that transcript. Some editors request clipboard data without a timestamp. For a response from the focused process, the service keeps the same text available for 350 ms after the last text read, up to 1.8 seconds after dispatch. A subsequent paste waits its turn. An application that leaves the paste unread is paused and its transcript stays available through **Copy**. X11 cannot distinguish an unrelated same-process read, or one delayed indefinitely, from a new untagged paste.

For a screenshot copied with GTK’s standard image command on Pop!_OS, dictation restores a lossless PNG with the original pixels and transparency. For mixed selections, it backs up each supported format, including editable project data. If a format is unavailable or exceeds the backup limit, the original clipboard stays in place and the overlay offers **Copy**.

If text reaches the application's clipboard handler, **Sent to app** offers Copy for four seconds. Open **Last Dictation** in the application launcher to recall the latest acknowledged transcript or **Resume** a paused app, even after dismissing its card. A clipboard read alone cannot confirm what an editor kept. Unhandled transcripts remain available until copied, dismissed or cleared when the session locks.

## Testing

Run `/usr/bin/python3 apps/desktop-dictation/test_x11.py` with Xvfb and xdotool on PATH. The fixture creates a private X server, supplies audio and verifies input, focus, clipboard and overlay behavior. Pass `--chrome` for browser fields in a throwaway profile with extensions disabled. Add `--real-model` to dictate three different recordings into those fields using the installed local engine.
