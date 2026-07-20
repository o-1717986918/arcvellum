"""Frozen application-service and embedded-engine entry point for Tauri."""

from __future__ import annotations

import sys
import os
import threading
import time

from literary_engineering_studio.cli import main


def _monitor_parent(parent_pid: int) -> None:
    def wait_for_parent() -> None:
        if os.name == "nt":
            import ctypes

            synchronize = 0x00100000
            infinite = 0xFFFFFFFF
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(synchronize, False, parent_pid)
            if handle:
                kernel32.WaitForSingleObject(handle, infinite)
                kernel32.CloseHandle(handle)
            os._exit(0)
        while True:
            try:
                os.kill(parent_pid, 0)
            except OSError:
                os._exit(0)
            time.sleep(1)

    threading.Thread(target=wait_for_parent, name="studio-parent-monitor", daemon=True).start()


if __name__ == "__main__":
    arguments = list(sys.argv[1:])
    if "--parent-pid" in arguments:
        index = arguments.index("--parent-pid")
        if index + 1 >= len(arguments):
            raise SystemExit("--parent-pid requires a process id")
        _monitor_parent(int(arguments[index + 1]))
        del arguments[index : index + 2]
    if arguments[:2] == ["-m", "literary_engineering_studio_engine"]:
        from literary_engineering_studio_engine.cli import main as engine_main

        raise SystemExit(engine_main(arguments[2:]))
    raise SystemExit(main(arguments))
