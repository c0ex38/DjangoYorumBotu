from django.apps import AppConfig


class TrendyolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trendyol'
    '''
    def ready(self):
        from trendyol.workers import start_review_worker
        start_review_worker()
    '''