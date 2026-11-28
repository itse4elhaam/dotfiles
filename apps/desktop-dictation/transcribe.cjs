// Each hold sends :start, base64 mono 16 kHz s16le blocks, then :finish, one per line.
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

// From T3 Code's apps/server/src/speech at 031ee2dd, under t3-speech/LICENSE.
const {makeSpeechTextCorrector, normalizeSpeechCustomWords} = require("./t3-speech/customWords.mts");
const {removeSpeechFillerWords} = require("./t3-speech/fillerWords.mts");

function prepareCleanup(settings, supportsVocabulary) {
  const words = (settings.speechCustomWords ?? []).flatMap(word => {
    if (typeof word === "string") return [{term: word, aliases: []}];
    if (typeof word?.term !== "string") return [];
    const aliases = Array.isArray(word.aliases) ? word.aliases.filter(alias => typeof alias === "string") : [];
    return [{term: word.term, aliases}];
  });
  const dictionary = normalizeSpeechCustomWords(words);
  const preferred = dictionary.map(word => word.term);
  const vocabulary = supportsVocabulary ? preferred : [];
  const correct = makeSpeechTextCorrector(supportsVocabulary ? [] : preferred, dictionary);
  function format(text) {
    let result = correct(text);
    if (settings.speechRemoveFillerWords !== false) {
      // This Parakeet model recognizes English.
      result = removeSpeechFillerWords(result, "en", settings.speechCorrectionWord);
    }
    // Only repair a complete standalone command with a replacement number.
    return result.trim().replace(/^((?:set|make|change) (?:it|that)(?: to)? )[0-9]+(?:\.[0-9]+)?,\s*(?:sorry|I mean|make that),\s*([0-9]+(?:\.[0-9]+)?)([.!]?)$/iu, "$1$2$3");
  }
  return {vocabulary, format};
}

function clean(text, settings) {
  return prepareCleanup(settings, false).format(text);
}

async function run() {
  const bundle = path.join(path.dirname(process.execPath), "resources", "app.asar");
  const data = path.join(process.env.T3CODE_HOME || path.join(os.homedir(), ".t3"), "userdata");
  const models = path.join(data, "speech/models");
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
    let cleanup;
    for await (const line of lines) {
      if (line === ":start") {
        const settings = fs.existsSync(prefs) ? JSON.parse(fs.readFileSync(prefs, "utf8")) : {};
        cleanup = prepareCleanup(settings, loaded.supportsVocabulary);
        const options = {timestamps: "none"};
        if (cleanup.vocabulary.length) options.vocabulary = cleanup.vocabulary;
        await request({kind: "begin", options, filterSilence: settings.speechSilenceFiltering !== false,
          vadPath: path.join(models, "silero-vad-v6.2-F32.gguf")});
      } else if (line === ":finish") {
        const {text} = await request({kind: "finish"});
        emit("final", cleanup.format(text));
      } else {
        const bytes = Buffer.from(line, "base64");
        const pcm = new Float32Array(bytes.length / 2);
        for (let i = 0; i < pcm.length; i++) pcm[i] = bytes.readInt16LE(i * 2) / 32768;
        const {preview} = await request({kind: "feed", pcm});
        if (preview) emit("partial", cleanup.format([preview.committed, preview.tentative].filter(Boolean).join(" ")));
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
