import json
import subprocess
import sys


def test_cli_scripted_mode_returns_verification_status(tmp_path):
    completed = subprocess.run(
        [
            sys.executable, "-m", "src.demo.run_demo",
            "--scripted", "dev-python", "--json", "--output-dir", str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["verification_status"] == "passed"
    assert payload["task_id"] == "dev-python"
