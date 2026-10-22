# RecIt tab recorder

This optional unpacked Chrome/Chromium extension records a real browser tab.
It has no server, upload, content scripts, telemetry or native messaging.
It requests only `desktopCapture`; microphone and camera access use separate
browser permission prompts only when you tick those options.

1. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
   and select this `browser-companion` directory from your reviewed checkout.
   RecIt does not install the extension automatically.
2. Click the extension's toolbar action. A visible recorder page opens.
3. Choose optional tab audio, microphone or camera, then click **Choose tab and
   record**. The browser picker offers tabs only. Choose a tab and consent.
   Tab audio is requested only if the picker grants it. Declining audio records
   without tab audio and shows that status. No system Pulse audio is captured.
4. Keep the recorder page open. Use **Stop and save / cancel**, or revoke sharing
   in Chrome to finalize and release capture. Closing the selected tab also
   finalizes available data. Cancel or denied permission never falls back to a
   window, screen, microphone or another tab.
5. Click **Download recording as WebM** before closing the recorder page.
6. In RecIt open **Recordings → Import video** and select that download. RecIt
   inspects streams with ffprobe and converts VP8/VP9 and Opus to H.264/AAC MP4.
   Compatible H.264 yuv420p and AAC streams can be copied. Originals remain
   unchanged on success or failure. Imports never trigger automatic upload.

Native RecIt hotkeys, pointer zoom, audio filters and camera preferences do not
control this recorder. Its optional camera uses a fixed circular corner overlay.
It does not support pause or trimming. Chrome chooses available source quality;
output uses the browser's supported WebM codec. Long recordings consume browser
memory, so download promptly. Closing this recorder page during capture can lose
the recording; a leave-page prompt is offered where Chrome permits it.

Load the extension yourself only after reviewing it. No browser extension was
installed and no live tab, device or desktop was captured during automated QA.
The mocked Node tests exercise lifecycle behavior, not browser permission UI,
Chrome codec support or real media capture. Live browser verification is pending.

References: [Chrome desktopCapture](https://developer.chrome.com/docs/extensions/reference/api/desktopCapture),
[Chrome tabCapture](https://developer.chrome.com/docs/extensions/reference/api/tabCapture),
[screen capture security model](https://www.w3.org/TR/screen-capture/).

Run the synthetic tests with `node --test test_recorder.cjs` in this directory.
