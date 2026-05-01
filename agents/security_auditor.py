"""
agents/security_auditor.py
--------------------------
MEMBER 3 – Security Auditor Agent
Performs a two-pass security audit:
  Pass 1: Local regex scan for dangerous code patterns (no network).
  Pass 2: OSV.dev CVE lookup for imported third-party packages.
Then the LLM synthesises both passes into a structured findings list.
"""

import json
import time

from langchain_ollama import OllamaLLM

from observability.logger import build_log_entry, print_live_trace
from state import AgentState
from tools.cve_lookup import (
    extract_imports,
    get_package_version,
    query_osv_database,
    scan_code_for_security_patterns,
)

# ── LLM setup (shared model, all agents use qwen2:1.5b) ────────────────────────
llm = OllamaLLM(model="qwen2:1.5b", temperature=0.0)

SECURITY_AUDITOR_SYSTEM_PROMPT = """You are the Security Auditor Agent in an automated code review system.
Your persona: a penetration tester and application security engineer.

Your responsibilities:
- Analyse the code for OWASP Top 10 vulnerabilities.
- Flag hardcoded credentials, secrets, and API keys.
- Identify injection vulnerabilities (SQL, command, code).
- Detect use of insecure cryptographic primitives.
- Identify unsafe deserialisation.
- Review third-party dependency vulnerabilities from the CVE scan results provided.

Constraints:
- Output ONLY a valid JSON array. No preamble, no explanation, no markdown fences.
- Each element must have exactly: "line" (int), "issue" (str), "severity" (str).
- Valid severities: "critical", "high", "medium", "low".
- Do NOT duplicate issues already clearly identified in the pattern scan.
- If no issues are found, output an empty array: [].
- You MUST assign "critical" to any hardcoded credentials or remote code execution vectors.
- You MUST cite the exact line numbers provided by the pattern scan findings. Do not guess line numbers.

<examples>
Input Code:
```python
import os
def get_user():
    db_pass = "super_secret_123"
    return db_pass
```
Output:
[{"line": 3, "issue": "Hardcoded password literal found in code.", "severity": "critical"}]

Input Code:
```python
def add(a, b):
    return a + b
```
Output:
[]
</examples>

Output format (strict):
[{"line": <int>, "issue": "<string>", "severity": "<critical|high|medium|low>"}, ...]"""


def security_auditor_node(state: AgentState) -> AgentState:
    """
    LangGraph node for the Security Auditor Agent.

    Performs a local regex-based pattern scan, queries OSV.dev for CVEs in
    imported packages, then invokes the LLM to synthesise all findings.

    Args:
        state: Current AgentState containing source_code and language.

    Returns:
        Updated AgentState with security_findings populated and log entry appended.
    """
    t_start = time.time()
    tool_calls: list[dict] = []

    # ── Pass 1: local pattern scan (no network) ───────────────────────────────
    pattern_findings = scan_code_for_security_patterns(state["source_code"])
    tool_calls.append({
        "tool": "scan_code_for_security_patterns",
        "args": {"code_chars": len(state["source_code"])},
        "result_summary": f"{len(pattern_findings)} pattern matches",
    })

    # ── Pass 2: CVE lookup for imports ────────────────────────────────────────
    imports = extract_imports(state["source_code"])
    cve_findings: list[dict] = []

    for pkg in imports[:8]:   # cap at 8 to avoid long waits on slow connections
        try:
            version = get_package_version(pkg)
            result = query_osv_database(pkg, version)
            if result["vulnerable"]:
                cve_findings.append(result)
        except (ConnectionError, Exception):
            # Never crash the pipeline due to a network issue
            pass

    tool_calls.append({
        "tool": "query_osv_database",
        "args": {"packages_checked": len(imports)},
        "result_summary": f"{len(cve_findings)} packages with known CVEs",
    })

    # ── LLM call ──────────────────────────────────────────────────────────────
    prompt = f"""{SECURITY_AUDITOR_SYSTEM_PROMPT}

Language: {state.get("language", "Python")}
Code summary: {state.get("code_summary", "N/A")}

Pattern scan results (use as your primary evidence):
{json.dumps(pattern_findings, indent=2)}

CVE scan results for imported packages:
{json.dumps(cve_findings, indent=2)}

Source code to audit:
```
{state["source_code"][:4000]}
```"""

    raw_response = llm.invoke(prompt)

    # ── Parse LLM output ──────────────────────────────────────────────────────
    import re
    try:
        match = re.search(r'\[.*\]', raw_response, re.DOTALL)
        if match:
            clean = match.group(0)
        else:
            clean = raw_response.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        findings: list[dict] = json.loads(clean)
        if not isinstance(findings, list):
            findings = []
    except json.JSONDecodeError:
        findings = []

    # Always include pattern scan findings even if LLM fails
    llm_lines = {f.get("line") for f in findings}
    for pf in pattern_findings:
        if pf["line"] not in llm_lines:
            findings.append({
                "line": pf["line"],
                "issue": pf["issue"],
                "severity": pf["severity"],
            })

    duration_ms = (time.time() - t_start) * 1000

    log_entry = build_log_entry(
        agent_name="security_auditor",
        input_summary={
            "code_chars": len(state["source_code"]),
            "imports_found": len(imports),
        },
        tool_calls=tool_calls,
        output_summary={
            "pattern_hits": len(pattern_findings),
            "cve_hits": len(cve_findings),
            "total_findings": len(findings),
        },
        duration_ms=duration_ms,
    )
    print_live_trace(log_entry)

    return {
        **state,
        "security_findings": findings,
        "logs": state["logs"] + [log_entry],
    }