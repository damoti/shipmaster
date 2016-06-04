from django.apps import AppConfig


class ShipmasterConfig(AppConfig):
    name = "shipmaster.server"
    verbose_name = "Shipmaster"

    def ready(self):
        # Do django monkeypatches
        from .hacks import monkeypatch_django
        monkeypatch_django()
