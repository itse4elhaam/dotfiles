# Reference: verified commands and Remotion scaffold

Everything here was verified against the agent-browser core skill (installed version) or the Remotion docs at remotion.dev. Facts that could not be pinned down are marked *verify before first use* rather than asserted.

## Verified agent-browser recording

From `agent-browser skills get core` and its `references/video-recording.md`:

```bash
agent-browser open <url>              # launch a session first
agent-browser record start ./raw.webm # start recording to a WebM file
# ... snapshot / click / fill / wait steps ...
agent-browser record stop             # stop and save

agent-browser record restart ./take2.webm  # stop current, start a new take
agent-browser wait 500                     # short pause so a human can follow along
agent-browser close                        # end the session
```

- Output is WebM, VP8/VP9 codec.
- Recordings add slight overhead; keep the recorded run short and deterministic.
- Viewability trick from the guide: put a short `wait 500` before each meaningful action.
- The guide pairs recording with screenshots (`agent-browser screenshot page.png`) when still frames are useful as fallback evidence.

## Verified inspection and trimming (ffmpeg / ffprobe)

```bash
# duration in seconds
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 raw.webm

# frame rate, as a fraction
ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of default=noprint_wrappers=1:nokey=1 raw.webm

# one frame every 2 seconds, for scanning the whole take
ffmpeg -i raw.webm -vf fps=1/2 frames/scan_%03d.png

# dense frames: 5 fps for 2 seconds starting at t=7
ffmpeg -ss 7 -i raw.webm -vf fps=5 -frames:v 10 frames/dense_%03d.png

# cut dead time out of the raw before rendering (stream copy is lossless and instant)
ffmpeg -ss <start> -to <end> -i raw.webm -c copy trimmed.webm
```

## Verified Remotion render

From the Remotion docs:

- Render command: `npx remotion render <entry-point> <composition-id> <output-location>`. Example: `npx remotion render src/index.ts DocumentUx out/final.mp4`.
- A composition is registered via `registerRoot(RemotionRoot)` in the entry point and declared with a `Composition` that has `id`, `component`, `durationInFrames`, `fps`, `width`, `height`.
- A local video plays back with `<OffthreadVideo src={staticFile('video.webm')} />`; `staticFile` resolves against the project's `public/` folder, so the raw recording is copied there.
- Overlay timing uses `useCurrentFrame()` for the current frame and `interpolate()` for fade-in/out. `AbsoluteFill` gives a full-screen layer.

## Minimal Remotion scaffold

A single-composition project. Create it inside the artifact folder (e.g. `./bug-artifacts/<slug>-<timestamp>/render/`), drop the trimmed raw recording in as `public/raw.webm`, write `annotations.json` one level up, and fill in the `fps` and `durationInFrames` from the ffprobe values.

### package.json

```json
{
  "name": "document-ux-render",
  "private": true,
  "scripts": {
    "render": "remotion render src/index.ts DocumentUx ../final.mp4"
  },
  "dependencies": {
    "@remotion/cli": "latest",
    "react": "latest",
    "react-dom": "latest",
    "remotion": "latest"
  }
}
```

Install with `npm i`. (Pinning `latest` keeps the scaffold version-agnostic; Remotion's own template pins exact versions, which is fine too.)

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "lib": ["DOM", "ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "resolveJsonModule": true
  }
}
```

### src/index.ts

```tsx
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

### src/Root.tsx

```tsx
import React from "react";
import { Composition } from "remotion";
import { DocumentUx } from "./DocumentUx";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="DocumentUx"
      component={DocumentUx}
      durationInFrames={552}
      fps={30}
      width={1280}
      height={720}
    />
  );
};
```

`durationInFrames = round(durationSeconds * fps)` from the ffprobe values. `width`/`height` match the recording's resolution (read it with `ffprobe -v error -select_streams v:0 -show_entries stream=width,height` if unknown).

### src/DocumentUx.tsx

```tsx
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import annotationsJson from "../annotations.json";

// Seconds a caption stays on screen; the window covers fade in plus fade out.
const BEAT_LENGTH = 2.2;
const ENTER = 0.3; // entrance: ease-out fade plus 10px rise
const EXIT = 0.2; // exit: pure fade

const SYSTEM =
  "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
const MONO =
  "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace";

const COLORS = {
  text: "#e6e1d9",
  muted: "#aaa39a",
  accent: "#8ab4ff",
  bug: "#e5746e",
  expected: "#7fc9a0",
};

const clamp = (v: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, v));
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

type Region = { x: number; y: number; w: number; h: number };

type AnnotationStep = {
  at: number;
  caption: string;
  highlight?: boolean;
  region?: Region;
};

type Annotations = {
  kind?: "bug" | "feature";
  title: string;
  expected?: string;
  actual?: string;
  steps: AnnotationStep[];
};

const annotations = annotationsJson as Annotations;
const kind = annotations.kind === "feature" ? "feature" : "bug";

// Shared beat timing: ease-out entrance (fade plus rise), pure-fade exit.
const useBeatMotion = (time: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame / fps - time;
  const enter = easeOut(clamp(local / ENTER, 0, 1));
  const exit = interpolate(local, [BEAT_LENGTH - EXIT, BEAT_LENGTH], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return { opacity: enter * (1 - exit), rise: (1 - enter) * 10 };
};

const StepCaption: React.FC<{ step: AnnotationStep; index: number }> = ({
  step,
  index,
}) => {
  const { opacity, rise } = useBeatMotion(step.at);
  if (opacity <= 0.001) {
    return null;
  }
  const highlight = step.highlight === true;
  const accent = highlight ? COLORS.bug : COLORS.accent;
  const kicker = highlight
    ? kind === "feature"
      ? "KEY"
      : "BUG"
    : "STEP " + String(index + 1).padStart(2, "0");
  return (
    <div
      style={{
        position: "absolute",
        left: 56,
        bottom: 56,
        width: "65%",
        opacity,
        transform: "translateY(" + rise + "px)",
      }}
    >
      <div style={{ display: "flex", alignItems: "stretch", gap: 18 }}>
        <div
          style={{
            width: 3,
            borderRadius: 2,
            background: accent,
            flexShrink: 0,
          }}
        />
        <div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: accent,
              marginBottom: 10,
            }}
          >
            {kicker}
          </div>
          <div
            style={{
              fontFamily: SYSTEM,
              fontSize: 28,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              lineHeight: 1.35,
              color: COLORS.text,
            }}
          >
            {step.caption}
          </div>
        </div>
      </div>
    </div>
  );
};

const FocusRegion: React.FC<{ step: AnnotationStep }> = ({ step }) => {
  const { opacity } = useBeatMotion(step.at);
  const r = step.region;
  if (!r || opacity <= 0.001) {
    return null;
  }
  const dim = "rgba(0, 0, 0, 0.35)";
  const top = r.y;
  const left = r.x;
  const bottom = clamp(100 - r.y - r.h, 0, 100);
  const right = clamp(100 - r.x - r.w, 0, 100);
  const strips = [
    { left: 0, top: 0, width: "100%", height: top + "%" },
    { left: 0, top: top + r.h + "%", width: "100%", height: bottom + "%" },
    { left: 0, top: top + "%", width: left + "%", height: r.h + "%" },
    {
      left: left + r.w + "%",
      top: top + "%",
      width: right + "%",
      height: r.h + "%",
    },
  ];
  return (
    <>
      {strips.map((strip, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: strip.left,
            top: strip.top,
            width: strip.width,
            height: strip.height,
            background: dim,
            opacity,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: left + "%",
          top: top + "%",
          width: r.w + "%",
          height: r.h + "%",
          border: "2px solid " + COLORS.bug,
          opacity,
          transform: "scale(" + (1 - (1 - opacity) * 0.02) + ")",
        }}
      />
    </>
  );
};

const CompareColumn: React.FC<{
  label: string;
  color: string;
  text: string;
}> = ({ label, color, text }) => (
  <div
    style={{
      display: "flex",
      alignItems: "stretch",
      gap: 12,
      width: "46%",
      maxWidth: 420,
    }}
  >
    <div
      style={{
        width: 3,
        borderRadius: 2,
        background: color,
        flexShrink: 0,
      }}
    />
    <div>
      <div
        style={{
          fontFamily: MONO,
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: SYSTEM,
          fontSize: 20,
          fontWeight: 500,
          letterSpacing: "-0.01em",
          lineHeight: 1.4,
          color: COLORS.text,
        }}
      >
        {text}
      </div>
    </div>
  </div>
);

const CompareStrip: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  const beat = annotations.steps.find(
    (s) => s.highlight && time >= s.at && time < s.at + BEAT_LENGTH
  );
  const { opacity, rise } = useBeatMotion(beat ? beat.at : -1);
  if (kind === "feature") {
    return null;
  }
  if (!beat || opacity <= 0.001) {
    return null;
  }
  return (
    <div
      style={{
        position: "absolute",
        top: 56,
        left: 56,
        display: "flex",
        gap: 28,
        width: "58%",
        opacity,
        transform: "translateY(" + rise + "px)",
      }}
    >
      <CompareColumn
        label="EXPECTED"
        color={COLORS.expected}
        text={annotations.expected}
      />
      <CompareColumn
        label="ACTUAL"
        color={COLORS.bug}
        text={annotations.actual}
      />
    </div>
  );
};

const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;

  const firstStep = annotations.steps[0];
  const bugStep = annotations.steps.find((s) => s.highlight);

  // Fade in over ENTER, hold about 3.5s, fade out before the first caption.
  const holdEnd = firstStep
    ? Math.max(ENTER, Math.min(ENTER + 3.5, firstStep.at - EXIT))
    : ENTER + 3.5;
  const enter = easeOut(clamp(time / ENTER, 0, 1));
  const exit = interpolate(time, [holdEnd - EXIT, holdEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = enter * (1 - exit);
  if (opacity <= 0.001) {
    return null;
  }

  const minutes = bugStep ? Math.floor(bugStep.at / 60) : 0;
  const seconds = bugStep
    ? String(Math.round(bugStep.at % 60)).padStart(2, "0")
    : "00";

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background:
          "linear-gradient(165deg, rgba(18, 18, 18, 0.92) 0%, rgba(18, 18, 18, 0.72) 100%)",
        opacity,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "70%",
          textAlign: "center",
          transform: "scale(" + (1 + (1 - enter) * 0.04) + ")",
        }}
      >
        <div
          style={{
            fontFamily: MONO,
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: COLORS.accent,
            marginBottom: 20,
          }}
        >
          {kind === "feature" ? "UX WALKTHROUGH" : "BUG REPRO"}
        </div>
        <div
          style={{
            fontFamily: SYSTEM,
            fontSize: 56,
            fontWeight: 650,
            letterSpacing: "-0.02em",
            lineHeight: 1.12,
            color: COLORS.text,
            marginBottom: 24,
          }}
        >
          {annotations.title}
        </div>
        <div
          style={{
            width: 200,
            height: 2,
            borderRadius: 1,
            background: COLORS.accent,
            transform: "scaleX(" + enter + ")",
            marginBottom: 20,
          }}
        />
        {kind !== "feature" && bugStep && (
          <div
            style={{
              fontFamily: MONO,
              fontSize: 13,
              letterSpacing: "0.08em",
              color: COLORS.muted,
            }}
          >
            breaks at {minutes}:{seconds}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

export const DocumentUx: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;

  const active = annotations.steps.find(
    (s) => time >= s.at && time < s.at + BEAT_LENGTH
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo src={staticFile("raw.webm")} />

      {active && active.region && <FocusRegion step={active} />}

      {active && (
        <StepCaption
          step={active}
          index={annotations.steps.indexOf(active)}
        />
      )}

      <CompareStrip />

      <TitleCard />
    </AbsoluteFill>
  );
};

```


Note: the component uses only the verified Remotion API set (AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, interpolate). All easing, dimming, and focus math is plain JavaScript plus CSS transforms, so no additional Remotion APIs were introduced. `durationInFrames` is not read in the component body; the `fps` read drives all the time math, which keeps the overlay honest even if a recording is not exactly 30 fps.

### Render

```bash
npx remotion render src/index.ts DocumentUx ../final.mp4
```

The output is `final.mp4` next to the render folder, ready to attach to a GitHub issue or PR.

## Verify before first use

- Default recording frame rate of agent-browser WebM output is not documented in the installed guide. Always read fps from `ffprobe` in step 3 and set the composition `fps` to match.
- Remotion's current Node.js requirement: check remotion.dev before pinning a Node version in setup docs.
- Remotion `Video`/`OffthreadVideo` also accept `startFrom`/`endAt` trim props, but this scaffold uses the ffmpeg cut instead, which is already verified.
