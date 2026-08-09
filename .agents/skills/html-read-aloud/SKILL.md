---
name: html-read-aloud
description: Use when a standalone HTML document, dossier, or report should be read aloud in the browser with synchronized highlighting and scrolling, or when a generated HTML file needs a self-contained narration controller. Adds block-by-block narration with the Web Speech API that works from a file:// URL, with no server, framework, build step, or external dependency.
---

# HTML Read Aloud

Give a standalone HTML document in-browser narration: a floating controller that reads the document block by block with a visible active highlight and synchronized scrolling. Everything runs in the reader's browser on the Web Speech API, so the file works from `file://` with zero infrastructure.

## When to use

Use it when a document is long, linear, or read by someone who may prefer listening: research dossiers, audit reports, review evidence, onboarding material. Skip it for short or scannable pages where narration adds noise. The reader is an add-on; the document must stay fully readable and styled with the controller absent.

## Steps

1. **Decide if narrated reading serves the reader.** State the decision before embedding.
   Completion: a clear yes or no.

2. **Load the scaffold and embed the controller.** Load [REFERENCES.md](REFERENCES.md) and copy its three blocks into the generated HTML: the CSS into `<head>`, the controller markup before `</body>`, and the script after the markup. Mark the reading root with `data-readable-root` on the main content element.
   Completion: the file contains the full controller CSS, markup, and script, and exactly one reading root.

3. **Apply opt-in and opt-out only where needed.** Use `data-readable` to force-read a block and `data-reader-ignore` to exclude one. Let the defaults handle everything else.
   Completion: only blocks meant for the ear are narrated.

4. **Verify once from source.** Open the generated file from `file://` and confirm the controller renders, Play reads the first block with an active highlight, the document scrolls block by block, and controls never overlap speech. One pass only, no browser automation, no screenshots, no type checks. This is an HTML document, not application code.
   Completion: the checklist under Verification passes from a directly opened file.

## Required HTML semantics

- `data-readable-root` on the main content element. This is the predictable reading root; extraction never reads outside it. Convention: `<article data-readable-root>`.
- `data-readable` on a block that must be read even when the defaults would skip it.
- `data-reader-ignore` on a block that must never be read. Put it on any element that should stay out of narration: toolbars, footers, navigation, supplementary asides.
- Attributes are opt-in exceptions. Defaults cover ordinary documents; do not decorate every block.

## Content extraction

Extraction builds a deterministic readable-block list from the reading root, in DOM order.

- Default readable selectors: `h1,h2,h3,h4,p,li,blockquote,figcaption,td,th`.
- Default ignored content: `script,style,nav,button,input,select,textarea,[hidden],[aria-hidden="true"],[data-reader-ignore],pre,code`. Code blocks are excluded by default because they narrate poorly.
- Empty and whitespace-only blocks are dropped.
- Nested elements are never read twice. When a readable block is collected, its descendants are skipped; the topmost readable block wins. A `blockquote` holding several paragraphs becomes one block.
- DOM order is preserved.
- Excessive whitespace is collapsed to single spaces and trimmed.
- Raw URLs are not narrated unless the URL is the block's visible text itself. Embedded URLs are replaced with the word "link".

## Speech model

Use `window.speechSynthesis` and `SpeechSynthesisUtterance`, and create exactly ONE utterance per semantic block, never one for the whole document. One utterance per block gives reliable block synchronization, working previous and next navigation, clean pause boundaries, and resumable progress without depending on word-boundary events.

Per block: build the utterance from normalized `textContent`, apply the current rate and voice, and on `start` mark the block active and scroll to it when auto-follow is on. On `end` advance to the next block, or complete when the list ends. On `error` show a non-blocking status message and stop safely; ignore `interrupted` and `canceled` errors because they come from the controller's own `cancel()` calls.

Always call `speechSynthesis.cancel()` before starting a new queue, before speaking after previous or next navigation, and before restarting the current block after a rate or voice change.

## Reader controls

A compact floating controller with:

- Play or resume, Pause, Stop, Previous block, Next block.
- Playback-rate selector, 0.5 through 2.
- Voice selector populated from installed voices.
- Auto-follow toggle.
- Progress indicator in the form `12 / 84`.

Keyboard shortcuts, active only while focus is inside the controller: Space toggles play and pause, Escape stops, Alt+ArrowLeft and Alt+ArrowRight move to the previous and next block. Never intercept keys while the reader is typing in an input, textarea, select, or contentEditable region.

## Highlighting and scrolling

- Mark the active block with `data-reader-active="true"`.
- Give it a subtle treatment that is not color-only: outline plus a left accent bar, never background color alone.
- With auto-follow on, call `scrollIntoView({ behavior: "smooth", block: "center" })`.
- Respect `prefers-reduced-motion`: scroll instantly instead of smoothly.
- If the reader scrolls away manually while playing, stop following automatically. The explicit auto-follow toggle re-enables it.

## State machine

Transitions: `idle -> playing`, `playing -> paused`, `paused -> playing`, `playing -> stopped`, `playing -> completed`, and `any -> error`. Stopped and completed return to `playing`.

The state object:

```js
{
  blocks: [],       // collected readable blocks in DOM order
  currentIndex: -1, // 0-based index of the block being read
  status: "idle" | "playing" | "paused" | "stopped" | "completed" | "error",
  rate: 1,
  voiceURI: null,
  autoFollow: true
}
```

## Persistence

Store preferences in `localStorage` under a document-specific key derived from the `pathname` and title. Persist `voiceURI`, `rate`, `autoFollow`, and the last completed block index, and restore them on load so a refresh resumes the reader's choices. Never auto-start narration on load; browser autoplay restrictions make it unreliable, and reading starts only on an explicit reader action. Wrap all storage access in `try` and `catch`: on `file://` some browsers restrict `localStorage`, and the reader must fall back to in-memory state without breaking.

## Accessibility

- Every control is keyboard operable.
- Every icon-only control carries an accessible label through `aria-label` and `title`.
- A `role="status"` region with `aria-live="polite"` announces state changes: Playing, Paused, Stopped, Completed, and errors.
- The active highlight is not color-only.
- Every control has a visible focus indicator.
- The controller stays usable at 200% zoom and narrow widths: it wraps and never overflows the viewport.
- Print styles hide the controller and all active decoration.

## Privacy and dependencies

V1 runs entirely in the browser. It uses only installed or native voices, makes no network requests for narration, loads no external JavaScript, and works from `file://`. There is no server, no build step, no framework, and no browser extension. No analytics, no fonts, no CDN.

## file:// constraints

The controller is plain HTML, CSS, and JavaScript with no module loading, no `fetch`, and no CORS-sensitive code, so a directly opened `file://` file behaves the same as a served page. Guard against two local-file quirks: `localStorage` may be restricted on opaque file origins, and voices may load asynchronously through `voiceschanged`. Both are handled in the scaffold: storage degrades to memory, and voice loading retries.

## Verification checklist

A narrated document passes when all of these hold:

- The controller renders and Play reads the first block.
- Blocks narrate one at a time in DOM order, each as its own utterance.
- The active block shows a visible, non-color-only highlight.
- Auto-follow scrolls the active block into view, respects reduced motion, and yields when the reader scrolls away.
- Play, Pause, Stop, Previous, Next, rate, voice, and auto-follow all work, and no speech overlaps.
- Voice and rate are changeable, and preferences and progress survive a refresh.
- Keyboard shortcuts work from the controller and never steal typing from form controls.
- The controller is usable at 200% zoom and at narrow widths.
- Code, navigation, form controls, and `data-reader-ignore` regions are never narrated.
- The controller and active decoration are hidden in print.
- The file works from `file://` with no server, build, framework, automation, or external JavaScript.
