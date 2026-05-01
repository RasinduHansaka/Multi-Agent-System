"""
tools/linter_tool.py
--------------------
MEMBER 2 – Custom Tool
Runs pyflakes static analysis on Python source code via subprocess.
Returns a structured list of findings rather than raw stdout text.
"""

import os
import subprocess
import tempfile
from typing import Final

LINTER_TIMEOUT_SECONDS: Final[int] = 20


def run_linter_analysis(code: str, filename: str = "review_target.py") -> list[dict]:
    """
    Executes pyflakes static analysis on the provided Python source code.

    Writes the code to a temporary file, invokes pyflakes via subprocess,
    parses the output line-by-line into structured dicts, then cleans up
    the temporary file.

    Args:
        code:     The Python source code as a plain string.
        filename: Optional logical filename used in error messages (default: 'review_target.py').

    Returns:
        A list of finding dicts.  Each dict contains:
            - "line"     (int):  Line number where the issue was found.
            - "message"  (str):  Human-readable description of the issue.
            - "severity" (str):  Always "warning" for pyflakes findings.
        Returns an empty list if no issues are found.

    Raises:
        RuntimeError: If pyflakes is not installed or the subprocess times out.

    Example:
        >>> results = run_linter_analysis("import os\\nprint(undefined_var)")
        >>> results[0]["message"]
        "undefined name 'undefined_var'"
    """
    tmp_path: str = ""

    # ── Write to temp file ────────────────────────────────────────────────────
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        # ── Run pyflakes ──────────────────────────────────────────────────────
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "pyflakes", tmp_path],
            capture_output=True,
            text=True,
            timeout=LINTER_TIMEOUT_SECONDS,
        )

        findings: list[dict] = []
        
        all_output = result.stdout + "\n" + result.stderr
        for raw_line in all_output.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            
            parts = raw_line.split(':')
            
            line_num = -1
            message = ""
            for i, part in enumerate(parts):
                if part.strip().isdigit() and i >= 1:
                    line_num = int(part.strip())
                    message = ":".join(parts[i+1:]).strip()
                    # Pyflakes often outputs column number next, skip it if present
                    if message and message.split(':')[0].strip().isdigit():
                        message = ":".join(message.split(':')[1:]).strip()
                    break
                    
            if line_num != -1:
                findings.append({
                    "line": line_num,
                    "message": message,
                    "severity": "warning",
                })

        return findings

    except FileNotFoundError as exc:
        raise RuntimeError(
            "pyflakes is not installed. Run: pip install pyflakes"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Linter subprocess timed out after {LINTER_TIMEOUT_SECONDS} seconds."
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def count_lines(code: str) -> int:
    """
    Returns the number of non-empty, non-comment lines in the code.

    Args:
        code: Source code string.

    Returns:
        Integer count of substantive lines.

    Example:
        >>> count_lines("x = 1\\n# comment\\n\\ny = 2")
        2
    """
    return sum(
        1 for line in code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )