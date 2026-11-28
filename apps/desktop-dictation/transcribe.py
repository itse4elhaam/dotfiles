#!/usr/bin/python3
"""Warm native speech worker. One line per command or base64 s16le audio block."""
from array import array
import base64
from collections import deque
import json
import os
from pathlib import Path
import re
import sys

DATA = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local/share") / "desktop-dictation"
CONFIG = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / "desktop-dictation/settings.json"
FILLERS = "uh uhm umm uhh uhhh ehh ehm ahm hmm hm mmm хм ммм um ah eh".split()
REPAIR = re.compile(
    r"^((?:set|make|change) (?:it|that)(?: to)? )\d+(?:\.\d+)?,\s*"
    r"(?:sorry|I mean|make that),\s*(\d+(?:\.\d+)?)([.!]?)$", re.I)


def whole(words):
    return r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + r")(?!\w)"

def read_settings(path):
    try:
        settings = json.loads(path.read_text())
        if not isinstance(settings, dict):
            raise ValueError("expected a JSON object")
        words = settings.get("speechCustomWords", [])
        if not isinstance(words, list):
            raise ValueError("speechCustomWords must be a list")
        for word in words:
            if not isinstance(word, dict) or not isinstance(word.get("term"), str):
                raise ValueError("each dictionary entry needs a term")
            aliases = word.get("aliases", [])
            if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
                raise ValueError("each alias must be a string")
        if not isinstance(settings.get("speechCorrectionWord", ""), str):
            raise ValueError("speechCorrectionWord must be a string")
        return settings
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"Using default dictation settings ({path}: {error})", file=sys.stderr)
        return {}


def clean(text, settings):
    spellings = {}
    for word in settings.get("speechCustomWords", []):
        term = word["term"]
        for spelling in [term, *word.get("aliases", [])]:
            if term and spelling:
                spellings[spelling.casefold()] = term
    if spellings:
        text = re.sub(whole(spellings), lambda m: spellings.get(m[0].casefold(), m[0]), text, flags=re.I)
    if settings.get("speechRemoveFillerWords", True):
        cue = settings.get("speechCorrectionWord", "").strip()
        pattern = (f"({whole([cue])})|" if cue else "") + whole(FILLERS) + r"[,.]?"
        text = re.sub(pattern, lambda m: m[0] if m.lastindex else "", text, flags=re.I)
    text = REPAIR.sub(r"\1\2\3", text.strip())
    return re.sub(r"[^\S\r\n]+", " ", text).strip()


class SpeechGate:
    """Pass speech with 256 ms pre-roll and 512 ms trailing silence."""
    def __init__(self, vad, frame_samples):
        self.vad = vad
        self.vad.stream_reset()
        self.frame_samples = frame_samples
        self.pending = array("f")
        self.before = deque(maxlen=8)
        self.tail = 0

    def filter(self, pcm, final=False):
        self.pending.extend(pcm)
        probabilities = self.vad.stream_feed(pcm).probs
        if final:
            probabilities += self.vad.stream_flush().probs
        output = array("f")
        offset = 0
        for probability in probabilities:
            frame = self.pending[offset:offset + self.frame_samples]
            offset += len(frame)
            if probability >= 0.5:
                for previous in self.before:
                    output.extend(previous)
                self.before.clear()
                output.extend(frame)
                self.tail = 16
            elif self.tail:
                output.extend(frame)
                self.tail -= 1
            else:
                self.before.append(frame)
        del self.pending[:offset]
        return output


def emit(kind, text):
    print(json.dumps({"type": kind, "text": text}), flush=True)


def recognize():
    cpus = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0, cpus)
    os.environ["TRANSCRIBE_BACKENDS"] = "cpu"
    os.environ["OMP_NUM_THREADS"] = str(len(cpus))
    native = DATA / "engine-0.5.1"
    os.environ["TRANSCRIBE_LIBRARY"] = str(native / "transcribe_cpp_native/_native/libtranscribe.so")
    sys.path.insert(0, str(native))
    emit("progress", "Loading speech models…")
    from transcribe_cpp import Model

    models = DATA / "models"
    with Model(models / "parakeet-unified-en-0.6b-Q8_0.gguf", backend="cpu") as model, \
         Model(models / "silero-vad-v6.2-F32.gguf", backend="cpu") as silero, \
         model.session(n_threads=len(cpus)) as session, silero.vad_session(n_threads=1) as vad:
        stream = None
        for raw_line in sys.stdin.buffer:
            line = raw_line.rstrip(b"\r\n")
            if line == b":start" and stream is None:
                settings = read_settings(CONFIG)
                terms = [w["term"] for w in settings.get("speechCustomWords", [])]
                stream = session.stream(vocabulary=terms if terms and model.supports("vocabulary") else None)
                gate = SpeechGate(vad, silero.vad_info.frame_samples) if settings.get("speechSilenceFiltering", True) else None
                emit("progress", "Listening…")
            elif stream is None or line == b":start":
                raise ValueError("Unexpected recording command")
            elif line == b":finish":
                if gate:
                    tail = gate.filter(array("f"), final=True)
                    if tail:
                        stream.feed(tail)
                stream.finalize()
                emit("final", clean(stream.text().full, settings))
                stream.reset()
                stream = None
            else:
                samples = array("h", base64.b64decode(line, validate=True))
                pcm = array("f", (sample / 32768.0 for sample in samples))
                if gate:
                    pcm = gate.filter(pcm)
                if pcm and stream.feed(pcm).result_changed:
                    emit("partial", clean(stream.text().display, settings))
        if stream is not None:
            raise EOFError("Recording ended before :finish")


if __name__ == "__main__":
    try:
        recognize()
    except Exception as error:
        print("Dictation engine:", error, file=sys.stderr)
        sys.exit(1)
