# RecIt

A native Linux recorder with two modes: screen with a camera widget, or a camera that fills the frame. Uses Qt for the interface, libobs for capture/composition/encoding, and FFmpeg to prepare MP4 files without re-encoding.

## Use

Open **RecIt** from the application launcher, or run `recit`.

1. Choose Camera or Loom. New preferences default to Camera; existing preferences keep your last mode.
2. In Loom mode, choose **Entire screen** or **A specific window**. For a window, select it from the list; use the refresh button after opening another window. Choose your camera and microphone, then a camera shape, size, and corner.
3. Start recording. A three-second countdown gives you time to get ready.
4. Press **Ctrl + Shift + F9** to stop and save. **Ctrl + Shift + F10** pauses or resumes. **Ctrl + Shift + F8** toggles pointer-follow zoom. These also work while the main window is hidden. The tray menu has the same controls.

Screen recordings hide the main window before capture begins. A live camera widget remains visible above your desktop, including when you change workspaces. Drag it to move it; right-click for Stop, Pause, Zoom, or Open RecIt. It also appears while preparing a screen recording. Camera recordings keep the main preview visible and use the camera for the complete video frame. Escape cancels the countdown.

Videos save to `~/Videos/RecIt`. Recordings opens a dedicated library page with a newest-first list of saved MP4 and MKV videos, dates, file sizes, and filename search. Select a recording to play, pause, seek, or adjust volume in the embedded player. Use **Copy path**, **Delete recording**, or **Upload to Loom** for the selected video. Long names are shortened in the list; hover to see the complete path. Refresh reloads the list; Open folder opens the directory. **Back to recorder** stops playback and restores your recorder setup. The library is unavailable during countdown, recording, saving, or uploading. Recording hotkeys and tray recording are disabled while browsing, and pending recording starts cannot run behind the library.

Window capture records the selected window's content, including when another window covers it. Keep the selected window open and unminimized. Closing or minimizing it stops and saves the recording with a warning. Resizing the selected window refits it to the video frame. Computer sound, if enabled, still records the computer's audio rather than audio isolated to that window.

In Camera mode, **Expand camera** hides the settings panel while keeping recording controls visible. **Show controls** brings the settings back. The complete camera image fits inside the video frame without cropping; sources with a different aspect ratio have black borders.

## Microphones and Bluetooth headsets

**Clean microphone** is on by default, reduces background microphone noise and controls loud peaks when available, and remembers your choice; setup warnings show when processing falls back.

Automatic microphone follows the system input. When the system output is a Bluetooth headset, the live recorder preview automatically prepares that headset's hands-free microphone instead. This includes OnePlus earbuds. RecIt prefers advertised LC3 speech or mSBC profiles over narrowband CVSD; actual quality depends on the headset and audio server. Hands-free mode can reduce playback quality while monitoring or recording.

An explicit microphone selection always wins. Microphone off records without a microphone. Live microphone levels are on by default while the recorder page is visible. They use the recording microphone and Clean microphone processing, and can switch a Bluetooth headset to hands-free mode. Turn off Live microphone levels to release the microphone. Recordings, hiding or closing the app, and Microphone off release monitoring and safely restore playback. Starting a recording keeps the live microphone open through preparation, without restoring and reopening the headset. Quick audio check pauses monitoring and releases its stream before opening the check; monitoring resumes when the check closes. Recording preparation runs in the background; closing during preparation waits for that worker, restores safely, and never starts capture. The recording status shows the exact microphone source in use. An unavailable headset fails visibly instead of silently selecting a webcam microphone. If the selected microphone disappears during recording, RecIt stops and saves with a warning.

For PipeWire Bluetooth devices, RecIt reads BlueZ's live `org.bluez.Device1.Connected` property through `busctl`. PipeWire can retain `api.bluez5.connection=disconnected` on a connected card and its sources. A failed connection query produces an error rather than trusting stale nodes. Preparation allows a short reconnect interval within its existing timeout. Regression tests replay a sanitized OnePlus Buds 4 A2DP snapshot; the hands-free source and profile changes are simulated.

After capture stops, RecIt releases its audio sources and restores the previous profile only if it still owns the change and no other audio streams use that headset. It retries deferred restoration while idle. Another application's profile changes take precedence. Closing performs one final safe restoration attempt; active streams can leave restoration deferred. Offscreen integration tests exercise the real device helper with a synthetic audio server through A2DP → hands-free → capture → release → the exact prior profile, including repeated recordings, failed starts, disconnects, closing during preparation, explicit microphone overrides, busy streams, and external profile changes; no live headset capture or profile switching was used to verify this integration.

Before recording with a microphone, RecIt checks that the exact source is connected, unmuted, and has nonzero input volume. It never changes system mute or gain. A temporarily missing Default output retries for up to four seconds and fails visibly instead of selecting a webcam microphone. A real non-Bluetooth output still uses the actual system default input.

Preparation then shows **Checking microphone; say a few words** for up to eight seconds while the camera and interface remain responsive. Recording requires fresh microphone callbacks with at least one nonzero post-filter packet, even if very quiet. Computer sound cannot satisfy this check. No samples and zero-only samples produce different errors and offer **Check microphone** or another attempt; turning Clean microphone off can help distinguish suppression in a quiet room. Escape cancels preparation. Microphone off bypasses this check. During recording, five seconds without samples or fifteen seconds of exact-zero audio produce a warning retained with the save result; normal quiet pauses do not stop recording. These checks detect a dead microphone path, but do not prove encoded audio or resolve the unverified cause of the previously silent Bluetooth clip. Regression tests use synthetic native callbacks and mocked device metadata, without opening capture devices or changing audio settings.

### Microphone processing

The microphone uses verified OBS RNNoise followed by a peak limiter at -3 dB with a 60 ms release. Computer audio bypasses these filters. If RNNoise is unavailable, RecIt uses gentle verified Speex suppression at -15 dB; if neither is available, it keeps the microphone without noise reduction. Missing filters produce a setup warning. Turning **Clean microphone** off bypasses both filters.

There is no gate, automatic gain, or separate compressor. Suppression helps with mild background noise and can change wanted vocal detail. It does not cancel speaker echo or repair an overloaded microphone, and the microphone limiter cannot protect the combined microphone-plus-computer mix. See [audio research and verification notes](docs/audio-notes.md) for source references, timing, and test limits.

## Camera shapes

Circle, rounded square, square, and a custom image mask. For a custom mask, use a PNG with transparent areas where the camera should be hidden and opaque areas where it should show. The desktop widget uses a binary silhouette, so partially transparent custom edges become a hard boundary. The existing camera source renders directly into this native widget; it does not open the camera a second time.

## Pointer zoom

During a screen recording, point at the part you want to explain and press **Ctrl + Shift + F8**. The video smoothly zooms to the pointer and follows it. Press the shortcut again to smoothly return to the complete screen. Choose 1.5×, 2×, or 2.5× in the main window before recording. Zoom also appears in the tray and camera widget's right-click menu. Pause freezes the zoom animation; stopping resets it.

Zoom changes the recorded composition, not the desktop you are using. It is clamped at the capture edges. With **A specific window**, the pointer is tracked relative to that window and the camera stays independently anchored in the recorded video. The visible camera widget can still be dragged to move the recorded camera.

With **Entire screen**, OBS's X11 capture includes the floating camera window and cannot exclude individual windows. RecIt records the desktop camera once rather than adding a duplicate. The camera can move, enlarge, or leave the video frame during zoom, because it is part of the captured desktop. Its context menu and tooltips also appear if you open them while recording.

## Loom

Open **Sharing → Connect Loom account**. A terminal opens Atlassian's consent and browser sign-in flow. Complete it using the account that owns your Loom workspace. RecIt never handles the account password. The official TWG CLI stores its own credentials.

Choose who can watch uploads and optionally enable automatic uploads. The bundled CLI applies visibility after uploading, so the Loom account's defaults apply during upload. Successful uploads copy the Loom link to the clipboard. Files remain on your computer if uploading fails.

The verified official CLI binary is installed at `~/.local/share/glint/twg`. It supports `loom video upload`, but actual account upload and plan eligibility require signing in and testing with your account. Loom documents uploads on Business, Business + AI, and Enterprise plans, excluding Business + AI trials, with a 4 GB or 12-hour limit. RecIt checks file size; Loom enforces account eligibility and duration. No hosting or DNS changes are needed for Loom links. `loom.truedevs.tech` has not been configured.

Loom does not currently publish an open API for local-file uploads. The Loom recording SDK records inside an integrated app; it is not a public MP4 upload API. RecIt therefore uses the official CLI's OAuth 2.1 flow, not custom OAuth credentials or private endpoints. No app registration or secret is needed in RecIt. Connecting only signs in; it does not upload a video. Installation alone does not mean an account is connected.

On 2026-10-22, read-only help checks of installed TWG 1.3.6 confirmed `loom video upload <file>`, optional `--title`, and `loom video visibility set <id> --visibility owner|workspace|public`. This version has no upload-time visibility flag. RecIt keeps the selected file, CLI, and visibility fixed for each upload. It copies the link only after the visibility command succeeds. A failed upload can leave a remote video; check the Loom library before retrying. A successful CLI response does not prove Loom has finished processing the video. Raw CLI errors are not displayed because they can contain account details or credentials.

Complete consent and browser sign-in yourself through **Connect Loom account** using the Atlassian account/site with access to your Loom workspace. The CLI owns credential storage and refresh. Then, when you want to send a particular recording, open **Recordings**, select that video, and choose **Upload to Loom**. Upload progress and results appear in the recorder; successful uploads copy the link to your clipboard. Account sign-in, workspace access, plan eligibility, and a real upload remain unverified; tests mock all CLI processes and never authenticate or transmit recordings.

Official references: [TWG command catalog](https://atlassian.github.io/twg-cli/commands/commands-catalog/), [OAuth authentication](https://developer.atlassian.com/platform/teamwork-graph/twg-cli/getting-started/how-authentication-works/), [CLI setup](https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/), [Loom open API status](https://support.atlassian.com/loom/docs/does-loom-have-an-open-api/), [Loom recording SDK API](https://dev.loom.com/docs/record-sdk/details/api), and [upload plans and limits](https://support.atlassian.com/loom/docs/upload-or-import-videos/).

## Video and performance

- Default output: 3840 × 2160, 30 fps, H.264 with AAC audio.
- Intel VAAPI hardware encoding is preferred. The app labels CPU encoding if hardware encoding cannot start.
- Alternative output: 1920 × 1080, 30 fps.
- Cameras advertising MJPEG use an explicit resolution and frame rate instead of inheriting the driver's raw-video defaults. RecIt chooses the largest advertised MJPEG resolution within the output size at 30 fps, or the smallest advertised size if none fits. Other cameras keep OBS's defaults. The MX Brio advertises 3840 × 2160 MJPEG at 30 fps.
- Output resolution does not create missing source detail. This machine's display is 1920 × 1200; its built-in camera currently opens at 1920 × 1080 MJPEG/30. A higher-resolution source is needed for native 4K detail.
- The preview and recording use OBS's native GPU rendering. Python does not copy video frames through the interface.
- This version targets the installed **OBS 27.x**, x86-64 Linux, and X11. It uses GLX for desktop and window capture and keeps the OpenGL library loaded to work around an OBS 27 loader issue. The engine also supports an explicit EGL fallback for desktop-only capture. It does not support Wayland capture.

## Recovery

Recording first writes MKV, which is recoverable after many kinds of interruption. After stopping, FFmpeg copies its streams into an MP4 and adds streaming metadata. Only a successful conversion removes the MKV. An interrupted app can leave an MKV in Videos/RecIt. Select an MKV in **Recordings** and choose **Prepare MP4** to recover it. Recovery never triggers automatic upload; review the MP4 before choosing Upload to Loom. You can also recover it with:

```bash
ffmpeg -i recording.mkv -c copy -movflags +faststart recovered.mp4
```

Logs: `~/.local/state/glint/glint.log`. Once the log exceeds 10 MB, the launcher retains one previous log on the next launch.

### Audio troubleshooting evidence

The existing stderr log at `~/.local/state/glint/glint.log` now includes lines starting with `recit.audio ` followed by one JSON object. The launcher's 10 MB rotation is unchanged. Each new capture session gets a `session` ID before device preparation, shared by the UI, device worker, OBS engine, restoration and saved-file validation. Live monitoring starts a session with `purpose:"idle"`; recording reuses that session and emits `record.requested` and `idle.handoff` when it takes the live source. `purpose` records the capture origin and stays `idle` through the recording, save and restoration. A genuinely new recording capture uses `purpose:"record"`; each Quick audio check uses `purpose:"check"`. A deferred profile restore retains the session that originally changed the profile, even if a newer capture has begun. `elapsed_ms` uses a monotonic clock; `duration_ms` measures individual operations. Failures name their `phase` and `exception_type`, without copying raw exception or command output.

To inspect one capture session after it finishes, find its `session.start` and filter by that session:

```bash
rg 'recit.audio ' ~/.local/state/glint/glint.log
rg '"session":"YOUR_SESSION_ID"' ~/.local/state/glint/glint.log
```

Look for `selection.chosen`, `profile.selected`, `profile.requested`, `profile.ready`, and `source.resolved`. The exact Pulse source and BlueZ card are separate fields. `changed:false` means the hands-free profile was already active. `connection.checked` identifies the live BlueZ signal separately from PipeWire's potentially stale connection property. `source.resolved` reports mute, per-channel Pulse volume values, input sample specification and OBS's 48000 Hz rate. A 16000 Hz headset input remains limited by that input even though OBS mixes at 48000 Hz. RecIt does not change mute or gain.

`obs.source` distinguishes requested, created and retained capture sources. `filters.backend`, `filter.applied` and `filter.failed` show the actual suppression backend and limiter settings or fallback. `route.verified` records the server's actual attachment; `route.mismatch` records both `requested_source` and `actual_source` plus the stream index. A device ID requested from OBS alone does not prove attachment.

`idle.preparing`, `idle.opened`, `idle.verified`, `idle.stopping`, `idle.stopped` and `idle.discarded` describe the live monitor lifecycle. `idle.failed` reports a monitor failure without copying its error text. `idle.telemetry`, `readiness.telemetry`, `health.telemetry` and Quick audio check's `check.telemetry` contain packet/nonzero-packet counts, packet age, state and post-filter levels. Summaries come from polling at most once per five seconds, with explicit readiness/final-check results and warnings at event boundaries. There is no logging in native callbacks and no per-frame log. JSON `null` for a level represents no finite dBFS value. A readiness timeout distinguishes missing/stale packets from zero-only audio through these fields. Quick audio check shows the friendly headset label and keeps the exact source ID in its tooltip and logs.

Follow `record_start`, `record_stop`, `audio_release`, and `restore` events after capture. `restore.deferred` gives the ownership or busy-stream reason; `restore.skipped` means the card vanished, disconnected, or another app changed its profile. `restore.requested` means the server accepted the restoration command, not independent proof that the hardware completed it. `saved_validation.result` distinguishes missing track, exact digital silence and nonzero decoded audio. `saved_validation.failed` means validation could not finish; it does not mean silence. Validation currently decodes the stopped MKV before MP4 remux. Quick checks validate their temporary sample instead.

The structured events contain no voice samples, PCM, transcripts, credentials, environment dumps, full pactl JSON, filenames or raw process output. Source/card IDs and friendly device names are included as diagnostic evidence. These traces identify where the path failed; meter activity or nonzero decoded samples do not prove intelligible speech or headset quality. Automated checks use mocks and synthetic samples only. Live Bluetooth capture, audible playback and hardware profile changes remain unverified by these checks.

## Install again

Requires the system OBS 27 package and its plugins, FFmpeg, `v4l2-ctl`, `pactl`, X11, and `uv`.

```bash
./apps/recit/install.sh
```

The installer includes matching pinned PySide6 Essentials and Addons packages for the Qt multimedia player and creates a private Python environment, launcher, and app icon. It does not install or accept consent for the optional Loom CLI. For another machine, install the official CLI following [Atlassian's instructions](https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/), then use Connect Loom account.

## Checks

Qt is pinned to PySide6 6.11.1. On the tested Python 3.10 runtime, 6.12.0 loses references to Python's `None` during ordinary widget updates and eventually aborts with `none_dealloc: deallocating None`. The offscreen `test_qt_runtime.py` subprocess exercises 10,000 microphone-meter updates and interpreter shutdown without opening capture devices. Keep Essentials and Addons on the same version when changing the pin. This dependency fix does not establish Bluetooth microphone reliability.

An audio-only hardware comparison requires explicit recording authorization and a closed RecIt process, with no other capture stream active:

```bash
RECIT_TEST_XVFB=/path/to/Xvfb ~/.local/share/glint/venv/bin/python apps/recit/test_hardware_audio.py --microphone-hardware
```

Ordinary discovery skips this test. `RECIT_TEST_MIC_HARDWARE=1` also opts in; `--source EXACT_PULSE_NAME` explicitly overrides Default. The test requires a Bluetooth microphone, records five-second native Pulse samples from the exact source, then observes the same live OBS source before and after production filters. Default goes through `AudioDevices.prepare`; actual stream attachment is verified. Production readiness controls whether a synthetic black scene can be encoded to AAC/MKV. No camera or desktop source is loaded. There is no playback or upload. Artifacts and numeric evidence remain in the printed owner-only `/tmp/recit-hardware-audio-*` directory; remove that directory when no longer needed. Cleanup releases capture and safely restores any profile change owned by the test, including on failure. Missing/very low native signal gives an explicit inconclusive skip; ambient nonzero samples cannot establish intelligible speech or audio quality.

The authorized 2026-10-22 diagnostic used OnePlus Buds 4, active mSBC HFP, 16000 Hz mono, unmuted at 88% source gain. Repeated native Pulse samples, including a speech retry, contained exact zeros. A direct PipeWire capture linked to the same source also contained exact zeros. OBS's verified stream delivered unmuted packets containing exact-zero floats both before and after RNNoise and the limiter. The readiness guard therefore blocked live AAC recording. This establishes where silence was observed in this session, but does not explain the reported working Meet/Loom path or establish a Bluetooth root cause. No production audio fix was justified by this comparison. The separate synthetic 16 kHz mono → production filters → 48 kHz stereo AAC check passed.

```bash
env -u DISPLAY QT_QPA_PLATFORM=offscreen ~/.local/share/glint/venv/bin/python -m unittest discover -s apps/recit
```

Do not run live checks on the user's active desktop during agent work. They open windows, move the pointer, and capture devices. Use an isolated test desktop only when explicitly requested. Close RecIt on that test desktop first. The tests delete temporary recordings afterward:

```bash
QT_QPA_PLATFORM=xcb ~/.local/share/glint/venv/bin/python apps/recit/test_engine.py --capture --camera /dev/video0
QT_QPA_PLATFORM=xcb ~/.local/share/glint/venv/bin/python apps/recit/test_live_ui.py --capture
```

Short hardware smoke tests verify encoding, pause/resume, shape masking, scene changes, output recovery, and app lifecycle. They do not establish sustained performance under every workload.

The MX Brio format selection and full-image layout have automated regression coverage; live Brio recording has not been verified. Earlier checks on this machine recorded 4K at 30 fps with zero lagged frames and zero dropped frames in both screen and camera modes, including pointer-follow zoom. Automated checks cover UI state, recording safety, failed conversion, upload failure handling, camera ownership, shape clipping, and zoom transforms. Live checks also exercise physical mouse dragging and keeping the widget visible while the main window is hidden.

Playback regression checks generate silent H.264 MP4/MKV clips with FFmpeg and assert decoded frames through Qt QVideoSink offscreen, without an audio output device. They cover pause, seek, switching files, missing/corrupt files, and cleanup. Desktop video rendering and audible volume output have not been tested by these checks.

Navigation checks use a mocked OBS engine and synthetic silent video to exercise repeated Recordings/back transitions. The recorder destroys its native OBS preview before hiding it and recreates it after Qt lays out the recorder again; playback stops and clears its source on return. Tests check teardown order and cancel stale queued restoration, but offscreen Qt cannot establish X11/GLX stacking correctness. No live desktop or device capture was used to verify this fix.
