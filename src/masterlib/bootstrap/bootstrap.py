# src/masterlib/bootstrap/bootstrap.py

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional

from masterlib.bootstrap.launcher import Launcher, LauncherConfig


# =========================
# === LOGGING ============
# =========================

def _make_bootstrap_logger(app_dir: Path, app_name: str) -> logging.Logger:
    """
    Logger unique bootstrap / launcher.
    Toute la phase de démarrage passe ici.
    """
    log_dir = app_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "bootstrap.log"

    logger = logging.getLogger("bootstrap")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.info("=== BOOTSTRAP START (%s) ===", app_name)
    return logger


# =========================
# === HOOKS FUTURS ========
# =========================

def before_launcher_start(app_dir: Path) -> None:
    """Hook: avant création du launcher (config, checks, etc.)"""
    pass


def after_launcher_stop(app_dir: Path) -> None:
    """Hook: après arrêt complet de l'application"""
    pass


# =========================
# === API PUBLIQUE ========
# =========================

def run_project_cli(app_dir: Path, app_name: Optional[str] = None) -> int:
    """
    Point d’entrée officiel appelé par reinerouge/cli.py
    """
    app_dir = app_dir.resolve()
    app_name = (app_name or os.environ.get("APP_NAME", app_dir.name)).strip() or app_dir.name

    before_launcher_start(app_dir)

    logger = _make_bootstrap_logger(app_dir, app_name)
    logger.info("app_dir=%s", app_dir)

    launcher = Launcher(
        LauncherConfig(
            app_dir=app_dir,
            logger=logger,
        )
    )

    try:
        return launcher.run()

    except KeyboardInterrupt:
        logger.info("⏹ Interruption clavier (CTRL+C)")
        launcher.stop()
        return 0

    except Exception:
        logger.exception("❌ Erreur fatale bootstrap")
        raise

    finally:
        after_launcher_stop(app_dir)
        
