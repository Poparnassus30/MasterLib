"""
cli.py — Stub universel pour projets MasterLib/MasterKernel

But
---
Fichier CLI minimal à copier dans chaque projet métier.
Il délègue le démarrage à `masterlib.bootstrap.run_project_cli()`.

Hypothèses
----------
- Le projet possède un `main.py` à la racine (même 2 lignes).
- La venv est activée quand tu lances la commande du projet.

Comportement
------------
- Mode AUTO :
  - Si MasterLib locale existe (MASTERLIB_LOCAL / ../MasterLib / /home/poparnassus/github/MasterLib) :
    => utilisation SANS git pull/reset (safe pour dev non committé)
  - Sinon :
    => utilisation d'un cache jetable (~/.cache/<app>/deps/MasterLib) avec sync (fetch/reset hard)
  - Offline :
    => si fetch échoue, on utilise le cache existant

À configurer dans le projet
aprés copie du fichier , le renommée en cli.py
---------------------------
Dans pyproject.toml (exemple) :
[project.scripts]
<nom_commande> = "cli:main"
"""

from __future__ import annotations
from pathlib import Path

from masterlib.bootstrap import run_project_cli

def _guess_names() -> tuple[Path, str]:
    """
    Suppose:
    - ce fichier est dans <package>/cli.py
    - le repo est le parent du package
    """
    pkg_dir = Path(__file__).resolve().parent          # .../reinerouge
    app_dir = pkg_dir.parents[2]                           # .../<repo>
    pkg_name = pkg_dir.name                            # "reinerouge"
    return app_dir, pkg_name

def _project_name(pkg_name: str, default: str) -> str:
    try:
        from importlib.metadata import metadata
        return (metadata(pkg_name).get("Name") or "").strip() or default
    except Exception:
        return default

def main() -> int:
    app_dir, pkg_name = _guess_names()
    app_name = _project_name(pkg_name, default=app_dir.name)
    return run_project_cli(app_dir=app_dir, app_name=app_name)

if __name__ == "__main__":
    raise SystemExit(main())
