import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shipmaster.server.settings')
from celery import Celery
from django.conf import settings
app = Celery('shipmaster.server')
app.config_from_object(settings)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
