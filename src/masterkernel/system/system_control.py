#!/usr/bin/env python3
import re
import pkgutil
import ast
import os
import sys
import subprocess
import importlib
import logging

# Dossier racine du projet
DOSSIER_SOURCE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Modules internes à ignorer
EXCLUSIONS = {
    "sys", "os", "time", "logging", "json", "datetime", "math",
    "builtins", "configparser", "shutil", "subprocess", "importlib",
    "ast", "threading", "keyboard","core","noyau","variation_analyzer","ia_core",
}
logger = None

def setup_logger_brut():
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(logs_dir, exist_ok=True)  # <-- important

    #log du programme
    log_path = os.path.join(logs_dir, "verificateur_dependances.log")  

    logger = logging.getLogger("verificateur")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - [verificateur] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def lister_fichiers_py(dossier):
    fichiers = []
    for root, _, files in os.walk(dossier):
        for file in files:
            if file.endswith(".py"):
                fichiers.append(os.path.join(root, file))
    return fichiers

def extraire_imports(fichier):
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=fichier)
    except Exception as e:
        logger.info(f"⚠️ Erreur d'analyse AST pour {fichier} : {e}")
        return set()
    imports = set()
    for elem in ast.walk(node):
        if isinstance(elem, ast.Import):
            for alias in elem.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(elem, ast.ImportFrom):
            if elem.module:
                imports.add(elem.module.split('.')[0])
    return imports

def verifier_et_installer(imports):
    for module in sorted(imports):
        if module in EXCLUSIONS:
            continue
        try:
            importlib.import_module(module)
            logger.info(f"✅ {module} déjà installé.")
        except ImportError:
            logger.info(f"📦 Installation de : {module}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", module])
            except subprocess.CalledProcessError:
                logger.warning(f"❌ Impossible d’installer le module : {module}")

def main():
    global logger
    logger = setup_logger_brut()



    fichiers = lister_fichiers_py(DOSSIER_SOURCE)
    logger.info("\n🔍 Fichiers .py trouvés dans MasterApp :")
    for fichier in fichiers:
        logger.info(f" - {fichier}")

    tous_les_imports = set()
    for fichier in fichiers:
        tous_les_imports.update(extraire_imports(fichier))

    logger.info(f"\n📦 Modules à vérifier :{ sorted(tous_les_imports) }")
    verifier_et_installer(tous_les_imports)

if __name__ == "__main__":
    main()
