# MasterLib est une librairie développé par Poparnassus

Nous avons une structure de code universel à importer dans les appications développés:
SP1 = structure général d'application :
    #import SP1  #Pour importer la structure
    core/ 
        core.py # l'interfacage de l'application métier se fait ici
        core_manager.py
        core_module_scanner.py #scan les applications copié dans modules/ et les integre
        core_socket.py #Socket interne à l'application structure
    system/
        system.py
        system_manager_config.py
        system_manager_noeud.py
        system_manager_subprocess.py
        system_manager_thread.py
        system_controle_dependance.py
    registre/
        registre_manager.py #Point centrale du registre
    config/
    modules/
        modules_framework.py
    network/
        network_manager.py
        network_manager_dht.py
        network_manager_lan.py
        network_protocol.py
    ihm/
        #ihm est construis via le registre
        ihm_manager.py
        ihm_console.py
        ihm_graph.py
    data/ #dossier de travail de l'application 
        logs/
        registre/


Processus de création programme:
    - Creation d'application métier "mon_app.py"
    - importation de la strcuture SP1 "mon_app.py"
    - definition du métier dans core.py au travers de la section modules/



    