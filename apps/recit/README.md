# RecIt

A native Linux recorder with two modes: screen with a camera widget, or a camera that fills the frame. Uses Qt for the interface, libobs for capture/composition/encoding, and FFmpeg to prepare MP4 files without re-encoding.

## Use

Open **RecIt** from the application launcher, or run `recit`.

1. Choose Loom or Camera.
2. In Loom mode, choose **Entire screen** or **A specific window**. For a window, select it from the list; use the refresh button after opening another window. Choose your camera and microphone, then a camera shape, size, and corner.
3. Start recording. A three-second countdown gives you time to get ready.
4. Press **Ctrl + Shift + F9** to stop and save. **Ctrl + Shift + F10** pauses or resumes. **Ctrl + Shift + F8** toggles pointer-follow zoom. These also work while the main window is hidden. The tray menu has the same controls.

Screen recordings hide the main window before capture begins. A live camera widget remains visible above your desktop, including when you change workspaces. Drag it to move it; right-click for Stop, Pause, Zoom, or Open RecIt. It also appears while preparing a screen recording. Camera recordings keep the main preview visible and use the camera for the complete video frame. Escape cancels the countdown.

Videos save to `~/Videos/RecIt`. The latest video has Play, Upload to Loom, and Copy file path buttons. Recordings opens the folder containing earlier videos.

Window capture records the selected window's content, including when another window covers it. Keep the selected window open and unminimized. Closing or minimizing it stops and saves the recording with a warning. Resizing the selected window refits it to the video frame. Computer sound, if enabled, still records the computer's audio rather than audio isolated to that window.

## Camera shapes

Circle, rounded square, square, and a custom image mask. For a custom mask, use a PNG with transparent areas where the camera should be hidden and opaque areas where it should show. The desktop widget uses a binary silhouette, so partially transparent custom edges become a hard boundary. The existing camera source renders directly into this native widget; it does not open the camera a second time.

## Pointer zoom

During a screen recording, point at the part you want to explain and press **Ctrl + Shift + F8**. The video smoothly zooms to the pointer and follows it. Press the shortcut again to smoothly return to the complete screen. Choose 1.5×, 2×, or 2.5× in the main window before recording. Zoom also appears in the tray and camera widget's right-click menu. Pause freezes the zoom animation; stopping resets it.

Zoom changes the recorded composition, not the desktop you are using. It is clamped at the capture edges. With **A specific window**, the pointer is tracked relative to that window and the camera stays independently anchored in the recorded video. The visible camera widget can still be dragged to move the recorded camera.

With **Entire screen**, OBS's X11 capture includes the floating camera window and cannot exclude individual windows. RecIt records the desktop camera once rather than adding a duplicate. The camera can move, enlarge, or leave the video frame during zoom, because it is part of the captured desktop. Its context menu and tooltips also appear if you open them while recording.

## Loom

Open **Sharing → Connect Loom account**. A terminal opens Atlassian's consent and browser sign-in flow. Complete it using the account that owns your Loom workspace. RecIt never handles the account password. The official TWG CLI stores its own credentials.

Choose who can watch uploads and optionally enable automatic uploads. The bundled CLI applies visibility after uploading, so the Loom account's defaults apply during upload. Successful uploads copy the Loom link to the clipboard. Files remain on your computer if uploading fails.

The verified official CLI binary is installed at `~/.local/share/glint/twg`. It supports `loom video upload`, but actual account upload and plan eligibility require signing in and testing with your account. Loom currently documents uploads on paid Business/Enterprise plans and a 4 GB file limit. No hosting or DNS changes are needed for Loom links. `loom.truedevs.tech` has not been configured.

## Video and performance

- Default output: 3840 × 2160, 30 fps, H.264 with AAC audio.
- Intel VAAPI hardware encoding is preferred. The app labels CPU encoding if hardware encoding cannot start.
- Alternative output: 1920 × 1080, 30 fps.
- Output resolution does not create missing source detail. This machine's display is 1920 × 1200; its built-in camera currently opens at 1920 × 1080 MJPEG/30. A higher-resolution source is needed for native 4K detail.
- The preview and recording use OBS's native GPU rendering. Python does not copy video frames through the interface.
- This version targets the installed **OBS 27.x**, x86-64 Linux, and X11. It uses GLX for desktop and window capture and keeps the OpenGL library loaded to work around an OBS 27 loader issue. The engine also supports an explicit EGL fallback for desktop-only capture. It does not support Wayland capture.

## Recovery

Recording first writes MKV, which is recoverable after many kinds of interruption. After stopping, FFmpeg copies its streams into an MP4 and adds streaming metadata. Only a successful conversion removes the MKV. An interrupted app can leave an MKV in Videos/RecIt. When it is the latest recording, RecIt offers **Prepare MP4** to recover it. Play earlier MKVs from the Recordings folder, or recover them with:

```bash
ffmpeg -i recording.mkv -c copy -movflags +faststart recovered.mp4
```

Logs: `~/.local/state/glint/glint.log`. Once the log exceeds 10 MB, the launcher retains one previous log on the next launch.

## Install again

Requires the system OBS 27 package and its plugins, FFmpeg, `v4l2-ctl`, `pactl`, X11, and `uv`.

```bash
./apps/recit/install.sh
```

The installer creates a private Python environment, launcher, and app icon. It does not install or accept consent for the optional Loom CLI. For another machine, install the official CLI following [Atlassian's instructions](https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/), then use Connect Loom account.

## Checks

```bash
env -u DISPLAY QT_QPA_PLATFORM=offscreen ~/.local/share/glint/venv/bin/python -m unittest discover -s apps/recit
```

Do not run live checks on the user's active desktop during agent work. They open windows, move the pointer, and capture devices. Use an isolated test desktop only when explicitly requested. Close RecIt on that test desktop first. The tests delete temporary recordings afterward:

```bash
QT_QPA_PLATFORM=xcb ~/.local/share/glint/venv/bin/python apps/recit/test_engine.py --capture --camera /dev/video0
QT_QPA_PLATFORM=xcb ~/.local/share/glint/venv/bin/python apps/recit/test_live_ui.py --capture
```

Short hardware smoke tests verify encoding, pause/resume, shape masking, scene changes, output recovery, and app lifecycle. They do not establish sustained performance under every workload.

On this machine, short real event-loop tests recorded 4K at 30 fps with zero lagged frames and zero dropped frames in both screen and camera modes, including pointer-follow zoom. Automated checks cover UI state, recording safety, failed conversion, upload failure handling, camera ownership, shape clipping, and zoom transforms. Live checks also exercise physical mouse dragging and keeping the widget visible while the main window is hidden.
