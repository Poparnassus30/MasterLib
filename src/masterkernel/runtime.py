# masterstruct/runtime.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .paths import build_paths, Paths
from .system.system import System
from .kernel.masterkernel import Kernel


@dataclass
class Context:
    app_core: Any
    paths: Paths
    system: System


def run(
    app_core: Any,
    *,
    app_name: Optional[str] = None,
    app_root: Optional[str] = None,
    paths_mode: str = "auto",
) -> int:
    name = app_name or getattr(app_core, "name", None) or app_core.__class__.__name__
    paths = build_paths(name, app_root=app_root, mode=paths_mode)

    system = System(app_name=name, paths=paths)  # <- c’est lui qui setup logger/config/registre
    ctx = Context(app_core=app_core, paths=paths, system=system)

    kernel = Kernel(ctx)
    return kernel.run()

def main(argv: Optional[list[str]] = None) -> int:
    """
    Point d’entrée CLI de masterkernel.
    Permet: python -m masterkernel.runtime --project-root <path>
    """
    import argparse

    p = argparse.ArgumentParser(prog="masterkernel")
    p.add_argument("--project-root", default=".", help="Racine du projet (workspace)")
    p.add_argument("--app-name", default=None, help="Nom logique de l'app (sinon déduit)")
    p.add_argument("--paths-mode", default="auto", choices=["auto", "local", "xdg"], help="Mode de Paths")
    args = p.parse_args(argv)

    class DefaultAppCore:
        # minimal: le kernel a juste besoin d’un objet
        name = args.app_name or "masterkernel"

    return run(
        DefaultAppCore(),
        app_name=args.app_name or "masterkernel",
        app_root=args.project_root,
        paths_mode=args.paths_mode,
    )


if __name__ == "__main__":
    raise SystemExit(main())

