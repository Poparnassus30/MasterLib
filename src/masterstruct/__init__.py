"""
MasterStruct — paquet de contrats et schémas communs.

Rôle :
- Fournir les structures de données *officielles* partagées entre MasterKernel, ReineRougeCore et les nœuds réseau.
- Garantir compatibilité, stabilité et versioning des formats (events, policies, packets).

Ce paquet ne contient pas :
- Réseau, threads, subprocess, accès DB, connecteurs IA, logique de vote/attestation.
"""
