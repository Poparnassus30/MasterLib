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


5) IHM — interface de supervision

    5.1) Rôle de l’IHM

        MasterLib fournit une IHM système commune aux applications qui utilisent la
        bibliothèque.

        Elle permet de superviser une instance locale : son noyau, son registre, ses
        services et ses modules. Elle ne contient pas directement les fonctions propres
        à chaque application métier.

        L’IHM affiche l’état du système. Lorsqu’une action est disponible, elle transmet
        la demande au MasterKernel via le KernelBus. Elle ne pilote pas directement les
        services et les modules.

    5.2) IHM console — outil de transition et de diagnostic

        L’IHM console Rich reste disponible pendant le développement pour faciliter
        l’observation du noyau.

        Elle est en lecture seule :
        - elle affiche les informations disponibles ;
        - elle ne capte pas le clavier ;
        - elle ne commande pas les services ou les modules.

        Elle n’est pas l’interface normale d’exploitation d’une instance en arrière-plan.
        Elle pourra être désactivée lorsque l’IHM Web remplira correctement son rôle.

    5.3) IHM Web locale — interface de supervision cible

        L’IHM principale est une interface Web accessible localement, par défaut sur
        `127.0.0.1`, avec une adresse et un port définis par la configuration de
        l’application.

        Elle présente les informations fournies par le registre, les services de
        supervision et les extensions déclarées par l’application. Elle peut utiliser
        WebSocket pour recevoir les mises à jour en direct ; WebSocket est un moyen de
        communication de l’interface, pas l’IHM elle-même.

        L’interface ne doit pas afficher de secrets ni exposer de fonction d’administration
        au-delà des permissions prévues.

    5.4) Vues communes fournies par MasterLib

        L’IHM système de MasterLib comprend les vues génériques suivantes :

        - **Vue d’ensemble**
        - identité de l’application et UUID de l’instance ;
        - état du MasterKernel ;
        - état général des services et modules connus ;
        - alertes et événements récents.

        - **Registre**
        - consultation des entrées du registre local ;
        - type, nom, identifiant ou PID, état, parent, relations et date de mise à jour.

        - **Modules**
        - liste des modules déclarés ou disponibles dans le catalogue configuré ;
        - état installé, activé ou arrêté, lorsqu’il est connu ;
        - demande d’activation ou de désactivation selon la configuration et les
            permissions disponibles.

        - **Journaux et ressources**
        - consultation des événements et journaux accessibles ;
        - affichage des ressources et processus suivis par le système.

        Les actions proposées par l’IHM sont transmises au MasterKernel par le KernelBus.
        Le noyau valide la demande et pilote ensuite le service ou le module concerné.

    5.5) Extensions propres aux applications métier

        Une application peut ajouter ses propres vues à l’IHM, sans modifier le cœur
        générique de MasterLib.

        Par exemple, ReineRouge pourra fournir des vues dédiées à son réseau d’instances,
        à leurs rôles et à sa blockchain. Ces éléments ne font pas partie de l’IHM
        commune de MasterLib.

        Une vue métier utilise les interfaces fournies par MasterLib pour consulter les
        informations ou transmettre des commandes. Elle ne contourne pas le KernelBus
        pour piloter directement le noyau.

        5.6) État de l’implémentation

        L’IHM Web décrite ci-dessus est la cible fonctionnelle ; elle n’est pas encore
        implémentée.

        L’IHM Rich actuelle est un prototype. Elle affiche une partie du registre local,
        mais tente aussi d’interroger un socket qui n’est pas opérationnel dans la
        configuration actuelle. L’écoute clavier est séparée de l’affichage et doit être
        désactivée pour le fonctionnement normal en arrière-plan.

        Les vues de modules, de journaux, de ressources et les extensions métier restent
        à réaliser ou à raccorder aux données réellement disponibles.

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