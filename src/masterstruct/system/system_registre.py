from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime
from enum import Enum
import json

class DesiredState(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    #RESTARTED = "restarted"
    #UNKNOWN = "unknown"

class EntryState(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    CRASHED = "CRASHED"

class RestartPolicy(str, Enum):
    NEVER = "NEVER"
    ON_FAILURE = "ON_FAILURE"
    ALWAYS = "ALWAYS"



# 🌟 Classe de base ultra-flexible
class RegistreEntry:
    def __init__(self, nom: str, type_objet: str = "generic", meta: dict = None):
        self.uuid_noeud = None 
        self.id = str(uuid.uuid4())         # identifiant unique
        self.nom = nom                      # identifiant logique, nom du script ex: vpn.py
        self.type = type_objet              # module, thread, subprocess,, socket unix, socket ip, etc
        self.meta = meta or {}              # Dictionnaire d'info supplémentaire
        self.timestamp = datetime.now()     # derniere mise à jour
        self.relations = []                 # liste des id d'autre obljet, mise ne relation
        self.source = ""                    # ajoute la source de chaque entrée

        self.desired_state: str = DesiredState.RUNNING.value
        self.state: str = EntryState.STARTING.value
        self.restart_policy: str = RestartPolicy.ON_FAILURE.value
        self.restart_count: int = 0
        self.last_error: Optional[str] = None

        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()


    def maj_timestamp(self):
        self.timestamp = datetime.now()
    def ajouter_relation(self, autre_id: str):
        if autre_id not in self.relations:
            self.relations.append(autre_id)
    def lier(self, autre_id : str):
        self.ajouter_relation(autre_id)
    def est_actif(self) -> bool:
        # Nouveau modèle prioritaire
        if getattr(self, "state", None):
            return self.state == EntryState.RUNNING.value
        # Fallback ancien modèle (compat)
        en_ligne = self.meta.get("en_ligne", False)
        demarrage = self.meta.get("demarrage", False)
        return bool(en_ligne) and not bool(demarrage)

    def touch(self):
        self.updated_at = datetime.utcnow()
    def set_desired(self, desired):
        # accepte "RUNNING"/"STOPPED" ou DesiredState.RUNNING
        self.desired_state = desired.value if isinstance(desired, Enum) else desired
        self.touch()
    def set_state(self, state, error: Optional[str] = None):
        # accepte "RUNNING"/... ou EntryState.RUNNING
        self.state = state.value if isinstance(state, Enum) else state
        if error:
            self.last_error = error
        self.touch()
        
    def to_dict(self) -> dict:
        return {
            "uuid_noeud":self.uuid_noeud,
            "id": self.id,
            "nom": self.nom,
            "type": self.type,
            "meta": self.meta,
            "timestamp": self.timestamp.isoformat(),
            "relations": self.relations,

            "desired_state": self.desired_state,
            "state": self.state,
            "restart_policy": self.restart_policy,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),

        }

# Spécialisation pour les services
class ConfigEntry(RegistreEntry):
    def __init__(self, name: str, config: dict):
        super().__init__(name, type_objet="config")
        self.config = config
        self.timestamp = datetime.utcnow()


    def to_dict(self):
        data = super().to_dict()
        data.update({
            "config": self.config,
            "timestamp": self.timestamp.isoformat()

        })
        return data
    
# Spécialisation pour le kernel
class KernelEntry(RegistreEntry):
    def __init__(self, name: str):
        super().__init__(name, type_objet="kernel")
        self.pid = None
        self.uptime = None
        self.timestamp = datetime.utcnow()


    def to_dict(self):
        data = super().to_dict()
        data.update({
            "pid": self.pid,
            "uptime": self.uptime,
            "timestamp": self.timestamp.isoformat()

        })
        return data

# Système d'exploitation
class SystemEntry(RegistreEntry):
    def __init__(self, name: str):
        super().__init__(name, type_objet="system")
        self.os_name = None
        self.os_version = None
        self.architecture = None
        self.timestamp = datetime.utcnow()


    def to_dict(self):
        data = super().to_dict()
        data.update({
            "os_name": self.os_name,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "timestamp": self.timestamp.isoformat()

        })
        return data

        
# Spécialisation pour subprocess
class SubprocessEntry(RegistreEntry):
    def __init__(self, name: str, pid: Optional[int] = None):
        super().__init__(name, type_objet="subprocess")
        self.pid = pid
        self.path_exec = None
        self.terminal = False
        self.demarrage = False
        self.en_cours = False
        self.en_ligne = False
        self.timestamp = datetime.utcnow()


    def est_actif(self):
        return self.en_ligne == 1 and self.demarrage == 1

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "path_exec": self.path_exec,
            "terminal": self.terminal,
            "pid": self.pid,
            "demarrage": self.demarrage,
            "en_cours": self.en_cours,
            "en_ligne": self.en_ligne,
            "actif": self.est_actif(),
            "timestamp": self.timestamp.isoformat()

        })
        return data

# Spécialisation pour threads
class ThreadEntry(RegistreEntry):
    def __init__(self, name: str):
        super().__init__(name, type_objet="thread")
        self.ident = None
        self.is_daemon = None
        #self.actif = False
        self.last_heartbeat = datetime.utcnow()
        self.timestamp = datetime.utcnow()

    # Compat : actif devient un alias de state
    @property
    def actif(self) -> bool:
        return self.state == EntryState.RUNNING.value

    @actif.setter
    def actif(self, valeur: bool):
        if valeur:
            self.set_state(EntryState.RUNNING)
        else:
            self.set_state(EntryState.STOPPED)
    def heartbeat(self):
        self.last_heartbeat = datetime.utcnow()
        self.set_state(EntryState.RUNNING)

    def etat_simplifie(self):
        return "✅ actif" if self.actif else f"❌ {self.state.lower()}"

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "ident": self.ident,
            "is_daemon": self.is_daemon,
            "actif": self.actif,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "timestamp": self.timestamp.isoformat()
        })
        return data

# Spécialisation pour réseau
class NetworkEntry(RegistreEntry):
    def __init__(self, name: str, port: int, ip: str = "127.0.0.1"):
        super().__init__(name, type_objet="network")
        self.ip = ip
        self.port = port
        self.protocol = "tcp"
        self.timestamp = datetime.utcnow()


    def to_dict(self):
        data = super().to_dict()
        data.update({
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "timestamp": self.timestamp.isoformat()

        })
        return data

# Spécialisation pour les modules de MasterAPpp
class ModuleEntry(RegistreEntry):
    def __init__(self, name: str, module):
        super().__init__(name, type_objet="module")
        self.module_nom = module
        self.meta = {"status":"inconnu"}
        self.protocol = "local"

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "module_nom": self.module_nom,
            "meta": self.meta,
            "protocol": self.protocol
        })
        return data


# Manager global du registre
class ManagerRegistre:
    def __init__(self, system = None):
        self.system = system

        self._registre: Dict[str, RegistreEntry] = {}
        self._grouped_cache: dict[str, list[tuple]] = {}
        """
        try:
            entry.uuid_noeud = self.system.uuid_noeud
        except AttributeError:
            if self.system and self.system.logger:
                self.system.logger.warning("[⚠️] uuid_noeud non disponible lors de l'ajout au registre.")
        """

    #############################################################
    # Commande principale du registre
    def creer_subprocess(self, nom: str, chemin_exec: str, terminal: bool) -> SubprocessEntry:
        """Crée et ajoute une entrée SubprocessEntry dans le registre."""
        entry = SubprocessEntry(nom)
        entry.path_exec = chemin_exec
        entry.terminal = terminal
        entry.demarrage = True
        entry.en_cours = True
        self.ajouter(entry)

        return entry

    def ajouter(self, entry: RegistreEntry):
        if self.system:
            entry.uuid_noeud = self.system.uuid_noeud

        self._registre[entry.id] = entry
        self.lier_automatiquement(entry)  # auto-relation intelligente
        
    def supprimer(self, identifiant: str):
        if identifiant in self._registre:
            self._registre.pop(identifiant)
            self.system.logger.debug(f"[🗑️] Entrée supprimée par ID : {identifiant}")
            return

        ids_a_supprimer = [
            id_ for id_, entry in self._registre.items()
            if entry.nom == identifiant
        ]
        for id_ in ids_a_supprimer:
            self._registre.pop(id_)
            self.system.logger.debug(f"[🗑️] Entrée supprimée par nom : {identifiant} (ID {id_})")
        
        # Supprimer aussi les relations vers cette entrée
        for id_, entry in self._registre.items():
            if identifiant in entry.relations:
                entry.relations.remove(identifiant)

    def modifier(self, id: str, **nouvelles_valeurs) -> bool:
        """
        Met à jour les champs d'une entrée identifiée par son id.
        Retourne True si une modification a été faite, False sinon.
        """
        entree = self._registre.get(id)
        if not entree:
            self.system.logger.warning(f"[🛑] Impossible de modifier — ID introuvable : {id}")
            return False

        modifie = False
        for cle, valeur in nouvelles_valeurs.items():
            if hasattr(entree, cle) and getattr(entree, cle) != valeur:
                setattr(entree, cle, valeur)
                modifie = True

        if modifie:
            entree.timestamp = datetime.utcnow()
            self.system.logger.info(f"[🔄] Entrée modifiée : {entree.nom} (ID {entree.id})")

        return modifie

        
    #############################################################
    # Accesseur 
    def get_by_id(self, id_: str) -> Optional[RegistreEntry]:
        return self._registre.get(id_)

    def get_by_name(self, nom: str) -> List[RegistreEntry]:
        return [entry for entry in self._registre.values() if entry.nom == nom]

    def get_by_type(self, type_objet: str) -> List[RegistreEntry]:
        return [entry for entry in self._registre.values() if entry.type == type_objet]

    def get_modifies_depuis(self, since: datetime):
        return [r for r in self._registre.values() if r.timestamp > since]

    def get_relations(self, identifiant: str) -> list[RegistreEntry]:
        """
        Retourne les objets liés à un identifiant (id ou nom).
        """
        # Recherche par id ou nom
        entree = self._registre.get(identifiant)
        if not entree:
            # Recherche par nom si id introuvable
            for item in self._registre.values():
                if item.nom == identifiant:
                    entree = item
                    break

        if not entree:
            self.system.logger.warning(f"[📛] Aucun registre trouvé pour : {identifiant}")
            return []

        # Résolution des relations
        relations = []
        for related_id in getattr(entree, "relations", []):
            related = self._registre.get(related_id)
            if related:
                relations.append(related)

        return relations

    def get_etat_registre(self, grouped = True) -> list[tuple]:
        """Retourne une liste d’entrées formatées pour affichage dans le manager"""
        donnees = []
        self._grouped_cache = {}

        #type_str = getattr(entry, "type", "❓")
        #pid = str(getattr(entry, "pid", "—"))

        for entry in self._registre.values():
            type_str = entry.type
            nom = entry.nom

            # PID ou identifiant thread
            pid = "—"
            if hasattr(entry, "pid") and entry.pid is not None:
                pid = str(entry.pid)
            elif hasattr(entry, "ident") and entry.ident is not None:
                pid = str(entry.ident)

            # État (via méthode .est_actif() si disponible)
            etat = "—"
            if hasattr(entry, "est_actif") and callable(entry.est_actif):
                etat = "✅ actif" if entry.est_actif() else "❌ inactif"

            # Relations
            rel_count = len(entry.relations) if entry.relations else 0
            rel_str = f"{rel_count} lien(s)" if rel_count else "—"

            # Horodatage
            horodatage = entry.timestamp.strftime("%H:%M:%S")

            # Parent (si une relation pointe vers un module)
            parent = "—"
            for rel_id in entry.relations:
                parent_entry = self._registre.get(rel_id)
                if parent_entry and parent_entry.type == "module":
                    parent = parent_entry.nom
                    break

            ligne = (type_str, nom, pid, etat, parent, rel_str, horodatage)


            if grouped:
                if type_str not in self._grouped_cache:
                    self._grouped_cache[type_str] = []
                self._grouped_cache[type_str].append(ligne)
            else:
                donnees.append(ligne)

        return self._grouped_cache if grouped else donnees


    def tous(self) -> List[RegistreEntry]:
        return list(self._registre.values())

    def mettre_a_jour_meta(self, id_: str, cle: str, valeur):
        registre = self.get_by_id(id_)
        if registre:
            registre.meta[cle] = valeur
            registre.maj_timestamp()
            return True
        return False


    def to_dict(self):
        return {id_: reg.to_dict() for id_, reg in self._registre.items()}

    ##########################################################################
    # Mise en relations des différents dict {}
    def lier(self, id1: str, id2: str):
        r1 = self.get_by_id(id1)
        r2 = self.get_by_id(id2)
        if r1 and r2:
            r1.ajouter_relation(id2)
            r2.ajouter_relation(id1)
            r1.maj_timestamp()
            r2.maj_timestamp()
    
    def lier_automatiquement(self, nouvelle_entree: RegistreEntry):
        nom = nouvelle_entree.nom
        id_nouvel = nouvelle_entree.id

        for autre_id, autre in self._registre.items():
            if autre.id == id_nouvel:
                continue

            # Ex : tous ceux qui partagent le même nom de base
            if autre.nom == nom or autre.nom.startswith(nom) or nom.startswith(autre.nom):
                nouvelle_entree.lier(autre.id)
                autre.lier(nouvelle_entree.id)

                self._registre[autre.id] = autre
                self._registre[nouvelle_entree.id] = nouvelle_entree


    ##########################################################################
    # Extraction to_json
    def to_json(self, indent=2) -> str:
        try:
            donnees = {}
            for k, v in self._registre.items():
                try:
                    donnees[k] = v.to_dict()
                    if self.system and self.system.logger:
                        self.system.logger.debug(f"[↪️] Sérialisation de l'entrée : {v.nom} ({v.type})")
                except Exception as e:
                    if self.system and self.system.logger:
                        self.system.logger.warning(f"[⚠️] Échec de sérialisation pour : {v.nom} — {e}")
            json_str = json.dumps(donnees, indent=indent)
            if self.system and self.system.logger:
                self.system.logger.info(f"[✅] Registre converti en JSON ({len(donnees)} entrées)")
            return json_str
        except Exception as e:
            if self.system and self.system.logger:
                self.system.logger.error(f"[❌] Erreur globale lors de la conversion JSON : {e}")
            return "{}"

    def sauvegarder_json(self, chemin_fichier: str):
        """
        Sauvegarde le registre complet dans un fichier JSON.
        """
        try:
            json_data = self.to_json()
            with open(chemin_fichier, "w") as f:
                f.write(json_data)
            if self.system and self.system.logger:
                self.system.logger.info(f"[💾] Registre sauvegardé dans {chemin_fichier}")
        except Exception as e:
            if self.system and self.system.logger:
                self.system.logger.error(f"[❌] Échec de la sauvegarde JSON : {e}")

    ##########################################################################

