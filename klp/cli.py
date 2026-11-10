"""`klp`: run one task through KLP Standard from your repository.

    klp init                                   # write your model routes and limits once
    klp run "Fix the pagination bug" --check "python -m pytest -q tests/test_queue.py"

The run works on a private copy of your repository inside a sandbox. Your working tree is not
touched. You get a patch, a receipt, and the decision.

Model routes, API key names, spend limits and sandbox mounts come only from your own config
(~/.config/klp/config.json or --config). A repository's klp.json can declare checks and critical
triggers and nothing else, so a cloned repository cannot redirect your keys or open the sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .llm import Ledger, Model
from .sandbox import Sandbox
from .snapshot import Snapshots
from .standard import Limits, run_standard

USER_CONFIG = {
    "worker": {"name": "deepseek-flash", "family": "deepseek", "base_url": "https://api.deepseek.com",
               "api_key_env": "DEEPSEEK_API_KEY",
               "params": {"max_tokens": 16384, "thinking": {"type": "enabled"}, "reasoning_effort": "high"}},
    "critic": {"name": "gpt-6.1-sol", "family": "openai", "base_url": "https://api.openai.com/v1",
               "api_key_env": "OPENAI_API_KEY",
               # One review is one request, so skip the cache write: plain input price, nothing to reuse.
               "params": {"max_completion_tokens": 16384, "prompt_cache_options": {"mode": "explicit"}}},
    "limits": {"cost_usd": 2.0, "max_steps": 100, "repair_steps": 40, "repair_rounds": 2, "time_seconds": 3600},
    "sandbox": {"read_only_paths": [], "path": "", "network": False},
}
REPO_CONFIG = {"checks": [], "critical_triggers": []}


def repo_root(start: Path) -> Path:
    done = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if done.returncode:
        sys.exit("klp: run this inside a git repository")
    return Path(done.stdout.strip())


def user_config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    if os.environ.get("KLP_CONFIG"):
        return Path(os.environ["KLP_CONFIG"])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "klp" / "config.json"


def load_config(root: Path, explicit: str | None) -> dict:
    """Trusted settings from the user's config; only checks and triggers from the repository."""
    config = json.loads(json.dumps({**USER_CONFIG, **REPO_CONFIG}))
    file = user_config_path(explicit)
    if file.is_file():
        for key, value in json.loads(file.read_text()).items():
            if key in USER_CONFIG:
                config[key] = {**config[key], **value} if isinstance(value, dict) else value
    elif explicit:
        sys.exit(f"klp: config {file} not found")
    repo_file = root / "klp.json"
    if repo_file.is_file():
        declared = json.loads(repo_file.read_text())
        for key in REPO_CONFIG:
            if isinstance(declared.get(key), list) and all(isinstance(item, str) for item in declared[key]):
                config[key] = declared[key]
        ignored = sorted(set(declared) - set(REPO_CONFIG))
        if ignored:
            print(f"note: {repo_file.name} keys ignored ({', '.join(ignored)}); "
                  f"model routes, limits and sandbox settings come from {file}", file=sys.stderr)
    return config


def cmd_init(args) -> int:
    root = repo_root(Path.cwd())
    user_file = user_config_path(args.config)
    if not user_file.exists():
        user_file.parent.mkdir(parents=True, exist_ok=True)
        user_file.write_text(json.dumps(USER_CONFIG, indent=2) + "\n")
        print(f"Wrote {user_file} (model routes, limits, sandbox).")
    repo_file = root / "klp.json"
    if not repo_file.exists():
        repo_file.write_text(json.dumps(REPO_CONFIG, indent=2) + "\n")
        print(f"Wrote {repo_file} (checks and critical triggers for this repository).")
    print(f"Set {USER_CONFIG['worker']['api_key_env']} and {USER_CONFIG['critic']['api_key_env']}, "
          "then: klp run \"<task>\" --check \"<command>\"")
    return 0


def cmd_run(args) -> int:
    root = repo_root(Path.cwd())
    config = load_config(root, args.config)
    task = Path(args.task_file).read_text() if args.task_file else args.task
    if not task:
        sys.exit("klp: give the task as text or with --task-file")
    checks = args.check or config["checks"]
    if not checks:
        sys.exit('klp: declare at least one check, e.g. --check "python -m pytest -q"')
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if dirty:
        print("note: uncommitted changes are not part of the run; it starts from HEAD", file=sys.stderr)
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower())[:40].strip("-") or "task"
    run_dir = root / ".klp" / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"
    (root / ".klp").mkdir(exist_ok=True)
    (root / ".klp" / ".gitignore").write_text("*\n")
    workspace = run_dir / "ws"
    workspace.mkdir(parents=True)
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(root), str(workspace / "repo")], check=True)
    box = config["sandbox"]
    # The copy appears at your repository's own path, so existing virtualenvs and editable installs work.
    sandbox = Sandbox(workspace, ro_binds={p: p for p in box["read_only_paths"]}, rw_binds={str(workspace / "repo"): str(root)},
                      path_prefix=box["path"], network=bool(box["network"]), repo_dir=str(root))
    limits = Limits(**{**config["limits"], **({"cost_usd": args.cap} if args.cap else {})})
    ledger = Ledger(run_dir / "ledger.jsonl", limits.cost_usd)
    worker = Model.from_spec(config["worker"])
    critic = None if args.no_review else Model.from_spec(config["critic"])
    say = (lambda *a, **k: print(*a, file=sys.stderr, **k)) if args.json else print
    say(f"KLP Standard: worker {worker.name} via {worker.base_url}, "
        f"critic {critic.name + ' via ' + critic.base_url if critic else 'none'}, "
        f"limit ${limits.cost_usd:.2f}, {len(checks)} check(s), sandbox network {'on' if box['network'] else 'off'}")
    receipt = run_standard(ledger=ledger, worker=worker, critic=critic, sandbox=sandbox, task=task, checks=checks,
                           scope=slug, limits=limits, out_dir=run_dir, task_id=slug,
                           critical_triggers=config["critical_triggers"], project_revision=head)
    done = receipt["completion"]
    patch = Snapshots(sandbox, run_dir / "snapshots").patch(receipt["base_revision"], done["final_revision"])
    (run_dir / "candidate.patch").write_bytes(patch)
    relative = run_dir.relative_to(root)
    if args.json:
        # One JSON object on stdout for a calling agent; everything else went to stderr.
        print(json.dumps(dict(
            state=done["state"], checks_passed=done["checks_passed"], usd=done["measured_effort"]["usd"],
            seconds=done["measured_effort"]["seconds"], reviews=[r["verdict"] for r in receipt["reviews"]],
            findings_confirmed=sum(f["disposition"] == "confirmed" for r in receipt["reviews"] for f in r["findings"]),
            findings_fixed=sum(p["closed"] for r in receipt["repairs"] for p in r["probes"]),
            unresolved_findings=[dict(id=f["id"], claim=f["claim"], disposition=f["disposition"])
                                 for f in done["unresolved_findings"]],
            receipt=f"{relative}/receipt.json", receipt_text=f"{relative}/receipt.md",
            patch=f"{relative}/candidate.patch", apply=f"git apply {relative}/candidate.patch",
            human_decisions_required=done["human_decisions_required"])))
    else:
        print((run_dir / "receipt.md").read_text())
        print(f"Receipt:  {relative}/receipt.md\nPatch:    {relative}/candidate.patch\n"
              f"Apply it: git apply {relative}/candidate.patch")
    return 0 if done["state"] == "completed" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="klp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="write your config and this repository's klp.json")
    init.add_argument("--config", help="path for your user config")
    init.set_defaults(run=cmd_init)
    run = commands.add_parser("run", help="run one task through KLP Standard")
    run.add_argument("task", nargs="?", help="what should change")
    run.add_argument("--task-file", help="read the task from a file")
    run.add_argument("--check", action="append", help="command that must pass; repeatable")
    run.add_argument("--cap", type=float, help="cost limit in USD for this run")
    run.add_argument("--config", help="path to your user config (default ~/.config/klp/config.json)")
    run.add_argument("--no-review", action="store_true", help="worker only, for comparison")
    run.add_argument("--json", action="store_true", help="print one JSON result object on stdout (for calling agents)")
    run.set_defaults(run=cmd_run)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
