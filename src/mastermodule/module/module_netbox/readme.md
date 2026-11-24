# Module NetBox — MasterLib

## Rôle

Ce dépôt contient le projet de connecteur entre MasterLib / ReineRouge et
[NetBox](https://netbox.readthedocs.io/).

NetBox est un logiciel indépendant de gestion d’inventaire réseau et
d’infrastructure. Il peut représenter des équipements, des adresses IP, des
sites et des machines virtuelles. Le présent module n’est pas NetBox lui-même :
il a vocation à communiquer avec une instance NetBox au moyen de son API.

## Objectif envisagé

Le module devra permettre à MasterLib ou à une application métier de :

- se connecter à une instance NetBox ;
- consulter et, selon les droits configurés, modifier les objets de son inventaire ;
- fournir ces informations à des outils d’inventaire, de découverte ou de visualisation ;
- fonctionner seul pendant le développement, puis être intégrable dans MasterLib.

La classe `NetBoxCore` est prévue pour centraliser les échanges avec l’API :
configuration de la connexion, requêtes HTTP, pagination et traitement des
erreurs. Cette architecture reste une intention de conception tant que les
fonctions correspondantes ne sont pas implémentées.

## État actuel

Le module n’est pas encore fonctionnel.

- `main.py` contient actuellement une description du futur point d’entrée, sans
  logique exécutable.
- `netboxcore/netboxcore.py` décrit la classe envisagée, sans client API
  implémenté.
- Les notes d’installation documentent un essai de déploiement local de NetBox
  avec Docker.
- Le contenu de `bdd/` correspond à des données de travail ou de test locales ;
  il ne constitue pas une base de données à distribuer.

Ne pas considérer le module comme un connecteur opérationnel avant
l’implémentation et la vérification de ses fonctions.

## Configuration et sécurité

L’URL de l’instance NetBox, le jeton API et les autres paramètres de connexion
devront être fournis par une configuration locale ou par l’environnement.

Les secrets et les données locales ne doivent pas être ajoutés au dépôt. Aucun
jeton, mot de passe ou export d’inventaire ne doit être écrit dans les logs ou
dans un export public.

## Utilisation prévue

À terme, le module pourra être lancé de manière autonome pour les besoins de
développement, ou chargé par MasterLib selon le contrat d’intégration défini
par MasterLib.

Les modalités de lancement et d’intégration seront documentées quand elles
seront réellement disponibles.