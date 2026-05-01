"""
agents/code_analyzer.py
-----------------------
MEMBER 2 – Code Analyzer Agent
Uses pyflakes linter output + LLM reasoning to identify bugs, anti-patterns,
and code smells.  Receives the triage strategy from state to focus its analysis.
"""

import json
import time

from langchain_ollama import OllamaLLM

from observability.logger import build_log_entry, print_live_trace
from state import AgentState
from tools.linter_tool import count_lines, run_linter_analysis

# ── LLM setup (shared model, all agents use qwen2:1.5b) ────────────────────────
llm = OllamaLLM(model="qwen2:1.5b", temperature=0.1)

CODE_ANALYZER_SYSTEM_PROMPT = """You are a Code Analysis Agent – a meticulous software engineer
performing a deep code review.

Your persona: You are thorough, precise, and never speculate. You only report what you
can directly observe in the code.

Your responsibilities:
- Identify bugs (logic errors, off-by-one, incorrect comparisons).
- Identify anti-patterns (bare except, mutable default arguments, shadowing builtins).
- Identify code smells (overly long functions, dead code, unnecessary complexity).
- Use the linter results as supporting evidence, not as your only source.

Constraints:
- Output ONLY a valid JSON array. No preamble, no explanation, no markdown fences.
- Each element must have exactly: "line" (int), "type" (str), "description" (str).
- Valid types: "bug", "antipattern", "smell", "warning".
- If no issues are found, output an empty array: [].
- Do NOT suggest fixes here. That is another agent's job.
- Be specific: name the variable, the function, or the pattern you observe.

<examples>
Input Code:
```python
def append_to(num, target=[]):
    target.append(num)
    return target
```
Output:
[{"line": 1, "type": "antipattern", "description": "Mutable default argument 'target=[]' used in function definition."}]

Input Code:
```python
def calc():
    pass
```
Output:
[]

Input Code:
```python
def clean_function(a, b):
    return a + b
```
Output:
[]
</examples>

Output format (strict):
[{"line": <int>, "type": "<bug|antipattern|smell|warning>", "description": "<string>"}, ...]"""


def code_analyzer_node(state: AgentState) -> AgentState:
    """
    LangGraph node for the Code Analyzer Agent.

    Runs the linter tool on the source code, then passes both the linter output
    and the raw code to the LLM for deep analysis.  Results are stored in
    state["code_findings"].

    Args:
        state: Current AgentState containing source_code and review_strategy.

    Returns:
        Updated AgentState with code_findings populated and log entry appended.
    """
    t_start = time.time()
    tool_calls: list[dict] = []

    # ── Tool call: run linter ─────────────────────────────────────────────────
    try:
        linter_results = run_linter_analysis(state["source_code"])
        tool_calls.append({
            "tool": "run_linter_analysis",
            "args": {"code_chars": len(state["source_code"])},
            "result_summary": f"{len(linter_results)} linter findings",
        })
    except RuntimeError as exc:
        linter_results = []
        tool_calls.append({
            "tool": "run_linter_analysis",
            "args": {},
            "result_summary": f"Tool error: {exc}",
        })

    line_count = count_lines(state["source_code"])

    # ── LLM call ──────────────────────────────────────────────────────────────
    prompt = f"""{CODE_ANALYZER_SYSTEM_PROMPT}

Review strategy from Triage Agent: {state.get("review_strategy", "logic,security")}
Language: {state.get("language", "Python")}
Code summary: {state.get("code_summary", "N/A")}
Total substantive lines: {line_count}

Linter findings (use as supporting evidence):
{json.dumps(linter_results, indent=2)}

Source code to analyse:
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
        findings = [{
            "line": 0,
            "type": "parse_error",
            "description": f"LLM returned non-JSON output: {raw_response[:200]}",
        }]

    # Merge linter findings not already captured by the LLM
    llm_lines = {f.get("line") for f in findings}
    for lf in linter_results:
        if lf["line"] not in llm_lines:
            findings.append({
                "line": lf["line"],
                "type": "warning",
                "description": lf["message"],
            })

    duration_ms = (time.time() - t_start) * 1000

    log_entry = build_log_entry(
        agent_name="code_analyzer",
        input_summary={
            "code_chars": len(state["source_code"]),
            "strategy": state.get("review_strategy", ""),
        },
        tool_calls=tool_calls,
        output_summary={
            "total_findings": len(findings),
            "linter_hits": len(linter_results),
            "llm_findings": len(findings) - len(linter_results),
        },
        duration_ms=duration_ms,
    )
    print_live_trace(log_entry)

    return {
        **state,
        "code_findings": findings,
        "logs": state["logs"] + [log_entry],
    }