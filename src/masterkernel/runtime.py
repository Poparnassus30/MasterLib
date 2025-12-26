# masterstruct/runtime.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .paths import build_paths, Paths
from .system.system import System
from .kernel.kernel import Kernel


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
