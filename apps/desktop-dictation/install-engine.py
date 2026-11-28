#!/usr/bin/python3
"""Install the pinned upstream transcribe.cpp Linux x86_64 wheels user-locally."""
import fcntl
import hashlib
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

WHEELS = {
    "ff/3c/260cb16b397352e5f029822799930044f8b2a39751d7ac2c5bc21e3d7f8b/transcribe_cpp-0.5.1-py3-none-any.whl":
        "a3976f6b90f5af21773ccbd5e6a523b7e48964a7f4bb5e5b770c0df597a6d439",
    "d8/0c/9371eae4c01ed9232439679f6a96148ab69dbfea56c4fcaddcc84038b488/transcribe_cpp_native-0.5.1-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl":
        "f36ea3043bfcc99b8536439e7cb7fbdcf25cd0cc4130bedc4754579bf730c64c",
}


def install():
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise RuntimeError("This engine requires Linux x86_64")
    data = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local/share") / "desktop-dictation"
    data.mkdir(parents=True, exist_ok=True)
    target = data / "engine-0.5.1"
    with (data / ".engine.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.is_dir():
            return
        with tempfile.TemporaryDirectory(dir=data) as tmp:
            stage = Path(tmp) / "engine"
            for path, expected in WHEELS.items():
                print("Installing", path.split("/")[-1], file=sys.stderr, flush=True)
                wheel = Path(tmp) / "download.whl"
                with urlopen("https://files.pythonhosted.org/packages/" + path, timeout=60) as src, wheel.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
                    raise ValueError("Wheel SHA-256 mismatch")
                with ZipFile(wheel) as archive:
                    archive.extractall(stage)
            stage.rename(target)


if __name__ == "__main__":
    install()
