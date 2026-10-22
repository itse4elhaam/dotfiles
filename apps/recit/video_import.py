"""Explicit local video import. Never alters the selected original or uploads."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from naming import clean_title
from PySide6.QtCore import QThread, Signal


def import_video(source, directory):
    source, directory = Path(source).absolute(), Path(directory)
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in ('.webm', '.mp4', '.mkv'):
        raise ValueError('Select a local WebM, MP4 or MKV video file, not a symbolic link.')
    if not source.stat().st_size:
        raise ValueError('The selected video is empty. The original has not changed.')
    # Never follow network protocols referenced by a crafted local media file.
    probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_streams', '-of', 'json', str(source)], capture_output=True, timeout=30, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if not video or video.get('disposition', {}).get('attached_pic'):
        raise ValueError('No playable video stream was found. The original has not changed.')
    copy_video = video.get('codec_name') == 'h264' and video.get('pix_fmt') == 'yuv420p'
    directory.mkdir(parents=True, exist_ok=True)
    # Encode inside an owner-only staging directory. Publish with an exclusive
    # hard link, so a concurrent import or symlink can never be overwritten.
    with tempfile.TemporaryDirectory(prefix='.recit-import-', dir=directory) as temporary:
        staging = Path(temporary) / 'video.mp4'
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
            '-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
            '-c:v', 'copy' if copy_video else 'libx264']
        if not copy_video:
            command += ['-preset', 'fast', '-crf', '20', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p']
        command += ['-c:a', 'copy' if audio and audio.get('codec_name') == 'aac' else 'aac',
            '-movflags', '+faststart', str(staging)]
        subprocess.run(command, capture_output=True, timeout=3600, check=True)
        if not staging.is_file() or not staging.stat().st_size:
            raise ValueError('Conversion produced no video. The original has not changed.')
        stem = clean_title(source.stem)
        number = 1
        while True:
            target = directory / f'{stem}{"" if number == 1 else f" ({number})"}.mp4'
            try:
                os.link(staging, target)
                return target
            except FileExistsError:
                number += 1


class ImportWorker(QThread):
    result = Signal(object, str)

    def __init__(self, source, directory, parent):
        super().__init__(parent)
        self.source, self.directory = source, directory

    def run(self):
        try:
            self.result.emit(import_video(self.source, self.directory), '')
        except Exception:
            # Raw codec errors may include paths or metadata from an untrusted file.
            self.result.emit(None, 'Import failed. The original is unchanged. Check the file and FFmpeg availability, then retry.')
