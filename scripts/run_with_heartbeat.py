"""Run one workflow stage with streaming output, heartbeat, and timeout evidence."""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence


TIMEOUT_EXIT_CODE = 124


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate a stage and its descendants so timed-out tools cannot become orphans."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)


def run_command(
    command: Sequence[str],
    *,
    log_path: Path,
    stage: str,
    heartbeat_seconds: float,
    timeout_seconds: float,
    emit: Callable[[str], None],
) -> dict[str, Any]:
    """Run a command while streaming merged output and emitting progress heartbeats."""
    if not command:
        raise ValueError("command must not be empty")
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds must be greater than zero")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=os.name != "nt",
    )
    output_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                output_queue.put(line)
        finally:
            process.stdout.close()
            output_queue.put(None)

    reader = threading.Thread(target=read_output, name=f"workflow-{stage}-output", daemon=True)
    reader.start()

    next_heartbeat = started + heartbeat_seconds
    stream_closed = False
    timed_out = False
    with log_path.open("w", encoding="utf-8", newline="\n") as log_file:
        while True:
            now = time.monotonic()
            elapsed = now - started
            if not timed_out and elapsed >= timeout_seconds and process.poll() is None:
                timed_out = True
                emit(f"timeout stage={stage} elapsed_s={elapsed:.1f} limit_s={timeout_seconds:g} pid={process.pid}")
                _terminate_process_tree(process)

            wait_seconds = max(0.01, min(0.1, next_heartbeat - now))
            try:
                line = output_queue.get(timeout=wait_seconds)
            except queue.Empty:
                line = ""

            if line is None:
                stream_closed = True
            elif line:
                normalized = line.rstrip("\r\n")
                log_file.write(normalized + "\n")
                log_file.flush()
                emit(normalized)

            now = time.monotonic()
            if process.poll() is None and now >= next_heartbeat:
                emit(f"heartbeat stage={stage} elapsed_s={now - started:.1f} pid={process.pid}")
                next_heartbeat = now + heartbeat_seconds

            if process.poll() is not None and stream_closed and output_queue.empty():
                break

    reader.join(timeout=1)
    exit_code = TIMEOUT_EXIT_CODE if timed_out else int(process.wait())
    return {
        "stage": stage,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "log_file": str(log_path),
    }


def _main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--result-file", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--heartbeat-seconds", type=float, default=15)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command[1:] if arguments.command[:1] == ["--"] else arguments.command

    result = run_command(
        command,
        log_path=arguments.log_file.resolve(),
        stage=arguments.stage,
        heartbeat_seconds=arguments.heartbeat_seconds,
        timeout_seconds=arguments.timeout_seconds,
        emit=lambda line: print(line, flush=True),
    )
    arguments.result_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"stage_process_complete stage={arguments.stage} exit_code={result['exit_code']} "
        f"duration_ms={result['duration_ms']} timed_out={str(result['timed_out']).lower()}",
        flush=True,
    )
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(_main())
