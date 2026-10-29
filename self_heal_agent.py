
from pathlib import Path
import ast
import subprocess
import sys

from ollama import chat

ROOT = Path.home() / "local-ai-rca"
PROJECT = ROOT / "sample_app"
MODEL = "qwen3:8b"

MAX_STEPS = 15
MAX_REPAIRS = 2
MAX_TEST_RUNS = 4

allowed_files = {"calculator.py", "test_calculator.py"}

state = {
    "read_log": False,
    "read_source": set(),
    "repairs": 0,
    "test_runs": 0,
    "tests_passed": False,
}


def read_failure_log() -> str:
    """Read the most recent pytest report."""
    state["read_log"] = True
    return (ROOT / "failure.log").read_text()[:10000]


def read_source_file(filename: str) -> str:
    """Read an allowed source or test file from the sample project."""
    if filename not in allowed_files:
        return "ERROR: File is not allowed."

    state["read_source"].add(filename)
    return (PROJECT / filename).read_text()[:10000]


def apply_fix(content: str) -> str:
    """Replace calculator.py with a validated, restricted Python function."""
    if not state["read_log"] or not {
        "calculator.py", "test_calculator.py"
    }.issubset(state["read_source"]):
        return "ERROR: Read the failure log and both source files first."

    if state["repairs"] >= MAX_REPAIRS:
        return "ERROR: Repair limit reached."

    if len(content) > 5000:
        return "ERROR: Proposed file is too large."

    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        return f"ERROR: Invalid Python syntax: {exc}"

    # Only allow a simple calculator function. No imports, file access,
    # shell commands, network access, or arbitrary function calls.
    allowed_nodes = (
        ast.Module, ast.FunctionDef, ast.arguments, ast.arg,
        ast.Expr, ast.Constant, ast.Assign, ast.Name, ast.BinOp,
        ast.Mult, ast.Sub, ast.Add, ast.Div, ast.Return,
        ast.Load, ast.Store, ast.UnaryOp, ast.USub, ast.UAdd,
    )

    if any(not isinstance(node, allowed_nodes) for node in ast.walk(tree)):
        return "ERROR: Repair contains disallowed Python operations."

    if (
        len(tree.body) != 1
        or not isinstance(tree.body[0], ast.FunctionDef)
        or tree.body[0].name != "calculate_total"
    ):
        return "ERROR: Only calculate_total may be defined."

    (PROJECT / "calculator.py").write_text(content)
    state["repairs"] += 1
    return "Fix applied to calculator.py. Tests have NOT yet been verified."


def run_tests() -> str:
    """Run the fixed pytest command against the sample project."""
    if state["test_runs"] >= MAX_TEST_RUNS:
        return "ERROR: Test-run limit reached."

    state["test_runs"] += 1

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "sample_app"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = result.stdout + "\n" + result.stderr
        state["tests_passed"] = result.returncode == 0

        report = (
            f"Exit code: {result.returncode}\n"
            f"Tests passed: {state['tests_passed']}\n{output}"
        )
    except subprocess.TimeoutExpired:
        state["tests_passed"] = False
        report = "Tests timed out after 30 seconds."

    (ROOT / "failure.log").write_text(report)
    return report[:12000]


tools = [read_failure_log, read_source_file, apply_fix, run_tests]

messages = [{
    "role": "user",
    "content": """
You are a self-healing coding agent working on a small Python project.

Your goal is to repair the failing test, not merely explain it.

Required process:
1. Read the failure log.
2. Read calculator.py and test_calculator.py.
3. Compare the implementation with the test expectations.
4. Use apply_fix to propose a complete replacement for calculator.py.
5. Call run_tests to validate the repair.
6. If tests fail, inspect the output and try another repair if needed.
7. Stop only when tests pass or you cannot safely repair the problem.

Important:
- Never modify the test file.
- Never claim success without a passing test run.
- Use the actual code and test output as evidence.
- Explain the root cause, changes made, and validation results.
- You must use the tools; do not merely describe a fix.
"""
}]

for step in range(MAX_STEPS):
    response = chat(
        model=MODEL,
        messages=messages,
        tools=tools,
    )

    messages.append(response.message)
    calls = response.message.tool_calls or []

    if not calls:
        if state["tests_passed"]:
            print("\n=== VERIFIED SELF-HEALING REPORT ===")
            print(response.message.content)
            print(
                f"\nRepairs: {state['repairs']}; "
                f"test runs: {state['test_runs']}"
            )
            break

        # Do not accept an unverified diagnosis as successful healing.
        messages.append({
            "role": "user",
            "content": (
                "The repair is not verified. Continue the investigation "
                "using the available tools. Apply a repair and run tests "
                "before reporting success."
            ),
        })
        continue

    for call in calls:
        name = call.function.name
        args = call.function.arguments

        print(f"\n[Step {step + 1}] Tool: {name}")
        print("Arguments:", args)

        dispatch = {
            "read_failure_log": read_failure_log,
            "read_source_file": read_source_file,
            "apply_fix": apply_fix,
            "run_tests": run_tests,
        }

        if name not in dispatch:
            output = "ERROR: Unknown tool."
        else:
            try:
                output = dispatch[name](**args)
            except Exception as exc:
                output = f"Tool error: {type(exc).__name__}: {exc}"

        print(str(output)[:1500])

        messages.append({
            "role": "tool",
            "tool_name": name,
            "content": str(output),
        })

    if state["tests_passed"]:
        print("\nAll tests passed. The repair is verified.")
        print(
            f"Repairs: {state['repairs']}; "
            f"test runs: {state['test_runs']}"
        )
        break
else:
    print("\nStopped: maximum agent steps reached.")

if not state["tests_passed"]:
    print("SELF-HEALING NOT VERIFIED.")
    print("Review the tool outputs before accepting any repair.")

