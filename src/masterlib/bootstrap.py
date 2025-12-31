from __future__ import annotations
from datetime import datetime
import os
import sys
import shutil
import subprocess
import shlex
import shutil
from pathlib import Path
from dataclasses import dataclass
import time

# ----------------------------
# Utils
# ----------------------------
_BOOTSTRAP_LOG_FILE: Path | None = None


# ----------------------------
# Path helpers
# ----------------------------

def _resolve_app_root(app_dir: Path) -> Path:
    """Normalise app_dir vers la racine du projet (heuristique)."""
    p = Path(app_dir).expanduser().resolve()
    if p.name == "src" and p.parent.exists():
        p = p.parent

    markers = ("pyproject.toml", ".git", "main.py")
    for _ in range(8):
        if any((p / m).exists() for m in markers):
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(app_dir).expanduser().resolve()

def _bootstrap_log_init(app_dir: Path) -> None:
    """
    Initialise un log bootstrap fiable.

    Priorité:
      1) BOOTSTRAP_LOG (override) si défini
      2) app_dir/data/logs/bootstrap.log (dev-friendly)
      3) fallback ~/.cache/<app_dir.name>/logs/bootstrap.log si le projet n'est pas inscriptible

    Comportement:
      - crée les dossiers si besoin
      - écrit une "preuve de vie" immédiatement
      - en cas d'échec, écrit l'erreur sur stderr (pas effacé par Rich)
      - optionnel: BOOTSTRAP_PAUSE=1 => pause (Enter si possible, sinon sleep 60s)
    """
    global _BOOTSTRAP_LOG_FILE

    app_dir = _resolve_app_root(Path(app_dir))

    override = os.environ.get("BOOTSTRAP_LOG", "").strip()
    if override:
        primary = Path(override).expanduser()
    else:
        primary = app_dir / "data" / "logs" / "bootstrap.log"

    # Tentative 1: chemin primaire
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        _BOOTSTRAP_LOG_FILE = primary
    except Exception as e:
        # Tentative 2: fallback cache utilisateur
        fallback = Path.home() / ".cache" / app_dir.name / "logs" / "bootstrap.log"
        try:
            fallback.parent.mkdir(parents=True, exist_ok=True)
            _BOOTSTRAP_LOG_FILE = fallback
            print(
                f"[bootstrap] log fallback to {fallback} (reason={e!r})",
                file=sys.stderr,
                flush=True,
            )
        except Exception as e2:
            _BOOTSTRAP_LOG_FILE = None
            print(
                f"[bootstrap] log init failed: {e2!r} (path={primary})",
                file=sys.stderr,
                flush=True,
            )
            return

    # Affiche le chemin réellement utilisé (stderr => pas “effacé” par Rich)
    log = _BOOTSTRAP_LOG_FILE
    print(f"[bootstrap] log file = {log}", file=sys.stderr, flush=True)

    # Preuve de vie
    try:
        log.open("a", encoding="utf-8").write(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ bootstrap logger init | app_dir={app_dir}\n"
        )
    except Exception as e:
        print(
            f"[bootstrap] log write failed: {e!r} (path={log})",
            file=sys.stderr,
            flush=True,
        )

    # Pause debug optionnelle
    if os.environ.get("BOOTSTRAP_PAUSE", "").strip() == "1":
        try:
            if log:
                log.open("a", encoding="utf-8").write(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏸️ BOOTSTRAP_PAUSE=1 (pause)\n"
                )
        except Exception:
            pass

        print(
            "[bootstrap] BOOTSTRAP_PAUSE=1 → pause active (Entrée pour continuer, sinon sleep 60s).",
            file=sys.stderr,
            flush=True,
        )
        try:
            input()
        except EOFError:
            time.sleep(60)        



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

def _pause_if_debug(step: str) -> None:
    if os.environ.get("BOOTSTRAP_PAUSE", "").strip() == "1":
        _print(f"⏸️ DEBUG pause active (step={step})")
        print(f"[bootstrap] pause step={step} → Entrée pour continuer…", file=sys.stderr, flush=True)
        try:
            input()
        except EOFError:
            # stdin indisponible (ex: lancé via service) → on ne bloque pas
            print("[bootstrap] stdin fermé, pause ignorée.", file=sys.stderr, flush=True)

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


def _clip_log_text(s: str, limit: int = 4000) -> str:
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit] + f"… (truncated, {len(s)-limit} chars more)"


def _sh(cmd: list[str], cwd: Path | None = None, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    log_cmds = os.environ.get("BOOTSTRAP_LOG_COMMANDS", "").strip() == "1"
    if not quiet:
        _print("▶ " + " ".join(cmd))
    cp = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if log_cmds or (cp.returncode != 0 and not quiet):
        out = _clip_log_text(cp.stdout or "")
        err = _clip_log_text(cp.stderr or "")
        if out:
            _print("↳ stdout:" + out)
        if err:
            _print("↳ stderr:" + err)
    return cp

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
    """
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
    """

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



# ----------------------------
# Dev UX helpers (terminal tabs)
# ----------------------------

def _open_tabs_window(app_dir: Path, log_file: Path, kernel_argv: list[str]) -> bool:
    """
    Ouvre une nouvelle fenêtre de terminal avec 2 onglets :
    - Onglet 1 : suivi live du bootstrap.log (tail -f)
    - Onglet 2 : exécution de l'application (app_main / masterkernel)

    Déclenché via : BOOTSTRAP_TABS=1
    Retourne True si une fenêtre a été ouverte, sinon False.
    """
    log_q = shlex.quote(str(log_file))
    kernel_cmd = "cd " + shlex.quote(str(app_dir)) + " && " + " ".join(shlex.quote(a) for a in kernel_argv) + " ; exec bash"
    tail_cmd = f"tail -n 200 -f {log_q} ; exec bash"

    session_name = f"bootstrap_{app_dir.name.replace('/', '_').replace(' ', '_')}"

    # Try tmux first (works in headless)
    if shutil.which("tmux"):
        _print(f"🖥️  Using tmux for sessions: {session_name}")
        # Kill existing session if any
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Create new detached session with first window
        r1 = subprocess.run(["tmux", "new-session", "-d", "-s", session_name, "-n", "bootstrap", "bash", "-c", tail_cmd], check=False)
        if r1.returncode != 0:
            _print("⚠️  Failed to create tmux session.")
            return False
        # Add second window
        r2 = subprocess.run(["tmux", "new-window", "-t", session_name, "-n", "masterkernel", "bash", "-c", kernel_cmd], check=False)
        if r2.returncode != 0:
            _print("⚠️  Failed to add tmux window.")
            return False
        # If a terminal is available, open it with tmux attach
        term = (
            shutil.which("gnome-terminal")
            or shutil.which("konsole")
            or shutil.which("xfce4-terminal")
            or shutil.which("tilix")
            or shutil.which("xterm")
        )
        if term:
            attach_cmd = f"tmux attach -t {session_name}"
            if term.endswith("gnome-terminal"):
                cmd = [term, "--", "bash", "-c", attach_cmd]
            elif term.endswith("konsole"):
                cmd = [term, "-e", "bash", "-c", attach_cmd]
            elif term.endswith("xfce4-terminal"):
                cmd = [term, "-e", attach_cmd]
            elif term.endswith("tilix"):
                cmd = [term, "-e", attach_cmd]
            else:  # xterm
                cmd = [term, "-e", "bash", "-c", attach_cmd]
            subprocess.Popen(cmd, cwd=str(app_dir))
            _print(f"🧭 Tmux session created and terminal opened: {session_name}")
        else:
            _print(f"🧭 Tmux session created (no GUI terminal): {session_name}")
            _print(f"   To attach: tmux attach -t {session_name}")
        return True

    # Fallback to GUI terminals
    term = (
        shutil.which("gnome-terminal")
        or shutil.which("konsole")
        or shutil.which("xfce4-terminal")
        or shutil.which("tilix")
        or shutil.which("xterm")
    )
    if not term:
        _print("⚠️  Aucun terminal détecté (gnome-terminal/konsole/xfce4-terminal/tilix/xterm/tmux).")
        return False

    if term.endswith("gnome-terminal"):
        cmd = [
            term,
            "--window",
            "--tab", "--title=bootstrap", "--", "bash", "-lc", tail_cmd,
            "--tab", "--title=masterkernel", "--", "bash", "-lc", kernel_cmd,
        ]
        subprocess.Popen(cmd, cwd=str(app_dir))
        return True

    if term.endswith("konsole"):
        cmd = [
            term,
            "--new-tab", "-p", "tabtitle=bootstrap", "-e", "bash", "-lc", tail_cmd,
            "--new-tab", "-p", "tabtitle=masterkernel", "-e", "bash", "-lc", kernel_cmd,
        ]
        subprocess.Popen(cmd, cwd=str(app_dir))
        return True

    if term.endswith("xfce4-terminal"):
        cmd = [
            term,
            "--tab", "--title=bootstrap", "-e", f"bash -lc {shlex.quote(tail_cmd)}",
            "--tab", "--title=masterkernel", "-e", f"bash -lc {shlex.quote(kernel_cmd)}",
        ]
        subprocess.Popen(cmd, cwd=str(app_dir))
        return True

    if term.endswith("tilix"):
        # Tilix: on ouvre une session, puis un split. Pas parfait mais utile.
        cmd = [term, "-e", f"bash -lc {shlex.quote(tail_cmd)}"]
        subprocess.Popen(cmd, cwd=str(app_dir))
        cmd2 = [term, "-e", f"bash -lc {shlex.quote(kernel_cmd)}"]
        subprocess.Popen(cmd2, cwd=str(app_dir))
        return True

    # xterm fallback (2 fenêtres)
    subprocess.Popen([term, "-hold", "-e", "bash", "-lc", tail_cmd], cwd=str(app_dir))
    subprocess.Popen([term, "-hold", "-e", "bash", "-lc", kernel_cmd], cwd=str(app_dir))
    return True


def run_project_cli(*, app_dir: Path, app_main: Path | None = None, app_name: str | None = None) -> int:
    """
    One-call entrypoint for projects:
    - resolves MasterLib (local dev or cache)
    - installs it editable in the current env
    - launches app_main with the same interpreter
    """
    if os.environ.get("BOOTSTRAP_SENTINEL", "").strip() == "1":
        raise SystemExit("BOOTSTRAP_SENTINEL: run_project_cli reached")

    app_dir = _resolve_app_root(app_dir)
    _bootstrap_log_init(app_dir)
    _print(f"🚀 Bootstrap start | app_dir={app_dir}")
    _print(f"🐍 Python: {sys.executable}")
    _pause_if_debug("after_log_init")

    app_main = (app_main or (app_dir / "main.py")).resolve()

    os.environ["APP_PATH"] = str(app_dir)
    os.environ["APP_NAME"] = (app_name or os.environ.get("APP_NAME", app_dir.name)).strip() or app_dir.name

    py = sys.executable

    # pip upgrade: best effort (offline-friendly)
    try:
        _sh([py, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=False, quiet=False)
    except Exception:
        pass

    _pause_if_debug("start_resolve")
    src = resolve_masterlib_source(app_dir)
    _pause_if_debug("after_resolve")

    _print(f"🧠 MasterLib source: mode={src.mode} ref={src.ref} commit={src.commit} dirty={src.dirty}")
    _print(f"📍 MasterLib path: {src.path}")

    dirty_tag = "DIRTY" if src.dirty else "clean"
    _print(f"🧠 MasterLib source: {src.mode} | ref={src.ref} | commit={src.commit} | {dirty_tag}")

    # SAFETY: never run destructive git operations on local dev repos.
    # (enforced by resolve_masterlib_source)

    _pause_if_debug("start_install")
    ensure_masterlib_installed(py, src.path)
    _pause_if_debug("after_install")
    r = _sh([py, "-c", "import masterlib; print(masterlib.__file__)"], check=False, quiet=False)
    _print(f"🔎 masterlib import path => {(r.stdout or '').strip()}")
    _pause_if_debug("verify_import")


    if not app_main.exists():
        raise SystemExit(f"APP_MAIN introuvable: {app_main}")

    _print(f"▶️  Launch: {app_main}")
    argv = [py, str(app_main), *sys.argv[1:]]

    # Dev UX : ouvrir une fenêtre avec 2 onglets (bootstrap log + kernel)
    if os.environ.get("BOOTSTRAP_TABS", "").strip() == "1":
        log_file = _BOOTSTRAP_LOG_FILE or (app_dir / "data/logs/bootstrap.log")
        opened = _open_tabs_window(app_dir=app_dir, log_file=log_file, kernel_argv=argv)
        if opened:
            _print("🧭 Fenêtre avec onglets ouverte (bootstrap / masterkernel).")
            _print("✅ BOOTSTRAP_TABS=1 : pas de exec(), retour au shell.")
            return 0
        _print("⚠️  BOOTSTRAP_TABS=1 demandé, mais impossible d'ouvrir un terminal. On continue en exec().")

    os.execv(py, argv)

    return 0
