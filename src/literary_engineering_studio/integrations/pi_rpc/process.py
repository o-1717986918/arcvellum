"""Short-lived Pi RPC subprocess with request correlation and bounded shutdown."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ...subprocess_utils import popen_hidden
from .framing import JsonlFramer, PiRpcProtocolError, encode_jsonl


class PiRpcProcessError(RuntimeError):
    pass


class PiRpcProcess:
    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.command = tuple(str(part) for part in command)
        self.cwd = cwd
        self.event_sink = event_sink
        self._process: subprocess.Popen[bytes] | None = None
        self._pending: dict[str, queue.Queue[dict[str, Any] | BaseException]] = {}
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._counter = 0
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._stderr: list[str] = []
        self._protocol_error: BaseException | None = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None and self._process.poll() is None else None

    @property
    def returncode(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    @property
    def stderr(self) -> str:
        return "".join(self._stderr)

    def start(self) -> None:
        if self._process is not None:
            raise PiRpcProcessError("Pi RPC process is already started")
        self._process = popen_hidden(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        self._reader = threading.Thread(target=self._read_stdout, name="arcvellum-pi-rpc-stdout", daemon=True)
        self._stderr_reader = threading.Thread(
            target=self._read_stderr,
            name="arcvellum-pi-rpc-stderr",
            daemon=True,
        )
        self._reader.start()
        self._stderr_reader.start()

    def request(self, command_type: str, *, timeout: float = 10.0, **payload: Any) -> dict[str, Any]:
        process = self._require_process()
        with self._lock:
            self._counter += 1
            request_id = f"arcvellum-{self._counter}"
            response_queue: queue.Queue[dict[str, Any] | BaseException] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        message = {"id": request_id, "type": command_type, **payload}
        try:
            assert process.stdin is not None
            with self._write_lock:
                process.stdin.write(encode_jsonl(message))
                process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            with self._lock:
                self._pending.pop(request_id, None)
            raise PiRpcProcessError(f"failed to write Pi RPC request: {exc}") from exc
        try:
            result = response_queue.get(timeout=max(0.05, timeout))
        except queue.Empty as exc:
            with self._lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"Pi RPC request timed out: {command_type}") from exc
        if isinstance(result, BaseException):
            raise PiRpcProcessError(str(result)) from result
        if result.get("success") is not True:
            raise PiRpcProcessError(str(result.get("error") or f"Pi RPC command failed: {command_type}"))
        return result

    def wait_for_event(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float,
        on_wait: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.05, timeout)
        while True:
            if on_wait is not None:
                on_wait()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for Pi RPC event")
            try:
                event = self._events.get(timeout=min(0.1, remaining))
            except queue.Empty:
                process = self._require_process()
                if process.poll() is not None:
                    raise PiRpcProcessError(self._exit_message())
                continue
            if predicate(event):
                return event

    def abort(self, *, timeout: float = 3.0) -> None:
        process = self._require_process()
        if process.poll() is not None:
            return
        try:
            self.request("abort", timeout=timeout)
        except (PiRpcProcessError, TimeoutError):
            self.terminate()

    def close(self, *, timeout: float = 5.0) -> int | None:
        process = self._process
        if process is None:
            return None
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=max(0.1, timeout))
        except subprocess.TimeoutExpired:
            self.terminate()
        self._join_readers()
        self._close_streams()
        return process.poll()

    def terminate(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        self._join_readers()
        self._close_streams()

    def _read_stdout(self) -> None:
        process = self._require_process()
        assert process.stdout is not None
        framer = JsonlFramer()
        try:
            while True:
                chunk = process.stdout.read1(4096)
                if not chunk:
                    break
                for record in framer.feed(chunk):
                    self._dispatch(record)
            for record in framer.finish():
                self._dispatch(record)
        except (OSError, PiRpcProtocolError) as exc:
            self._protocol_error = exc
        finally:
            self._fail_pending(self._protocol_error or PiRpcProcessError(self._exit_message()))

    def _read_stderr(self) -> None:
        process = self._require_process()
        assert process.stderr is not None
        while True:
            chunk = process.stderr.read1(4096)
            if not chunk:
                break
            self._stderr.append(chunk.decode("utf-8", errors="replace"))

    def _dispatch(self, record: dict[str, Any]) -> None:
        request_id = str(record.get("id") or "")
        if record.get("type") == "response" and request_id:
            with self._lock:
                pending = self._pending.pop(request_id, None)
            if pending is not None:
                pending.put(record)
                return
        self._events.put(record)
        if self.event_sink is not None:
            self.event_sink(record)

    def _fail_pending(self, error: BaseException) -> None:
        with self._lock:
            pending = tuple(self._pending.values())
            self._pending.clear()
        for response_queue in pending:
            response_queue.put(error)

    def _require_process(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise PiRpcProcessError("Pi RPC process has not started")
        return self._process

    def _exit_message(self) -> str:
        process = self._process
        code = process.poll() if process is not None else None
        detail = self.stderr.strip()
        return f"Pi RPC process exited with {code}" + (f": {detail}" if detail else "")

    def _join_readers(self) -> None:
        for thread in (self._reader, self._stderr_reader):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=2)

    def _close_streams(self) -> None:
        process = self._process
        if process is None:
            return
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
