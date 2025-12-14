import os
import uuid
import time
from configparser import ConfigParser

class ManagerConfig:
    def __init__(self, base_path: str, system = None , logger=None):
        self.system = system
        self.base_path = base_path
        self.logger = logger or logging.getLogger("System.Config")

        self._chemin_config = self.chemin_absolu("config_ini")
        self._chemin_uuid = self.chemin_absolu("uuid")

        self._last_config_mtime = None
        self.auto_save = True

        self.config = self.charger_config()

        #4. Initialise le système avec le chemin de base du projet.
        self.base_path = self.config.get("system", "app_path", fallback=self.base_path)
        self.logger.info(f"🔧 System init  base_path : {self.base_path}")
        
        #5. python de l'environement virtuel (venv)
        self.venv_path = self.config.get("system", "venv_path", fallback="")
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        
        self.uuid_path = self.chemin_absolu("uuid")
        self.uuid_noeud = self.get_or_create_uuid()

        self.logger.info(f"🔧 System init  base_path : {self.base_path}")
    
    def get_python_path(self) -> str:
        venv_path = self.get("system", "venv_path", fallback="")
        return os.path.join(venv_path, "bin", "python")

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)


    ##################################################################################################################
    #Fonctionne de system.py avant creation de MAnagerConfig, été fonctionnel
    def charger_config(self):
        config = ConfigParser()
        #chemin_config = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "config.ini"))
        chemin_config =self.chemin_absolu("config_ini")

        if not os.path.exists(chemin_config):
            raise FileNotFoundError(f"Fichier de configuration non trouvé : {chemin_config}")
        
        config.read(chemin_config)
        self._chemin_config = chemin_config  # on le garde pour suivi ultérieur
        self._last_config_mtime = os.path.getmtime(chemin_config)  # 🟡 ICI
        
         # 🔁 Récupération de app_path depuis config.ini (optionnel avec fallback)
        
        self.logger.info(f"🗂️ Configuration chargée depuis : {chemin_config}")
        #self.logger.info(f"📁 app_path défini sur : {self.app_path}")
        return config
    ##################################################################################################################


    ##################################################################################################################        
    def config_modifiee_depuis_derniere_lecture(self):
        mtime = os.path.getmtime(self._chemin_config)
        if mtime != self._last_config_mtime:
            self._last_config_mtime = mtime
            return True
        return False
    # ------------------------------------------------------------------------
    def recharger_config(self):
        self.config.read(self._chemin_config)
        if self.logger:
            self.logger.info("🔁 Fichier de configuration rechargé.")



    """
    #Fonction géchemin_modulenéré par chatGPT
    def controle_maj_configuration(self, callback_status=None):
        while True:
            if self.config_modifiee_depuis_derniere_lecture():
                if callback_status:
                    callback_status("Changement de config en cours")
                if self.logger:
                    self.logger.info("🔄 Changement détecté dans config.ini, rechargement...")
                self.recharger_config()
                if callback_status:
                    callback_status("Mise à jour terminée")
            else:
                if callback_status:
                    callback_status("RAS")
            time.sleep(5)
    """
    #Fonctionne de system.py avant creation de MAnagerConfig, été fonctionnel
    def controle_maj_configuration(self, noyau_ref):
        #est executer dans un thread au niveau du noyau.
        while True:
            if self.config_modifiee_depuis_derniere_lecture():
                noyau_ref.status_update_config = "Changement de config en cours"
                self.logger.info("🔄 Changement détecté dans config.ini, rechargement...")
                self.recharger_config()
                noyau_ref.status_update_config = "Mis à jour terminée"
            else:
                noyau_ref.status_update_config = "RAS"
            time.sleep(5)
    ##################################################################################################################

    def set_valeur(self, section: str, key: str, value: str):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)
        if self.auto_save:
            self.sauvegarder()

    def sauvegarder(self):
        #sauvegarde le fichier config.ini avec les nouvelles données contenue dans self.config
        with open(self._chemin_config, "w") as f:
            self.config.write(f)
        if self.logger:
            self.logger.info("💾 Fichier de configuration sauvegardé.")

    def get_or_create_uuid(self):
        uuid_path = self.chemin_absolu("uuid")

        if os.path.exists(uuid_path):
            with open(uuid_path, "r") as f:
                identifiant = f.read().strip()
                if identifiant:
                    return identifiant  # ✅ UUID existant
        # 🎲 Génération d’un nouvel UUID unique
        new_uuid = str(uuid.uuid4())
        os.makedirs(os.path.dirname(uuid_path), exist_ok=True)
        with open(uuid_path, "w") as f:
            f.write(new_uuid)
        return new_uuid

    def get_config(self):
        return self.config

    def chemin_absolu(self, element: str) -> str:
        #Retourne le chemin absolu d’un fichier ou dossier clé du projet.
        mapping = {
            "config_ini": os.path.join(self.base_path, "config", "config.ini"),
            "uuid": os.path.join(self.base_path, "config", "masterapp.uuid"),
            "log": os.path.join(self.base_path, "logs", "MasterApp.log"),
            "selecteur": os.path.join(self.base_path, "modules", "selecteur.py"),
            "system": os.path.join(self.base_path, "system", "system.py"),
            "modules": os.path.join(self.base_path, "modules"),
            "network": os.path.join(self.base_path, "network"),
            "registre_json":os.path.join(self.base_path, "config","registre_json.json"),

            "core": os.path.join(self.base_path, "core"),
            "console_management": os.path.join(self.base_path, "core" , "console_management.py"),
        }
        
        if element not in mapping:
            raise ValueError(f"Élément inconnu dans chemin_absolu(): {element}")

        return mapping[element]

    def chemin_module(self, nom_module):
        return os.path.abspath(os.path.join(self.base_path, "modules", f"{nom_module}.py"))

    def create_bloc_config(self):
        bloc_config_defaut = {"system": {
            "app_path": self.base_path,
            "venv_path": os.path.join(self.base_path, "venv")
        }} 
        for section, options in bloc_config_defaut.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)
        self.sauvegarder()