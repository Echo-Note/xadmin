from django.apps import AppConfig


class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'

    def ready(self):
        from . import signal_handler  # noqa
        super().ready()
