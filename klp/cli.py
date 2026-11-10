"""`klp`: run one task through KLP Standard from your repository.

    klp init                                   # write klp.json with model routes and limits
    klp run "Fix the pagination bug" --check "python -m pytest -q tests/test_queue.py"

The run works on a private copy of your repository inside a sandbox. Your working tree is not
touched. You get a patch, a receipt, and the decision.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .llm import Ledger, Model
from .review import GIT
from .sandbox import Sandbox
from .standard import Limits, run_standard

DEFAULT_CONFIG = {
    "worker": {"name": "deepseek-flash", "family": "deepseek", "base_url": "https://api.deepseek.com",
               "api_key_env": "DEEPSEEK_API_KEY",
               "params": {"max_tokens": 16384, "thinking": {"type": "enabled"}, "reasoning_effort": "high"}},
    "critic": {"name": "gpt-6.1-sol", "family": "openai", "base_url": "https://api.openai.com/v1",
               "api_key_env": "OPENAI_API_KEY", "params": {"max_completion_tokens": 16384}},
    "limits": {"cost_usd": 2.0, "max_steps": 40, "repair_steps": 20, "repair_rounds": 1, "time_seconds": 3600},
    "sandbox": {"read_only_paths": [], "path": "", "network": False},
    "checks": [],
    "critical_triggers": [],
}


def repo_root(start: Path) -> Path:
    done = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if done.returncode:
        sys.exit("klp: run this inside a git repository")
    return Path(done.stdout.strip())


def load_config(root: Path, path: str | None) -> dict:
    file = Path(path) if path else root / "klp.json"
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if file.exists():
        for key, value in json.loads(file.read_text()).items():
            config[key] = {**config[key], **value} if isinstance(config.get(key), dict) and isinstance(value, dict) else value
    elif path:
        sys.exit(f"klp: config {file} not found")
    return config


def cmd_init(args) -> int:
    root = repo_root(Path.cwd())
    target = root / "klp.json"
    if target.exists():
        print(f"{target} already exists")
        return 1
    target.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
    print(f"Wrote {target}. Set {DEFAULT_CONFIG['worker']['api_key_env']} and {DEFAULT_CONFIG['critic']['api_key_env']}, "
          "add your check commands, then: klp run \"<task>\"")
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
    print(f"KLP Standard: worker {worker.name}, critic {critic.name if critic else 'none'}, "
          f"limit ${limits.cost_usd:.2f}, {len(checks)} check(s)")
    receipt = run_standard(ledger=ledger, worker=worker, critic=critic, sandbox=sandbox, task=task, checks=checks,
                           scope=slug, limits=limits, out_dir=run_dir, task_id=slug,
                           critical_triggers=config["critical_triggers"])
    done = receipt["completion"]
    sandbox.run(f"{GIT} diff --binary {receipt['base_revision']} {done['final_revision']} > /workspace/candidate.patch", limit=200)
    shutil.copy(workspace / "candidate.patch", run_dir / "candidate.patch")
    print((run_dir / "receipt.md").read_text())
    relative = run_dir.relative_to(root)
    print(f"Receipt:  {relative}/receipt.md\nPatch:    {relative}/candidate.patch\n"
          f"Apply it: git apply {relative}/candidate.patch")
    return 0 if done["state"] == "completed" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="klp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="write klp.json").set_defaults(run=cmd_init)
    run = commands.add_parser("run", help="run one task through KLP Standard")
    run.add_argument("task", nargs="?", help="what should change")
    run.add_argument("--task-file", help="read the task from a file")
    run.add_argument("--check", action="append", help="command that must pass; repeatable")
    run.add_argument("--cap", type=float, help="cost limit in USD for this run")
    run.add_argument("--config", help="path to klp.json")
    run.add_argument("--no-review", action="store_true", help="worker only, for comparison")
    run.set_defaults(run=cmd_run)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
