#!/usr/bin/env python3

import os
import time
import subprocess
import traceback
from masterstruct.system.system_registre import RegistreEntry
from configparser import NoOptionError

class ModuleScanner:
    """
    Classe dédiée au scan cyclique des modules dans MasterApp.
    Elle tourne en thread autonome et permanent.
    Utilise le logger et le config de l'instance système passée au constructeur.
    """

    def __init__(self, system, modules_path="modules"):
        self.system = system

        self.modules_path = self.system.chemin_absolu(modules_path)

        self.config_manager = self.system.config_manager
        self.config_parser = self.system.config_manager.get_config()
        self.config_path = self.system.chemin_absolu("config_ini")

        #Module Scanner running
        self._stop = False

    def prompt_x(self) -> str:
        return """
        📦 Classe : ModuleScanner
        Rôle :      Scanner cycliquement les modules internes de MasterApp.
        Fonction :  Thread permanent, non conditionné par config.ini.
        Lancement:  via 'thread_manager.run("module_scanner", lambda: ModuleScanner(system).run())'
        Instructions IA :
        - Ne jamais désactiver sauf arrêt de MasterApp.
        - Logger proprement toutes les erreurs.
        - Ne pas interagir avec les sockets.
        - Peut être enrichi avec une logique de reload dynamique.
        Argument:
            - self.system.running : Si True, le programme MaserApp s'arrete
            - self._stop : Si True signal de demande d'arret mis à True, lors de l'appelle de stop()
        
        Methode :
        - lister_modules_disponibles() : Liste les dossiers valides dans /modules
        - mettre_a_jour_config() : Ajoute les modules présents et marque ceux disparus
        - lancer_modules_actifs() : Démarrer les modules qui ont pour valeur dans MasterApp/config/config.ini à la section [modules] une valeur à True
        - enregistrer_module_dans_registre(module: str) : ajoute le module à la class ManagerRegistre
        - run() : boucle principale de la class ModuleScanner qui es executer dans un thread par le noyau et géré par la class System.
        - stop() : signal d'arret, utilisé pour redemarrer ModuleScanner si besoin
        """

    def lister_modules_disponibles(self):
        """Liste les dossiers valides dans /modules"""
        return [
            d for d in os.listdir(self.modules_path)
            if os.path.isdir(os.path.join(self.modules_path, d)) and not d.startswith("__")
        ]

    def mettre_a_jour_config(self):
        """Ajoute les modules présents et marque ceux disparus"""
        """
        old:
        if "modules" not in self.config:
            self.config["modules"] = {}
        """

        modules_sur_disque = self.lister_modules_disponibles()

        if not self.config_parser.has_section("modules"):
            self.config_parser.add_section("modules")

        clefs_ini = set(self.config_parser.options("modules"))
        modifications = False

        # Ajouter nouveaux modules
        for module in modules_sur_disque:
            if module not in clefs_ini:
                self.config_parser.set("modules", module, "false")
                self.system.logger.info(f"📦 Nouveau module détecté : {module} — ajouté désactivé")
                self.enregistrer_module_dans_registre(module)  # 👈 Ajout ici
                modifications = True


        # Marquer les modules supprimés du disque
        for module in clefs_ini:
            if module not in modules_sur_disque:
                valeur = self.config_parser.get("modules", module)
                if not valeur.endswith("_absent"):
                    self.config_parser.set("modules", module, valeur + "_absent")
                    self.system.logger.warning(f"⚠️ Module absent physiquement : {module} — marqué _absent")
                    modifications = True

        if modifications:
            self.config_manager.sauvegarder()

    def lancer_modules_actifs(self):
        """
        Lance tous les modules marqués comme 'true' dans la section [modules] de la config.
        """
        for module in self.config_parser.options("modules"):
            actif = self.config_parser.get("modules", module)

            try:
                self.system.logger.debug(f"[🕵️] Vérification du statut du module '{module}'")
                if actif.lower() == "true" and not self.system.process_manager.est_enregistre_et_vivant(module):
                    chemin_script = os.path.join(self.modules_path, module, f"{module}.py")
                    chemin_module_absolu = os.path.join(self.modules_path, module)
                    if os.path.exists(chemin_script):
                        self.system.logger.info(f"🚀 Lancement du module noyau : {module}")
                        self.system.process_manager.run(                                        
                            name=module,
                            chemin_module=chemin_module_absolu,
                            terminal_visible= True  # ou True pour debug    
                        )
                    else:
                        self.system.logger.warning(f"⚠️ Fichier d'entrée introuvable pour le module : {chemin}")
                        self.system.logger.error(f"📋 Trace:\n{traceback.format_exc()}")
            except Exception as e :
                self.system.logger.error(f"[❌] Erreur lors du traitement du module '{module}' : {e}")
                self.system.logger.debug(traceback.format_exc())
        
    def enregistrer_module_dans_registre(self, module: str):
        from system.system_registre import ModuleEntry

        # Vérifie si une entrée existe déjà
        deja_enregistre = any(

            #old. entry.nom == module and entry.type == "module"
            getattr(entry, "nom", None) == module and getattr(entry, "type", None) == "module"

            for entry in self.system.registre.tous()
        )

        if not deja_enregistre:
            entry = ModuleEntry(module, module)
            self.system.registre.ajouter(entry)
            self.system.logger.info(f"[📘] Module '{module}' ajouté au registre.")

    def run(self):
        """Module ModuleScanner instancié dans un thread"""
        try:
            while not self._stop and self.system.running:
                self.system.logger.debug("🔄 ModuleScanner : cycle actif")

                self.mettre_a_jour_config()
                self.lancer_modules_actifs()
                time.sleep(5)

        except Exception as e:
            self.system.logger.error(f"[❌] Erreur fatale dans ModuleScanner : {e}")
        finally:
            if self._stop:
                self.system.logger.info("🛑 ModuleScanner : signal d’arrêt local reçu")
            else:
                self.system.logger.info("🛑 ModuleScanner terminé.")

    def lancer_scan_initial(self):
        """Scan unique pour lancement initial (si besoin en mode bloquant)"""
        self.mettre_a_jour_config()
        self.lancer_modules_actifs()

    def stop(self):
        self.system.logger.info("🛑 ModuleScanner : signal d’arrêt reçu")
        self._stop = True
