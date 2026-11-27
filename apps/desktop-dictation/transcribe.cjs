// Run with T3's AppImage in Electron's Node mode. stdin is mono 16 kHz s16le.
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

function clean(text, settings) {
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const whole = body => new RegExp(`(?<![\\p{L}\\p{N}_])(?:${body})(?![\\p{L}\\p{N}_])`, "giu");
  for (const {term, aliases = []} of settings.speechCustomWords ?? []) {
    if (term) text = text.replace(whole([term, ...aliases].filter(Boolean).map(escape).join("|")), () => term);
  }
  if (settings.speechRemoveFillerWords !== false) {
    const cue = settings.speechCorrectionWord?.trim();
    const filler = "uh|uhm|umm|uhh|uhhh|ehh|ehm|ahm|hmm|hm|mmm|хм|ммм|um|ah|eh";
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])(?:(${cue ? escape(cue) : "(?!)"})(?![\\p{L}\\p{N}_])|(?:${filler})(?![\\p{L}\\p{N}_])[,.]?)`, "giu");
    text = text.replace(pattern, (_, correction) => correction ?? "");
  }
  return text.replace(/[^\S\r\n]+/g, " ").trim();
}

async function run() {
  const bundle = path.join(path.dirname(process.execPath), "resources", "app.asar");
  process.env.TRANSCRIBE_LIBRARY = bundle + ".unpacked/node_modules/@transcribe-cpp/linux-x64-cpu-vulkan/libtranscribe.so";
  const {TranscribeModel} = require(bundle + "/node_modules/transcribe-cpp/dist/index.js");
  const data = path.join(process.env.T3CODE_HOME || path.join(os.homedir(), ".t3"), "userdata");
  const models = path.join(data, "speech/models");
  let settings = {};
  const prefs = path.join(data, "client-settings.json");
  if (fs.existsSync(prefs)) settings = JSON.parse(fs.readFileSync(prefs, "utf8"));
  const model = await TranscribeModel.load(path.join(models, "parakeet-unified-en-0.6b-Q8_0.gguf"), {backend: "cpu"});
  const session = model.createSession({nThreads: Math.min(2, os.availableParallelism())});
  const stream = await session.stream({timestamps: "none"});
  const vad = settings.speechSilenceFiltering === false ? null : (await TranscribeModel.load(
    path.join(models, "silero-vad-v6.2-F32.gguf"), {backend: "cpu"})).createVadSession({nThreads: 1});
  let voiced = !vad, previous = "", carry = Buffer.alloc(0);
  const emit = (type, text) => process.stdout.write(JSON.stringify({type, text}) + "\n");
  for await (const chunk of process.stdin) {
    const bytes = Buffer.concat([carry, chunk]);
    const samples = new Float32Array(Math.floor(bytes.length / 2));
    carry = bytes.subarray(samples.length * 2);
    for (let i = 0; i < samples.length; i++) samples[i] = bytes.readInt16LE(i * 2) / 32768;
    if (!samples.length) continue;
    if (!voiced) voiced = (await vad.streamFeed(samples)).probs.some(p => p >= 0.5);
    await stream.feed(samples);
    const text = stream.text.full;
    if (voiced && text !== previous) emit("partial", text);
    previous = text;
  }
  if (voiced) await stream.finalize();
  emit("final", voiced ? clean(stream.text.full, settings) : "");
}

if (require.main === module) run().catch(error => {
  console.error("Dictation engine:", error.message);
  process.exitCode = 1;
});
module.exports = {clean};
