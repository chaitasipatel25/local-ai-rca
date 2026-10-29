from pathlib import Path
from ollama import chat

MODEL = "qwen3:8b"
PROJECT = Path.home() / "local-ai-rca" / "sample_app"
MAX_STEPS = 8

ALLOWED_FILES = {
    "calculator.py",
    "test_calculator.py",
}


def read_failure_log() -> str:
    """Read the saved pytest failure report."""
    report = Path.home() / "local-ai-rca" / "failure.log"
    return report.read_text()[:12000]


def read_source_file(filename: str) -> str:
    """Read calculator.py or test_calculator.py from the sample project."""
    if filename not in ALLOWED_FILES:
        return "Error: file is not allowed."

    path = PROJECT / filename
    return path.read_text()[:8000]


messages = [{
    "role": "user",
    "content": (
        "Investigate the failing test in the saved pytest report. "
        "Use the tools to inspect the failure and relevant source files. "
        "Identify the likely root cause, cite the relevant code or test, "
        "and recommend a minimal fix. Do not modify any files. "
        "Distinguish confirmed evidence from assumptions."
    ),
}]

for step in range(MAX_STEPS):
    response = chat(
        model=MODEL,
        messages=messages,
        tools=[read_failure_log, read_source_file],
    )

    messages.append(response.message)
    calls = response.message.tool_calls or []

    if not calls:
        print("\n=== RCA REPORT ===\n")
        print(response.message.content)
        break

    for call in calls:
        name = call.function.name
        args = call.function.arguments

        print(f"\n[Agent step {step + 1}] Tool: {name}")
        print("Arguments:", args)

        if name == "read_failure_log":
            result = read_failure_log()
        elif name == "read_source_file":
            result = read_source_file(**args)
        else:
            result = "Error: unknown tool."

        print("Tool result received.")
        messages.append({
            "role": "tool",
            "tool_name": name,
            "content": result,
        })
else:
    print("Stopped: maximum agent steps reached.")
