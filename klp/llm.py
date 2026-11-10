"""OpenAI-compatible chat client with a spend ledger and a hard budget cap.

Standard library only. Every call is written to the ledger before the next one
is allowed, so a run can never drift past its cost limit unnoticed.

A route is an HTTP endpoint ("chat" or "responses") or a local command: an agent
CLI on a subscription you already hold. Command routes are recorded as unmetered,
because the runner cannot see what a subscription charges.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from decimal import Decimal as D
from pathlib import Path

PRICES_PATH = Path(__file__).with_name("prices.json")


class BudgetExceeded(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Model:
    """One model route. `family` is what the independence rule compares."""

    name: str
    base_url: str
    api_key_env: str
    family: str
    params: dict = field(default_factory=dict)
    api: str = "chat"  # "chat" = /chat/completions, "responses" = OpenAI /responses, "command" = a local CLI
    command: tuple = ()  # argv for a command route; "{prompt}" is replaced, otherwise the prompt goes to stdin
    reply: str = "text"  # where the answer is in the command's output: "text", "json:<field>" or "ndjson:<field>"

    @classmethod
    def from_spec(cls, spec: dict) -> "Model":
        return cls(spec["name"], spec.get("base_url", "").rstrip("/"), spec.get("api_key_env", ""),
                   spec.get("family") or spec["name"].split("-")[0], dict(spec.get("params", {})),
                   spec.get("api", "chat"), tuple(spec.get("command", ())), spec.get("reply", "text"))

    @property
    def route(self) -> str:
        return f"local command {self.command[0]}" if self.api == "command" else self.base_url


def load_prices(path: Path | None = None) -> dict:
    return json.loads((path or PRICES_PATH).read_text())["usd_per_million_tokens"]


def read_usage(raw: dict) -> dict:
    """Normalise provider usage. Cached and cache-write tokens are subsets of input."""
    details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
    prompt, output = raw.get("prompt_tokens", raw.get("input_tokens")), raw.get("completion_tokens", raw.get("output_tokens"))
    if all(type(v) is int for v in (prompt, output, raw.get("total_tokens"))):
        # Some providers leave reasoning tokens out of the completion count and bill them all the same.
        output = max(output, raw["total_tokens"] - prompt)
    usage = dict(
        input=prompt,
        output=output,
        cached=details.get("cached_tokens", raw.get("prompt_cache_hit_tokens", 0)) or 0,
        write=details.get("cache_write_tokens", details.get("cache_creation_tokens", 0)) or 0,
    )
    if any(type(v) is not int or v < 0 for v in usage.values()) or usage["cached"] + usage["write"] > usage["input"]:
        raise ProviderError("missing or inconsistent provider usage")
    return usage


RATE_KEYS = ("input", "cached", "write", "output")


def rates_at(entry: dict | None, when: float) -> tuple[dict | None, str]:
    """The rates in force at `when`. A provider with off-peak pricing lists both tiers and its peak hours."""
    if entry is None:
        return None, "standard"
    peak = entry.get("peak_utc")
    if peak and "off_peak" in entry:
        now = time.gmtime(when)
        if not (now.tm_wday in peak["days"] and any(start <= now.tm_hour < end for start, end in peak["hours"])):
            return entry["off_peak"], "off_peak"
    return entry, "standard"


def price(usage: dict, rates: dict | None) -> D | None:
    """USD for one call, or None when the model has no entry in prices.json."""
    if rates is None:
        return None
    r = {k: D(str(rates[k])) for k in RATE_KEYS if k in rates}
    fresh = usage["input"] - usage["cached"] - usage["write"]
    return (D(fresh) * r["input"] + D(usage["cached"]) * r.get("cached", r["input"])
            + D(usage["write"]) * r.get("write", r["input"]) + D(usage["output"]) * r["output"]) / D(1_000_000)


class Ledger:
    """Append-only record of every model call, with a spend cap shared by all threads."""

    def __init__(self, path: Path, cap_usd: float, *, prices: dict | None = None, transport=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap = D(str(cap_usd))
        self.prices = load_prices() if prices is None else prices
        self.transport = transport or _http_post
        self.command_runner = _run_command
        self.lock = threading.Lock()
        self.scope_caps: dict[str, D] = {}
        self.rows =[json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []

    def spent(self, **match) -> D:
        return sum((D(r["usd"]) for r in self.rows if r.get("usd") is not None
                    and all(r.get(k) == v for k, v in match.items())), D(0))

    def summary(self, **match) -> dict:
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in match.items())]
        out: dict = {}
        for r in rows:
            s = out.setdefault(r["role"], dict(calls=0, input=0, cached=0, write=0, output=0, usd=D(0), unpriced_calls=0,
                                               unmetered_calls=0))
            s["calls"] += 1
            s["unmetered_calls"] += r.get("metered") is False
            for k in ("input", "cached", "write", "output"):
                s[k] += (r.get("usage") or {}).get(k, 0)
            if r.get("usd") is None:
                s["unpriced_calls"] += 1
            else:
                s["usd"] += D(r["usd"])
        return {role: {**s, "usd": str(s["usd"])} for role, s in out.items()}

    def chat(self, model: Model, messages: list, *, role: str, scope: str = "", tools: list | None = None,
             extra: dict | None = None, timeout: float = 300) -> dict:
        """One chat completion. Returns the assistant message with `_usage` and `_usd` attached."""
        with self.lock:
            if self.spent() >= self.cap:
                raise BudgetExceeded(f"cost limit ${self.cap} reached; no further model calls")
            scope_cap = self.scope_caps.get(scope)
            if scope_cap is not None and self.spent(scope=scope) >= scope_cap:
                raise BudgetExceeded(f"task cost limit ${scope_cap} reached")
        if model.api == "command":
            return self._command(model, messages, role, scope, timeout)
        key = os.environ.get(model.api_key_env)
        if not key:
            raise ProviderError(f"{model.api_key_env} is not set")
        if model.api == "responses":
            path, body = "/responses", responses_request(model, messages, tools, extra)
        else:
            path = "/chat/completions"
            public = [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]
            body = {"model": model.name, "messages": public, **model.params, **(extra or {})}
            if tools:
                body["tools"] = tools
        last_error: Exception | None = None
        for attempt in range(2):  # one retry, and only when the transport itself failed
            row = dict(id=uuid.uuid4().hex, scope=scope, role=role, model=model.name, started=time.time(), status="sent")
            try:
                status, raw = self.transport(model.base_url + path, key, body, timeout)
                row["http_status"] = status
                if status != 200:
                    raise ProviderError(f"{model.name} HTTP {status}: {raw[:300]!r}")
                answer = json.loads(raw)
                usage = read_usage(answer.get("usage") or {})
                rates, row["tier"] = rates_at(self.prices.get(model.name), row["started"])
                usd = price(usage, rates)
                if model.api == "responses":
                    message, finish = responses_message(answer)
                else:
                    choice = answer["choices"][0]
                    message, finish = dict(choice["message"]), choice.get("finish_reason")
                row.update(status="completed", usage=usage, usd=None if usd is None else str(usd),
                           finish_reason=finish, returned_model=answer.get("model"))
                message["_usage"], message["_usd"], message["_finish_reason"] = usage, usd, finish
                return message
            except ProviderError as exc:
                row.update(status="failed", error=str(exc)[:300])
                raise
            except Exception as exc:  # connection reset, timeout, truncated body: billing unknown, recorded unpriced
                row.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:300])
                last_error = exc
            finally:
                self._record(row)
        raise ProviderError(f"{model.name} transport failed twice: {last_error}")

    def _record(self, row: dict) -> None:
        row["seconds"] = round(time.time() - row["started"], 2)
        with self.lock:
            self.rows.append(row)
            with self.path.open("a") as stream:
                stream.write(json.dumps(row) + "\n")

    def _command(self, model: Model, messages: list, role: str, scope: str, timeout: float) -> dict:
        """One answer from a local CLI. Recorded with zero metered cost and `metered: false`."""
        prompt = "\n\n".join(m["content"] for m in messages if m.get("content"))
        row = dict(id=uuid.uuid4().hex, scope=scope, role=role, model=model.name, started=time.time(), status="sent",
                   metered=False)
        try:
            content = reply_from(self.command_runner(model, prompt, max(timeout, 900)), model.reply)
            usage = dict(input=0, output=0, cached=0, write=0)
            row.update(status="completed", usage=usage, usd="0", finish_reason="stop", returned_model=model.name)
            return {"role": "assistant", "content": content, "_usage": usage, "_usd": D(0), "_finish_reason": "stop"}
        except ProviderError as exc:
            row.update(status="failed", error=str(exc)[:300])
            raise
        finally:
            self._record(row)


COMMAND_PROMPT_LIMIT = 120_000  # one argv string; Linux allows 128 KiB


def _run_command(model: Model, prompt: str, timeout: float) -> str:
    """Run the CLI in an empty directory, so an agentic tool starts with nothing to read or change."""
    in_argv = any("{prompt}" in part for part in model.command)
    if in_argv and len(prompt.encode()) > COMMAND_PROMPT_LIMIT:
        raise ProviderError(f"{model.name}: prompt too large for a command argument")
    argv = [part.replace("{prompt}", prompt) for part in model.command]
    with tempfile.TemporaryDirectory(prefix="klp-command-") as empty:
        try:
            done = subprocess.run(argv, input=None if in_argv else prompt, capture_output=True, text=True,
                                  timeout=timeout, cwd=empty, stdin=subprocess.DEVNULL if in_argv else None)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProviderError(f"{model.name} command failed: {type(error).__name__}") from None
    if done.returncode:
        raise ProviderError(f"{model.name} command exit {done.returncode}: {(done.stderr or done.stdout)[-300:]!r}")
    return done.stdout


def reply_from(stdout: str, how: str) -> str:
    """The model's answer inside a CLI's output, with one surrounding code fence removed."""
    kind, _, name = how.partition(":")
    try:
        if kind == "json":
            text = json.loads(stdout)[name]
        elif kind == "ndjson":
            lines = [json.loads(line) for line in stdout.splitlines() if line.lstrip().startswith("{")]
            text = [line[name] for line in lines if line.get("role") == "assistant" and isinstance(line.get(name), str)][-1]
        else:
            text = stdout
        text = text.strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("command output did not contain a reply") from None
    fence = re.fullmatch(r"```[A-Za-z]*\n(.*)\n```", text, re.S)
    return fence.group(1) if fence else text


def _http_post(url: str, key: str, body: dict, timeout: float, _attempts: int = 2):
    data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "klp-runner"})
    for attempt in range(_attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            text = error.read().decode("utf-8", "replace")
            # Rate limits and server errors are not billed; one retry, then stop.
            if error.code in (429, 500, 502, 503, 529) and attempt + 1 < _attempts:
                time.sleep(5)
                continue
            return error.code, text
    raise ProviderError("unreachable")


def responses_request(model: Model, messages: list, tools: list | None, extra: dict | None) -> dict:
    """Translate chat-style history into a stateless /responses request."""
    items, instructions = [], []
    for m in messages:
        if m["role"] == "system":
            instructions.append(m["content"])
        elif m["role"] == "user":
            items.append({"role": "user", "content": m["content"]})
        elif m["role"] == "tool":
            items.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": m["content"]})
        elif m.get("_items"):
            items.extend(m["_items"])  # reasoning, function calls and text exactly as the model produced them
        elif m.get("content"):
            items.append({"role": "assistant", "content": m["content"]})
    body = {"model": model.name, "input": items, "store": False, "include": ["reasoning.encrypted_content"],
            **model.params, **(extra or {})}
    if instructions:
        body["instructions"] = "\n\n".join(instructions)
    if tools:
        body["tools"] = [{"type": "function", **t["function"]} for t in tools]
    return body


def responses_message(answer: dict) -> tuple[dict, str]:
    """Turn a /responses answer into the chat-style assistant message the worker loop expects."""
    output = answer.get("output") or []
    text = "".join(part.get("text", "") for item in output if item.get("type") == "message"
                   for part in item.get("content", []) if part.get("type") == "output_text")
    calls = [{"id": item["call_id"], "type": "function",
              "function": {"name": item["name"], "arguments": item.get("arguments") or "{}"}}
             for item in output if item.get("type") == "function_call"]
    message = {"role": "assistant", "content": text, "_items": output}
    if calls:
        message["tool_calls"] = calls
    if answer.get("status") == "incomplete":
        finish = "length"
    else:
        finish = "tool_calls" if calls else "stop"
    return message, finish


def clean_message(message: dict) -> dict:
    """Assistant message as it must be replayed in history (no private bookkeeping)."""
    keep = {k: message[k] for k in ("role", "content", "tool_calls", "reasoning_content", "_items")
            if message.get(k) is not None}
    keep.setdefault("role", "assistant")
    keep.setdefault("content", "")
    return keep
