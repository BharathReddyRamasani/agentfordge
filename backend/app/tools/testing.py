"""Testing tool: executes generated test suites with timeout and parses results."""

import re
from dataclasses import dataclass

from app.core.config import settings
from app.tools.terminal import run_command, sandbox_env


@dataclass
class TestSuiteResult:
    total: int
    passed: int
    failed: int
    errors: int
    status: str
    output: str
    timed_out: bool = False


def parse_pytest_output(output: str) -> tuple[int, int, int, int]:
    total = passed = failed = errors = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) error", output)
    if m:
        errors = int(m.group(1))
    total = passed + failed + errors
    return total, passed, failed, errors


def run_pytest_tests(tests_dir: str, cwd: str, timeout: int | None = None) -> TestSuiteResult:
    """Run pytest on a generated test suite in a sandboxed subprocess."""
    timeout = timeout or settings.sandbox_timeout
    result = run_command(
        [
            "python",
            "-m",
            "pytest",
            str(tests_dir),
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-x",
            "--rootdir",
            cwd,
        ],
        cwd=cwd,
        timeout=timeout,
        env=sandbox_env({"PYTHONPATH": cwd}),
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.timed_out:
        return TestSuiteResult(0, 0, 0, 0, "timeout", output, timed_out=True)
    total, passed, failed, errors = parse_pytest_output(output)
    if total == 0 and not result.ok:
        status = "error"
    elif failed or errors:
        status = "failed"
    else:
        status = "passed"
    return TestSuiteResult(total, passed, failed, errors, status, output)
