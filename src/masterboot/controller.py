# src/masterboot/controller.py
from __future__ import annotations

"""
masterboot/controller.py

Contrôleur minimal et fonctionnel (V0).
Objectif : rendre la séquence de boot fiable pour que tu puisses coder masterkernel.

Responsabilités (V0) :
- créer le workspace: <project_root>/data/{logs,runtime,scan}
- écrire un log de boot: data/logs/masterboot.log
- exécuter prepare_workspace.sh (optionnel)
- lancer masterkernel via: python -m masterkernel.runtime --project-root <project_root>
- rediriger stdout/stderr du kernel vers: data/logs/masterkernel.log
"""

import os
import sys
import signal
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import psutil

from masterkernel.paths import build_paths
from masterservice.transport.ipc.transport_ipc import TransportIpc


@dataclass
class BootPaths:
    """
    Chemins standard du workspace d’un projet.

    Tout est relatif à project_root.
    On garde volontairement la V0 simple :
    - data/logs/ : logs boot + kernel
    - data/runtime/ : pid, commandes, etc.
    - data/scan/ : sorties de scripts (tree, scans, etc.)
    """
    project_root: Path

    @property
    def data(self) -> Path:
        return self.project_root / "data"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def runtime(self) -> Path:
        return self.data / "runtime"

    @property
    def scan(self) -> Path:
        return self.data / "scan"

    @property
    def boot_log(self) -> Path:
        return self.logs / "masterboot.log"

    @property
    def kernel_log(self) -> Path:
        return self.logs / "masterkernel.log"

    @property
    def pid_file(self) -> Path:
        return self.runtime / "masterkernel.pid"


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _log(paths: BootPaths, msg: str) -> None:
    _append_line(paths.boot_log, msg)
    print(msg, flush=True)


def _ensure_workspace(paths: BootPaths) -> None:
    paths.project_root.mkdir(parents=True, exist_ok=True)
    paths.data.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.scan.mkdir(parents=True, exist_ok=True)


def _run_prepare_workspace_sh(project_root: Path, paths: BootPaths) -> None:
    """
    Lance prepare_workspace.sh si présent.
    Le script est optionnel (il ne doit jamais empêcher le boot).
    """
    # script installé dans MasterLib/src/masterboot/scripts/prepare_workspace.sh
    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # .../MasterLib
    script = repo_root / "src" / "masterboot" / "scripts" / "prepare_workspace.sh"

    if not script.exists():
        _log(paths, f"[BOOT] (skip) prepare_workspace.sh introuvable: {script}")
        return

    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(project_root)
    env["WORKSPACE"] = str(project_root / "data")
    env["LOG_FILE"] = str(paths.boot_log)

    _log(paths, f"[BOOT] run prepare_workspace.sh -> data/scan/")
    out = paths.scan / "prepare_workspace.log"
    with out.open("a", encoding="utf-8") as f:
        subprocess.run(
            ["sh", str(script)],
            cwd=str(project_root),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            check=False,
        )


def _start_kernel(project_root: Path, project_name: str, paths: BootPaths) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "masterkernel.runtime",
        "--project-root",
        str(project_root),
        "--app-name",
        project_name,
        "--paths-mode",
        "local",
    ]
    _log(paths, f"[BOOT] launch kernel: {' '.join(cmd)}")
    env = os.environ.copy()
    env["MASTER_KERNEL_BACKGROUND"] = "1"
    kernel_log_f = paths.kernel_log.open("a", encoding="utf-8")
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=kernel_log_f,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=(os.name != "nt"),
        )
    finally:
        kernel_log_f.close()
    paths.pid_file.write_text(str(p.pid), encoding="utf-8")
    _log(paths, f"[BOOT] kernel pid={p.pid}")
    return p


class ProjectController:
    """
    API utilisée par masterboot/cli.py

    - start() : démarre le kernel
    - status() : indique si un pid existe et si le process semble vivant
    - stop() : terminate (V0)
    - init_project() : V0 = crée juste le workspace (le scaffolding métier viendra après)
    """
    @staticmethod
    def _confirm_before_start(paths: BootPaths, project_name: str, project_root: Path) -> bool:
        """
        Safety prompt (opt-in).
        Active si env MASTER_CONFIRM=1, et si stdin est un TTY.
        """
        import os
        import sys

        want = os.getenv("MASTER_CONFIRM", "0") == "1"
        if not want:
            return True  # pas de confirmation

        if not sys.stdin.isatty():
            _log(paths, "[BOOT] confirm requested but stdin is not a TTY -> skip confirm (auto-continue)")
            return True

        # "config_projet" minimal V0 (on enrichira après)
        _log(paths, "[BOOT] --- CONFIG PROJET ---")
        _log(paths, f"[BOOT] project_name = {project_name}")
        _log(paths, f"[BOOT] project_root = {project_root}")
        _log(paths, f"[BOOT] kernel_cmd   = {sys.executable} -m masterkernel.runtime --project-root {project_root}")
        _log(paths, "[BOOT] ----------------------")

        ans = input("Push Y pour démarrer le masterkernel (sinon exit) : ").strip()
        if ans.upper() == "Y":
            _log(paths, "[BOOT] confirm=Y -> start kernel")
            return True

        _log(paths, f"[BOOT] confirm={ans!r} -> abort (kernel not started)")
        return False

    def __init__(
        self,
        project_root: Path,
        project_name: str,
        config_path: Optional[Path] = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.project_name = (project_name or self.project_root.name).strip()

        # Chemin du fichier de config projet (par défaut dans le root du projet)
        self.config_path = Path(config_path).resolve() if config_path else (self.project_root / "config_projet.ini")

        self.paths = BootPaths(self.project_root)

    def init_project(self) -> None:
        _ensure_workspace(self.paths)
        _log(self.paths, f"[BOOT] init project={self.project_name} root={self.project_root}")

    def _runtime_paths(self):
        return build_paths(self.project_name, app_root=str(self.project_root), mode="local")

    def _pid_matches_kernel(self, pid: int) -> bool:
        try:
            process = psutil.Process(pid)
            command = process.cmdline()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False
        except psutil.AccessDenied:
            return True

        command_text = " ".join(command)
        return (
            "masterkernel.runtime" in command_text
            and str(self.project_root) in command_text
        )

    def _kernel_request(self, topic: str, data: dict | None = None) -> dict:
        paths = self._runtime_paths()
        return TransportIpc.request(
            paths.master_endpoint,
            {"topic": topic, "source": "masterboot", "data": data or {}},
            timeout=1.0,
        )

    def start(self) -> int:
        if self.paths.pid_file.exists():
            pid_s = self.paths.pid_file.read_text(encoding="utf-8").strip()
            try:
                pid = int(pid_s)
            except ValueError:
                self.paths.pid_file.unlink(missing_ok=True)
            else:
                if self._pid_matches_kernel(pid):
                    _log(self.paths, f"[BOOT] kernel déjà actif (pid={pid})")
                    return 1
                _log(self.paths, f"[BOOT] suppression du PID périmé ({pid})")
                self.paths.pid_file.unlink(missing_ok=True)
            
        self.init_project()
        _log(self.paths, f"[BOOT] === START ({self.project_name}) ===")


        # optionnel : tree + snapshot
        _run_prepare_workspace_sh(self.project_root, self.paths)

        if not self._confirm_before_start(self.paths, self.project_name, self.project_root):
            return 1

        # start kernel
        p = _start_kernel(self.project_root, self.project_name, self.paths)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            rc = p.poll()
            if rc is not None:
                self.paths.pid_file.unlink(missing_ok=True)
                _log(self.paths, f"[BOOT] ❌ kernel exited rc={rc} (voir {self.paths.kernel_log})")
                return 1
            try:
                response = self._kernel_request("kernel.status")
                if response.get("ok") and response.get("running"):
                    _log(self.paths, f"[BOOT] ✅ kernel prêt (pid={p.pid}, transport=IPC)")
                    _log(self.paths, f"[BOOT] log={self.paths.kernel_log}")
                    return 0
            except (OSError, ValueError, TimeoutError):
                time.sleep(0.2)

        _log(self.paths, "[BOOT] ❌ le noyau n'a pas répondu au contrôle IPC en 10 s")
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            p.kill()
        self.paths.pid_file.unlink(missing_ok=True)
        return 1

    def status(self) -> str:
        if not self.paths.pid_file.exists():
            return "STOPPED (no pid)"
        pid_s = self.paths.pid_file.read_text(encoding="utf-8").strip()
        try:
            pid = int(pid_s)
        except ValueError:
            self.paths.pid_file.unlink(missing_ok=True)
            return "STOPPED (invalid pid file removed)"

        if not self._pid_matches_kernel(pid):
            self.paths.pid_file.unlink(missing_ok=True)
            return f"STOPPED (stale pid {pid} removed)"

        try:
            response = self._kernel_request("kernel.status")
            if response.get("ok"):
                return f"RUNNING PID={pid} state={response.get('state', 'unknown')}"
        except (OSError, ValueError, TimeoutError):
            pass
        return f"RUNNING PID={pid} (IPC not responding; inspect {self.paths.kernel_log})"

    def stop(self) -> int:
        if not self.paths.pid_file.exists():
            _log(self.paths, "[BOOT] stop: no pid")
            return 0

        pid_s = self.paths.pid_file.read_text(encoding="utf-8").strip()
        _log(self.paths, f"[BOOT] stop requested pid={pid_s}")

        try:
            pid = int(pid_s)
        except ValueError:
            self.paths.pid_file.unlink(missing_ok=True)
            _log(self.paths, "[BOOT] pid invalide supprimé")
            return 0

        if not self._pid_matches_kernel(pid):
            self.paths.pid_file.unlink(missing_ok=True)
            _log(self.paths, f"[BOOT] PID périmé supprimé ({pid})")
            return 0

        try:
            response = self._kernel_request("kernel.shutdown", {"reason": "masterboot_stop"})
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "accusé IPC négatif"))
            _log(self.paths, f"[BOOT] arrêt propre accepté par le noyau (pid={pid})")
        except Exception as exc:
            _log(self.paths, f"[BOOT] IPC indisponible, arrêt du processus en secours : {exc}")
            try:
                process = psutil.Process(pid)
                process.terminate()
            except psutil.NoSuchProcess:
                self.paths.pid_file.unlink(missing_ok=True)
                return 0
            except Exception as e:
                _log(self.paths, f"[BOOT] stop error: {e}")
                return 1

        try:
            process = psutil.Process(pid)
            process.wait(timeout=10)
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            _log(self.paths, "[BOOT] délai dépassé, arrêt forcé du noyau")
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass
        self.paths.pid_file.unlink(missing_ok=True)
        _log(self.paths, "[BOOT] noyau arrêté")
        return 0
