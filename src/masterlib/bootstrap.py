from __future__ import annotations
from datetime import datetime
import os
import sys
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass


# ----------------------------
# Utils
# ----------------------------
_BOOTSTRAP_LOG_FILE: Path | None = None

def _bootstrap_log_init(app_dir: Path) -> None:
    """
    Initialise le log bootstrap dans <app_dir>/data/logs/bootstrap.log
    Override possible via env: BOOTSTRAP_LOG=/chemin/xxx.log
    """
    global _BOOTSTRAP_LOG_FILE

    # override si tu veux déporter le log
    override = os.environ.get("BOOTSTRAP_LOG", "").strip()
    if override:
        p = Path(override).expanduser()
    else:
        p = app_dir / "data" / "logs" / "bootstrap.log"

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        _BOOTSTRAP_LOG_FILE = p
    except Exception:
        _BOOTSTRAP_LOG_FILE = None  # on ne casse jamais le bootstrap pour un log

def _print(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"

    # console
    print(line, flush=True)

    # fichier (best effort)
    if _BOOTSTRAP_LOG_FILE:
        try:
            _BOOTSTRAP_LOG_FILE.open("a", encoding="utf-8").write(line + "\n")
        except Exception:
            pass

def _detect_installed_masterlib(py: str) -> tuple[bool, str]:
    """
    Returns (installed?, location_string).
    Tries to locate where masterlib is imported from in the current interpreter.
    """
    code = (
        "import importlib.util\n"
        "spec = importlib.util.find_spec('masterlib')\n"
        "print(spec.origin if spec and spec.origin else '')\n"
    )
    r = _sh([py, "-c", code], check=False, quiet=True)
    loc = (r.stdout or "").strip()
    return (bool(loc), loc)


def _uninstall_masterlib(py: str) -> None:
    _print("🧹 Uninstall existing masterlib…")
    _sh([py, "-m", "pip", "uninstall", "-y", "masterlib"], check=False, quiet=False)

def _print(msg: str) -> None:
    print(msg, flush=True)

def _sh(cmd: list[str], cwd: Path | None = None, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        _print("▶ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _git(cwd: Path, args: list[str], check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    return _sh(["git", "-C", str(cwd), *args], check=check, quiet=quiet)

def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()

def _git_commit_short(path: Path) -> str:
    try:
        r = _git(path, ["rev-parse", "--short", "HEAD"], check=True, quiet=True)
        return (r.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"

def _git_dirty(path: Path) -> bool:
    """
    True if there are local modifications (uncommitted) or untracked files.
    """
    try:
        r = _git(path, ["status", "--porcelain"], check=True, quiet=True)
        return bool((r.stdout or "").strip())
    except Exception:
        return False

def _have_network_for_git() -> bool:
    """
    Best effort: we don't ping internet; we attempt a tiny git command later.
    """
    return True

def _safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


# ----------------------------
# Source model
# ----------------------------

@dataclass(frozen=True)
class MasterLibSource:
    mode: str          # "local" | "cache"
    path: Path
    ref: str
    commit: str
    dirty: bool


# ----------------------------
# Resolution policy (AUTO)
# ----------------------------

def resolve_masterlib_source(app_dir: Path) -> MasterLibSource:
    """
    AUTO policy:
    - Prefer local dev repos (never touch git).
    - Else use cache repo (safe to sync/hard-reset).
    Handles: offline, cache missing/corrupt, etc.
    """
    def _is_forbidden_local_path(p: Path) -> bool:
        # Empêche de considérer une copie vendored (.deps) comme "repo local"
        return "/.deps/" in str(p.resolve()).replace("\\", "/")

    masterlib_local = os.environ.get("MASTERLIB_LOCAL", "").strip()
    masterlib_ref   = os.environ.get("MASTERLIB_REF", "dev").strip()
    masterlib_url   = os.environ.get("MASTERLIB_URL", "https://github.com/Poparnassus30/MasterLib.git").strip()

    # 1) local explicite
    if masterlib_local:
        p = Path(masterlib_local).expanduser()
        if p.is_dir() and not _is_forbidden_local_path(p):
            return MasterLibSource(
                mode="local",
                path=p,
                ref=masterlib_ref,
                commit=_git_commit_short(p) if _is_git_repo(p) else "no-git",
                dirty=_git_dirty(p) if _is_git_repo(p) else False,
            )

    # 2) repo voisin ../MasterLib
    neighbor = app_dir.parent / "MasterLib"
    if neighbor.is_dir() and not _is_forbidden_local_path(neighbor):
        return MasterLibSource(
            mode="local",
            path=neighbor,
            ref=masterlib_ref,
            commit=_git_commit_short(neighbor) if _is_git_repo(neighbor) else "no-git",
            dirty=_git_dirty(neighbor) if _is_git_repo(neighbor) else False,
        )

    # 3) standard dev WSL
    standard = Path.home() / "github" / "MasterLib"
    if standard.is_dir() and not _is_forbidden_local_path(standard):
        return MasterLibSource(
            mode="local",
            path=standard,
            ref=masterlib_ref,
            commit=_git_commit_short(standard) if _is_git_repo(standard) else "no-git",
            dirty=_git_dirty(standard) if _is_git_repo(standard) else False,
        )

    # 4) cache jetable (sync ok)
    app_name = os.environ.get("APP_NAME", app_dir.name).strip() or app_dir.name
    cache_base = Path(os.environ.get("MASTERLIB_CACHE_BASE", str(Path.home() / ".cache" / app_name / "deps"))).expanduser()
    cache_repo = Path(os.environ.get("MASTERLIB_CACHE_DIR", str(cache_base / "MasterLib"))).expanduser()

    cache_base.mkdir(parents=True, exist_ok=True)

    # If cache exists but is not a git repo => it's corrupt/partial => wipe it
    if cache_repo.exists() and not _is_git_repo(cache_repo):
        _print(f"⚠️  [cache] MasterLib cache exists but is not a git repo -> wipe: {cache_repo}")
        _safe_rmtree(cache_repo)

    # Clone if missing
    if not cache_repo.exists():
        _print("⬇️  [cache] Clone MasterLib…")
        # If offline, clone will fail -> we error with a clear message
        r = _sh(["git", "clone", "--branch", masterlib_ref, "--depth", "1", masterlib_url, str(cache_repo)], check=False)
        if r.returncode != 0:
            _print("❌ [cache] Clone failed (offline? url/ref?)")
            _print(r.stderr.strip())
            raise SystemExit(
                "MasterLib introuvable en local ET impossible de cloner en cache. "
                "=> Fournis un repo local (MASTERLIB_LOCAL) ou réessaie avec réseau."
            )

    # Sync cache: best effort (offline-friendly)
    # Rule: cache is disposable, so reset hard is OK.
    _print("🔄 [cache] Sync MasterLib…")
    fetched = False
    try:
        _git(cache_repo, ["fetch", "origin", masterlib_ref, "--depth", "1"], check=True, quiet=False)
        fetched = True
    except Exception as e:
        _print(f"⚠️  [cache] Fetch failed -> offline? Using existing cache. ({type(e).__name__})")

    if fetched:
        try:
            _git(cache_repo, ["reset", "--hard", f"origin/{masterlib_ref}"], check=True, quiet=False)
        except Exception as e:
            # If reset fails, the repo might be corrupt; wipe and re-clone once
            _print(f"⚠️  [cache] Reset failed -> wipe & re-clone. ({type(e).__name__})")
            _safe_rmtree(cache_repo)
            _print("⬇️  [cache] Re-clone MasterLib…")
            r = _sh(["git", "clone", "--branch", masterlib_ref, "--depth", "1", masterlib_url, str(cache_repo)], check=False)
            if r.returncode != 0:
                _print("❌ [cache] Re-clone failed. Using nothing.")
                _print(r.stderr.strip())
                raise SystemExit("Cache MasterLib corrompu et impossible de re-cloner.")

    return MasterLibSource(
        mode="cache",
        path=cache_repo,
        ref=masterlib_ref,
        commit=_git_commit_short(cache_repo),
        dirty=_git_dirty(cache_repo),
    )


# ----------------------------
# Install (editable) + launch
# ----------------------------

def ensure_masterlib_installed(py: str, masterlib_path: Path) -> None:
    """
    Installs MasterLib in editable mode into the current environment (venv).
    If an existing masterlib is installed from an unwanted location (e.g. project .deps),
    we uninstall it first to avoid .pth precedence issues.
    """
    masterlib_path = masterlib_path.resolve()
    _print(f"🧩 MasterLib target (editable): {masterlib_path}")

    installed, loc = _detect_installed_masterlib(py)
    if installed:
        loc_norm = loc.replace("\\", "/")
        _print(f"🔎 Existing masterlib detected: {loc_norm}")

        # If it comes from a .deps vendored copy, we consider it "poison" for bootstrap.
        if "/.deps/" in loc_norm:
            _print("⚠️  masterlib comes from .deps -> uninstall to let bootstrap control the source.")
            _uninstall_masterlib(py)

    r = _sh([py, "-m", "pip", "install", "-e", str(masterlib_path)], check=False, quiet=False)
    if r.returncode != 0:
        _print("❌ pip install -e failed")
        _print(r.stderr.strip())
        raise SystemExit("Échec installation MasterLib (pip).")


def run_project_cli(*, app_dir: Path, app_main: Path | None = None, app_name: str | None = None) -> int:
    """
    One-call entrypoint for projects:
    - resolves MasterLib (local dev or cache)
    - installs it editable in the current env
    - launches app_main with the same interpreter
    """
    app_dir = app_dir.resolve()
    _bootstrap_log_init(app_dir)
    _print(f"🚀 Bootstrap start | app_dir={app_dir}")
    _print(f"🐍 Python: {sys.executable}")

    app_main = (app_main or (app_dir / "main.py")).resolve()

    os.environ["APP_PATH"] = str(app_dir)
    os.environ["APP_NAME"] = (app_name or os.environ.get("APP_NAME", app_dir.name)).strip() or app_dir.name

    py = sys.executable

    # pip upgrade: best effort (offline-friendly)
    try:
        _sh([py, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=False, quiet=True)
    except Exception:
        pass

    src = resolve_masterlib_source(app_dir)
    _print(f"🧠 MasterLib source: mode={src.mode} ref={src.ref} commit={src.commit} dirty={src.dirty}")
    _print(f"📍 MasterLib path: {src.path}")

    dirty_tag = "DIRTY" if src.dirty else "clean"
    _print(f"🧠 MasterLib source: {src.mode} | ref={src.ref} | commit={src.commit} | {dirty_tag}")

    # SAFETY: never run destructive git operations on local dev repos.
    # (enforced by resolve_masterlib_source)

    ensure_masterlib_installed(py, src.path)

    if not app_main.exists():
        raise SystemExit(f"APP_MAIN introuvable: {app_main}")

    _print(f"▶️  Launch: {app_main}")
    os.execv(py, [py, str(app_main), *sys.argv[1:]])
    return 0
