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

Dictation sends one paste shortcut directly to the X11 window that had keyboard focus when recording started. It rechecks the window and its owner before sending. Some editors include the paste shortcut’s timestamp. Others, including Chrome, request clipboard formats and text in several steps without a timestamp. After the first untagged text read, dictation waits for a 350 ms gap in the app’s requests before restoring the clipboard. The next dictation waits for this paste to finish.

You can type or delete text as soon as the transcript appears, then use the app’s usual paste shortcut to insert your previous clipboard contents. Chrome also supports **Ctrl+Shift+V** to paste as plain text. If the app requests more data after you edit but before that shortcut or the end of the gap, dictation pauses paste and offers **Resume**.

When dictation detects a conflicting shortcut, it offers **Copy** before changing the clipboard. The window manager can reserve shortcuts outside that check. Automatic paste is addressed only to the editor window. A physical **Ctrl+V** you press yourself still follows your desktop shortcut settings.

Enter, Tab, Escape and caret navigation still reach the editor. If you navigate while an untagged paste is settling, the service guards the original clipboard even after the quiet period. X11 reports the same clipboard read whether the text already appeared or the app still plans to insert it in the newly focused field. A new Super+Left Alt hold after navigation can deliver another transcript in the same app, including a different Chrome window. You can start speaking immediately after Enter submits a chat message. Delivery waits for the previous offer to settle, and the original clipboard stays guarded during recording and after the new delivery. During the new offer, a delayed untagged read from the same process is indistinguishable from its new paste. If a possible late read reaches the service before dispatch, the new transcript goes to **Copy** and the app stays paused.

Once a paste settles after navigation, you can press the usual paste shortcut in any focused window that dictation can verify belongs to the same app. This releases the guard for that app, including any delayed clipboard read it makes afterward. Dictation releases its shortcuts when another app takes the clipboard or the screen locks. Unlocking restores them for eligible windows if dictation still serves the clipboard. If the shortcut is unavailable or a delayed read has paused the app, open **Last Dictation** and choose **Resume**.

If that 350 ms gap hasn’t elapsed by 1.8 seconds after the dictation paste shortcut, dictation pauses paste for the app. Even a single read can trigger this if it arrives close to the deadline. Other apps regain access to the original clipboard, and the transcript stays on the **Copy** card. X11 gives the service no way to distinguish a new untagged request from an old one that the same app delayed indefinitely.

After you release the shortcut, **Waiting for app** keeps the finished transcript visible. If the editor ignores the window-addressed shortcut or never reads the paste, dictation restores the previous clipboard after 1.8 seconds. The card shows **App didn’t read the paste** and offers **Copy** and **Resume**. A recovered copy is available immediately to other identified apps. Choose **Resume** before pasting it into the paused app.

For a screenshot copied with GTK’s standard image command on Pop!_OS, dictation restores a lossless PNG with the original pixels and transparency. For mixed selections, it backs up each supported format, including editable project data. If a payload uses 32-bit X11 elements, is unavailable, or exceeds the backup limit, the original clipboard stays in place and the overlay offers **Copy**.

**Sent to app** means the editor read the transcript. The card offers **Copy** for four seconds. When the card hides automatically, you can reopen the latest acknowledged transcript from **Last Dictation** in the application launcher. Clicking **×** removes that transcript from recall. **Last Dictation** still offers **Resume** for a paused app. Transcripts waiting for recovery stay available until you copy or dismiss them, or lock the screen.

## Testing

Run `/usr/bin/python3 apps/desktop-dictation/test_x11.py` with Xvfb and xdotool on PATH. The fixture creates a private X server, supplies audio and verifies input, focus, clipboard and overlay behavior. Pass `--chrome` for browser fields in a throwaway profile with extensions disabled. Add `--real-model` to dictate three different recordings into those fields using the installed local engine.
