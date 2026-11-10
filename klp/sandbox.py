"""Run worker commands, checks and probes inside a bubblewrap sandbox.

The sandbox sees the workspace, the system toolchain and any read-only paths
you name. It does not see your home directory, environment variables or
credentials, and has no network unless you ask for it.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

SYSTEM_DIRS = ("/usr", "/etc/alternatives", "/etc/ssl", "/etc/ca-certificates", "/etc/mime.types")
PASSWD = "root:x:0:0:root:/root:/bin/sh\nklp:x:65534:65534:klp:/tmp:/bin/sh\n"
GROUP = "root:x:0:\nklp:x:65534:\n"


class SandboxUnavailable(RuntimeError):
    pass


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    return text[:head] + f"\n... [{len(text) - limit} characters omitted] ...\n" + text[-(limit - head):]


class Sandbox:
    """`workspace` on the host is mounted read-write at /workspace."""

    def __init__(self, workspace: Path, *, ro_binds: dict[str, str] | None = None,
                 rw_binds: dict[str, str] | None = None, path_prefix: str = "",
                 env: dict[str, str] | None = None, network: bool = False, repo_dir: str = "/workspace/repo"):
        self.bwrap = shutil.which("bwrap")
        if not self.bwrap:
            raise SandboxUnavailable("bubblewrap (bwrap) is required: apt install bubblewrap")
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.ro_binds = dict(ro_binds or {})
        self.rw_binds = dict(rw_binds or {})
        self.network = network
        self.repo_dir = repo_dir  # where the repository appears inside the sandbox
        self.env = {"PATH": (path_prefix + ":" if path_prefix else "") + "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "GIT_PAGER": "cat",
                    "PAGER": "cat", "TERM": "dumb", **(env or {})}
        ident = self.workspace / ".klp-etc"
        ident.mkdir(exist_ok=True)
        (ident / "passwd").write_text(PASSWD)
        (ident / "group").write_text(GROUP)

    def argv(self, command: str, cwd: str) -> list[str]:
        args = [self.bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--uid", "65534", "--gid", "65534"]
        if self.network:
            args += ["--share-net", "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"]
        for path in SYSTEM_DIRS:
            if os.path.exists(path):
                args += ["--ro-bind", path, path]
        for link in ("bin", "sbin", "lib", "lib64"):
            if os.path.islink("/" + link):
                args += ["--symlink", "usr/" + link, "/" + link]
            elif os.path.exists("/" + link):
                args += ["--ro-bind", "/" + link, "/" + link]
        args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(self.workspace), "/workspace",
                 "--ro-bind", str(self.workspace / ".klp-etc/passwd"), "/etc/passwd",
                 "--ro-bind", str(self.workspace / ".klp-etc/group"), "/etc/group"]
        for host, inside in self.ro_binds.items():
            args += ["--ro-bind", host, inside]
        for host, inside in self.rw_binds.items():
            args += ["--bind", host, inside]
        args += ["--clearenv"]
        for name, value in self.env.items():
            args += ["--setenv", name, value]
        return args + ["--chdir", cwd, "/bin/bash", "-c", command]

    def run(self, command: str, *, timeout: float = 120, cwd: str | None = None, limit: int = 8000) -> dict:
        process = subprocess.Popen(self.argv(command, cwd or self.repo_dir), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            raw, _ = process.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raw, _ = process.communicate()
            timed_out = True
        output = raw.decode("utf-8", "replace")
        return dict(returncode=None if timed_out else process.returncode, timed_out=timed_out,
                    output=clip(output, limit) + (f"\n[timed out after {timeout:.0f}s]" if timed_out else ""))


def git(repo: Path, *args: str, check: bool = True, stdin: str | None = None) -> str:
    """Host-side git on a repository the runner owns. Never run on untrusted hooks: hooks are disabled."""
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=klp", "-c",
                             "user.email=klp@localhost", "-c", "commit.gpgsign=false", "-c", "safe.directory=*",
                             "-C", str(repo), *args], input=stdin, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {result.stderr.strip()[:400]}")
    return result.stdout
