"""Point d'entrée multiplateforme du module d'audit réseau."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent


def detect_platform() -> str:
    """Retourne windows, linux, android ou unsupported."""
    if sys.platform == "win32":
        return "windows"

    if (
        sys.platform == "android"
        or os.environ.get("ANDROID_ROOT")
        or os.environ.get("ANDROID_DATA")
        or os.environ.get("TERMUX_VERSION")
    ):
        return "android"

    if platform.system() == "Linux":
        return "linux"

    return "unsupported"


def build_command(target: str) -> list[str]:
    if target == "windows":
        script = MODULE_DIR / "audit-reseau.ps1"
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            raise RuntimeError(
                "PowerShell est introuvable. Installe PowerShell ou vérifie son PATH."
            )
        return [powershell, "-NoProfile", "-File", str(script)]

    if target == "linux":
        script = MODULE_DIR / "audit-reseau-linux.sh"
        bash = shutil.which("bash")
        if not bash:
            raise RuntimeError("Bash est introuvable sur ce système.")
        return [bash, str(script)]

    raise RuntimeError(
        "Ce système n'est pas encore pris en charge par le module d'audit."
    )


def main() -> int:
    target = detect_platform()

    if target == "android":
        print(
            "Android est détecté, mais son collecteur n'est pas encore disponible. "
            "Les accès système y sont différents de ceux de Linux."
        )
        return 2

    try:
        command = build_command(target)
    except RuntimeError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2

    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        print(f"Impossible de lancer le collecteur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
