from __future__ import annotations

import os
import sys
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    app_name: str
    app_root: Path
    mode: str  # "local" | "xdg"

    data_dir: Path
    config_dir: Path
    cache_dir: Path
    logs_dir: Path
    registry_dir: Path

    runtime_dir: Path
    socket_dir: Path

    registry_file: Path
    log_file: Path
    master_socket: Path

    def module_socket(self, module_name: str) -> Path:
        safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in module_name)
        return self.socket_dir / f"{self.app_name}_{safe}.sock"


def _default_app_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    env = os.getenv("APP_PATH")
    if env:
        return Path(env).expanduser().resolve()

    main = sys.modules.get("__main__")
    main_file = getattr(main, "__file__", None)
    if main_file:
        return Path(main_file).resolve().parent

    return Path.cwd().resolve()


def _xdg_dirs(app_name: str) -> tuple[Path, Path, Path]:
    # Linux-friendly defaults
    home = Path.home()

    if platform.system().lower().startswith("win"):
        appdata = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        localappdata = Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local"))
        return (
            localappdata / app_name,  # data
            appdata / app_name,       # config
            localappdata / app_name,  # cache
        )

    xdg_data = Path(os.getenv("XDG_DATA_HOME", home / ".local" / "share")) / app_name
    xdg_config = Path(os.getenv("XDG_CONFIG_HOME", home / ".config")) / app_name
    xdg_cache = Path(os.getenv("XDG_CACHE_HOME", home / ".cache")) / app_name
    return xdg_data, xdg_config, xdg_cache


def build_paths(app_name: str, app_root: str | None = None, mode: str = "auto") -> Paths:
    root = _default_app_root(app_root)

    mode_env = os.getenv("MASTERSTRUCT_WORKSPACE", "").strip().lower()
    if mode_env in {"local", "xdg"}:
        mode = mode_env

    if mode == "auto":
        # Si le projet a déjà une logique "data/", on respecte.
        if (root / "data").exists() or (root / "config").exists():
            mode = "local"
        else:
            mode = "xdg"

    if mode == "local":
        data_dir = root / "data"
        config_dir = root / "config"
        cache_dir = root / "data" / "cache"
    else:
        data_dir, config_dir, cache_dir = _xdg_dirs(app_name)

    logs_dir = data_dir / "logs"
    registry_dir = data_dir / "registry"

    runtime_dir = Path(os.getenv("XDG_RUNTIME_DIR", "/tmp")) / app_name
    socket_dir = runtime_dir / "sockets"

    registry_file = registry_dir / "registry.json"
    log_file = logs_dir / f"{app_name}.log"
    master_socket = socket_dir / f"{app_name}.sock"

    # mkdir (runtime_dir peut échouer si droits chelous -> on fallback /tmp)
    for p in (data_dir, config_dir, cache_dir, logs_dir, registry_dir):
        p.mkdir(parents=True, exist_ok=True)

    try:
        socket_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        runtime_dir = Path("/tmp") / app_name
        socket_dir = runtime_dir / "sockets"
        socket_dir.mkdir(parents=True, exist_ok=True)

        master_socket = socket_dir / f"{app_name}.sock"

    return Paths(
        app_name=app_name,
        app_root=root,
        mode=mode,
        data_dir=data_dir,
        config_dir=config_dir,
        cache_dir=cache_dir,
        logs_dir=logs_dir,
        registry_dir=registry_dir,
        runtime_dir=runtime_dir,
        socket_dir=socket_dir,
        registry_file=registry_file,
        log_file=log_file,
        master_socket=master_socket,
    )
