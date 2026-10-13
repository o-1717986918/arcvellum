"""Atomic original/result storage and one active extraction per content key."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
from uuid import uuid4


def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(text, encoding='utf-8', newline='')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_json(path, value):
    save_text(path, json.dumps(value, ensure_ascii=False, indent=2))


@contextmanager
def extraction_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b'0'); handle.flush()
            _windows_lock(handle, msvcrt)
            try:
                yield
            finally:
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _windows_lock(handle, locking):
    while True:
        handle.seek(0)
        try:
            locking.locking(handle.fileno(), locking.LK_NBLCK, 1)
            return
        except OSError:
            time.sleep(.05)
