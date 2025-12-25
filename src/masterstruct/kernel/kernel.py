#!/usr/bin/env python3
import logging
import time
import os
import threading
import sys
from pathlib import Path    
from masterstruct.system.system import System
from masterstruct.kernel.kernel_ihm import NoyauManager
from masterstruct.kernel.kernel_module import ModuleScanner

#CORE INTELIGENCE
class Kernel:
    def __init__(self, ctx) -> None:
        # Initialisation du noyau avec le contexte fourni.
        self.ctx = ctx

        #Initialise le noyau avec une instance du système.
        #chemin_absolu = Path(__file__).resolve().parent.parent
        #self.system = System(base_path=str(chemin_absolu))
        self.system = getattr(ctx, "system", None)
        if self.system is None and isinstance(ctx, dict):
            self.system = ctx.get("system")

        if self.system is None:
            raise RuntimeError("ctx.system manquant : runtime doit fournir System")

        self.logger = getattr(self.system, "logger", logging.getLogger("Kernel"))

        #Variable de status
        self.live_mode = True
        self.status_update_config = "None"
        self.running = False
        self.stopping = False

        #self.logger = self.system.logger
        #self.config = self.system.get_config()
        #variable de debug visuel pour noyau_manager.py #False = pas de menu afficher dynamiquement
        #self.live_mode = True

        #Socket du noyau pour les processus enfants de MAsterApp
        self.socket_interface = None
        try:
            from masterstruct.kernel.kernel_socket import NoyauSocket
            self.socket_interface = NoyauSocket(self)
        except ImportError as e:
            self.logger.error(f"❌ Impossible d’importer NoyauSocket : {e}")
        
        #self.uuid = self.system.get_or_create_uuid()
        #self.update_manager = None
        #self.network_node = None
        #self.memory_engine = None
        #self.module_manager = None
        #self.interface = None
        
        #Gestion des modules
        #self.module = ModuleBase()
                
        self.logger.info(" Noyau - Initialisation ")
        

    def run(self):
        self.running = True
        #controle de l'environnement graphique, l'interception du clavier fonctionne que sous x11
        self.system.verifier_environnement_graphique()
            
        try:
            self.logger.info("✅ Noyau ===> running, démmarrage de la boucle.")

            while self.running:

                # ------------------------------------------------------------------------
                # -- NOYAU MANAGER                               
                if not self.system.thread_manager.is_alive("noyau_manager"):
                    self.logger.warning("🛠️ Thread 'noyau_manager' inactif — redémarrage")
                    try:  
                        self.logger.warning("🛠️ Le thread 'noyau_manager' est mort — relance en cours")
                        self.system.thread_manager.run("noyau_manager", lambda: NoyauManager(self, live_mode = self.live_mode).run())
                    except:
                        self.logger.error(f"❌ Impossible de relancer noyau_manager : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # -- SOCKET UNIX
                if not self.system.thread_manager.is_alive("noyau_socket"):
                    self.logger.warning("🛠️ Thread 'noyau_socket' inactif — redémarrage")                 
                    try:
                        self.system.thread_manager.run("noyau_socket", self.socket_interface.start_threadable)   
                        self.logger.warning("🛠️ Thread 'noyau_socket' inactif — redémarrage")
                    except Exception as e   :
                        self.logger.error(f"❌ Impossible de relancer noyau_socket : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # --WATCH CONFIG config.ini
                if not self.system.thread_manager.is_alive("watch_config"):
                    self.logger.warning("🛠️ Thread 'watch_config' inactif — redémarrage")
                    try:
                        self.system.thread_manager.run("watch_config", lambda: self.system.config_manager.controle_maj_configuration(self))
                        self.logger.warning("✅ Thread 'module_scanner' relancé proprement.")
                    except Exception as e   :
                        self.logger.error(f"❌ Impossible de relancer watch_config : {e}")
                ###########################################################################

                # ------------------------------------------------------------------------
                # --CLAVIER
                if (not self.stopping) and self.system.en_cours_clavier:
                    if not self.system.thread_manager.is_alive("lancer_ecoute_clavier"):
                        self.logger.warning("🛠️ Thread 'lancer_ecoute_clavier' inactif — redémarrage")
                        try:
                            self.system.thread_manager.run("lancer_ecoute_clavier", self.system.lancer_ecoute_clavier)
                            self.logger.warning("✅ Thread 'lancer_ecoute_clavier' relancé proprement.")
                        except Exception as e  :
                            self.logger.error(f"❌ Impossible de relancer lancer_ecoute_clavier : {e}")
                ###########################################################################
                """
                # ------------------------------------------------------------------------
                # -- MODULE SCANNER (scan le dossier "modules")               
                if not self.system.thread_manager.is_alive("module_scanner"):
                    self.logger.warning("🛠️ Thread 'module_scanner' inactif — redémarrage en cours")

                    try:
                        #creation du ModuleScanner , une seul fois.
                        if not hasattr(self.system, "module_scanner"):
                            self.system.module_scanner = ModuleScanner(self.system)

                        self.system.thread_manager.run("module_scanner", lambda: self.system.module_scanner.run())    

                        self.logger.warning("✅ Thread 'module_scanner' relancé proprement.")

                    except Exception as e:
                        self.logger.error(f"❌ Impossible de relancer ModuleScanner : {e}")
                """
                ###########################################################################


                """
                # ------------------------------------------------------------------------
                # 🔍 Vérifier les threads vivants
                for nom, etat in self.system.lister_threads_actifs():
                    if etat == "terminé ❌":
                        self.logger.warning(f"⚠️ Thread '{nom}' s’est terminé.")
                ###########################################################################
                """


                ###########################################################################
                        
        
                time.sleep(3) #on evite la charge GPU

        except KeyboardInterrupt:
            self.logger.info("🛑 Arrêt manuel de MasterApp en cours.")
            self.stop()
                
    def stop(self):
        #Fermeture du programme:

        # Mettre self.running = False (arrête la boucle while).

        # Logger l’arrêt.

        # Stopper les subprocess : self.system.process_manager.stop_all()

        # Fermer la socket UNIX : self.socket_interface.arreter()

        # Stopper l’écoute clavier : self.system.en_cours_clavier = False

        # Attendre la fin des threads (join) pour ne pas tuer brutalement.

        # Logger la fermeture terminée.

        # Terminer le programme avec os._exit(0)

        self.stopping = True
        self.logger.info("🛑 Arrêt de MasterApp via stop() ")

        #.0. Sauvegadre du registre
        try:
            self.system.registre.sauvegarder_json(self.system.chemin_absolu("registre_json"))    
            self.logger.info(f"📦 Registre système (ID): {id(self.system.registre)}")
            self.logger.info(f"📦 Entrées dans le registre : {len(self.system.registre.tous())}")
        except Exception as e:
            self.logger.error(f"❌ Erreur de sauvegarde du registre: {e}")        

        #.1. Signaux d'interruption de la boucle principale et du clavier
        self.running = False  # stoppe la boucle while principale
        self.system.en_cours_clavier = False  # stoppe l’écoute clavier

        if hasattr(self.system, "module_scanner"):
            try:
                self.system.logger.info("🛑 Arrêt demandé au ModuleScanner...")
                self.system.module_scanner.stop() #signal de stop à ModuleScanner pour pas qu'il redemarre les subprocss
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible d’arrêter ModuleScanner : {e}")

        #.2. Arrêt des subprocess
        self.logger.info("🛑 Arrêt des modules externes (subprocess)...")
        try:
            self.system.process_manager.stop_all()
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'arrêt des processus : {e}")

         # 3. Fermeture de la socket UNIX
        self.logger.info("🛑 Fermeture de la socket UNIX...")
        try:
            self.socket_interface.arreter()
        except Exception as e:
            self.logger.error(f"❌ Erreur socket : {e}")

        # 4. Attente des threads
        self.logger.info("⏳ Attente de l'arrêt des threads...")
        for nom, thread in self.system.threads.items():
            if thread.is_alive():
                self.logger.info(f"🕓 Attente thread : {nom}")
                thread.join(timeout=5)
                self.logger.info(f"✅ Thread terminé : {nom}")


        # 5. Nettoyagesocket file (si besoin)
        try:
            chemin_socket = "/tmp/masterapp.sock"
            if os.path.exists(chemin_socket):
                os.remove(chemin_socket)
                self.logger.info(f"🧹 Fichier socket supprimé : {chemin_socket}")
        except Exception as e:
            self.logger.warning(f"⚠️ Échec suppression fichier socket : {e}")

        # 6. Sortie
        self.logger.info("✅ MasterApp arrêté proprement.")
        os._exit(0)
