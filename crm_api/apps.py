from django.apps import AppConfig


class CrmApiConfig(AppConfig):
    name = 'crm_api'

    def ready(self):
        import crm_api.signals
        from crm_api.services.background_scheduler import start_background_sync
        start_background_sync()
