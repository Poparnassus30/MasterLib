### 1) Objectif :

MasterLib est un dépôt global fournissant un châssis logiciel unifié pour les applications Poparnassus.

Il regroupe :
- un noyau d’orchestration (masterkernel)
- une structure contractuelle fixe (masterstruct)
- des services activables (masterservice)
- des outils génériques (masterlib)
- des modules métiers encapsulables (mastermodule)

L’objectif n’est pas de créer une “grosse app monolithique”, mais un système fractalisé :
- chaque application peut être autonome, tout en pouvant être pilotée, observée et étendue par un MasterKernel.


### 2) Philosophie (important à lire) :

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



### 3) Cartographie du dépôt :

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


### 4) Communication : le cœur du système

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


### 5) IHM — interface de supervision

#### 5.0) Architecture commune des interfaces

##### Objectif

MasterLib doit pouvoir exposer l’état de son noyau à plusieurs interfaces indépendantes :

- une interface console utilisant Rich ;
- une interface web accessible depuis un navigateur ;
- à terme, des vues permettant de superviser les modules chargés par l’application.

Le noyau doit fonctionner même si aucune interface n’est lancée. Les interfaces sont des clientes de supervision : leur arrêt ne doit pas arrêter le noyau.

##### Principe général

Les interfaces ne collectent pas chacune les informations directement dans leurs propres objets et ne lisent pas les fichiers JSON du registre pour connaître l’état courant.

Le noyau détient l’état opérationnel. Le registre local tenu par le noyau constitue la source de référence pour la supervision en temps réel. Les fichiers persistés servent à conserver ou diagnostiquer des données ; ils ne remplacent pas l’état vivant du noyau. Une éventuelle référence blockchain appartient à une étape ultérieure et n’est pas encore mise en place.

Le service IHM rassemble les informations du noyau et du registre dans un snapshot structuré. Les interfaces demandent ce snapshot par le transport local et le présentent selon leur format.

```text
État du noyau et registre
          │
          ▼
ServiceIhm — construit le snapshot commun
          │
          ▼
KernelBus et transport IPC local
          │
          ├── Client IHM → affichage console Rich
          │
          └── Client IHM → serveur web → navigateur
```

##### Responsabilités des composants

| Composant | Responsabilité |
|---|---|
| `ServiceIhm` | Rassembler l’état du noyau et du registre, construire le snapshot commun et répondre à la requête de supervision. Il ne dépend d’aucune bibliothèque d’affichage. |
| `ClientIhm` | Envoyer la requête de snapshot au noyau via le transport IPC local et fournir une réponse commune aux interfaces. |
| IHM console | Mettre en forme le snapshot avec Rich et l’actualiser périodiquement. Elle ne possède pas sa propre copie de la logique de collecte. |
| IHM web | Servir l’interface web. Son serveur reçoit les demandes du navigateur et utilise le client commun pour obtenir l’état du noyau. Le navigateur ne se connecte pas directement au transport IPC. |
| Noyau | Maintenir l’état opérationnel, le registre, le bus et le transport local. Son démarrage ne dépend pas des interfaces. |

##### Requête de supervision

Le service doit exposer une requête unique, par exemple `ihm.snapshot`, via le KernelBus et le transport local.

Cette requête doit renvoyer un snapshot cohérent contenant au minimum :

- l’état du noyau ;
- son PID et son heure de démarrage ;
- les entrées du registre ;
- pour chaque entrée : son type, son nom, son identifiant éventuel, son état courant, son état souhaité, ses relations et sa dernière erreur.

Une requête unique évite que chaque interface assemble séparément plusieurs réponses et puisse afficher des informations prises à des instants différents.

Le snapshot décrit l’état de supervision de MasterLib. Les données propres au métier de ReineRouge et de ses futurs modules seront ajoutées par des mécanismes d’extension définis ultérieurement ; elles ne doivent pas transformer le registre de supervision en registre métier.

##### Chemins des fichiers prévus

| Chemin | Rôle prévu | État |
|---|---|---|
| `src/masterservice/service/ihm/__init__.py` | Déclarer le paquet du service IHM. | À créer si nécessaire |
| `src/masterservice/service/ihm/service_ihm.py` | Construire et fournir le snapshot commun depuis l’état du noyau et le registre. | À développer |
| `src/masterservice/service/ihm/client_ihm.py` | Centraliser les requêtes IPC utilisées par les interfaces. | À développer |
| `src/masterkernel/kernel/kernel_ihm.py` | Afficher le snapshot dans la console avec Rich. | Existe ; à adapter pour utiliser le client commun |
| `src/masterkernel/kernel/kernel_ihm_web.py` | Fournir l’interface et les routes du serveur web de supervision. | Fichier à compléter ou à créer |

Le nom des fichiers ou leur emplacement pourra être ajusté pendant l’implémentation, mais la séparation des responsabilités doit rester la même.

##### Fonctionnement des processus et des rafraîchissements

Le noyau est lancé par `master start` dans son propre processus. Il reste actif sans terminal Rich et sans serveur web.

La commande `master monitor` lance le moniteur Rich au premier plan dans le terminal où elle est exécutée. Le moniteur interroge périodiquement le noyau par IPC ; il ne démarre pas un thread dans le noyau et ne constitue pas une tâche de fond détachée.

- `Ctrl+C` ferme le moniteur Rich sans arrêter le noyau.
- `master stop` demande l’arrêt du noyau.
- `master monitor ... --once` demande un snapshot, l’affiche une fois et quitte.
- Le serveur web sera lui aussi un processus optionnel. Sa commande de lancement et son cycle d’arrêt seront documentés lorsqu’ils seront définis.

Dans la première version, le service répond aux requêtes reçues par le bus. Il n’a pas besoin d’un thread de rafraîchissement qui lui soit propre : ce sont les clients qui demandent un snapshot lorsqu’ils doivent actualiser leur affichage.

##### Séparation entre supervision système et interface métier

L’interface web de MasterLib constitue la supervision du système : état du noyau, registre, transport, services et modules chargés.

ReineRouge pourra fournir ses propres pages métier, accessibles depuis le menu de l’interface web. Ces pages pourront afficher et manipuler les fonctions métier de ReineRouge, notamment ses futurs cortex IA et son réseau neuronal.

La page métier ne doit pas être confondue avec le rendu Rich, ni imposer le démarrage de la console. Les règles d’intégration des pages et des vues de modules seront définies lorsque le socle de supervision web fonctionnera.

##### Feuille de route

1. Définir et documenter le format du snapshot de supervision.
2. Créer `ServiceIhm` et l’enregistrer auprès du noyau et du KernelBus.
3. Ajouter le client IPC commun utilisé par les interfaces.
4. Adapter l’IHM Rich pour afficher le snapshot fourni par ce client.
5. Vérifier que le noyau démarre, s’arrête et reste supervisable indépendamment de Rich.
6. Construire le serveur web comme un client indépendant du même snapshot.
7. Ajouter ensuite le menu et les points d’extension pour les pages métier et les vues des modules.

##### État actuel

L’IHM Rich existe et peut afficher l’état du noyau et du registre à travers le transport local. La collecte commune par `ServiceIhm`, la requête unique de snapshot et le client IHM partagé restent à développer. L’IHM web complète, son mode de lancement et l’intégration des pages métier restent également à définir et à implémenter.

### 5.1) Rôle de l’IHM

MasterLib fournit une IHM système commune aux applications qui utilisent la
bibliothèque.

Elle permet de superviser une instance locale : son noyau, son registre, ses
services et ses modules. Elle ne contient pas directement les fonctions propres
à chaque application métier.

L’IHM affiche l’état du système. Lorsqu’une action est disponible, elle transmet
la demande au MasterKernel via le KernelBus. Elle ne pilote pas directement les
services et les modules.


### 5.2) IHM console — outil de transition et de diagnostic

L’IHM console Rich reste disponible pendant le développement pour faciliter
l’observation du noyau.

Elle est en lecture seule :
- elle affiche les informations disponibles ;
- elle ne capte pas le clavier ;
- elle ne commande pas les services ou les modules.

Elle n’est pas l’interface normale d’exploitation d’une instance en arrière-plan.
Elle pourra être désactivée lorsque l’IHM Web remplira correctement son rôle.


### 5.3) IHM Web locale — interface de supervision cible

L’IHM principale est une interface Web accessible localement, par défaut sur
`127.0.0.1`, avec une adresse et un port définis par la configuration de
l’application.

Elle présente les informations fournies par le registre, les services de
supervision et les extensions déclarées par l’application. Elle peut utiliser
WebSocket pour recevoir les mises à jour en direct ; WebSocket est un moyen de
communication de l’interface, pas l’IHM elle-même.

L’interface ne doit pas afficher de secrets ni exposer de fonction d’administration
au-delà des permissions prévues.


### 5.4) Vues communes fournies par MasterLib

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


### 5.5) Extensions propres aux applications métier

Une application peut ajouter ses propres vues à l’IHM, sans modifier le cœur
générique de MasterLib.

Par exemple, ReineRouge pourra fournir des vues dédiées à son réseau d’instances,
à leurs rôles et à sa blockchain. Ces éléments ne font pas partie de l’IHM
commune de MasterLib.

Une vue métier utilise les interfaces fournies par MasterLib pour consulter les
informations ou transmettre des commandes. Elle ne contourne pas le KernelBus
pour piloter directement le noyau.

### 5.6) État de l’implémentation

L’IHM Web décrite ci-dessus est la cible fonctionnelle ; elle n’est pas encore
implémentée.

L’IHM Rich actuelle est un prototype. Elle affiche une partie du registre local.

Les vues de modules, de journaux, de ressources et les extensions métier restent
à réaliser ou à raccorder aux données réellement disponibles.

### 6) Activation des services :

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

### 7) Réseau et blockchain — axe de développement

### 7.1) Objectif

MasterLib est conçu pour permettre à des applications de communiquer et de
fonctionner en réseau.

À terme, MasterLib pourra fournir une capacité réseau et un registre distribué
réutilisables, éventuellement sous la forme d’un module ou service optionnel.
Une application pourra choisir de l’utiliser sans que toutes les applications
MasterLib soient obligées de rejoindre une blockchain.

### 7.2) Répartition des responsabilités

MasterLib fournira les mécanismes communs nécessaires au fonctionnement distribué,
selon une architecture qui reste à définir :
- communication entre instances ;
- identité des nœuds et vérification des messages ;
- stockage et synchronisation d’un registre partagé ;
- validation des données et des opérations.

Chaque application définira les informations et les règles propres à son usage :
- types de données ou d’opérations échangées ;
- droits accordés aux nœuds ;
- conditions d’adhésion au réseau ;
- rôle éventuel d’une instance maîtresse et des instances rattachées.

ReineRouge pourra être la première application à utiliser cette capacité pour
superviser ses instances et coordonner leurs échanges. Ses règles de gouvernance
et ses données métier resteront propres à ReineRouge.

### 7.3) Sécurité

Les opérations sensibles devront être authentifiées et vérifiables. Les clés
privées resteront protégées sur les machines qui les détiennent et ne seront
jamais publiées dans le dépôt ni intégrées au code source.

Les règles de confiance, la gestion des clés et les mécanismes de validation
devront être définis avant toute mise en service d’un réseau réel.

### 7.4) État et étapes

La blockchain et la communication entre instances ne sont pas encore implémentées.
Le KernelBus actuel fonctionne dans le processus local et ne constitue pas encore
un transport réseau.

Les étapes de développement envisagées sont :
    1. stabiliser le fonctionnement local du noyau, du registre et du bus ;
    2. définir les contrats de communication entre instances ;
    3. mettre en place une communication réseau sécurisée ;
    4. définir le registre distribué, sa validation et sa synchronisation ;
    5. intégrer ces capacités dans une première application, ReineRouge.

Le mécanisme de consensus, la découverte des nœuds et la procédure de création
ou de rejoint d’un réseau restent à concevoir.


### 8) Utiliser MasterLib (HOW TO)

### 8.1) Commandes de l’instance

La commande `master` est installée avec MasterLib. Elle sert à initialiser,
démarrer, vérifier, superviser et arrêter une instance locale.

Depuis la racine du projet, `--project-root` peut être omis : le répertoire
courant est utilisé par défaut. Dans les exemples ci-dessous, il est indiqué
explicitement pour éviter toute ambiguïté.

- `master init reinerouge --project-root "$HOME/github/reinerouge"`
    Initialise le projet si nécessaire, notamment sa configuration et son dossier
    `data/`.

- `master start reinerouge --project-root "$HOME/github/reinerouge"`
    Prépare l’espace de travail puis démarre le MasterKernel en arrière-plan.
    La commande confirme son démarrage lorsque le noyau est prêt et que le
    transport local répond.

- `master status --project-root "$HOME/github/reinerouge"`
    Affiche l’état du processus et du noyau.

- `master monitor reinerouge --project-root "$HOME/github/reinerouge"`
    Ouvre l’IHM console Rich en lecture seule. Elle interroge le noyau et actualise
    l’affichage. Elle peut être lancée dans un autre terminal. `Ctrl+C` ferme le
    moniteur sans arrêter le noyau.

- `master monitor reinerouge --project-root "$HOME/github/reinerouge" --once`
    Affiche un seul état puis quitte.

- `master stop --project-root "$HOME/github/reinerouge"`
    Demande l’arrêt propre du noyau via le transport local.

Séquence habituelle :

```bash
master start reinerouge --project-root "$HOME/github/reinerouge"
master status --project-root "$HOME/github/reinerouge"
master monitor reinerouge --project-root "$HOME/github/reinerouge"
master stop --project-root "$HOME/github/reinerouge"
```

### 8.2) Créer une application métier

Structure recommandée (classique Python src/) :

reinerouge/
├── pyproject.toml
├── main.py
└── src/
    └── reinerouge/
        ├── __init__.py
        ├── core.py
        └── cli.py


### 8.3) CLI minimal (obligatoire)

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


### 8.4) pyproject.toml minimal

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


### 8.5) Lancer l’application

    pip install -e .
    reinerouge



### 9) Sécurité dev (important)

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