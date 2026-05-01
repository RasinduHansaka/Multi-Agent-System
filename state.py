"""
state.py
--------
Defines the single global state object that flows through every node in the
LangGraph pipeline.  All agents READ from and RETURN an updated copy of this
TypedDict – nothing is ever passed as a raw string between agents.
"""

from typing import Optional, TypedDict


class AgentState(TypedDict):
    # ── session metadata ──────────────────────────────────────────────────────
    session_id: str                  # UUID, set once at startup in main.py
    filepath: str                    # path to the file being reviewed

    # ── raw input ─────────────────────────────────────────────────────────────
    source_code: str                 # populated by the Triage Agent (Member 1)

    # ── triage output (Member 1) ──────────────────────────────────────────────
    language: str                    # detected language, e.g. "Python"
    code_summary: str                # 1-2 sentence description of what the code does
    review_strategy: str             # comma-separated focus areas, e.g. "logic,security"

    # ── analysis output (Member 2) ───────────────────────────────────────────
    code_findings: list[dict]        # [{"line": int, "type": str, "description": str}]

    # ── security output (Member 3) ───────────────────────────────────────────
    security_findings: list[dict]    # [{"line": int, "issue": str, "severity": str}]

    # ── report output (Member 4) ─────────────────────────────────────────────
    final_report: str                # full markdown report

    # ── observability ─────────────────────────────────────────────────────────
    logs: list[dict]                 # append-only trace; each agent appends one entry
    error: Optional[str]             # set if any agent catches a fatal exception