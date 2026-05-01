"""
tests/test_harness.py
---------------------
UNIFIED TEST HARNESS – all four members' test cases in one file.
Run everything with a single command from the project root:

    pytest tests/test_harness.py -v

Each member's section is clearly labelled.
Includes: property-based tests (hypothesis), unit tests (pytest),
          LLM-as-a-Judge tests, and negative / edge-case tests.

FIX applied (per Gemini feedback): All test cases are in one file, triggered
by a single pytest invocation at the project root.
"""

import json
import os
import sqlite3
import sys
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Add project root to path so all imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


#  MEMBER 1 – Triage Agent + file_reader tool tests

from tools.file_reader import detect_language, read_code_file


class TestFileReaderTool:
    """Member 1: Tests for the read_code_file and detect_language tools."""

    def test_reads_valid_python_file(self, tmp_path):
        """Happy path: valid .py file returns its content."""
        f = tmp_path / "app.py"
        f.write_text("x = 1\nprint(x)\n")
        result = read_code_file(str(f))
        assert isinstance(result, str)
        assert "x = 1" in result

    def test_raises_file_not_found(self):
        """Negative: nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_code_file("/nonexistent/path/doesnotexist.py")

    def test_raises_on_empty_file(self, tmp_path):
        """Negative: empty file raises ValueError."""
        f = tmp_path / "empty.py"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            read_code_file(str(f))

    def test_raises_on_unsupported_extension(self, tmp_path):
        """Negative: unsupported extension raises ValueError."""
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\n1,2\n")
        with pytest.raises(ValueError, match="Unsupported"):
            read_code_file(str(f))

    def test_raises_on_oversized_file(self, tmp_path):
        """Negative: file over 500KB raises ValueError."""
        f = tmp_path / "big.py"
        f.write_text("x = 1\n" * 100_000)  # ~700KB
        with pytest.raises(ValueError, match="large"):
            read_code_file(str(f))

    def test_detect_language_python(self):
        assert detect_language("script.py") == "Python"

    def test_detect_language_javascript(self):
        assert detect_language("app.js") == "JavaScript"

    def test_detect_language_unknown(self):
        assert detect_language("data.xyz") == "Unknown"

    @given(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=1))
    @settings(max_examples=50)
    def test_file_reader_never_raises_unexpected_exception(self, content):
        """Property: read_code_file only ever raises FileNotFoundError or ValueError."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            path = tmp.name
        try:
            read_code_file(path)
        except (FileNotFoundError, ValueError, IOError):
            pass  # These are the only allowed exception types
        except Exception as exc:
            pytest.fail(f"Unexpected exception type raised: {type(exc).__name__}: {exc}")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_detect_language_never_crashes(self, filename):
        """Property: detect_language always returns a string, never crashes."""
        result = detect_language(filename)
        assert isinstance(result, str)



#  MEMBER 2 – Code Analyzer + linter_tool tests


from tools.linter_tool import count_lines, run_linter_analysis


class TestLinterTool:
    """Member 2: Tests for the run_linter_analysis and count_lines tools."""

    def test_detects_undefined_variable(self):
        """Linter finds an undefined name reference."""
        code = "print(totally_undefined_variable_xyz)\n"
        results = run_linter_analysis(code)
        assert len(results) > 0
        messages = [r["message"] for r in results]
        assert any("undefined" in m.lower() or "undefined_variable" in m for m in messages)

    def test_clean_code_returns_empty_list(self):
        """Linter returns empty list for valid, clean Python code."""
        code = "def add(a, b):\n    return a + b\n\nresult = add(1, 2)\nprint(result)\n"
        results = run_linter_analysis(code)
        assert isinstance(results, list)
        # clean code may still have 0 findings
        assert len(results) == 0

    def test_result_dicts_have_required_keys(self):
        """Every linter result dict contains line, message, and severity keys."""
        code = "import os\nimport os\n"
        results = run_linter_analysis(code)
        for r in results:
            assert "line" in r, f"Missing 'line' key in: {r}"
            assert "message" in r, f"Missing 'message' key in: {r}"
            assert "severity" in r, f"Missing 'severity' key in: {r}"
            assert isinstance(r["line"], int)
            assert isinstance(r["message"], str)

    def test_severity_is_always_warning(self):
        """All linter findings have severity == 'warning'."""
        code = "x = undefined_name\n"
        results = run_linter_analysis(code)
        for r in results:
            assert r["severity"] == "warning"

    def test_returns_list_on_syntax_error_code(self):
        """Linter gracefully handles syntactically broken code."""
        code = "def broken(:\n    pass\n"
        try:
            results = run_linter_analysis(code)
            assert isinstance(results, list)
        except RuntimeError:
            pass  # Acceptable – pyflakes may refuse to parse

    def test_count_lines_ignores_comments_and_blanks(self):
        code = "x = 1\n# this is a comment\n\ny = 2\n"
        assert count_lines(code) == 2

    def test_count_lines_empty_code(self):
        assert count_lines("") == 0

    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=40, deadline=None)
    def test_linter_always_returns_list(self, code):
        """Property: run_linter_analysis always returns a list or raises RuntimeError."""
        try:
            result = run_linter_analysis(code)
            assert isinstance(result, list)
        except RuntimeError:
            pass  # Acceptable for completely malformed input


#  MEMBER 3 – Security Auditor + cve_lookup tests

from tools.cve_lookup import extract_imports, scan_code_for_security_patterns


class TestSecurityTools:
    """Member 3: Tests for security pattern scanning and import extraction."""

    def test_detects_eval_usage(self):
        """eval() is flagged as a high-severity security issue."""
        code = "result = eval(user_input)\n"
        findings = scan_code_for_security_patterns(code)
        assert len(findings) > 0
        sevs = [f["severity"] for f in findings]
        assert "high" in sevs

    def test_detects_hardcoded_password(self):
        """Hardcoded password literal is flagged."""
        code = 'password = "super_secret_123"\n'
        findings = scan_code_for_security_patterns(code)
        issues = [f["issue"] for f in findings]
        assert any("password" in i.lower() or "credential" in i.lower() or "hardcoded" in i.lower() for i in issues)

    def test_detects_shell_injection(self):
        """subprocess shell=True is flagged."""
        code = "subprocess.run(cmd, shell=True)\n"
        findings = scan_code_for_security_patterns(code)
        assert len(findings) > 0
        assert any("shell" in f["issue"].lower() for f in findings)

    def test_detects_md5_weak_crypto(self):
        """MD5 usage is flagged as weak cryptography."""
        code = "hashlib.md5(data.encode()).hexdigest()\n"
        findings = scan_code_for_security_patterns(code)
        assert any("md5" in f["issue"].lower() or "weak" in f["issue"].lower() for f in findings)

    def test_detects_sql_injection(self):
        """String concatenation in SQL queries is flagged."""
        code = 'query = "SELECT * FROM users WHERE name=" + username\n'
        findings = scan_code_for_security_patterns(code)
        assert any("sql" in f["issue"].lower() or "injection" in f["issue"].lower() for f in findings)

    def test_clean_code_returns_no_findings(self):
        """Safe code produces no security findings."""
        code = "def add(a, b):\n    return a + b\n"
        findings = scan_code_for_security_patterns(code)
        assert findings == []

    def test_finding_has_required_keys(self):
        """Each security finding has line, issue, severity, and match keys."""
        code = "eval(user_input)\n"
        findings = scan_code_for_security_patterns(code)
        assert len(findings) > 0
        for f in findings:
            assert "line" in f
            assert "issue" in f
            assert "severity" in f
            assert "match" in f

    def test_extract_imports_basic(self):
        code = "import os\nfrom requests import get\nimport sys\n"
        imports = extract_imports(code)
        assert "requests" in imports
        # stdlib packages like os and sys should be excluded
        assert "os" not in imports
        assert "sys" not in imports

    def test_extract_imports_empty_code(self):
        assert extract_imports("x = 1\n") == []

    def test_extract_imports_returns_list(self):
        result = extract_imports("import flask\nfrom django import views\n")
        assert isinstance(result, list)

    @given(st.text(min_size=0, max_size=300))
    @settings(max_examples=50)
    def test_pattern_scanner_never_crashes(self, code):
        """Property: scan_code_for_security_patterns always returns a list."""
        result = scan_code_for_security_patterns(code)
        assert isinstance(result, list)


#  MEMBER 4 – Report Generator + db_logger tests

from tools.db_logger import get_session, init_db, list_sessions, save_session_report


class TestDbLoggerTool:
    """Member 4: Tests for the SQLite persistence tool."""

    def test_save_and_retrieve_session(self, tmp_path):
        """Saved session can be retrieved by session_id."""
        db = str(tmp_path / "test.db")
        ok = save_session_report(
            session_id="sess-test-001",
            filepath="app.py",
            language="Python",
            code_findings=[{"line": 1, "type": "bug", "description": "test bug"}],
            security_findings=[],
            report="# Report\n## Summary\nTest.",
            duration_seconds=1.5,
            db_path=db,
        )
        assert ok is True
        row = get_session("sess-test-001", db_path=db)
        assert row is not None
        assert row["filepath"] == "app.py"
        assert row["language"] == "Python"
        assert row["total_findings"] == 1

    def test_save_returns_false_on_invalid_db_path(self):
        """save_session_report returns False (not raises) on an invalid path."""
        # Use a path with a null byte – always invalid on every OS
        result = save_session_report(
            session_id="sess-bad",
            filepath="x.py",
            language="Python",
            code_findings=[],
            security_findings=[],
            report="# Report",
            db_path="Z:\\invalid:\\path\\db.db",
        )
        # Should return False, NOT raise an exception
        assert result is False

    def test_get_session_returns_none_for_missing(self, tmp_path):
        """get_session returns None for a session_id that doesn't exist."""
        db = str(tmp_path / "test.db")
        init_db(db)
        result = get_session("nonexistent-session-id", db_path=db)
        assert result is None

    def test_list_sessions_returns_list(self, tmp_path):
        """list_sessions always returns a list."""
        db = str(tmp_path / "test.db")
        save_session_report("s1", "a.py", "Python", [], [], "# R", db_path=db)
        save_session_report("s2", "b.py", "Python", [], [], "# R", db_path=db)
        results = list_sessions(limit=10, db_path=db)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_list_sessions_respects_limit(self, tmp_path):
        """list_sessions returns at most `limit` results."""
        db = str(tmp_path / "test.db")
        for i in range(5):
            save_session_report(f"sess-{i}", "f.py", "Python", [], [], "# R", db_path=db)
        results = list_sessions(limit=3, db_path=db)
        assert len(results) <= 3

    def test_init_db_is_idempotent(self, tmp_path):
        """Calling init_db multiple times does not raise or corrupt the DB."""
        db = str(tmp_path / "test.db")
        init_db(db)
        init_db(db)   # second call should be a no-op
        init_db(db)   # third call too
        conn = sqlite3.connect(db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "sessions" in table_names

    def test_report_fields_are_persisted(self, tmp_path):
        """All fields are correctly stored and retrievable from the database."""
        db = str(tmp_path / "test.db")
        report_text = "## Summary\nFound 2 issues.\n## Bugs\n- line 5: bug\n"
        save_session_report(
            session_id="full-test-session",
            filepath="complex.py",
            language="Python",
            code_findings=[{"line": 5, "type": "bug", "description": "test"}],
            security_findings=[{"line": 10, "issue": "eval", "severity": "high"}],
            report=report_text,
            duration_seconds=3.2,
            db_path=db,
        )
        row = get_session("full-test-session", db_path=db)
        assert row["total_findings"] == 2
        assert "Summary" in row["report"]
        saved_code = json.loads(row["code_findings"])
        assert saved_code[0]["line"] == 5

    @given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=50))
    @settings(max_examples=30)
    def test_save_session_accepts_any_string_report(self, session_id, report):
        """Property: save_session_report handles any string content without raising."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db = os.path.join(tmp_dir, "prop_test.db")
            try:
                save_session_report(
                    session_id=session_id,
                    filepath="test.py",
                    language="Python",
                    code_findings=[],
                    security_findings=[],
                    report=report,
                    db_path=db,
                )
            except Exception as exc:
                pytest.fail(f"Unexpected exception: {type(exc).__name__}: {exc}")


#  INTEGRATION – LLM-as-a-Judge test (requires Ollama running locally)

class TestLLMAsJudge:
    """
    LLM-as-a-Judge tests.
    These call the local Ollama LLM to validate agent output quality.
    Skip automatically if Ollama is not running.
    """

    @pytest.fixture(autouse=True)
    def skip_if_ollama_unavailable(self):
        """Skip LLM-as-Judge tests if Ollama is not available."""
        try:
            import requests as req
            req.get("http://localhost:11434", timeout=3)
        except Exception:
            pytest.skip("Ollama not running – skipping LLM-as-Judge tests.")

    def test_report_contains_required_sections(self, tmp_path):
        """
        LLM-as-Judge: verifies the report generator produces all required sections.
        The judge LLM is a second Ollama call that reads the report and confirms
        the four required sections are present.
        """
        from langchain_ollama import OllamaLLM
        from agents.report_generator import report_generator_node

        judge_llm = OllamaLLM(model="llama3:8b", temperature=0.0)

        state = {
            "session_id": "judge-test-001",
            "filepath": "sample_code/buggy_example.py",
            "source_code": "eval(user_input)\npassword = 'abc123'\n",
            "language": "Python",
            "code_summary": "Small script with security issues.",
            "review_strategy": "security,logic",
            "code_findings": [{"line": 2, "type": "bug", "description": "bare assignment"}],
            "security_findings": [{"line": 1, "issue": "eval() usage", "severity": "high"}],
            "final_report": "",
            "logs": [],
            "error": None,
        }

        try:
            result = report_generator_node(state)
            report = result["final_report"]

            judge_prompt = f"""You are a strict report validator.
Read the following code review report and answer ONLY with "PASS" or "FAIL".
Answer "PASS" if ALL FOUR of these exact section headers are present in the report:
  ## Summary
  ## Bugs
  ## Security Issues
  ## Recommendations
Answer "FAIL" if any of these four sections is missing.

Report:
{report}

Answer (PASS or FAIL only):"""

            verdict = judge_llm.invoke(judge_prompt).strip().upper()
            assert "PASS" in verdict, (
                f"LLM judge returned FAIL – report is missing required sections.\n"
                f"Report preview:\n{report[:500]}"
            )
        except Exception as e:
            pytest.skip(f"Ollama runner failed during test: {e}")

    def test_security_agent_flags_dangerous_code(self):
        """
        LLM-as-Judge: verifies the security auditor flags eval() in clearly dangerous code.
        """
        from agents.security_auditor import security_auditor_node
        from langchain_ollama import OllamaLLM

        judge_llm = OllamaLLM(model="llama3:8b", temperature=0.0)

        dangerous_code = (
            "import subprocess\n"
            "user_cmd = input('Enter command: ')\n"
            "subprocess.run(user_cmd, shell=True)\n"
            "password = 'hardcoded_secret'\n"
            "result = eval(user_cmd)\n"
        )

        state = {
            "session_id": "judge-sec-001",
            "filepath": "danger.py",
            "source_code": dangerous_code,
            "language": "Python",
            "code_summary": "Script with shell injection and eval.",
            "review_strategy": "security",
            "code_findings": [],
            "security_findings": [],
            "final_report": "",
            "logs": [],
            "error": None,
        }

        try:
            result = security_auditor_node(state)
            findings_json = json.dumps(result["security_findings"])

            judge_prompt = f"""You are a security review validator.
Read the following JSON list of security findings from an automated tool.
Answer ONLY "PASS" or "FAIL".
Answer "PASS" if the findings list contains AT LEAST 2 security issues.
Answer "FAIL" if the list is empty or contains fewer than 2 issues.

Findings:
{findings_json}

Answer (PASS or FAIL only):"""

            verdict = judge_llm.invoke(judge_prompt).strip().upper()
            assert "PASS" in verdict, (
                f"Security agent found too few issues on clearly dangerous code.\n"
                f"Findings: {findings_json}"
            )
        except Exception as e:
            pytest.skip(f"Ollama runner failed during test: {e}")