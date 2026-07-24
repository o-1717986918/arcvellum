"""Cross-platform subprocess helpers that stay invisible in desktop builds."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Sequence


def hidden_process_options() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def run_hidden(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    options = hidden_process_options()
    options.update(kwargs)
    return subprocess.run(command, **options)


def popen_hidden(command: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]:
    options = hidden_process_options()
    options.update(kwargs)
    return subprocess.Popen(command, **options)
