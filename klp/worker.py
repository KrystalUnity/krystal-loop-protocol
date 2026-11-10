"""The built-in worker: a model with one tool, a shell inside the sandbox."""
from __future__ import annotations

import json

from .llm import Ledger, Model, clean_message
from .sandbox import Sandbox

BASH_TOOL = [{"type": "function", "function": {
    "name": "bash",
    "description": "Run a shell command in the repository sandbox and return its exit code and output.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
}}]

SYSTEM = """You are a software engineer working in a git repository at {repo}.
Use the bash tool to read code, edit files and run tests. There is no network access.
Stay inside the task: change only what it needs, keep existing behaviour working, and do not
edit or delete existing tests to make them pass.
When the work is complete, reply WITHOUT a tool call and give a short factual handover:
what you changed, which commands you ran, and their actual results. Do not claim checks you did not run."""


def run_worker(ledger: Ledger, model: Model, sandbox: Sandbox, prompt: str, *, scope: str, max_steps: int,
               command_timeout: float = 180, messages: list | None = None, role: str = "worker") -> dict:
    """Drive the model until it hands over or runs out of steps. `messages` continues an earlier session."""
    history = list(messages) if messages else [{"role": "system", "content": SYSTEM.format(repo=sandbox.repo_dir)}]
    history.append({"role": "user", "content": prompt})
    steps, commands, handover = 0, [], None
    while steps < max_steps:
        steps += 1
        reply = ledger.chat(model, history, role=role, scope=scope, tools=BASH_TOOL)
        history.append(clean_message(reply))
        calls = reply.get("tool_calls") or []
        if not calls:
            handover = (reply.get("content") or "").strip()
            if handover or reply.get("_finish_reason") != "length":
                break
            history.append({"role": "user", "content": "Your reply was cut off. Continue with a tool call or the handover."})
            continue
        for call in calls:
            try:
                command = json.loads(call["function"]["arguments"])["command"]
                result = sandbox.run(command, timeout=command_timeout)
            except (KeyError, TypeError, ValueError) as error:
                command, result = None, dict(returncode=None, timed_out=False, output=f"invalid tool call: {error}")
            commands.append(dict(command=command, returncode=result["returncode"], timed_out=result["timed_out"]))
            history.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": json.dumps(result)})
    return dict(messages=history, steps=steps, commands=commands, handover=handover, finished=handover is not None)
