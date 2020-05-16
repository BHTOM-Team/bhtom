from django.apps import AppConfig


class DatatoolsConfig(AppConfig):
    name = 'datatools'

    def ready(self):
        import bhtom.signals
