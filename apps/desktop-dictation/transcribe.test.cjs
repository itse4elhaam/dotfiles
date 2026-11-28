const assert = require("node:assert/strict");
const test = require("node:test");
const {clean} = require("./transcribe.cjs");

test("use the longest alias, then correct sound-alike preferred names", () => {
  const settings = {speechCustomWords: [
    {term: "VS", aliases: []}, {term: "VS Code", aliases: ["vs code"]}, "Tailscale",
  ]};
  assert.equal(clean("um, open vs code on tail scale.", settings), "open VS Code on Tailscale.");
  assert.equal(clean("中vs code日", settings), "中VS Code日");
});

test("keep the correction cue and respect the filler setting", () => {
  assert.equal(clean("keep um   correction, uh, here.", {speechCorrectionWord: "um correction"}),
    "keep um correction, here.");
  assert.equal(clean("um, leave it.", {speechRemoveFillerWords: false}), "um, leave it.");
});

test("repair standalone numeric changes and preserve a literal apology", () => {
  assert.equal(clean("Make it 42, sorry, 24.", {}), "Make it 24.");
  const literal = "If you set it to 42, sorry, 24 people will leave.";
  assert.equal(clean(literal, {}), literal);
});
