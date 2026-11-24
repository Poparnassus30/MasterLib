"""
netboxcore.py — Client NetBox unifié (NetBoxCore)

But
---
NetBoxCore encapsule l’accès à l’API NetBox afin de fournir un objet unique,
réutilisable et testable, qui centralise :
- authentification (token)
- configuration (base_url, timeouts, vérifications TLS, proxies)
- requêtes HTTP (GET/POST/PATCH/DELETE)
- pagination + filtres
- normalisation des erreurs (exceptions propres)
- helpers de haut niveau (ex: devices(), vms(), ip_addresses(), tags(), custom_fields())

Pourquoi une classe dédiée ?
---------------------------
1) Découplage : le reste du programme ne dépend pas de requests/HTTP directement.
2) Évolutivité : on pourra changer de backend (mock, cache, proxy, bus kernel) sans
   réécrire l’application.
3) Intégration MasterLib : NetBoxCore devient une “brique service” consommée par :
   - collectors (découverte)
   - reconciler (mise à jour CMDB)
   - exporter (graph/topology)
   - UI/maquette 2D

Contrat d’interface (stable)
----------------------------
NetBoxCore doit fournir :
- des méthodes bas niveau : request(), get(), post(), patch(), delete()
- des méthodes de ressources : list(resource,...), retrieve(resource,id), create(...), update(...)
- des helpers : paginate(), build_url(), sanitize_logs()
- des primitives “métier” minimales (facultatives en V1) : upsert_device(), ensure_tag(), etc.

Politique de données
--------------------
- NetBoxCore ne stocke pas de secrets persistants sur disque.
- Il ne fait que transporter des identifiants de référence (ex: bw_item_ref),
  jamais de mots de passe / clés privées.

Compatibilité future
--------------------
- Prévu pour tourner en “service isolé” (thread/subprocess) :
  NetBoxCore peut être encapsulé dans un adaptateur bus (kernel_bus) plus tard.
- Prévu pour supporter cache + rate limiting (NetBox peut throttler).
- Prévu pour instrumentation (timings, métriques) sans changer les appels.

"""
