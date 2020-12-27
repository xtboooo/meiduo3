"""
xtbo97
"""
import os

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meiduo_mall.settings.dev')

from celery import Celery

# 1.创建Celery对象
celery_app = Celery('demo')

# 2.加载config.py的配置
celery_app.config_from_object('celery_tasks.config')

# 3.celery worker启动时自动加载任务
celery_app.autodiscover_tasks(['celery_tasks.sms',
                               'celery_tasks.email',
                               'celery_tasks.html'])
