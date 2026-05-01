"""
main.py
-------
Entry point for the Code Review Multi-Agent System.

Usage:
    python main.py <path_to_source_file>
    python main.py sample_code/buggy_example.py

The LangGraph StateGraph IS the orchestrator – it manages routing, state flow,
and node sequencing.  Each agent node is a pure function that takes AgentState
and returns an updated AgentState.

Pipeline:
    triage_agent → code_analyzer → security_auditor → report_generator → END
"""

import sys
import time
import uuid

# Force UTF-8 output to prevent crashes on Windows terminals with cp1252
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from langgraph.graph import END, StateGraph

from agents.code_analyzer import code_analyzer_node
from agents.report_generator import report_generator_node
from agents.security_auditor import security_auditor_node
from agents.triage_agent import triage_agent_node
from observability.logger import write_trace_log
from state import AgentState


def route_from_triage(state: AgentState) -> str:
    """
    Dynamically routes after triage based on the review strategy.
    """
    if state.get("error"):
        return "report_generator"
        
    strategy = state.get("review_strategy", "").lower()
    
    # If strategy asks for logic, style, performance, etc.
    if any(k in strategy for k in ["logic", "style", "performance", "error_handling"]):
        return "code_analyzer"
    
    # If it only asks for security
    if any(k in strategy for k in ["security", "crypto", "sql"]):
        return "security_auditor"
        
    # If it asks for neither, go straight to report
    return "report_generator"


def route_from_analyzer(state: AgentState) -> str:
    """
    Dynamically routes after the code analyzer.
    """
    if state.get("error"):
        return "report_generator"
        
    strategy = state.get("review_strategy", "").lower()
    
    # If strategy also asks for security, go there next
    if any(k in strategy for k in ["security", "crypto", "sql"]):
        return "security_auditor"
        
    return "report_generator"


def build_graph() -> object:
    """
    Constructs and compiles the LangGraph StateGraph for the code review pipeline.

    The graph is a sequential pipeline with four nodes.  Each node corresponds to
    one team member's agent.  State flows automatically via the AgentState TypedDict.

    Returns:
        A compiled LangGraph application ready to invoke.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("triage_agent", triage_agent_node)
    graph.add_node("code_analyzer", code_analyzer_node)
    graph.add_node("security_auditor", security_auditor_node)
    graph.add_node("report_generator", report_generator_node)

    # ── Define dynamic conditional edges ──────────────────────────────────────
    graph.set_entry_point("triage_agent")
    
    graph.add_conditional_edges(
        "triage_agent", 
        route_from_triage,
        {
            "code_analyzer": "code_analyzer",
            "security_auditor": "security_auditor",
            "report_generator": "report_generator"
        }
    )
    
    graph.add_conditional_edges(
        "code_analyzer",
        route_from_analyzer,
        {
            "security_auditor": "security_auditor",
            "report_generator": "report_generator"
        }
    )
    
    graph.add_edge("security_auditor", "report_generator")
    graph.add_edge("report_generator", END)

    return graph.compile()


def run_review(filepath: str) -> dict:
    """
    Runs the full code review pipeline on a single source file.

    Args:
        filepath: Path to the source code file to review.

    Returns:
        The final AgentState dict after all agents have executed.
    """
    session_id = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"  CODE REVIEW MAS  –  Session {session_id[:8]}")
    print(f"  File: {filepath}")
    print(f"{'='*60}")

    # ── Build initial state ───────────────────────────────────────────────────
    initial_state: AgentState = {
        "session_id": session_id,
        "filepath": filepath,
        "source_code": "",
        "language": "",
        "code_summary": "",
        "review_strategy": "",
        "code_findings": [],
        "security_findings": [],
        "final_report": "",
        "logs": [],
        "error": None,
    }

    pipeline_start = time.time()
    app = build_graph()
    result = app.invoke(initial_state)
    total_seconds = time.time() - pipeline_start

    # ── Write trace log to disk ───────────────────────────────────────────────
    write_trace_log(session_id, result["logs"])

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  REVIEW COMPLETE in {total_seconds:.1f}s")
    print(f"  Code findings    : {len(result.get('code_findings', []))}")
    print(f"  Security findings: {len(result.get('security_findings', []))}")
    print(f"  Report saved to  : logs/report_{session_id[:8]}.md")
    print(f"{'='*60}\n")

    if result.get("final_report"):
        print(result["final_report"])

    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_code/buggy_example.py"
    run_review(target)