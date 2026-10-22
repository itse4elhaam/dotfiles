"""Readable local recording names, without transcription or network access."""
from datetime import datetime
import os
from pathlib import Path
import re
import unicodedata


_LEGACY = re.compile(r'^(?:RecIt|Glint)-(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(\d{2})(?:-\d+)?$')
_READABLE = re.compile(r'^(.*?) - (\d{4}-\d{2}-\d{2}) at (\d{2})\.(\d{2})(?: \((\d+)\))?$')


def clean_title(value):
    """Keep Unicode words, remove path separators, control and format characters."""
    value = unicodedata.normalize('NFC', str(value))
    value = ''.join(' ' if ch in '/\\<>:"|?*' or unicodedata.category(ch).startswith('C') else ch for ch in value)
    value = ' '.join(value.split()).strip(' .')
    # Leave room for date, collision suffix and extension within a 255-byte component.
    value = value.encode('utf-8')[:160].decode('utf-8', errors='ignore').strip(' .')
    return value or 'Recording'


def next_recording_path(directory, mode='camera', window_title='', now=None):
    """Choose an unused MKV/MP4 stem. The engine also refuses existing files."""
    now = now or datetime.now()
    title = clean_title(window_title) if window_title else ('Camera recording' if mode == 'camera' else 'Screen recording')
    base = f'{title} - {now:%Y-%m-%d} at {now:%H.%M}'
    number = 1
    while True:
        stem = base if number == 1 else f'{base} ({number})'
        path = Path(directory) / (stem + '.mkv')
        if not path.exists() and not path.with_suffix('.mp4').exists():
            return path
        number += 1


def recording_title(path):
    """A display/upload title, including legacy recording names."""
    stem = Path(path).stem
    match = _LEGACY.fullmatch(stem)
    if match:
        date, hour, minute, _ = match.groups()
        title, suffix = 'Recording', ''
    else:
        match = _READABLE.fullmatch(stem)
        if not match:
            return stem
        title, date, hour, minute, collision = match.groups()
        suffix = f' ({collision})' if collision else ''
    try:
        date = datetime.strptime(f'{date} {hour}:{minute}', '%Y-%m-%d %H:%M')
    except ValueError:
        return stem
    return f'{title} · {date.day} {date:%b %Y}, {date:%H:%M}{suffix}'


def rename_recording(path, title):
    """Rename a released local video without replacing any existing file."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Choose an existing local recording, not a symbolic link.')
    if path.suffix.lower() not in ('.mp4', '.mkv'):
        raise ValueError('Only MP4 and MKV recordings can be renamed.')
    title = unicodedata.normalize('NFC', str(title)).strip()
    if not title or '/' in title or '\\' in title or title in ('.', '..'):
        raise ValueError('Enter a title without folders or path separators.')
    if title == recording_title(path):
        return path
    # Pasting a filename must not add another container extension to the title.
    while title.lower().endswith(('.mp4', '.mkv')):
        title = title[:-4].rstrip(' .')
    if not title:
        raise ValueError('Enter a recording title.')
    cleaned = clean_title(title)
    if cleaned == 'Recording' and not any(ch.isalnum() for ch in title):
        raise ValueError('Enter a recording title.')
    occupied = {entry.stem.casefold() for entry in path.parent.iterdir()
                if entry != path and entry.suffix.lower() in ('.mp4', '.mkv')}
    number = 1
    while True:
        stem = cleaned if number == 1 else f'{cleaned} ({number})'
        target = path.with_name(stem + path.suffix)
        if target == path:
            return path
        if stem.casefold() not in occupied:
            try:
                # Same-directory hard link is atomic and refuses existing targets.
                # Unlike Path.rename on Linux, it can never overwrite a video.
                os.link(path, target, follow_symlinks=False)
            except FileExistsError:
                pass
            else:
                try:
                    path.unlink()
                except OSError:
                    target.unlink()
                    raise
                return target
        number += 1


def recording_files(directory):
    """Newest first, tolerating files removed during discovery."""
    entries = []
    try:
        for path in Path(directory).iterdir():
            try:
                if path.is_file() and path.suffix.lower() in ('.mp4', '.mkv'):
                    entries.append((path.stat().st_mtime_ns, path.name, path))
            except OSError:
                continue
    except FileNotFoundError:
        return []
    return [entry[2] for entry in sorted(entries, reverse=True)]
