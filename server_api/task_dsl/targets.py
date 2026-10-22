"""Where compiled task scripts run: a Slurm cluster over SSH, or this laptop."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from .compiler import REPO_ROOT, Plan

STATE_DIR = Path(os.environ.get("PYTC_DSL_STATE_DIR", Path.home() / ".pytc_task_dsl"))


class TargetError(RuntimeError):
    pass


class ClusterTarget:
    """Configured with environment variables, for example::

    PYTC_DSL_CLUSTER_HOST=user@login.cluster.edu
    PYTC_DSL_CLUSTER_ROOT=/projects/lab/user/dsl-demo
    PYTC_DSL_CLUSTER_PYTHON=/home/user/.conda/envs/pytc/bin/python
    """

    name = "cluster"

    def __init__(self) -> None:
        self.host = os.environ.get("PYTC_DSL_CLUSTER_HOST", "")
        self.root = os.environ.get("PYTC_DSL_CLUSTER_ROOT", "").rstrip("/")
        self.python = os.environ.get("PYTC_DSL_CLUSTER_PYTHON", "python3")
        self.pytc = os.environ.get("PYTC_DSL_CLUSTER_PYTC", f"{self.root}/pytorch_connectomics")
        self.partition = os.environ.get("PYTC_DSL_CLUSTER_PARTITION", "short")
        self.minutes = int(os.environ.get("PYTC_DSL_CLUSTER_MINUTES", "30"))
        self._exists_cache: dict[str, tuple[float, bool]] = {}

    @property
    def configured(self) -> bool:
        return bool(self.host and self.root)

    def _ssh(self, command: str, stdin: Optional[str] = None, timeout: int = 40) -> str:
        if not self.configured:
            raise TargetError("The cluster is not set up. Set PYTC_DSL_CLUSTER_HOST and PYTC_DSL_CLUSTER_ROOT.")
        control = STATE_DIR / "ssh-%r@%h-%p"
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        args = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "ControlMaster=auto", "-o", f"ControlPath={control}", "-o", "ControlPersist=15m",
            self.host, command,
        ]
        try:
            done = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise TargetError("The cluster did not answer in time.") from exc
        if done.returncode == 255:
            raise TargetError(f"Could not connect to {self.host}: {done.stderr.strip()[:200]}")
        if done.returncode != 0:
            raise TargetError(done.stderr.strip()[:400] or f"Command failed with exit code {done.returncode}.")
        return done.stdout

    def exists(self, paths: list[str]) -> dict[str, bool]:
        now = time.time()
        wanted = [p for p in dict.fromkeys(paths) if not (p in self._exists_cache and now - self._exists_cache[p][0] < 20)]
        if wanted:
            script = "; ".join(f"[ -e {shlex.quote(p)} ] && echo 1 || echo 0" for p in wanted)
            answers = self._ssh(script).split()
            for path, answer in zip(wanted, answers):
                self._exists_cache[path] = (now, answer == "1")
        return {p: self._exists_cache[p][1] for p in paths if p in self._exists_cache}

    def list_files(self, folder: str, limit: int = 60) -> list[str]:
        out = self._ssh(
            f"find {shlex.quote(folder)} -maxdepth 4 -type f \\( -name '*.h5' -o -name '*.hdf5' -o -name '*.tif' "
            f"-o -name '*.tiff' -o -name '*.pth.tar' -o -name '*.yaml' \\) 2>/dev/null | head -n {limit}"
        )
        return [line for line in out.splitlines() if line.strip()]

    def submit(self, plan: Plan, job_id: str) -> dict[str, Any]:
        job_dir = f"{self.root}/jobs/{job_id}"
        command = plan.command.format(python=shlex.quote(self.python), pytc=shlex.quote(self.pytc))
        gpu = "#SBATCH -G 1\n" if plan.needs_gpu else ""
        run_sh = (
            "#!/bin/bash\n"
            f"#SBATCH -J pytc-{plan.verb}\n#SBATCH -p {self.partition}\n{gpu}"
            f"#SBATCH -t {self.minutes}\n#SBATCH --mem=16g\n#SBATCH -c 4\n#SBATCH -o {job_dir}/out.log\n"
            f"cd {shlex.quote(job_dir)}\n"
            f"export PYTHONPATH={shlex.quote(self.pytc)}:$PYTHONPATH\n"
            "echo \"[task-script] started on $(hostname) at $(date)\"\n"
            f"{command}\n"
            "code=$?\necho \"[task-script] finished with exit code $code\"\nexit $code\n"
        )
        files = dict(plan.files, **{"run.sh": run_sh})
        self._ssh(f"mkdir -p {shlex.quote(job_dir)}")
        for name, text in files.items():
            self._ssh(f"cat > {shlex.quote(job_dir + '/' + name)}", stdin=text)
        for folder in {v for k, v in plan.outputs.items() if k == "folder"}:
            self._ssh(f"mkdir -p {shlex.quote(folder)}")
        slurm_id = self._ssh(f"cd {shlex.quote(job_dir)} && sbatch --parsable run.sh").strip().split(";")[0]
        return {"job_dir": job_dir, "slurm_id": slurm_id}

    def status(self, handle: dict[str, Any]) -> dict[str, Any]:
        sid, job_dir = handle["slurm_id"], handle["job_dir"]
        out = self._ssh(
            f"squeue -h -j {sid} -o %T 2>/dev/null; echo ===; "
            f"sacct -n -X -P -j {sid} -o State 2>/dev/null | head -1; echo ===; "
            f"tail -n 60 {shlex.quote(job_dir)}/out.log 2>/dev/null; echo ===; "
            f"cat {shlex.quote(job_dir)}/metrics.json 2>/dev/null; true"
        )
        queue, acct, log, metrics = (out.split("===\n") + ["", "", "", ""])[:4]
        state = (queue.strip() or acct.strip() or "PENDING").split()[0]
        return {"state": _normalize_state(state), "raw_state": state, "log": log, "metrics": metrics.strip()}

    def cancel(self, handle: dict[str, Any]) -> None:
        self._ssh(f"scancel {handle['slurm_id']}")

    def fetch(self, paths: list[str]) -> list[str]:
        cache = STATE_DIR / "fetched"
        cache.mkdir(parents=True, exist_ok=True)
        local = []
        for path in paths:
            dest = cache / path.lstrip("/").replace("/", "__")
            if not dest.exists():
                done = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{self.host}:{path}", str(dest)],
                                      capture_output=True, text=True, timeout=180)
                if done.returncode != 0:
                    raise TargetError(f"Could not copy {path}: {done.stderr.strip()[:200]}")
            local.append(str(dest))
        return local


class LaptopTarget:
    name = "laptop"

    def __init__(self) -> None:
        self.python = os.environ.get("PYTC_DSL_LAPTOP_PYTHON", sys.executable)
        self.pytc = os.environ.get("PYTC_DSL_LAPTOP_PYTC", str(REPO_ROOT / "pytorch_connectomics"))
        self._procs: dict[str, subprocess.Popen] = {}

    configured = True

    def exists(self, paths: list[str]) -> dict[str, bool]:
        return {p: Path(os.path.expanduser(p)).exists() for p in paths}

    def list_files(self, folder: str, limit: int = 60) -> list[str]:
        root = Path(os.path.expanduser(folder))
        found = []
        for pattern in ("*.h5", "*.hdf5", "*.tif", "*.tiff", "*.pth.tar", "*.yaml"):
            found.extend(str(p) for p in root.rglob(pattern))
        return sorted(found)[:limit]

    def submit(self, plan: Plan, job_id: str) -> dict[str, Any]:
        job_dir = STATE_DIR / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        for name, text in plan.files.items():
            (job_dir / name).write_text(text)
        for folder in {v for k, v in plan.outputs.items() if k == "folder"}:
            Path(folder).mkdir(parents=True, exist_ok=True)
        command = plan.command.format(python=shlex.quote(self.python), pytc=shlex.quote(self.pytc))
        env = dict(os.environ, PYTHONPATH=f"{self.pytc}:{os.environ.get('PYTHONPATH', '')}")
        log = open(job_dir / "out.log", "w")
        log.write(f"[task-script] started on this laptop at {time.ctime()}\n")
        log.flush()
        proc = subprocess.Popen(command, shell=True, cwd=job_dir, stdout=log, stderr=subprocess.STDOUT, env=env)
        self._procs[job_id] = proc
        return {"job_dir": str(job_dir), "pid": proc.pid, "job_id": job_id}

    def status(self, handle: dict[str, Any]) -> dict[str, Any]:
        job_dir = Path(handle["job_dir"])
        proc = self._procs.get(handle.get("job_id", ""))
        code = proc.poll() if proc else None
        if proc is None:
            state = "UNKNOWN"
        elif code is None:
            state = "RUNNING"
        else:
            state = "COMPLETED" if code == 0 else "FAILED"
        log_path = job_dir / "out.log"
        log = "\n".join(log_path.read_text(errors="replace").splitlines()[-60:]) if log_path.exists() else ""
        metrics = (job_dir / "metrics.json").read_text() if (job_dir / "metrics.json").exists() else ""
        return {"state": _normalize_state(state), "raw_state": state, "log": log, "metrics": metrics.strip()}

    def cancel(self, handle: dict[str, Any]) -> None:
        proc = self._procs.get(handle.get("job_id", ""))
        if proc and proc.poll() is None:
            proc.terminate()

    def fetch(self, paths: list[str]) -> list[str]:
        return [os.path.expanduser(p) for p in paths]


def _normalize_state(state: str) -> str:
    state = state.upper().rstrip("+")
    if state in ("PENDING", "CONFIGURING", "REQUEUED"):
        return "queued"
    if state in ("RUNNING", "COMPLETING"):
        return "running"
    if state == "COMPLETED":
        return "done"
    if state.startswith("CANCELLED"):
        return "cancelled"
    if state in ("FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL"):
        return "failed"
    return "unknown"


_TARGETS: dict[str, Any] = {}


def get_target(name: str):
    if name not in _TARGETS:
        _TARGETS[name] = ClusterTarget() if name == "cluster" else LaptopTarget()
    return _TARGETS[name]
