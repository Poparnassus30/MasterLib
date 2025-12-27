from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass


# ----------------------------
# Utils
# ----------------------------

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
    masterlib_local = os.environ.get("MASTERLIB_LOCAL", "").strip()
    masterlib_ref   = os.environ.get("MASTERLIB_REF", "dev").strip()
    masterlib_url   = os.environ.get("MASTERLIB_URL", "https://github.com/Poparnassus30/MasterLib.git").strip()

    # 1) local explicite
    if masterlib_local:
        p = Path(masterlib_local).expanduser()
        if p.is_dir():
            return MasterLibSource(
                mode="local",
                path=p,
                ref=masterlib_ref,
                commit=_git_commit_short(p) if _is_git_repo(p) else "no-git",
                dirty=_git_dirty(p) if _is_git_repo(p) else False,
            )

    # 2) repo voisin ../MasterLib
    neighbor = app_dir.parent / "MasterLib"
    if neighbor.is_dir():
        return MasterLibSource(
            mode="local",
            path=neighbor,
            ref=masterlib_ref,
            commit=_git_commit_short(neighbor) if _is_git_repo(neighbor) else "no-git",
            dirty=_git_dirty(neighbor) if _is_git_repo(neighbor) else False,
        )

    # 3) standard dev WSL
    standard = Path("/home/poparnassus/github/MasterLib")
    if standard.is_dir():
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
    Safe & idempotent: pip will update the .pth/direct_url accordingly.
    """
    _print(f"🧩 MasterLib (editable): {masterlib_path}")
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
