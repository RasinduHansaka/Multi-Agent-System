"""
observability/logger.py
-----------------------
Fully local, zero-dependency observability layer.
Writes structured JSONL trace files to the /logs directory.
No internet connection, no API keys, no LangSmith.

Each agent calls `log_agent_event()` to record its activity, and
`write_trace_log()` is called once at the end of main.py to flush
all log entries to disk.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def _ensure_log_dir() -> None:
    """Create the logs directory if it does not exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def build_log_entry(
    agent_name: str,
    input_summary: dict,
    tool_calls: list[dict],
    output_summary: dict,
    duration_ms: float,
    error: Optional[str] = None,
) -> dict:
    """
    Builds a single structured log entry for one agent execution.

    Args:
        agent_name:     Human-readable name of the agent, e.g. "triage_agent".
        input_summary:  Dict summarising what the agent received (never full code – too large).
        tool_calls:     List of dicts, each describing one tool invocation:
                        {"tool": str, "args": dict, "result_summary": str}.
        output_summary: Dict summarising what the agent produced.
        duration_ms:    Wall-clock time the agent took in milliseconds.
        error:          Optional exception message if the agent failed.

    Returns:
        A flat dict suitable for JSON serialisation.
    """
    return {
        "agent": agent_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 2),
        "input_summary": input_summary,
        "tool_calls": tool_calls,
        "output_summary": output_summary,
        "error": error,
    }


def write_trace_log(session_id: str, log_entries: list[dict]) -> str:
    """
    Writes all accumulated log entries for a session to a .jsonl file.
    One JSON object per line – compatible with any log aggregator.

    Args:
        session_id:  The UUID of the current session.
        log_entries: The `logs` list from AgentState.

    Returns:
        The absolute path of the written log file.
    """
    _ensure_log_dir()
    short_id = session_id[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(LOG_DIR, f"trace_{short_id}_{timestamp}.jsonl")

    with open(filename, "w", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n[OBSERVABILITY] Trace log written → {filename}")
    return filename


def print_live_trace(entry: dict) -> None:
    """
    Pretty-prints a single log entry to stdout during execution.
    Gives a real-time console view of the pipeline as it runs.

    Args:
        entry: A log entry dict produced by build_log_entry().
    """
    bar = "─" * 60
    print(f"\n{bar}")
    print(f"  AGENT : {entry['agent'].upper()}")
    print(f"  TIME  : {entry['timestamp_utc']}")
    print(f"  TOOK  : {entry['duration_ms']} ms")
    if entry.get("tool_calls"):
        for tc in entry["tool_calls"]:
            print(f"  TOOL  : {tc.get('tool')} → {tc.get('result_summary', '')}")
    if entry.get("error"):
        print(f"  ERROR : {entry['error']}")
    out = entry.get("output_summary", {})
    for k, v in out.items():
        print(f"  {k.upper():<10}: {v}")
    print(bar)