"""Runner-owned snapshots of the working tree.

The worker can change anything inside the repository, including its `.git` directory and git
configuration. So the runner keeps its own record somewhere the worker's sandbox never mounts:
a separate git directory with the runner's configuration. Every candidate, the diff the critic
reviews and the patch you apply all come from that record. External diff drivers, text
converters, filters, replace refs and hooks configured by the worker have no effect on it, and
files are always diffed as text so an attribute cannot hide a change from review.

A snapshot holds what git would track: tracked files plus new files that the project's ignore
rules do not exclude. Ignored files (caches, build output, installed dependencies) are outside
review and are never part of the delivered patch.
"""
from __future__ import annotations

import copy
import shutil
from pathlib import Path

from .sandbox import Sandbox

STORE = "/klp-snapshots"
SYSTEM_PATH = "/usr/bin:/bin"
# For repositories the runner created itself and the worker never touched.
GIT_SAFE = ("git --no-pager --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false "
            "-c user.name=klp -c user.email=klp@localhost -c commit.gpgsign=false")
DIFF = "diff --no-color --no-ext-diff --no-textconv --text"


class Snapshots:
    def __init__(self, sandbox: Sandbox, store: Path):
        store = Path(store)
        fresh = not (store / "git").exists()
        store.mkdir(parents=True, exist_ok=True)
        git = shutil.which("git", path=SYSTEM_PATH)
        if not git:
            raise RuntimeError("git must be installed under /usr/bin or /bin")
        self.box = copy.copy(sandbox)  # same sandbox, plus the store; used only for the runner's own commands
        self.box.rw_binds = {**sandbox.rw_binds, str(store.resolve()): STORE}
        # The runner's git is the system binary on a system-only PATH, so nothing the worker can
        # write (a virtualenv, a tools directory in the repository) is ever executed for a snapshot.
        self.box.env = {**sandbox.env, "PATH": SYSTEM_PATH}
        self.git = (f"{git}{GIT_SAFE.removeprefix('git')} -c core.attributesFile=/dev/null -c gc.auto=0 "
                    f"--git-dir={STORE}/git --work-tree={sandbox.repo_dir}")
        if fresh:
            self._run(f"{git} init -q --bare {STORE}/git")

    def _run(self, command: str, **kwargs) -> dict:
        done = self.box.run(command, **{"limit": 600, "timeout": 300, **kwargs})
        if done["returncode"] != 0:
            raise RuntimeError(f"snapshot command failed: {command[:80]}: {done['output'][-300:]}")
        return done

    def take(self, label: str) -> str:
        """Record the working tree as it is now and return its identifier."""
        self._run(f"{self.git} add -A && {self.git} commit -q --allow-empty -m 'klp {label}'")
        return self._run(f"{self.git} rev-parse HEAD")["output"].strip()

    def restore(self, revision: str) -> None:
        """Put the working tree back exactly as it was at `revision`."""
        self._run(f"{self.git} reset -q --hard {revision} && {self.git} clean -fdq")

    def diff(self, base: str, head: str, flags: str = "") -> str:
        return self._run(f"{self.git} {DIFF} {flags} {base} {head}", limit=None)["output"]

    def patch(self, base: str, head: str) -> bytes:
        """The exact bytes to hand to `git apply`."""
        return self._run(f"{self.git} {DIFF} --binary {base} {head}", limit=None)["raw"]
