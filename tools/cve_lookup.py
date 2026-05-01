"""
tools/cve_lookup.py
-------------------
MEMBER 3 – Custom Tool
Queries the OSV.dev public vulnerability database for known CVEs in Python packages.
100% free, no API key required, no cloud costs.  Runs entirely over the public internet.
"""

import re
from typing import Final, Optional

import requests

OSV_API_URL: Final[str] = "https://api.osv.dev/v1/query"
OSV_BATCH_URL: Final[str] = "https://api.osv.dev/v1/querybatch"
REQUEST_TIMEOUT_SECONDS: Final[int] = 10

# Patterns that indicate security issues in code, independent of CVE data
DANGEROUS_PATTERNS: Final[list[dict]] = [
    {"pattern": r"\beval\s*\(", "issue": "Use of eval() – arbitrary code execution risk", "severity": "high"},
    {"pattern": r"\bexec\s*\(", "issue": "Use of exec() – arbitrary code execution risk", "severity": "high"},
    {"pattern": r"shell\s*=\s*True", "issue": "subprocess shell=True – shell injection risk", "severity": "high"},
    {"pattern": r"password\s*=\s*['\"]", "issue": "Hardcoded password literal", "severity": "high"},
    {"pattern": r"(api_key|apikey|secret|token)\s*=\s*['\"]", "issue": "Hardcoded secret/API key", "severity": "high"},
    {"pattern": r"hashlib\.md5\b", "issue": "Use of MD5 – weak cryptographic hash", "severity": "medium"},
    {"pattern": r"hashlib\.sha1\b", "issue": "Use of SHA-1 – weak cryptographic hash", "severity": "medium"},
    {"pattern": r"SELECT\s.*\+\s*[a-zA-Z]", "issue": "Possible SQL injection via string concatenation", "severity": "high"},
    {"pattern": r"pickle\.load", "issue": "Use of pickle.load – unsafe deserialisation", "severity": "high"},
    {"pattern": r"__import__\s*\(", "issue": "Dynamic __import__() call – obfuscation risk", "severity": "medium"},
]


def query_osv_database(package_name: str, version: str, ecosystem: str = "PyPI") -> dict:
    """
    Queries the OSV.dev API for known vulnerabilities in a specific package version.

    Uses the public OSV REST API (https://osv.dev) which is completely free and
    requires no authentication.  Returns a structured result dict.

    Args:
        package_name: The name of the package to check, e.g. "requests".
        version:      The version string to check, e.g. "2.25.0".
        ecosystem:    The package ecosystem (default: "PyPI" for Python packages).

    Returns:
        A dict with the following keys:
            - "package"     (str):  The queried package name.
            - "version"     (str):  The queried version string.
            - "vulnerable"  (bool): True if at least one CVE was found.
            - "vuln_ids"    (list[str]): List of CVE/OSV IDs found.
            - "vuln_count"  (int):  Total number of vulnerabilities found.

    Raises:
        ConnectionError: If the OSV API is unreachable or returns a non-200 status.
        ValueError: If package_name or version are empty strings.

    Example:
        >>> result = query_osv_database("requests", "2.25.0")
        >>> result["vulnerable"]
        True
    """
    if not package_name.strip():
        raise ValueError("package_name must not be empty.")
    if not version.strip():
        raise ValueError("version must not be empty.")

    payload = {
        "version": version,
        "package": {
            "name": package_name,
            "ecosystem": ecosystem,
        },
    }

    try:
        response = requests.post(
            OSV_API_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise ConnectionError(
            f"OSV API request timed out after {REQUEST_TIMEOUT_SECONDS}s."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ConnectionError(f"OSV API unreachable: {exc}") from exc

    data = response.json()
    vulns = data.get("vulns", [])

    return {
        "package": package_name,
        "version": version,
        "vulnerable": len(vulns) > 0,
        "vuln_ids": [v.get("id", "UNKNOWN") for v in vulns],
        "vuln_count": len(vulns),
    }


def scan_code_for_security_patterns(code: str) -> list[dict]:
    """
    Scans raw source code for dangerous patterns using regex.
    This operates entirely locally – no network calls.

    Args:
        code: The source code string to scan.

    Returns:
        A list of finding dicts, each with:
            - "line"      (int):  Line number of the match (1-indexed).
            - "issue"     (str):  Description of the security issue.
            - "severity"  (str):  "high", "medium", or "low".
            - "match"     (str):  The matched text snippet.

    Example:
        >>> findings = scan_code_for_security_patterns("result = eval(user_input)")
        >>> findings[0]["severity"]
        'high'
    """
    findings: list[dict] = []
    lines = code.splitlines()

    for pattern_def in DANGEROUS_PATTERNS:
        compiled = re.compile(pattern_def["pattern"], re.IGNORECASE)
        for line_num, line_text in enumerate(lines, start=1):
            match = compiled.search(line_text)
            if match:
                findings.append({
                    "line": line_num,
                    "issue": pattern_def["issue"],
                    "severity": pattern_def["severity"],
                    "match": match.group(0),
                })

    return findings


def extract_imports(code: str) -> list[str]:
    """
    Extracts top-level imported package names from Python source code.

    Args:
        code: Python source code as a string.

    Returns:
        A deduplicated list of top-level package name strings.

    Example:
        >>> extract_imports("import os\\nfrom requests import get")
        ['os', 'requests']
    """
    pattern = re.compile(r"^(?:import|from)\s+([\w]+)", re.MULTILINE)
    matches = pattern.findall(code)
    # Exclude stdlib packages that are never in OSV
    stdlib = {
        "os", "sys", "re", "json", "time", "datetime", "math", "random",
        "string", "io", "abc", "ast", "copy", "functools", "itertools",
        "collections", "pathlib", "typing", "hashlib", "subprocess",
        "tempfile", "shutil", "logging", "unittest", "dataclasses",
    }
    return list({m for m in matches if m not in stdlib})

def get_package_version(package_name: str) -> str:
    """
    Attempts to read the package version from requirements.txt in the workspace.
    Falls back to a default '0.0.1' if not found.
    """
    import os
    req_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
    if os.path.exists(req_path):
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{package_name}=="):
                        return line.split("==")[1].strip()
        except Exception:
            pass
    return "0.0.1"