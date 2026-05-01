"""
sample_code/buggy_example.py
----------------------------
Intentionally buggy Python file used as the demo input for the MAS pipeline.
Contains a variety of bugs, security vulnerabilities, and code smells.
DO NOT USE IN PRODUCTION.
"""

import os
import subprocess
import hashlib
import pickle
import sqlite3

# ── SECURITY: Hardcoded credentials ──────────────────────────────────────────
password = "admin123"
API_KEY = "sk-abc123xyzSECRET"
database_url = "postgresql://admin:password123@localhost/prod"

# ── BUG: Unused import ────────────────────────────────────────────────────────
import json   # noqa: imported but never used


def authenticate_user(username, password):
    """Authenticate a user against the database."""
    # ── SECURITY: SQL injection via string concatenation ─────────────────────
    conn = sqlite3.connect("users.db")
    query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
    result = conn.execute(query)
    return result.fetchone()


def run_system_command(user_input):
    """Run a system command provided by the user."""
    # ── SECURITY: Shell injection ─────────────────────────────────────────────
    result = subprocess.run(user_input, shell=True, capture_output=True)
    return result.stdout


def hash_password(data):
    """Hash a password for storage."""
    # ── SECURITY: Weak MD5 hash ───────────────────────────────────────────────
    return hashlib.md5(data.encode()).hexdigest()


def load_user_session(session_file):
    """Load a user session from a file."""
    # ── SECURITY: Unsafe deserialisation ─────────────────────────────────────
    with open(session_file, "rb") as f:
        return pickle.load(f)


def evaluate_expression(expression):
    """Evaluate a math expression from user input."""
    # ── SECURITY: Arbitrary code execution ───────────────────────────────────
    return eval(expression)


def process_items(items=[]):
    """Process a list of items."""
    # ── BUG: Mutable default argument ────────────────────────────────────────
    for i in range(len(items)):    # anti-pattern: should use enumerate
        print(items[i])


def divide(a, b):
    """Divide two numbers."""
    # ── BUG: No zero division guard ──────────────────────────────────────────
    return a / b


def read_file(path):
    """Read a file and return its contents."""
    try:
        with open(path) as f:
            return f.read()
    except:                        # BUG: bare except swallows all exceptions
        return None


def find_item(items, target):
    """Find the index of target in items."""
    for i in range(len(items)):
        if items[i] == target:
            return i
    # ── BUG: No return for not-found case ────────────────────────────────────


# ── BUG: Variable used before assignment in some paths ───────────────────────
def get_config(env):
    if env == "production":
        config = {"debug": False, "db": "prod.db"}
    elif env == "staging":
        config = {"debug": True, "db": "staging.db"}
    # Missing: else branch – config may be undefined
    return config


# ── SMELL: Dead code ──────────────────────────────────────────────────────────
def _legacy_hash(data):
    """Old hashing function. No longer called anywhere."""
    return hashlib.sha1(data.encode()).hexdigest()


# Entry point
if __name__ == "__main__":
    print(authenticate_user("admin", "' OR '1'='1"))
    print(hash_password("mysecretpassword"))
    print(evaluate_expression("2 + 2"))