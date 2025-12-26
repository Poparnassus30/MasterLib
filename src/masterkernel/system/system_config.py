# -*- coding: utf-8 -*-
"""
ManagerConfig
- Charge config/config.ini
- Auto-bootstrap si absent
- UUID stocké DANS config.ini (section [node])
- Ajoute un header de version par défaut en commentaire en tête de fichier
"""

from __future__ import annotations

import os
import uuid
import time
import logging
from datetime import datetime, timezone
from configparser import ConfigParser
from typing import Optional


class ManagerConfig:
    DEFAULT_CONFIG_VERSION = "1.0"
    HEADER_MARKER = "MASTERLIB_DEFAULT_CONFIG_VERSION"

    def __init__(self, base_path: str, system=None, logger=None):
        self.system = system
        self.base_path = base_path
        self.logger = logger or logging.getLogger("System.Config")

        self._chemin_config = self.chemin_absolu("config_ini")
        self._last_config_mtime = None
        self.auto_save = True

        # 1) S'assure que config.ini existe (bootstrap)
        self._ensure_config_file()

        # 2) Ajoute un header de version (commentaire) si absent
        self._ensure_header()

        # 3) UUID dans config.ini (généré si manquant)
        self._ensure_uuid_in_config()

        # 4) Charge la config en mémoire
        self.config = self.charger_config()

        # 5) Base path peut être surchargé par config.ini (optionnel)
        self.base_path = self.config.get("system", "app_path", fallback=self.base_path)
        self.logger.info(f"🔧 System init  base_path : {self.base_path}")

        # 6) Python de l'environnement virtuel
        self.venv_path = self.config.get("system", "venv_path", fallback="") or self._detect_venv_path()
        self.python_path = os.path.join(self.venv_path, "bin", "python") if self.venv_path else ""

        # 7) UUID node
        self.uuid_noeud = self.get("node", "uuid", fallback=None)
        if not self.uuid_noeud:
            # sécurité : ne devrait pas arriver car _ensure_uuid_in_config le met
            self.uuid_noeud = str(uuid.uuid4())
            self.set_valeur("node", "uuid", self.uuid_noeud)

    def get_or_create_uuid(self) -> str:
        """Retourne l'UUID du node depuis config.ini, le génère et le sauvegarde s'il manque."""
        section = "node"
        key = "uuid"

        if not self.config.has_section(section):
            self.config.add_section(section)

        uid = (self.config.get(section, key, fallback="") or "").strip()
        if not uid:
            uid = str(uuid.uuid4())
            self.config.set(section, key, uid)

            # Sauvegarde (utilise ta méthode existante si tu l'as)
            if hasattr(self, "sauvegarder_config"):
                self.sauvegarder_config()
            elif hasattr(self, "save"):
                self.save()
            else:
                # fallback simple
                with open(self.config_path, "w", encoding="utf-8") as f:
                    self.config.write(f)

            self.logger.info(f"🆔 UUID généré et stocké dans config.ini : {uid}")

        return uid

    def get_python_path(self) -> str:
        venv_path = self.get("system", "venv_path", fallback="") or self._detect_venv_path()
        return os.path.join(venv_path, "bin", "python") if venv_path else "python3"

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)

    # ---------------------------------------------------------------------
    # Bootstrapping config.ini
    def _ensure_config_file(self) -> None:
        """Crée config/config.ini si absent.
        - Priorité : config/config_default.ini ou config/config_defaut.ini si présent
        - Sinon : crée un minimal fonctionnel (system + node + metier).
        """
        config_path = self._chemin_config
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)

        if os.path.exists(config_path):
            return

        template = self._find_template()
        if template:
            with open(template, "r", encoding="utf-8") as src, open(config_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            self.logger.info(f"🧩 config.ini généré depuis template : {template}")
        else:
            venv_path = self._detect_venv_path()
            node_uuid = str(uuid.uuid4())
            minimal = self._minimal_config_text(app_path=self.base_path, venv_path=venv_path, node_uuid=node_uuid)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(minimal)
            self.logger.info(f"🧩 config.ini créé (minimal) : {config_path}")

    def _find_template(self) -> Optional[str]:
        candidates = [
            os.path.join(self.base_path, "config", "config_default.ini"),
            os.path.join(self.base_path, "config", "config_defaut.ini"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _minimal_config_text(self, app_path: str, venv_path: str, node_uuid: str) -> str:
        header = self._header_text()
        return (
            header
            + "\n"
            + "[system]\n"
            + f"app_path = {app_path}\n"
            + (f"venv_path = {venv_path}\n" if venv_path else "venv_path =\n")
            + "\n"
            + "[node]\n"
            + f"uuid = {node_uuid}\n"
            + "\n"
            + "[metier]\n"
            + "; paramètres spécifiques au programme métier (ex: caméra, UI, robot, etc.)\n"
        )

    def _detect_venv_path(self) -> str:
        # 1) env var (le plus fiable si start.sh active bien le venv)
        env = os.environ.get("VIRTUAL_ENV")
        if env and os.path.isdir(env):
            return env

        # 2) dossiers standards
        for candidate in (".venv", "venv"):
            p = os.path.join(self.base_path, candidate)
            if os.path.isdir(p):
                return p
        return ""

    # ---------------------------------------------------------------------
    # Header version (commentaire en tête)
    def _header_text(self) -> str:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return (
            f"; {self.HEADER_MARKER}={self.DEFAULT_CONFIG_VERSION}\n"
            f"; generated_utc={now}\n"
            "; note: ce fichier est local (non versionné), il peut contenir un UUID machine\n"
        )

    def _ensure_header(self) -> None:
        path = self._chemin_config
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return

        if self.HEADER_MARKER in content[:300]:
            return  # déjà présent (on check juste le début)

        header = self._header_text() + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + content)
        self.logger.info("📝 Header version ajouté en tête de config.ini")

    # ---------------------------------------------------------------------
    # UUID dans config.ini (section [node])
    def _ensure_uuid_in_config(self) -> None:
        path = self._chemin_config
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_node = False
        node_found = False
        uuid_line_idx = None
        node_header_idx = None

        def is_section(line: str) -> bool:
            s = line.strip()
            return s.startswith("[") and s.endswith("]")

        for i, line in enumerate(lines):
            stripped = line.strip()

            if is_section(line):
                in_node = (stripped.lower() == "[node]")
                if in_node:
                    node_found = True
                    node_header_idx = i
                continue

            if in_node:
                if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                    continue
                if stripped.lower().startswith("uuid"):
                    uuid_line_idx = i
                    break

        new_uuid = str(uuid.uuid4())

        if not node_found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines += ["\n", "[node]\n", f"uuid = {new_uuid}\n"]
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            self.logger.info("🎲 UUID généré et ajouté (nouvelle section [node])")
            return

        if uuid_line_idx is None:
            insert_at = node_header_idx + 1 if node_header_idx is not None else len(lines)
            lines.insert(insert_at, f"uuid = {new_uuid}\n")
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            self.logger.info("🎲 UUID généré et ajouté dans [node]")
            return

        current = lines[uuid_line_idx].split("=", 1)
        if len(current) == 2 and current[1].strip():
            return  # déjà OK

        lines[uuid_line_idx] = f"uuid = {new_uuid}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        self.logger.info("🎲 UUID généré (remplacement uuid vide)")

    # ---------------------------------------------------------------------
    # Chargement / rechargement
    def charger_config(self):
        config = ConfigParser()
        chemin_config = self._chemin_config

        if not os.path.exists(chemin_config):
            self._ensure_config_file()

        config.read(chemin_config)
        self._last_config_mtime = os.path.getmtime(chemin_config)

        self.logger.info(f"🗂️ Configuration chargée depuis : {chemin_config}")
        return config

    def config_modifiee_depuis_derniere_lecture(self):
        mtime = os.path.getmtime(self._chemin_config)
        if mtime != self._last_config_mtime:
            self._last_config_mtime = mtime
            return True
        return False

    def recharger_config(self):
        self.config.read(self._chemin_config)
        if self.logger:
            self.logger.info("🔁 Fichier de configuration rechargé.")

    def controle_maj_configuration(self, noyau_ref):
        def push_config_status_to_registre(status: str, state: str = None, error: str = None):
            """Miroir snapshot dans le registre pour Rich (évite de dépendre de variables volatiles)."""
            try:
                entries = noyau_ref.system.registre.get_by_name("config")
                if not entries:
                    return
                cfg = entries[0]

                # évite d'écrire si rien n'a changé
                if cfg.meta.get("status") == status and (state is None or cfg.state == state) and error is None:
                    return

                cfg.meta["status"] = status
                if error:
                    cfg.last_error = error
                if state:
                    cfg.set_state(state)
                else:
                    cfg.touch()
            except Exception:
                # pas de crash du watcher si le registre n'est pas prêt
                pass

        while True:
            try:
                if self.config_modifiee_depuis_derniere_lecture():
                    noyau_ref.status_update_config = "Changement de config en cours"
                    push_config_status_to_registre("Changement de config en cours", state="RUNNING")

                    self.logger.info("🔄 Changement détecté dans config.ini, rechargement...")
                    self.recharger_config()

                    noyau_ref.status_update_config = "Mis à jour terminée"
                    push_config_status_to_registre("Mis à jour terminée", state="RUNNING")
                else:
                    noyau_ref.status_update_config = "RAS"
                    push_config_status_to_registre("RAS", state="RUNNING")

            except Exception as e:
                noyau_ref.status_update_config = f"Erreur de mise à jour : {e}"
                push_config_status_to_registre(f"Erreur de mise à jour : {e}", state="CRASHED", error=str(e))
                self.logger.error(f"❌ Erreur lors du rechargement de la config : {e}")

        time.sleep(5)



    # ---------------------------------------------------------------------
    # Ecriture (ConfigParser ne préserve pas les commentaires internes)
    def set_valeur(self, section: str, key: str, value: str):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        if self.auto_save:
            self.sauvegarder()

    def sauvegarder(self):
        header = ""
        try:
            with open(self._chemin_config, "r", encoding="utf-8") as f:
                existing = f.read()
            if self.HEADER_MARKER in existing[:500]:
                head_lines = []
                for line in existing.splitlines(True):
                    if line.strip().startswith("["):
                        break
                    head_lines.append(line)
                header = "".join(head_lines).rstrip() + "\n\n"
        except Exception:
            header = self._header_text() + "\n"

        from io import StringIO
        buf = StringIO()
        self.config.write(buf)
        body = buf.getvalue()

        with open(self._chemin_config, "w", encoding="utf-8") as f:
            f.write(header + body)

        self._ensure_header()

        if self.logger:
            self.logger.info("💾 Fichier de configuration sauvegardé.")

    def chemin_absolu(self, element: str) -> str:
        mapping = {
            "config_ini": os.path.join(self.base_path, "config", "config.ini"),
            "log": os.path.join(self.base_path, "logs", "MasterApp.log"),
            "selecteur": os.path.join(self.base_path, "modules", "selecteur.py"),
            "system": os.path.join(self.base_path, "system", "system.py"),
            "modules": os.path.join(self.base_path, "modules"),
            "network": os.path.join(self.base_path, "network"),
            "registre_json": os.path.join(self.base_path, "config", "registre_json.json"),
            "core": os.path.join(self.base_path, "core"),
            "console_management": os.path.join(self.base_path, "core", "console_management.py"),
        }

        if element not in mapping:
            raise ValueError(f"Élément inconnu dans chemin_absolu(): {element}")

        return mapping[element]

    def chemin_module(self, nom_module):
        return os.path.abspath(os.path.join(self.base_path, "modules", f"{nom_module}.py"))
