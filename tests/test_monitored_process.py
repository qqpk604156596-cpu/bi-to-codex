"""Behavior tests for the workflow subprocess monitor."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_with_heartbeat.py"


def load_runner():
    specification = importlib.util.spec_from_file_location("run_with_heartbeat", RUNNER_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("run_with_heartbeat.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class MonitoredProcessTests(unittest.TestCase):
    def test_cli_survives_unicode_stage_output_under_legacy_console_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            result_path = directory / "result.json"
            environment = {**os.environ, "PYTHONIOENCODING": "gbk"}
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER_PATH),
                    "--log-file",
                    str(directory / "unicode.log"),
                    "--result-file",
                    str(result_path),
                    "--stage",
                    "UnicodeStage",
                    "--heartbeat-seconds",
                    "1",
                    "--timeout-seconds",
                    "5",
                    "--",
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write('⚠ warning\\n'.encode('utf-8'))",
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout.decode("gbk", errors="replace"))
            self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["exit_code"], 0)

    def test_silent_command_emits_heartbeat_and_streams_output_to_log(self) -> None:
        runner = load_runner()
        events: list[str] = []
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "stage.log"
            result = runner.run_command(
                [
                    sys.executable,
                    "-c",
                    "import time; print('started', flush=True); time.sleep(0.25); print('finished', flush=True)",
                ],
                log_path=log_path,
                stage="SilentStage",
                heartbeat_seconds=0.05,
                timeout_seconds=2,
                emit=events.append,
            )

            self.assertEqual(result["exit_code"], 0)
            self.assertFalse(result["timed_out"])
            self.assertTrue(any(event.startswith("heartbeat stage=SilentStage") for event in events))
            self.assertEqual(log_path.read_text(encoding="utf-8").splitlines(), ["started", "finished"])
            self.assertLess(events.index("started"), events.index("finished"))

    def test_timeout_terminates_command_and_returns_stable_exit_code(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = runner.run_command(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                log_path=Path(temporary_directory) / "timeout.log",
                stage="TimeoutStage",
                heartbeat_seconds=0.05,
                timeout_seconds=0.15,
                emit=lambda _event: None,
            )

            self.assertEqual(result["exit_code"], 124)
            self.assertTrue(result["timed_out"])
            self.assertLess(result["duration_ms"], 2000)

    @unittest.skipUnless(os.name == "nt", "Windows process-tree behavior")
    def test_timeout_terminates_descendant_processes(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "orphan-finished.txt"
            grandchild_code = (
                "import pathlib,sys,time; time.sleep(0.8); "
                "pathlib.Path(sys.argv[1]).write_text('orphan', encoding='utf-8')"
            )
            parent_code = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable, '-c', {grandchild_code!r}, {str(marker)!r}]); "
                "time.sleep(5)"
            )
            runner.run_command(
                [sys.executable, "-c", parent_code],
                log_path=Path(temporary_directory) / "tree-timeout.log",
                stage="TreeTimeoutStage",
                heartbeat_seconds=0.05,
                timeout_seconds=0.15,
                emit=lambda _event: None,
            )
            time.sleep(1)

            self.assertFalse(marker.exists(), "timeout left a descendant process running")


if __name__ == "__main__":
    unittest.main()
