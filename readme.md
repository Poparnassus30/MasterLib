1) Objectif :

    MasterLib est un dépôt global fournissant un châssis logiciel unifié pour les applications Poparnassus.

    Il regroupe :
        - un noyau d’orchestration (masterkernel)
        - une structure contractuelle fixe (masterstruct)
        - des services activables (masterservice)
        - des outils génériques (masterlib)
        - des modules métiers encapsulables (mastermodule)

    L’objectif n’est pas de créer une “grosse app monolithique”, mais un système fractalisé :
        - chaque application peut être autonome, tout en pouvant être pilotée, observée et étendue par un MasterKernel.


2) Philosophie (important à lire) :

    Pas de cascade d’exécution :
        - Les modules ne s’appellent pas les uns les autres de manière incontrôlée.

    Fractalisation :
        - Un masterkernel peut exécuter des modules codés avec masterkernel sans s’imbriquer récursivement.

    Unification :   
        - Tous les composants parlent le même langage via le kernel_bus.

    Séparation stricte :
        - Structure
        - Kernel
        - Services
        - Modules
        - Application métier
            chacun a son rôle, ses responsabilités, et ses frontières.



3) Cartographie du dépôt :

    MasterLib/
    └── src/
        ├── masterstruct/    # Structure fixe, importable
        │                    # Contrats, schémas, invariants
        │                    # Sécurité anti-encapsulation en cascade
        │
        ├── masterkernel/    # Le noyau
        │                    # Boucle principale, registre, bus, orchestration
        │
        ├── masterservice/   # Services (daemons)
        │                    # Activables dynamiquement par config
        │
        ├── masterlib/       # Outils génériques
        │                    # Helpers, graphiques, réseau, utilitaires
        │
        ├── mastermodule/    # Modules métiers
        │                    # Exécutables seuls OU encapsulables
        │
        └── masterchaine/    # (en cours / réservé)


4) Communication : le cœur du système

    La seule interface officielle entre :
        - le masterkernel
        - l'application métier
        - les services
        - les modules

    => c’est kernel_bus.py

    App métier
        ↓
    kernel_bus
        ↓
    masterkernel
        ↓
    services / modules / registre / ihm

    Aucun service n’importe directement le kernel.
    Tout passe par le bus.

5) IHM système :

    masterkernel possède sa propre IHM console
    Elle affiche :
        - l’état des services
        - les changements d’état
        - les événements du registre
    C’est un gestionnaire système, pas une IHM métier

    Les IHM graphiques métier sont externes au kernel.



6) Activation des services :

    Les services sont pilotés par configuration, pas par code.
    Exemple : conf_service.ini

        [service.wrapper]
            service_nmap = True

        [service.interne]
            ia_connector = True   # Sert à interconnecter des IAs

    Fonctionnement :
        - le kernel surveille la config
        - détecte les changements
        - consigne l’état dans le registre
        - déclenche les actions associées
        - l’IHM système affiche l’état

7) Utiliser MasterLib (HOW TO)

    7.1) Créer une application métier

        Structure recommandée (classique Python src/) :

        reinerouge/
        ├── pyproject.toml
        ├── main.py
        └── src/
            └── reinerouge/
                ├── __init__.py
                ├── core.py
                └── cli.py


    7.2) CLI minimal (obligatoire)

        Chaque application métier doit exposer un CLI minimal.
        Ce CLI **ne contient aucune logique métier** : il délègue entièrement le démarrage à MasterLib.

        #### Template fourni
        Un fichier modèle est fourni dans MasterLib :
            - MasterLib/templates/cli_project_stub.py

        Un fichier modèle est fourni dans MasterLib :


        Ce fichier est **prévu pour être copié** dans chaque projet métier.

        #### Mise en place dans le projet
        Dans un projet utilisant le layout classique `src/`, procéder ainsi :
        1) Copier le template :
            src/template/cli_project_stub.py
        2) Le coller dans le package métier et le renommer :
            src/<nom_du_package>/cli.py

        Exemple pour ReineRouge :
            copié de "MasterLib/templates/cli_project_stub.py" vers "src/reinerouge/cli.py"

            #### Contenu minimal attendu

            ```python
            from pathlib import Path
            from masterlib.bootstrap import run_project_cli

            def main() -> int:
                # En layout src/, la racine du projet est deux niveaux au-dessus
                app_dir = Path(__file__).resolve().parents[2]
                return run_project_cli(app_dir=app_dir, app_name="reinerouge")
        Aucun autre CLI n’est nécessaire.
        Toute la logique de démarrage (résolution de MasterLib, cache, online/offline, installation editable, etc.)
        est gérée par MasterLib.

        > ⚠️ Convention :  
        > Tous les projets Poparnassus30 utilisent le layout `src/`.  
        > Toute déviation doit être justifiée explicitement.


    7.3) pyproject.toml minimal

        [build-system]
        requires = ["setuptools>=68", "wheel"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "reinerouge"
        version = "0.0.1"
        requires-python = ">=3.10"

        [tool.setuptools.packages.find]
        where = ["src"]

        [project.scripts]
        reinerouge = "reinerouge.cli:main"


    7.4) Lancer l’application

        pip install -e .
        reinerouge



8) Sécurité dev (important)

    Jamais de git pull/reset sur un repo MasterLib local
    Le code non committé est sacré
    Les mises à jour automatiques ne se font que dans le cache jetable

    export MASTERLIB_LOCAL=/home/poparnassus/github/MasterLib
    export MASTERLIB_REF=dev


En résumé :

MasterLib = châssis
masterkernel = cerveau
kernel_bus = langage commun
services = capacités activables
modules = fonctions métiers encapsulables
application métier = chef d’orchestre externe

Si tu connais la carte, tu es en terrain ami 😄