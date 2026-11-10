"""Run worker commands, checks and probes inside a bubblewrap sandbox.

The sandbox sees the workspace, the system toolchain and any read-only paths
you name. It does not see your home directory, environment variables or
credentials, and has no network unless you ask for it.
"""
from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

SYSTEM_DIRS = ("/usr", "/etc/alternatives", "/etc/ssl", "/etc/ca-certificates", "/etc/mime.types")
PASSWD = "root:x:0:0:root:/root:/bin/sh\nklp:x:65534:65534:klp:/tmp:/bin/sh\n"
GROUP = "root:x:0:\nklp:x:65534:\n"


class SandboxUnavailable(RuntimeError):
    pass


_IDENTITY: Path | None = None


def identity_dir() -> Path:
    """passwd and group files for the sandbox, kept where sandboxed code cannot write."""
    global _IDENTITY
    if _IDENTITY is None:
        _IDENTITY = Path(tempfile.mkdtemp(prefix="klp-etc-"))
        (_IDENTITY / "passwd").write_text(PASSWD)
        (_IDENTITY / "group").write_text(GROUP)
    return _IDENTITY


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
                 "--ro-bind", str(identity_dir() / "passwd"), "/etc/passwd",
                 "--ro-bind", str(identity_dir() / "group"), "/etc/group"]
        for host, inside in self.ro_binds.items():
            args += ["--ro-bind", host, inside]
        for host, inside in self.rw_binds.items():
            args += ["--bind", host, inside]
        args += ["--clearenv"]
        for name, value in self.env.items():
            args += ["--setenv", name, value]
        return args + ["--chdir", cwd, "/bin/bash", "-c", command]

    def run(self, command: str, *, timeout: float = 120, cwd: str | None = None, limit: int | None = 8000,
            stdin: str | None = None) -> dict:
        """Run one shell command inside the sandbox. `limit=None` returns the whole output.

        The host never opens files the sandbox can write: results come back on stdout and
        files go in through stdin, so a symlink planted in the workspace cannot redirect either.
        """
        process = subprocess.Popen(self.argv(command, cwd or self.repo_dir),
                                   stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            raw, _ = process.communicate(input=None if stdin is None else stdin.encode(), timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raw, _ = process.communicate()
            timed_out = True
        output = raw.decode("utf-8", "replace")
        result = dict(returncode=None if timed_out else process.returncode, timed_out=timed_out,
                      output=(output if limit is None else clip(output, limit))
                      + (f"\n[timed out after {timeout:.0f}s]" if timed_out else ""))
        if limit is None:
            result["raw"] = raw  # exact bytes, for patches
        return result

    def write_file(self, inside_path: str, content: str) -> None:
        """Create a file from inside the sandbox, so its path is resolved there and nowhere else."""
        folder, target = shlex.quote(os.path.dirname(inside_path)), shlex.quote(inside_path)
        # Replace anything that is not a real directory (a planted link, a file) before writing.
        done = self.run(f"if [ -L {folder} ] || [ ! -d {folder} ]; then rm -rf -- {folder}; fi; "
                        f"mkdir -p -- {folder} && rm -f -- {target} && cat > {target}",
                        stdin=content, cwd="/workspace", limit=400)
        if done["returncode"] != 0:
            raise RuntimeError(f"could not write {inside_path} in the sandbox: {done['output']}")
