# Microphone processing in OBS 27

Research and implementation checked on 2026-10-22 against OBS 27.2.3 and the installed Ubuntu/Debian package `27.2.3+dfsg1-1`.

## Chosen signal path

The selected microphone uses one denoiser followed by a peak limiter. Computer audio bypasses this chain. The existing 48 kHz stereo engine and AAC settings remain in use.

- Prefer verified RNNoise with `{"method": "rnnoise"}`.
- If RNNoise is absent, use verified Speex with `{"method": "speex", "suppress_level": -15}` and report the fallback. This is a deliberately mild engineering choice.
- Follow suppression with `limiter_filter`, `{"threshold": -3.0, "release_time": 60}`. These values mean dB and milliseconds. No gain boost is applied.
- If suppression is unavailable, retain the microphone without denoising. If either filter cannot be created, skip that filter and report the failure through `Engine.warnings`.
- `Engine.configure(..., microphone_processing=False)` bypasses both filters. The UI's **Clean microphone** preference supplies this option.

RNNoise exposes no strength control in OBS 27. `suppress_level` controls Speex only. We do not stack denoisers. [OBS 27 denoiser implementation](https://github.com/obsproject/obs-studio/blob/27.2.3/plugins/obs-filters/noise-suppress-filter.c)

The limiter's threshold leaves 3 dB of microphone headroom. Its release uses the OBS default. This choice controls occasional loud peaks without compressing the normal speech range. OBS recommends placing a limiter last. [OBS limiter guide](https://obsproject.com/kb/limiter-filter)

## Backend checks

The engine prefers the registered `noise_suppress_filter_v2` ID, then considers the older `noise_suppress_filter`. A generic filter ID alone does not prove RNNoise support.

For each candidate, it copies enabled string values from the `method` property. A build with only one denoiser can omit that property, so the engine checks the untouched source defaults instead. A Speex-only default also requires its compiled `suppress_level` property. Null properties or defaults do not establish support. Temporary properties and settings are released. [OBS 27 property declarations](https://github.com/obsproject/obs-studio/blob/27.2.3/libobs/obs-properties.h), [source defaults and properties](https://github.com/obsproject/obs-studio/blob/27.2.3/libobs/obs-source.c)

Local read-only ELF inspection found `rnnoise_create`, `rnnoise_process_frame`, `rnnoise_destroy`, and the bundled model in `/usr/lib/x86_64-linux-gnu/obs-plugins/obs-filters.so`. No separate `librnnoise` dependency appears in `ldd`; OBS can compile RNNoise directly into the plugin. [OBS 27 build rules](https://github.com/obsproject/obs-studio/blob/27.2.3/plugins/obs-filters/CMakeLists.txt)

## Ordering, timing, and dynamics

OBS 27 inserts added filters at the front of its list, then processes audio backward through that list. Adding suppression first and the limiter second therefore runs suppression before limiting. The parent source owns each attached filter after the engine releases its local reference. [OBS audio filter execution and ownership](https://github.com/obsproject/obs-studio/blob/27.2.3/libobs/obs-source.c)

The denoiser processes 10 ms blocks and adjusts output timestamps for that buffering. RecIt adds no second fixed sync correction. At 48 kHz, RNNoise needs no extra sample-rate conversion. These facts do not establish total microphone latency; device, buffering, and encoding delays remain. [OBS denoiser timing](https://github.com/obsproject/obs-studio/blob/27.2.3/plugins/obs-filters/noise-suppress-filter.c)

The built-in limiter has no lookahead or configurable attack. Its OBS 27 attack constant is effectively 1 microsecond, giving negligible ordinary sample-peak overshoot at 48 kHz. It is not an encoded true-peak guarantee and cannot repair clipping that already happened in the microphone or input converter. It also cannot protect the summed microphone-plus-computer mix. [OBS limiter implementation](https://github.com/obsproject/obs-studio/blob/27.2.3/plugins/obs-filters/limiter-filter.c), [OBS source mixing](https://github.com/obsproject/obs-studio/blob/27.2.3/libobs/obs-audio.c)

We omit a gate, expander, separate compressor, and automatic gain. There is no measured need for them in this task. A gate adds a threshold that can remove quiet beginnings and endings; compression and makeup gain can raise residual room noise. The chosen limiter reduces peaks without making quiet speech louder.

## Limits and verification

Suppression can reduce mild environmental noise such as a fan. It cannot guarantee removal of loud competing sounds, room reverberation, or every keyboard impact. RNNoise is tuned for speech and can change wanted vocal detail; turn **Clean microphone** off when that tradeoff is undesirable. [OBS suppression guidance](https://obsproject.com/kb/noise-suppression-filter)

Noise suppression is not acoustic echo cancellation. This chain has no playback reference or echo canceller, so it cannot promise removal of computer audio leaking from speakers into the microphone. It does not change global PipeWire or PulseAudio configuration and adds no model downloads or runtime dependencies.

`test_audio.py` uses mocked OBS calls to cover backend selection, single-backend builds, disabled methods, filter settings and order, reference ownership, missing filters, bypass, and microphone-only routing. Its optional installed-backend check runs twenty 480-sample silent frames directly through the bundled RNNoise functions. It never calls OBS startup or opens capture devices.

Run the project checks with:

```bash
env -u DISPLAY QT_QPA_PLATFORM=offscreen ~/.local/share/glint/venv/bin/python -m unittest discover -s apps/recit
```

Silent frames establish that this installed backend can allocate and process valid data. They do not establish speech quality, real-world noise reduction, CPU usage, device latency, or audible synchronization. No real microphone, camera, desktop capture, or listening test was used. A separate maximum-reasoning review agreed with the chain, fallback, and timing choices.
