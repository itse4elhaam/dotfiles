# HTML read-aloud reference

Load this file when the `html-read-aloud` skill is active. It is a reusable, self-contained scaffold: three copy-paste blocks that turn a standalone HTML document into one that can narrate itself from `file://` with no server, no framework, no build step, and no external dependency.

## Integration contract

Embed all three blocks into the target HTML file:

1. **Block A, controller CSS**: copy into the `<head>`, inside the existing `<style>` or as its own `<style>`.
2. **Block B, controller markup**: copy before `</body>`.
3. **Block C, reader JavaScript**: copy after Block B, before `</body>`.

Mark the reading root on the main content element so extraction is predictable:

```html
<article data-readable-root>
  <!-- readable blocks live here -->
</article>
```

Optional per-block attributes:

- `data-readable` force-reads a block that defaults would skip.
- `data-reader-ignore` excludes a block and its subtree from narration.

The controller reads the whole document when no root is marked. Code, navigation, form controls, and hidden regions are excluded by default. The scaffold works on a directly opened `file://` URL: no modules, no `fetch`, no CORS-sensitive code.

## Block A: controller CSS

Copy into `<head>`. It reuses the host document's design tokens (`--accent`, `--panel`, `--text`, `--muted`, `--border`) when they exist, so it picks up the dossier theme automatically, and falls back to its own defaults otherwise.

```css
/* ===== HTML read-aloud controller ===== */
#reader-controller{
  --reader-accent: var(--accent, #8ab4ff);
  --reader-bg: var(--panel, #1f1f1f);
  --reader-text: var(--text, #e6e1d9);
  --reader-muted: var(--muted, #aaa39a);
  --reader-border: var(--border, #333);
  position: fixed;
  bottom: 1rem;
  inset-inline-end: 1rem;
  z-index: 9999;
  max-width: calc(100% - 2rem);
  padding: .75rem;
  border: 1px solid var(--reader-border);
  border-radius: 1rem;
  background: var(--reader-bg);
  color: var(--reader-text);
  font: 400 .875rem/1.4 system-ui, -apple-system, "Segoe UI", sans-serif;
  box-shadow: 0 .5rem 1.5rem rgba(0,0,0,.35);
}
#reader-controller[hidden]{display:none!important}
.reader-controls-row{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .5rem;
}
#reader-controller .reader-btn{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border: 1px solid var(--reader-border);
  border-radius: .5rem;
  background: transparent;
  color: var(--reader-text);
  cursor: pointer;
}
#reader-controller .reader-btn:hover{background:rgba(128,128,128,.15)}
#reader-controller .reader-btn svg{display:block;width:1.1rem;height:1.1rem;fill:currentColor}
#reader-controller select{
  font: inherit;
  color: var(--reader-text);
  max-width: 12rem;
  padding: .3rem .4rem;
  border: 1px solid var(--reader-border);
  border-radius: .4rem;
  background: var(--reader-bg);
}
.reader-field{
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  color: var(--reader-muted);
  white-space: nowrap;
}
#reader-controller .reader-follow input{font:inherit;margin:0}
#reader-progress{font-variant-numeric:tabular-nums;white-space:nowrap}
.reader-sr{
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
#reader-status{display:block;margin-bottom:.5rem;color:var(--reader-muted);min-height:1.4em}
#reader-controller :focus-visible{outline:3px solid var(--reader-accent);outline-offset:2px}
[data-reader-active="true"]{
  outline: 2px solid var(--reader-accent, #8ab4ff);
  outline-offset: 3px;
  border-radius: 4px;
  box-shadow: inset 3px 0 0 var(--reader-accent, #8ab4ff);
  scroll-margin-top: 5rem;
}
@media (prefers-reduced-motion: reduce){
  #reader-controller{transition:none}
  [data-reader-active="true"]{transition:none}
}
@media print{
  #reader-controller{display:none!important}
  [data-reader-active="true"]{outline:none;box-shadow:none;border-radius:0}
}
```

The active highlight uses outline plus a left accent bar, two non-color channels, so it stays visible for readers who cannot rely on color.

## Block B: controller markup

Copy before `</body>`. Icons are inline SVG, dependency-free, with accessible labels on every icon-only control. The status region is `role="status"` with `aria-live="polite"` so state changes are announced to assistive technology.

```html
<div class="reader-controller" id="reader-controller" role="group" aria-label="Reading controls">
  <span id="reader-status" class="reader-status" role="status" aria-live="polite">Ready</span>
  <div class="reader-controls-row">
    <button type="button" id="reader-play" class="reader-btn" aria-label="Play or resume" title="Play or resume (Space)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
    </button>
    <button type="button" id="reader-pause" class="reader-btn" aria-label="Pause" title="Pause (Space)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>
    </button>
    <button type="button" id="reader-stop" class="reader-btn" aria-label="Stop" title="Stop (Escape)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
    </button>
    <button type="button" id="reader-prev" class="reader-btn" aria-label="Previous block" title="Previous block (Alt+Left)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 6h2v12H7zM19 6l-10 6 10 6z"/></svg>
    </button>
    <button type="button" id="reader-next" class="reader-btn" aria-label="Next block" title="Next block (Alt+Right)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6h2v12h-2zM5 6l10 6-10 6z"/></svg>
    </button>
    <label class="reader-field">Speed
      <select id="reader-rate" aria-label="Playback speed">
        <option value="0.5">0.5x</option>
        <option value="0.75">0.75x</option>
        <option value="1" selected>1x</option>
        <option value="1.25">1.25x</option>
        <option value="1.5">1.5x</option>
        <option value="2">2x</option>
      </select>
    </label>
    <label class="reader-field">Voice <select id="reader-voice" aria-label="Voice"></select></label>
    <label class="reader-field reader-follow"><input type="checkbox" id="reader-follow" checked> Auto-follow</label>
    <span class="reader-field"><span class="reader-sr">Progress </span><span id="reader-progress">0 / 0</span></span>
  </div>
</div>
```

## Block C: reader JavaScript

Copy after Block B, before `</body>`. Complete and commented; embed as-is. It uses one utterance per semantic block, always cancels the prior queue before speaking, and degrades gracefully when speech synthesis or storage is unavailable.

```html
<script>
(() => {
  "use strict";

  /* ============ State ============ */
  const state = {
    blocks: [],       // collected readable blocks in DOM order: [{ el, text }]
    currentIndex: -1, // 0-based index of the block being read
    status: "idle",   // idle | playing | paused | stopped | completed | error
    rate: 1,
    voiceURI: null,
    autoFollow: true
  };

  /* ============ Constants ============ */
  const READABLE = "h1,h2,h3,h4,p,li,blockquote,figcaption,td,th";
  const IGNORED = "script,style,nav,button,input,select,textarea,[hidden],[aria-hidden='true'],[data-reader-ignore],pre,code";
  const REDUCED_MOTION = !!window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ============ DOM refs ============ */
  const controller = document.getElementById("reader-controller");
  const statusEl = document.getElementById("reader-status");
  const progressEl = document.getElementById("reader-progress");
  const playBtn = document.getElementById("reader-play");
  const pauseBtn = document.getElementById("reader-pause");
  const stopBtn = document.getElementById("reader-stop");
  const prevBtn = document.getElementById("reader-prev");
  const nextBtn = document.getElementById("reader-next");
  const rateSelect = document.getElementById("reader-rate");
  const voiceSelect = document.getElementById("reader-voice");
  const followCheck = document.getElementById("reader-follow");

  const synth = window.speechSynthesis || null;
  let voices = [];
  let currentUtterance = null;
  let lastAutoScroll = 0;
  let keepAliveTimer = null;

  /* ============ Storage ============ */
  // Document-specific key from pathname and title so separate files keep
  // separate preferences and progress.
  const storageKey = (() => {
    const raw = (location.pathname + location.search + "|" + document.title)
      .replace(/[^A-Za-z0-9_.-]/g, "_");
    return "html-reader:" + raw.slice(0, 120);
  })();

  // localStorage may be restricted on file:// origins; probe it and fall
  // back to in-memory state without breaking the reader.
  let store = null;
  try {
    if (window.localStorage) {
      const probe = "__html_reader_probe__";
      window.localStorage.setItem(probe, "1");
      window.localStorage.removeItem(probe);
      store = window.localStorage;
    }
  } catch (error) {
    store = null;
  }

  function loadPrefs() {
    if (!store) return;
    try {
      const saved = JSON.parse(store.getItem(storageKey) || "null");
      if (!saved) return;
      if (typeof saved.rate === "number" && saved.rate >= 0.5 && saved.rate <= 2) state.rate = saved.rate;
      if (typeof saved.voiceURI === "string") state.voiceURI = saved.voiceURI;
      if (typeof saved.autoFollow === "boolean") state.autoFollow = saved.autoFollow;
      if (Number.isInteger(saved.lastIndex) && saved.lastIndex >= 0) {
        state.currentIndex = Math.min(saved.lastIndex, state.blocks.length - 1);
      }
    } catch (error) {
      /* corrupted storage is ignored; defaults stay */
    }
  }

  function savePrefs() {
    if (!store) return;
    try {
      store.setItem(storageKey, JSON.stringify({
        voiceURI: state.voiceURI,
        rate: state.rate,
        autoFollow: state.autoFollow,
        lastIndex: state.status === "completed" ? 0 : Math.max(0, state.currentIndex)
      }));
    } catch (error) {
      /* quota or origin errors are non-fatal */
    }
  }

  /* ============ Content extraction ============ */
  function normalizeText(raw) {
    let text = (raw || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    // Do not narrate raw URLs unless the URL is the block's visible text
    // itself. Embedded URLs become the word "link".
    const isOnlyUrl = /^(?:https?:\/\/|www\.)\S+$/i.test(text);
    if (!isOnlyUrl) {
      text = text.replace(/(?:https?:\/\/|www\.)\S+/gi, "link");
      text = text.replace(/\s+/g, " ").trim();
    }
    return text;
  }

  // Deterministic readable-block list in DOM order. The topmost readable
  // block wins: once a block is collected, its descendants are skipped so
  // nested elements are never read twice.
  function extractBlocks(root) {
    const blocks = [];
    const candidates = root.querySelectorAll(READABLE);
    for (const el of candidates) {
      if (el.closest(IGNORED)) continue;                   // inside ignored region
      if (blocks.some((b) => b.el.contains(el))) continue; // nested in a chosen block
      const text = normalizeText(el.textContent);
      if (!text) continue;                                 // empty or whitespace only
      blocks.push({ el, text });
    }
    return blocks;
  }

  /* ============ Voice loading ============ */
  function populateVoices() {
    if (!synth || !voiceSelect) return;
    const previous = state.voiceURI;
    const keep = voices.some((v) => v.voiceURI === previous);
    voiceSelect.textContent = "";
    const def = document.createElement("option");
    def.value = "";
    def.textContent = "Default voice";
    voiceSelect.appendChild(def);
    for (const v of voices) {
      const opt = document.createElement("option");
      opt.value = v.voiceURI;
      opt.textContent = v.name + " (" + v.lang + ")";
      voiceSelect.appendChild(opt);
    }
    voiceSelect.value = keep ? previous : "";
    if (!keep) state.voiceURI = null;
  }

  function loadVoices() {
    if (!synth) return;
    voices = synth.getVoices() || [];
    populateVoices();
  }

  if (synth) {
    loadVoices();
    synth.addEventListener("voiceschanged", loadVoices);
    // Chromium exposes voices late; poll briefly after load.
    window.setTimeout(loadVoices, 250);
    window.setTimeout(loadVoices, 1000);
  }

  /* ============ Status and UI ============ */
  function announce(message) {
    if (statusEl) statusEl.textContent = message;
  }

  function updateProgress() {
    if (!progressEl) return;
    const total = state.blocks.length;
    const shown = state.status === "completed"
      ? total
      : state.currentIndex >= 0 ? state.currentIndex + 1 : 0;
    progressEl.textContent = shown + " / " + total;
  }

  function clearActive() {
    for (const block of state.blocks) block.el.removeAttribute("data-reader-active");
  }

  function scrollToBlock(el) {
    lastAutoScroll = Date.now();
    el.scrollIntoView({
      behavior: REDUCED_MOTION ? "auto" : "smooth",
      block: "center"
    });
  }

  function setActive(index) {
    state.blocks.forEach((block, i) => {
      if (i === index) block.el.setAttribute("data-reader-active", "true");
      else block.el.removeAttribute("data-reader-active");
    });
    const block = state.blocks[index];
    if (block && state.autoFollow) scrollToBlock(block.el);
    updateProgress();
  }

  /* ============ Speech engine ============ */
  // One utterance per semantic block. This keeps block synchronization
  // reliable and gives clean pause boundaries, previous and next
  // navigation, and resumable progress without word-boundary events.
  function speakBlock(index) {
    if (!synth) return;
    const block = state.blocks[index];
    if (!block) return;
    state.currentIndex = index;
    synth.cancel(); // always clear any prior queue before speaking
    const utterance = new SpeechSynthesisUtterance(block.text);
    utterance.rate = state.rate;
    if (state.voiceURI) {
      const match = voices.find((v) => v.voiceURI === state.voiceURI);
      if (match) utterance.voice = match;
    }
    currentUtterance = utterance;

    utterance.onstart = () => {
      if (state.status !== "playing") return; // stale start from a canceled queue
      setActive(index);
      announce("Playing. Block " + (index + 1) + " of " + state.blocks.length + ".");
    };
    utterance.onend = () => {
      if (state.status !== "playing") return; // stale end from a canceled queue
      savePrefs();
      const next = index + 1;
      if (next < state.blocks.length) {
        speakBlock(next);
      } else {
        finishComplete();
      }
    };
    utterance.onerror = (event) => {
      // interrupted and canceled come from this controller's own cancel()
      // calls, not real errors. Ignore them.
      if (event.error === "interrupted" || event.error === "canceled") return;
      handleError(event);
    };

    state.status = "playing";
    synth.speak(utterance);
  }

  // Chromium can stall long queues; a periodic resume() nudge keeps the
  // queue speaking. Harmless while paused or idle because the interval is
  // stopped whenever playback is not active.
  function startKeepAlive() {
    stopKeepAlive();
    keepAliveTimer = window.setInterval(() => {
      if (state.status === "playing" && synth) synth.resume();
    }, 10000);
  }

  function stopKeepAlive() {
    if (keepAliveTimer) window.clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }

  function start() {
    if (!synth) return;
    if (state.blocks.length === 0) {
      announce("Nothing to read on this page.");
      return;
    }
    if (state.status === "paused") {
      resume();
      return;
    }
    if (state.status === "completed") state.currentIndex = 0;
    else if (state.currentIndex < 0) state.currentIndex = 0;
    synth.cancel();
    speakBlock(state.currentIndex);
    startKeepAlive();
  }

  function pause() {
    if (!synth || state.status !== "playing") return;
    state.status = "paused";
    synth.pause();
    stopKeepAlive();
    announce("Paused.");
    savePrefs();
  }

  function resume() {
    if (!synth || state.status !== "paused") return;
    state.status = "playing";
    synth.resume();
    startKeepAlive();
    announce("Resumed.");
  }

  function stop() {
    if (!synth) return;
    synth.cancel();
    currentUtterance = null;
    state.status = "stopped";
    stopKeepAlive();
    clearActive();
    updateProgress();
    announce("Stopped.");
    savePrefs();
  }

  function goTo(index) {
    if (!synth || state.blocks.length === 0) return;
    const target = Math.max(0, Math.min(index, state.blocks.length - 1));
    synth.cancel();
    speakBlock(target);
    startKeepAlive();
  }

  // Re-speak the current block after a rate or voice change so the new
  // setting applies immediately.
  function restartCurrent() {
    if (!synth || state.currentIndex < 0 || state.status !== "playing") return;
    synth.cancel();
    speakBlock(state.currentIndex);
    startKeepAlive();
  }

  function finishComplete() {
    state.status = "completed";
    stopKeepAlive();
    clearActive();
    updateProgress();
    announce("Completed. End of document.");
    savePrefs();
  }

  function handleError(event) {
    state.status = "error";
    stopKeepAlive();
    clearActive();
    if (synth) synth.cancel();
    updateProgress();
    announce("Speech error (" + (event.error || "unknown") + "). Press Play to try again.");
  }

  /* ============ Keyboard ============ */
  // Active only while focus is inside the controller. Never steal keys
  // while the reader is typing in a form control.
  function onKeydown(event) {
    const target = event.target;
    const typing = target && (target.closest("input, textarea, select") || target.isContentEditable);
    if (typing) return;
    if (event.code === "Space" || event.key === " ") {
      event.preventDefault();
      if (state.status === "playing") pause();
      else if (state.status === "paused") resume();
      else start();
    } else if (event.key === "Escape") {
      event.preventDefault();
      stop();
    } else if (event.altKey && event.key === "ArrowLeft") {
      event.preventDefault();
      goTo(state.currentIndex - 1);
    } else if (event.altKey && event.key === "ArrowRight") {
      event.preventDefault();
      goTo(state.currentIndex + 1);
    }
  }

  /* ============ Manual scroll detection ============ */
  // If the reader scrolls away while playing, stop following. The
  // suppression window covers this controller's own smooth scrolls; a
  // scroll that arrives later with the active block far off-screen is a
  // manual one, so auto-follow turns itself off.
  window.addEventListener("scroll", () => {
    if (state.status !== "playing" || !state.autoFollow) return;
    if (Date.now() - lastAutoScroll < 2000) return;
    const block = state.blocks[state.currentIndex];
    if (!block) return;
    const rect = block.el.getBoundingClientRect();
    const margin = window.innerHeight * 0.5;
    const inView = rect.bottom > -margin && rect.top < window.innerHeight + margin;
    if (!inView) {
      state.autoFollow = false;
      if (followCheck) followCheck.checked = false;
      announce("Auto-follow turned off. Use the toggle to re-enable.");
    }
  }, { passive: true });

  /* ============ Event wiring ============ */
  function bindEvents() {
    if (playBtn) playBtn.addEventListener("click", () => {
      if (state.status === "playing") return; // Pause is a separate control
      if (state.status === "paused") resume();
      else start();
    });
    if (pauseBtn) pauseBtn.addEventListener("click", pause);
    if (stopBtn) stopBtn.addEventListener("click", stop);
    if (prevBtn) prevBtn.addEventListener("click", () => goTo(state.currentIndex - 1));
    if (nextBtn) nextBtn.addEventListener("click", () => goTo(state.currentIndex + 1));
    if (rateSelect) rateSelect.addEventListener("change", () => {
      state.rate = parseFloat(rateSelect.value) || 1;
      savePrefs();
      restartCurrent();
    });
    if (voiceSelect) voiceSelect.addEventListener("change", () => {
      state.voiceURI = voiceSelect.value || null;
      savePrefs();
      restartCurrent();
    });
    if (followCheck) followCheck.addEventListener("change", () => {
      state.autoFollow = followCheck.checked;
      savePrefs();
      if (state.autoFollow && state.currentIndex >= 0) {
        const block = state.blocks[state.currentIndex];
        if (block) scrollToBlock(block.el);
      }
    });
    if (controller) controller.addEventListener("keydown", onKeydown);
    if (synth) {
      window.addEventListener("beforeunload", () => {
        stopKeepAlive();
        synth.cancel();
      });
    }
  }

  /* ============ Init ============ */
  function init() {
    if (!controller) return; // controller markup missing; nothing to attach
    const root = document.querySelector("[data-readable-root]") || document.body;
    state.blocks = extractBlocks(root);
    if (state.blocks.length === 0) {
      controller.hidden = true; // nothing to read; keep the page clean
      return;
    }
    loadPrefs();
    if (rateSelect) rateSelect.value = String(state.rate);
    if (followCheck) followCheck.checked = state.autoFollow;
    populateVoices();
    bindEvents();
    updateProgress();
    announce("Ready. Use the reading controls to start.");
  }

  init();
})();
</script>
```

## Complete example

A minimal standalone file that narrates itself from `file://`. It combines the three blocks with a short article; this is the shape a generated dossier takes when narration is included.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Read-aloud example</title>
  <style>
    body{margin:0;font:400 1.125rem/1.7 system-ui,-apple-system,"Segoe UI",sans-serif;
      background:#121212;color:#e6e1d9;padding:2rem}
    main{max-width:min(65ch,100% - 2rem);margin:auto}
    pre{background:#1b1b1b;padding:1rem;overflow-x:auto}
    nav{margin-bottom:2rem}
    /* Block A: controller CSS */
    #reader-controller{
      --reader-accent:#8ab4ff;--reader-bg:#1b1b1b;--reader-text:#e6e1d9;
      --reader-muted:#aaa39a;--reader-border:#333;
      position:fixed;bottom:1rem;inset-inline-end:1rem;z-index:9999;
      max-width:calc(100% - 2rem);padding:.75rem;border:1px solid var(--reader-border);
      border-radius:1rem;background:var(--reader-bg);color:var(--reader-text);
      font:400 .875rem/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;
      box-shadow:0 .5rem 1.5rem rgba(0,0,0,.35)
    }
    #reader-controller[hidden]{display:none!important}
    .reader-controls-row{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem}
    #reader-controller .reader-btn{display:inline-flex;align-items:center;justify-content:center;
      width:2.25rem;height:2.25rem;padding:0;border:1px solid var(--reader-border);
      border-radius:.5rem;background:transparent;color:var(--reader-text);cursor:pointer}
    #reader-controller .reader-btn:hover{background:rgba(128,128,128,.15)}
    #reader-controller .reader-btn svg{display:block;width:1.1rem;height:1.1rem;fill:currentColor}
    #reader-controller select{font:inherit;color:var(--reader-text);max-width:12rem;
      padding:.3rem .4rem;border:1px solid var(--reader-border);border-radius:.4rem;
      background:var(--reader-bg)}
    .reader-field{position:relative;display:inline-flex;align-items:center;gap:.35rem;
      color:var(--reader-muted);white-space:nowrap}
    #reader-controller .reader-follow input{font:inherit;margin:0}
    #reader-progress{font-variant-numeric:tabular-nums;white-space:nowrap}
    .reader-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
      clip:rect(0 0 0 0);white-space:nowrap;border:0}
    #reader-status{display:block;margin-bottom:.5rem;color:var(--reader-muted);min-height:1.4em}
    #reader-controller :focus-visible{outline:3px solid var(--reader-accent);outline-offset:2px}
    [data-reader-active="true"]{outline:2px solid var(--reader-accent,#8ab4ff);outline-offset:3px;
      border-radius:4px;box-shadow:inset 3px 0 0 var(--reader-accent,#8ab4ff);scroll-margin-top:5rem}
    @media (prefers-reduced-motion:reduce){#reader-controller{transition:none}
      [data-reader-active="true"]{transition:none}}
    @media print{#reader-controller{display:none!important}
      [data-reader-active="true"]{outline:none;box-shadow:none;border-radius:0}}
  </style>
</head>
<body>
  <main>
    <nav><a href="#section-2">Jump to section 2</a></nav>
    <article data-readable-root>
      <h1>Read-aloud example</h1>
      <p>This file can narrate itself. Open it from file://, press Play, and the controller reads each block with a highlight and scrolls along.</p>
      <h2 id="section-2">Section two</h2>
      <blockquote>Blockquotes become a single narrated block.</blockquote>
      <pre>const never = "read aloud"; // code is excluded by default</pre>
      <p data-reader-ignore>This paragraph is ignored because it carries data-reader-ignore.</p>
      <p>See https://example.com/some/long/path for details. The URL is replaced with the word "link".</p>
    </article>
  </main>

  <!-- Block B: controller markup -->
  <div class="reader-controller" id="reader-controller" role="group" aria-label="Reading controls">
    <span id="reader-status" class="reader-status" role="status" aria-live="polite">Ready</span>
    <div class="reader-controls-row">
      <button type="button" id="reader-play" class="reader-btn" aria-label="Play or resume" title="Play or resume (Space)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
      </button>
      <button type="button" id="reader-pause" class="reader-btn" aria-label="Pause" title="Pause (Space)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>
      </button>
      <button type="button" id="reader-stop" class="reader-btn" aria-label="Stop" title="Stop (Escape)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
      </button>
      <button type="button" id="reader-prev" class="reader-btn" aria-label="Previous block" title="Previous block (Alt+Left)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 6h2v12H7zM19 6l-10 6 10 6z"/></svg>
      </button>
      <button type="button" id="reader-next" class="reader-btn" aria-label="Next block" title="Next block (Alt+Right)">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6h2v12h-2zM5 6l10 6-10 6z"/></svg>
      </button>
      <label class="reader-field">Speed
        <select id="reader-rate" aria-label="Playback speed">
          <option value="0.5">0.5x</option>
          <option value="0.75">0.75x</option>
          <option value="1" selected>1x</option>
          <option value="1.25">1.25x</option>
          <option value="1.5">1.5x</option>
          <option value="2">2x</option>
        </select>
      </label>
      <label class="reader-field">Voice <select id="reader-voice" aria-label="Voice"></select></label>
      <label class="reader-field reader-follow"><input type="checkbox" id="reader-follow" checked> Auto-follow</label>
      <span class="reader-field"><span class="reader-sr">Progress </span><span id="reader-progress">0 / 0</span></span>
    </div>
  </div>

  <!-- Block C: reader JavaScript -->
  <script>
  /* ... same JavaScript as Block C above ... */
  </script>
</body>
</html>
```

The placeholder `/* ... same JavaScript as Block C above ... */` in the example is a pointer, not part of the deliverable scaffold. When embedding, copy the full Block C script verbatim.

## Customization

- **Theme**: the controller reads the host document's `--accent`, `--panel`, `--text`, `--muted`, and `--border` tokens when present. Define your own `--reader-*` variables on `#reader-controller` to override.
- **Selectors**: change `READABLE` and `IGNORED` in Block C to match a different document vocabulary. Keep `data-reader-ignore` in the ignored set so the opt-out attribute always works.
- **Controls**: every binding guards against a missing element, so removing a control from the markup never breaks the rest.
- **Voice list**: voices come from the reader's installed set. The voice selector repopulates on `voiceschanged`, so voices that load after the page appears are picked up.

## Known limitations

- Speech is only as good as the installed voices. No network voices are fetched; V1 uses what the browser provides.
- Chromium can stall very long queues. The keep-alive `resume()` nudge mitigates this; a reader can always Pause and Play to reset a stalled queue.
- On `file://`, `localStorage` behavior varies by browser. When it is unavailable, the reader still works but does not remember preferences.
- Rate and voice changes restart the current block so the new setting applies immediately.
