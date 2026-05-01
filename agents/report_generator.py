"""
agents/report_generator.py
--------------------------
MEMBER 4 – Report Generator Agent
Synthesises all upstream findings into a professional markdown code review report.
Saves the report to disk and persists session metadata to the SQLite database.
"""

import json
import os
import time

from langchain_ollama import OllamaLLM

from observability.logger import build_log_entry, print_live_trace
from state import AgentState
from tools.db_logger import save_session_report

# ── LLM setup (shared model, all agents use qwen2:1.5b) ────────────────────────
llm = OllamaLLM(model="qwen2:1.5b", temperature=0.2)

REPORT_GENERATOR_SYSTEM_PROMPT = """You are the Report Generator Agent in a code review system.
Your persona: a technical lead writing a formal code review report for a development team.

Your responsibilities:
- Synthesise all code analysis and security findings into a clear, professional markdown report.
- Prioritise findings by severity.
- Provide a clear overall verdict.

Constraints:
- You MUST include EXACTLY these four section headers, in this order:
  ## Summary
  ## Bugs
  ## Security Issues
  ## Recommendations
- Under ## Bugs: list each code finding as a bullet point with the line number.
- Under ## Security Issues: list each security finding as a bullet point,
  prefixed with its severity in brackets, e.g. [HIGH], [MEDIUM].
- Under ## Recommendations: provide 3-5 actionable improvement suggestions.
- End the report with a single line: **Overall Severity: <Low|Medium|High|Critical>**
- Do NOT add any sections beyond the four required ones.
- Write in clear, professional English. Be concise but complete.

<examples>
Output Example:
## Summary
A brief 1-2 sentence summary of the code and findings.

## Bugs
- Line 10: Logic error because of an off-by-one issue.

## Security Issues
- [HIGH] Line 12: SQL Injection risk in the query builder.

## Recommendations
- Use parameterized queries to prevent SQL injection.
- Add unit tests for boundary conditions.

**Overall Severity: High**
</examples>"""


def report_generator_node(state: AgentState) -> AgentState:
    """
    LangGraph node for the Report Generator Agent.

    Builds the final markdown report from all upstream findings, saves it to
    disk as a .md file, and persists the session to the SQLite database.

    Args:
        state: Current AgentState with code_findings and security_findings populated.

    Returns:
        Updated AgentState with final_report set and log entry appended.
    """
    t_start = time.time()
    tool_calls: list[dict] = []

    code_findings = state.get("code_findings", [])
    security_findings = state.get("security_findings", [])

    # ── LLM call ──────────────────────────────────────────────────────────────
    prompt = f"""{REPORT_GENERATOR_SYSTEM_PROMPT}

File reviewed: {state.get("filepath", "unknown")}
Language: {state.get("language", "Unknown")}
Code summary: {state.get("code_summary", "N/A")}
Review strategy applied: {state.get("review_strategy", "N/A")}

Code analysis findings ({len(code_findings)} total):
{json.dumps(code_findings, indent=2)}

Security audit findings ({len(security_findings)} total):
{json.dumps(security_findings, indent=2)}

Write the complete markdown report now:"""

    report = llm.invoke(prompt)

    # Guarantee required sections exist even if LLM omits them
    for section in ["## Summary", "## Bugs", "## Security Issues", "## Recommendations"]:
        if section not in report:
            report += f"\n\n{section}\n_No findings in this category._\n"

    duration_seconds = time.time() - t_start

    # ── Tool call: save to SQLite ─────────────────────────────────────────────
    db_ok = save_session_report(
        session_id=state["session_id"],
        filepath=state.get("filepath", "unknown"),
        language=state.get("language", "Unknown"),
        code_findings=code_findings,
        security_findings=security_findings,
        report=report,
        duration_seconds=duration_seconds,
    )
    tool_calls.append({
        "tool": "save_session_report",
        "args": {"session_id": state["session_id"]},
        "result_summary": "Saved to DB" if db_ok else "DB save FAILED",
    })

    # ── Save report to disk ───────────────────────────────────────────────────
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"report_{state['session_id'][:8]}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Code Review Report\n")
        f.write(f"**Session:** {state['session_id']}\n")
        f.write(f"**File:** {state.get('filepath', 'unknown')}\n\n")
        f.write(report)
    tool_calls.append({
        "tool": "write_report_file",
        "args": {"path": report_path},
        "result_summary": f"Report saved ({len(report)} chars)",
    })

    log_entry = build_log_entry(
        agent_name="report_generator",
        input_summary={
            "code_findings": len(code_findings),
            "security_findings": len(security_findings),
        },
        tool_calls=tool_calls,
        output_summary={
            "report_chars": len(report),
            "report_path": report_path,
            "db_saved": db_ok,
        },
        duration_ms=duration_seconds * 1000,
    )
    print_live_trace(log_entry)

    return {
        **state,
        "final_report": report,
        "logs": state["logs"] + [log_entry],
    }