#!/usr/bin/env python3
#
# ServiceApi, base hérité pour les services de MasterLib
# L'API "ServiceApi" commune doit couvrir tout ce qui est identique pour n’importe quel service, et laisser le reste au service lui-même.

class ServiceApi(self, service_name: str):
    
    __init__(self):
        self.service_name = None
        self.service_id = None
        self.node_id = None
        self.service_version = None


    def get_idenity(self):
        pass

    def get_capabilities(self):
        pass

    def get_health(self):
        pass

    def get_handlers(self):
        pass

    def dispatch_request(self, request):
        pass



