"""
tools/file_reader.py
--------------------
MEMBER 1 – Custom Tool
Reads source code from a local file on disk and validates it before returning.
This is the first tool called in the pipeline – it feeds raw code into the state.
"""

import os
from typing import Final

SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = (".py", ".js", ".ts", ".java", ".cpp", ".c")
MAX_FILE_SIZE_BYTES: Final[int] = 500_000   # 500 KB safety cap


def read_code_file(filepath: str) -> str:
    """
    Reads and validates a source code file from the local filesystem.

    Performs the following checks before returning content:
    - File exists at the given path.
    - File extension is a supported source code type.
    - File is not empty.
    - File does not exceed the maximum allowed size (500 KB).

    Args:
        filepath: Absolute or relative path to the source code file.

    Returns:
        The full UTF-8 decoded text content of the file as a string.

    Raises:
        FileNotFoundError: If no file exists at the specified path.
        ValueError: If the extension is unsupported, the file is empty,
                    or the file exceeds the maximum size limit.
        IOError: If the file cannot be read due to a permissions error.

    Example:
        >>> code = read_code_file("sample_code/buggy_example.py")
        >>> print(code[:50])
        import os
    """
    # ── existence check ───────────────────────────────────────────────────────
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Source file not found: '{filepath}'. "
            "Please provide a valid path relative to the project root."
        )

    # ── extension check ───────────────────────────────────────────────────────
    _, ext = os.path.splitext(filepath)
    if ext.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # ── size check ────────────────────────────────────────────────────────────
    file_size = os.path.getsize(filepath)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large ({file_size} bytes). "
            f"Maximum allowed size is {MAX_FILE_SIZE_BYTES} bytes."
        )

    # ── read content ──────────────────────────────────────────────────────────
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception as exc:
            raise IOError(f"Failed to read '{filepath}' due to encoding issues.") from exc
    except PermissionError as exc:
        raise IOError(f"Permission denied when reading '{filepath}'.") from exc

    # ── empty check ───────────────────────────────────────────────────────────
    if not content.strip():
        raise ValueError(f"File '{filepath}' is empty or contains only whitespace.")

    return content


def detect_language(filepath: str) -> str:
    """
    Infers the programming language from the file extension.

    Args:
        filepath: Path to the source file (only extension is used).

    Returns:
        A human-readable language name string, e.g. "Python", "JavaScript".

    Example:
        >>> detect_language("app.py")
        'Python'
    """
    ext_map: dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
    }
    _, ext = os.path.splitext(filepath)
    return ext_map.get(ext.lower(), "Unknown")