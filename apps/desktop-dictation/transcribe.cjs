// Each hold sends :start, base64 mono 16 kHz s16le blocks, then :finish, one per line.
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

function clean(text, settings) {
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const whole = body => new RegExp(`(?<![\\p{L}\\p{N}_])(?:${body})(?![\\p{L}\\p{N}_])`, "giu");
  const spellings = new Map();
  for (const {term, aliases = []} of settings.speechCustomWords ?? []) {
    for (const spelling of [term, ...aliases]) {
      if (spelling && term) spellings.set(spelling.toLowerCase(), term);
    }
  }
  if (spellings.size) {
    const alternatives = [...spellings.keys()].sort((a, b) => b.length - a.length);
    text = text.replace(whole(alternatives.map(escape).join("|")), value => spellings.get(value.toLowerCase()) ?? value);
  }
  if (settings.speechRemoveFillerWords !== false) {
    const cue = settings.speechCorrectionWord?.trim();
    const filler = "uh|uhm|umm|uhh|uhhh|ehh|ehm|ahm|hmm|hm|mmm|хм|ммм|um|ah|eh";
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])(?:(${cue ? escape(cue) : "(?!)"})(?![\\p{L}\\p{N}_])|(?:${filler})(?![\\p{L}\\p{N}_])[,.]?)`, "giu");
    text = text.replace(pattern, (_, correction) => correction ?? "");
  }
  // A narrow spoken repair: "set it to 42, sorry, 24" becomes "set it to 24".
  // Leave units, quoted language and ambiguous sentence-level apologies alone.
  text = text.trim().replace(/^((?:set|make|change) (?:it|that)(?: to)? )[0-9]+(?:\.[0-9]+)?,\s*(?:sorry|I mean|make that),\s*([0-9]+(?:\.[0-9]+)?)([.!]?)$/iu, "$1$2$3");
  return text.replace(/[^\S\r\n]+/g, " ").trim();
}

async function run() {
  const bundle = path.join(path.dirname(process.execPath), "resources", "app.asar");
  const data = path.join(process.env.T3CODE_HOME || path.join(os.homedir(), ".t3"), "userdata");
  const models = path.join(data, "speech/models");
  let settings = {};
  const prefs = path.join(data, "client-settings.json");
  // This is T3's own local worker entry point. It owns ASR, VAD, pre-roll,
  // silence tails, and finalization, including its fallback for unavailable VAD.
  const worker = require("node:child_process").fork(path.join(bundle, "apps/server/dist/bin.mjs"),
    ["__speech-worker", "model"], {serialization: "advanced", stdio: ["ignore", "ignore", "inherit", "ipc"],
      env: {...process.env, TRANSCRIBE_BACKENDS: "cpu"}});
  const exited = new Promise((_, reject) => {
    worker.once("exit", () => reject(new Error("T3 speech worker exited")));
    worker.once("error", reject);
  });
  // One request at a time both bounds buffering and preserves audio order.
  function request(message) {
    return new Promise((resolve, reject) => {
      worker.once("message", reply => reply.ok ? resolve(reply) : reject(new Error(reply.error)));
      worker.send(message, err => { if (err) reject(err); });
    });
  }
  async function recognize() {
    const loaded = await request({kind: "load", path: path.join(models, "parakeet-unified-en-0.6b-Q8_0.gguf"), acceleration: "cpu"});
    const lines = require("node:readline").createInterface({input: process.stdin});
    const emit = (type, text) => process.stdout.write(JSON.stringify({type, text}) + "\n");
    for await (const line of lines) {
      if (line === ":start") {
        settings = fs.existsSync(prefs) ? JSON.parse(fs.readFileSync(prefs, "utf8")) : {};
        const vocabulary = (settings.speechCustomWords ?? []).map(word => word.term);
        const options = {timestamps: "none"};
        if (loaded.supportsVocabulary && vocabulary.length) options.vocabulary = vocabulary;
        await request({kind: "begin", options, filterSilence: settings.speechSilenceFiltering !== false,
          vadPath: path.join(models, "silero-vad-v6.2-F32.gguf")});
      } else if (line === ":finish") {
        const {text} = await request({kind: "finish"});
        emit("final", clean(text, settings));
      } else {
        const bytes = Buffer.from(line, "base64");
        const pcm = new Float32Array(bytes.length / 2);
        for (let i = 0; i < pcm.length; i++) pcm[i] = bytes.readInt16LE(i * 2) / 32768;
        const {preview} = await request({kind: "feed", pcm});
        if (preview) emit("partial", clean([preview.committed, preview.tentative].filter(Boolean).join(" "), settings));
      }
    }
  }
  try {
    await Promise.race([recognize(), exited]);
  } finally {
    worker.kill("SIGKILL");
    process.stdin.destroy();
  }
}

if (require.main === module) run().catch(error => {
  console.error("Dictation engine:", error.message);
  process.exitCode = 1;
});
module.exports = {clean};
