import os
import subprocess
import sys
from typing import List


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _run(cmd: List[str]) -> int:
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT)
    return int(p.returncode)


def main() -> int:
    checks = [
        [sys.executable, "Backend/tests/run_parser_regressions.py"],
        [sys.executable, "-m", "py_compile", "Backend/app/main.py"],
        [sys.executable, "-m", "py_compile", "Backend/app/local_parser.py"],
        [sys.executable, "-m", "py_compile", "Backend/app/llm_intent.py"],
    ]

    failed = []
    for cmd in checks:
        rc = _run(cmd)
        if rc != 0:
            failed.append((cmd, rc))

    if failed:
        print("\nStability checks FAILED:")
        for cmd, rc in failed:
            print(f"- rc={rc}: {' '.join(cmd)}")
        return 1

    print("\nStability checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
