"""
Schémas des politiques (MasterHead / Governance).

Rôle :
- Définir les structures de configuration qui pilotent le comportement du système :
  - RoutingPolicy (sélection enfants, timeouts, pondérations)
  - MemoryPolicy (quoi stocker, quoi résumer, TTL)
  - PromptProfile (schéma canonique + variantes par catégorie/enfant)
  - PolicyPack (ensemble cohérent et versionné)

Notes :
- Ici on décrit la forme des policies, pas leur application (ça = MasterKernel).
"""
