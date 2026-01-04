#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
masterboot/cli.py

RÔLE
----
Point d'entrée CLI officiel du socle (repo MasterLib).

Ce module expose la commande console `master` (définie dans pyproject.toml)
et sert d'interface humaine/OS vers le processus de contrôle `masterboot`.

RESPONSABILITÉS
---------------
- Parser les arguments de ligne de commande.
- Mapper les sous-commandes vers les actions masterboot (start/stop/status/init).
- Résoudre un minimum de contexte (ex: répertoire courant), sans implémenter
  la logique de boot (celle-ci appartient à masterboot.controller).

RÈGLES D'OR
-----------
- Aucune logique kernel ici (pas de registre, pas de bus, pas de sockets).
- Aucune logique "workspace" ici (création data/, logs, etc.).
- Le CLI doit rester stateless : il délègue à ProjectController et sort.

SÉQUENCE (résumé)
-----------------
Utilisateur -> `master ...` -> masterboot.cli -> ProjectController -> masterkernel

EXEMPLES
--------
- master start
- master start reinerouge
- master status
- master stop

NOTES
-----
Ce fichier est volontairement simple. Toute complexité (reconnexion, idempotence,
démarrage kernel, supervision) vit dans masterboot/controller.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import traceback



def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="master",
        description="CLI du socle MasterLib (boot + contrôle + kernel).",
    )

    sub = p.add_subparsers(dest="command", required=True)

    # --- start ---
    p_start = sub.add_parser(
        "start",
        help="Démarre ou reconnecte un projet (via masterboot).",
    )
    p_start.add_argument(
        "project_name",
        nargs="?",
        default=None,
        help="Nom du projet à démarrer (optionnel si config_projet.ini existe dans le dossier courant).",
    )
    p_start.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Chemin explicite vers un fichier config_projet.ini (optionnel).",
    )
    p_start.add_argument(
        "--project-root",
        dest="project_root",
        default=None,
        help="Dossier racine du projet (par défaut: dossier courant).",
    )
    p_start.add_argument(
        "--debug",
        action="store_true",
        help="Active un mode debug côté masterboot (logs plus verbeux).",
    )

    # --- status ---
    p_status = sub.add_parser(
        "status",
        help="Affiche l'état du projet (via masterboot/kernel).",
    )
    p_status.add_argument(
        "project_name",
        nargs="?",
        default=None,
        help="Nom du projet (optionnel si lancé depuis le dossier projet).",
    )
    p_status.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Chemin explicite vers un fichier config_projet.ini (optionnel).",
    )
    p_status.add_argument(
        "--project-root",
        dest="project_root",
        default=None,
        help="Dossier racine du projet (par défaut: dossier courant).",
    )

    # --- stop ---
    p_stop = sub.add_parser(
        "stop",
        help="Demande l'arrêt du projet (via masterboot/kernel).",
    )
    p_stop.add_argument(
        "project_name",
        nargs="?",
        default=None,
        help="Nom du projet (optionnel si lancé depuis le dossier projet).",
    )
    p_stop.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Chemin explicite vers un fichier config_projet.ini (optionnel).",
    )
    p_stop.add_argument(
        "--project-root",
        dest="project_root",
        default=None,
        help="Dossier racine du projet (par défaut: dossier courant).",
    )

    # --- init (optionnel mais pratique) ---
    p_init = sub.add_parser(
        "init",
        help="Initialise un dossier projet (crée config_projet.ini + data/).",
    )
    p_init.add_argument(
        "project_name",
        nargs="?",
        default=None,
        help="Nom du projet (optionnel si dossier courant).",
    )
    p_init.add_argument(
        "--project-root",
        dest="project_root",
        default=None,
        help="Dossier racine du projet (par défaut: dossier courant).",
    )

    return p


def _resolve_project_root(arg_project_root: str | None) -> Path:
    if arg_project_root:
        return Path(arg_project_root).expanduser().resolve()
    return Path.cwd().resolve()


def _resolve_config_path(project_root: Path, arg_config_path: str | None) -> Path | None:
    if arg_config_path:
        return Path(arg_config_path).expanduser().resolve()
    # Convention : config_projet.ini à la racine du projet
    candidate = project_root / "config_projet.ini"
    return candidate if candidate.exists() else None


def _set_boot_env(debug: bool) -> None:
    """
    Passe des flags simples à masterboot via variables d'environnement.
    (le CLI reste stateless, pas d'objet global).
    """
    if debug:
        os.environ["MASTERBOOT_DEBUG"] = "1"


def _cmd_start(args: argparse.Namespace) -> int:
    _set_boot_env(bool(args.debug))

    project_root = _resolve_project_root(args.project_root)
    config_path = _resolve_config_path(project_root, args.config_path)
    project_name = args.project_name

    # Import tardif : évite de charger masterboot si on ne l'utilise pas,
    # et réduit les effets de bord éventuels.
    from masterboot.controller import ProjectController  # type: ignore

    ctl = ProjectController(
        project_root=project_root,
        project_name=project_name,
        config_path=config_path,
    )

    try:
        return ctl.start()
    except Exception as e:
        tb = traceback.format_exc()
        _print(f"[BOOT] ❌ erreur: {e!r}")
        print(tb)
        return 1

    """
    try:
        # si paths est dispo, log direct
        from .controller import _log
        _log(ctl.paths, tb)
    except Exception:
        pass
    raise
    """


def _cmd_status(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args.project_root)
    config_path = _resolve_config_path(project_root, args.config_path)
    project_name = args.project_name

    from masterboot.controller import ProjectController  # type: ignore

    ctl = ProjectController(
        project_root=project_root,
        project_name=project_name,
        config_path=config_path,
    )
    info = ctl.status()

    # Affichage volontairement simple (ASCII).
    # Rich viendra plus tard dans masterkernel/ihm ou un module dédié.
    print(info)
    return 0


def _cmd_stop(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args.project_root)
    config_path = _resolve_config_path(project_root, args.config_path)
    project_name = args.project_name or project_root.name

    from masterboot.controller import ProjectController  # type: ignore

    ctl = ProjectController(
        project_root=project_root,
        project_name=project_name,
        config_path=config_path,
    )
    return ctl.stop()


def _cmd_init(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args.project_root)
    project_name = args.project_name or project_root.name

    from masterboot.controller import ProjectController  # type: ignore

    ctl = ProjectController(
        project_root=project_root,
        project_name=project_name,
        config_path=None,
    )
    return ctl.init_project()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    if ns.command == "start":
        return _cmd_start(ns)
    if ns.command == "status":
        return _cmd_status(ns)
    if ns.command == "stop":
        return _cmd_stop(ns)
    if ns.command == "init":
        return _cmd_init(ns)

    # Normalement impossible grâce à required=True sur subparsers
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
