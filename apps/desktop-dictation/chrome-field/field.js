(() => {
  const field = document.activeElement;
  const input = field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement;
  const originalType = input && field.type;
  function plainEditor() {
    return field.isContentEditable && !field.parentElement?.isContentEditable &&
      Array.from(field.childNodes).every(n => n.nodeType === Node.TEXT_NODE);
  }
  function writable() {
    return document.hasFocus() && field === document.activeElement && field.isConnected &&
      (input ? ["textarea", "text", "search", "url", "tel"].includes(field.type) &&
        field.type === originalType && !field.readOnly && !field.matches(":disabled") : plainEditor());
  }
  if (!writable()) return null;
  function selection() {
    if (input) return [field.selectionStart, field.selectionEnd];
    const s = window.getSelection();
    if (!s.rangeCount || !field.contains(s.anchorNode) || !field.contains(s.focusNode)) return [];
    const range = s.getRangeAt(0);
    const prefix = range.cloneRange();
    prefix.selectNodeContents(field);
    prefix.setEnd(range.startContainer, range.startOffset);
    const start = prefix.toString().length;
    return [start, start + range.toString().length];
  }
  function value() { return input ? field.value : field.textContent; }
  const before = value();
  const [start, end] = selection();
  if (!Number.isInteger(start) || !Number.isInteger(end)) return null;
  const token = crypto.getRandomValues(new Uint32Array(4)).join("-");
  const life = new AbortController();
  let port;
  function disarm() {
    life.abort();
    clearTimeout(timer);
    chrome.runtime.onConnect.removeListener(connect);
    port?.disconnect();
  }
  function connect(candidate) {
    if (candidate.name !== token || candidate.sender.id !== chrome.runtime.id) return;
    port = candidate;
    chrome.runtime.onConnect.removeListener(connect);
    port.onDisconnect.addListener(disarm);
    function commit({text, deadline}) {
      port.onMessage.removeListener(commit);
      // Consume the arm before executing page input handlers, which may move focus.
      life.abort();
      clearTimeout(timer);
      const [a, b] = selection();
      let ok = false;
      if (Number.isSafeInteger(deadline) && Date.now() <= deadline &&
          typeof text === "string" && text.length && text.length <= 8192 &&
          !/[\r\n\x00-\x1f]/.test(text) && writable() && value() === before &&
          a === start && b === end &&
          (!input || field.maxLength < 0 || before.length - end + start + text.length <= field.maxLength)) {
        let matched = false;
        const observe = e => {
          matched = e.isTrusted && e.target === field && e.inputType === "insertText" && e.data === text;
        };
        field.addEventListener("input", observe, true);
        try {
          const accepted = document.execCommand("insertText", false, text);
          ok = accepted && matched && value() === before.slice(0, start) + text + before.slice(end);
        } finally {
          field.removeEventListener("input", observe, true);
        }
      }
      port.postMessage({ok});
    }
    port.onMessage.addListener(commit);
    port.postMessage({armed: true});
  }
  const timer = setTimeout(disarm, 360000);
  field.addEventListener("blur", disarm, {once: true, signal: life.signal});
  field.addEventListener("input", disarm, {once: true, signal: life.signal});
  window.addEventListener("pagehide", disarm, {once: true, signal: life.signal});
  window.addEventListener("blur", disarm, {once: true, signal: life.signal});
  chrome.runtime.onConnect.addListener(connect);
  return token;
})();
