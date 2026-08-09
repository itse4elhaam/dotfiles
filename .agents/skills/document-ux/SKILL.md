---
name: document-ux
description: Use when a UI interaction must be shared with someone who wasn't there: a bug or a feature walkthrough, reproduced, annotated, and rendered as a short captioned video for a GitHub issue or PR. Triggers include "record a video of this bug/feature", "make a repro/demo video", "document this UX interaction", "annotate this reproduction/walkthrough", or any request to show a UI interaction to someone who cannot run the app themselves.
---

# Document UX

Turn a bug report or a feature walkthrough into a short annotated video: a raw browser recording, reviewed frame by frame, then rendered with captions that point at the exact moment things matter. The video rides in a GitHub issue or PR so a reviewer who was not there can see the interaction without running the app.

**Leading words:** _repro_ means the shortest deterministic path to the subject, the only thing the video should show; _key beat_ means the exact moment the video exists to show, the bug moment for a bug or the defining moment of the flow for a feature walkthrough, the frame everything else serves; _dead time_ means footage that carries no meaning, to be trimmed.

## When to use

Use when an interaction a reviewer must *see* needs to travel: UI glitches, layout breakage, broken interactions, wrong states, onboarding flows, new features, design reviews, before/after states. Anything where a screenshot tells half the story and a video tells all of it. Do not use for pure logic or API bugs that a minimal reproduction script already demonstrates: a video adds nothing there.

## Interface

Invoke as `/document-ux <description | issue/ticket context>`. The skill infers everything it can from the description; it asks only for what is missing: the URL or entry point, the exact steps, and what should happen instead.

## Workflow

### 1. Collect the minimum context

Read the bug description or issue. Pull out four facts: (a) the URL or app entry point, (b) the steps to run, (c) what happens on screen, (d) what should happen or be shown. If the description already has a URL and a concrete step or two, use them. Ask only for the missing pieces; do not interview for anything the video will not need. State the subject as one recipe: "open X, do Y, observe Z".

Completion: a one-paragraph recipe with a concrete entry point and observable outcome, written down before any tool runs.

### 2. Reproduce and record the raw _repro_

If the agent-browser commands below are unfamiliar, run `agent-browser skills get core` first: it is the usage guide for the installed version. Recording facts in this skill are taken from that guide and from its video-recording reference.

First explore to understand the subject, then find the shortest deterministic path:

```bash
agent-browser open <url>
agent-browser snapshot -i          # find stable refs
# walk the repro, one action per snapshot, re-snapshot after every page change
agent-browser wait --load networkidle   # wait for real conditions, not bare sleeps
```

When the path is confirmed, record a clean final run. A run is clean when it does the repro steps once, with no exploratory detours, no failed clicks, and no dead waits longer than needed. Add short `agent-browser wait 500` pauses before each meaningful beat so a human viewer can track the action (this is the documented pattern for viewable recordings).

```bash
agent-browser open <url>
agent-browser record start ./raw.webm
# ... the repro steps, confirmed working ...
agent-browser record stop
```

The recording saves as WebM (VP8/VP9). If the first take is not clean, restart: `agent-browser record restart ./take2.webm`. If the repro cannot be made deterministic after two takes, stop and report what is flaky rather than shipping a video that shows a different thing each run.

Completion: a raw `.webm` file exists, is non-zero bytes, and deterministically shows the subject from the recipe in step 1.

### 3. Review the recording before annotating

Never annotate from memory. Inspect the footage:

```bash
# duration and frame rate for the timeline
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 raw.webm
ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of default=noprint_wrappers=1:nokey=1 raw.webm

# a frame every 2 seconds to scan the whole take
mkdir -p frames
ffmpeg -i raw.webm -vf fps=1/2 frames/scan_%03d.png

# dense frames around a suspected moment (here 5 fps for the 2 seconds around t=8)
ffmpeg -ss 7 -i raw.webm -vf fps=5 -frames:v 10 frames/dense_%03d.png
```

View the scan frames to lay out the beats: where each step happens, where the _key beat_ lands, where the _dead time_ sits. When the scan is too sparse to pin the key beat, extract denser frames around the candidate moment and view those. Record a timeline: each beat with its start time, plus every dead-time range you will cut.

Completion: a written timeline with each meaningful moment pinned to a second-accurate timestamp from real frames, and a list of dead-time ranges to trim.

### 4. Create the annotation timeline

Write `annotations.json` next to the recording, following the schema below. Open it with `"kind": "bug"` or `"kind": "feature"`; expected and actual come from the recipe in step 1 and are used only for bugs. Timestamps must match the frames you actually viewed in step 3. A caption that points at the wrong second is worse than no caption. Every step gets a short caption; the key beat gets `highlight: true`.

Completion: every beat from the step 3 timeline appears as a step with a real timestamp, and for bugs `expected` and `actual` both state the divergence a reviewer can verify on screen.

### 5. Render the final video

Build the minimal Remotion project and render the annotated `.mp4`. The scaffold lives in `REFERENCES.md`: one composition, `OffthreadVideo` overlaid with the captions from `annotations.json`, rendered with:

```bash
npx remotion render src/index.ts DocumentUx out/final.mp4
```

The `durationInFrames` and `fps` in the composition come from the `ffprobe` values in step 3, so the overlay lines up with the footage. Trim _dead time_ before rendering by cutting the raw file with ffmpeg (`ffmpeg -ss <start> -to <end> -i raw.webm -c copy trimmed.webm`), then re-point the timeline at the trimmed file; do not leave a long dead intro in front of the subject.

Completion: a `.mp4` exists, the captions appear at the timestamps the frames showed, the key beat is clearly visible with its highlight, and every caption follows the Annotation style contract below.

### 6. Save and report the artifacts

Put both files in a predictable place: `./ux-artifacts/<slug>-<timestamp>/` under the invocation directory (slug from the subject, e.g. `empty-promo-crash`). Files: `raw.webm` (the untouched recording), `final.mp4` (the annotated render), `annotations.json` (the timeline). Target under 60 seconds of final video; keep it longer only when the subject genuinely needs it.

Completion: both video files and the timeline sit in one timestamped folder, and the final duration is under 60 seconds or the longer duration is justified by the repro itself.

### 7. Report

Give the user the artifact paths plus a one-paragraph summary: the recipe, where the key beat is, and for bugs the expected-versus-actual divergence. If the video is for an issue or PR, hand them the exact lines to paste: paths, key beat timestamp, and the divergence.

Completion: the user can grab the folder paths and paste a shareable description without re-watching the video.

## Annotations schema

`annotations.json` is the single source of truth the Remotion overlay reads. `at` values are seconds from the start of the video being rendered.

```json
{
  "kind": "bug",
  "title": "Checkout crashes on empty promo code",
  "fps": 30,
  "durationSeconds": 18.4,
  "expected": "Applying an empty promo code leaves the cart total unchanged.",
  "actual": "Applying an empty promo code throws a 500 and resets the cart to $0.",
  "steps": [
    { "at": 2.1, "caption": "Open the cart with two items", "highlight": false },
    { "at": 5.6, "caption": "Click the promo code field", "highlight": false },
    { "at": 8.3, "caption": "Apply with the field empty", "highlight": true },
    { "at": 9.8, "caption": "Error toast, cart total reset", "highlight": true, "region": { "x": 55, "y": 40, "w": 25, "h": 18 } }
  ]
}
```

`kind` is `"bug"` by default; set it to `"feature"` for a walkthrough, which switches the title kicker to `UX WALKTHROUGH`, the highlight chip to `KEY`, and hides the Expected vs Actual strip (the `expected` and `actual` fields are bug-only). The `region` field on a step is optional and in percent of the frame (x, y, w, h); when present, it focuses the key beat region with a red outline and a dimmed surround, so the eye goes to the subject. Render the title as a card in the first moments, captions during their step windows, an Expected vs Actual block while the highlighted beat plays for bugs, and a focus region when a step declares one, all per the Annotation style section below.

## Annotation style

The overlay is editorial motion graphics, not broadcast lower-thirds: type carries the message and chrome stays quiet. An agent generating a video should reproduce these rules from the contract below without seeing the rendered result.

**Pillars.** Editorial: dark, quiet, reading-first, like a printed magazine caption. Typography over chrome: communicate with kickers, weights, tracking, and mono accents, never with boxes or borders. Point, don't shout: one accent at a time, muted values, nothing saturated. Muted color discipline: every accent sits desaturated against the neutral scale. Restrained motion: entrances settle, exits vanish, nothing loops.

**Palette.** Neutral text `#e6e1d9`; muted `#aaa39a`; accent blue `#8ab4ff` for neutral emphasis (kickers, rules); muted red `#e5746e` for bug and actual (never a saturated red like `#dc2626`); muted green `#7fc9a0` for expected (never a saturated green like `#22c55e`). Overlays are soft gradients of `rgba(18, 18, 18, ...)`, never a hard-edged box.

**Typography.** Kickers: ui-monospace, uppercase, 13 to 14px, 700 weight, letter-spacing 0.12em. Caption body: system-ui, about 28px, 500 weight, letter-spacing -0.01em. Title: system-ui, about 56px, 650 weight, letter-spacing -0.02em. Mono is an accent for labels and metadata, never the body voice. All fonts are system fonts; the render stays offline-safe.

**Layout.** Step captions sit bottom-left with a thin 3px accent left rule and a kicker above the text, zero-padded ("STEP 01"), max-width about 65% of the frame. The key beat swaps the kicker for a chip in the muted red with a red left rule, no background: labeled `BUG` for bugs, `KEY` for features. When a step carries a `region`, draw a thin 2px red focus rectangle there, fade it in with a slight settle, and dim the frame outside the region about 35% black so the eye lands on the key beat. For bugs, Expected vs Actual renders as a compact two-column strip, top-left: each column has a mono uppercase label (EXPECTED in green, ACTUAL in red) over near-white text with a colored left rule. Type and rules, never colored boxes. The title card fills the frame with a soft dark gradient: a mono kicker in accent blue (`BUG REPRO` for bugs, `UX WALKTHROUGH` for features), the title at 56px, a hairline accent rule that draws across, and for bugs a mono meta line beneath reading when the bug appears ("breaks at 0:09"), derived from the first `highlight: true` step's `at`; features show no meta line.

**Motion.** Entrances ease out (cubic) over about 300ms with a small 8 to 10px rise; exits are pure fades of about 200ms; the title card fades in over 300ms, holds about 3.5s, fades out, with one subtle 1.04 to 1 scale settle. No springs, no looping, no constant motion.

Never render: the warning emoji, saturated red or green fill boxes, centered full-width captions, rounded black pills, or mono-everything blocks.

## Dependencies and setup

| Tool | What it does here | Install |
|---|---|---|
| agent-browser | record the raw `.webm` | `npm i -g agent-browser && agent-browser install` (Linux hosts may add `--with-deps` for browser libraries) |
| FFmpeg (`ffmpeg` + `ffprobe`) | inspect duration/fps, extract frames, trim dead time | Debian/Ubuntu: `sudo apt install ffmpeg`; Arch: `sudo pacman -S ffmpeg`; macOS: `brew install ffmpeg` |
| Node.js / npm | run the Remotion CLI | install via nvm or the distro package; Remotion needs a recent Node LTS, check the current requirement at remotion.dev |
| Remotion | render the annotated `.mp4` | per-project, inside the scaffold: `npm i remotion @remotion/cli react react-dom` |

Verify each tool once before first use (`agent-browser doctor` for agent-browser; `ffmpeg -version`; `node -v`).

## Reference

`REFERENCES.md` holds the verified command reference (agent-browser recording, ffmpeg inspection, Remotion render) and the full minimal Remotion scaffold, including the `kind`-aware overlay. Load it when you reach steps 2 and 5.
