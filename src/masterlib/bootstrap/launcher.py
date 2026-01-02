# src/masterlib/bootstrap/launcher.py

from __future__ import annotations
import subprocess
import sys
import os
from pathlib import Path
from dataclasses import dataclass
import logging
import time


@dataclass
class LauncherConfig:
    app_dir: Path
    python: str = sys.executable
    logger: logging.Logger | None = None


class Launcher:
    """
    Launcher long-vivant.

    Rôle :
    - préparer l'environnement d'exécution
    - lancer MasterKernel via runtime
    - rester actif jusqu'à arrêt
    - fournir des hooks pour MAJ / restart / supervision
    """

    def __init__(self, cfg: LauncherConfig):
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None
        self.logger = cfg.logger

    # =========================
    # === API PUBLIQUE ========
    # =========================

    def run(self) -> int:
        self._ensure_dirs()
        self._init_runtime_state()
        self._log("🚀 launcher start")

        self.before_start()
        self.start_kernel()
        self.after_start()

        code = self.wait()

        self.before_stop()
        self._log(f"🛑 kernel stopped (exit code={code})")
        self.after_stop()

        return code

    def stop(self) -> None:
        self._log("⏹ stop requested")
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    # =========================
    # === HOOKS (VIDES) =======
    # =========================

    def before_start(self) -> None:
        """Hook: avant le démarrage du kernel"""
        pass

    def after_start(self) -> None:
        """Hook: juste après le démarrage du kernel"""
        pass

    def before_stop(self) -> None:
        """Hook: avant l'arrêt du kernel"""
        pass

    def after_stop(self) -> None:
        """Hook: après l'arrêt du kernel"""
        pass

    def check_update(self) -> bool:
        """Hook: détecte une mise à jour disponible"""
        return False

    def restart_kernel(self) -> None:
        """Hook: redémarrage contrôlé du kernel"""
        pass

    # =========================
    # === MÉCANISME ACTIF =====
    # =========================

    def start_kernel(self) -> None:
        env = os.environ.copy()
        env["APP_DIR"] = str(self.cfg.app_dir)

        main_py = self.cfg.app_dir / "main.py"
        cmd = [self.cfg.python, str(main_py)]

        self._log(f"▶ start kernel: {' '.join(cmd)}")

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(self.cfg.app_dir),
            env=env,
            
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self._log(f"▶ kernel pid={self.proc.pid}")

    def wait(self) -> int:
        if not self.proc:
            raise RuntimeError("kernel not started")

        # boucle de vie du launcher (future supervision ici)
        while True:
            code = self.proc.poll()
            if code is not None:
                return code

            # future: check_update(), watchdog, bus, etc.
            time.sleep(0.5)

        out, err = self.proc.communicate()
        if out:
            self.log("KERNEL STDOUT:\n" + out)
        if err:
            self.log("KERNEL STDERR:\n" + err)
        return self.proc.returncode


    # =========================
    # === SETUP INTERNE =======
    # =========================

    def _ensure_dirs(self) -> None:
        (self.cfg.app_dir / "data" / "log").mkdir(parents=True, exist_ok=True)

    def _init_runtime_state(self) -> None:
        """Prépare l'état interne du launcher (futur runtime)"""
        pass

    def _log(self, msg: str) -> None:
        if self.logger:
            self.logger.info(msg)
        else:
            print(f"[launcher] {msg}", file=sys.stderr, flush=True)
