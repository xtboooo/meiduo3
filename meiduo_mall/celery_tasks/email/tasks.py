"""
xtbo97
"""
from celery_tasks.main import celery_app
from django.conf import settings
from django.core.mail import send_mail


@celery_app.task(name='send_verify_email')
def send_verify_email(to_email, verify_url):
    # 邮件标题
    subject = "美多商城邮箱验证"
    # 邮件正文(包含html)
    html_message = '<p>尊敬的用户您好！</p>' \
                   '<p>感谢您使用美多商城。</p>' \
                   '<p>您的邮箱为：%s 。请点击此链接激活您的邮箱：</p>' \
                   '<p><a href="%s">%s<a></p>' % (to_email, verify_url, verify_url)
    # 发送邮箱验证邮件
    # settings.EMAIL_FROM：此处是 dev.py 文件中配置的邮件发送者
    return send_mail(subject, '', settings.EMAIL_FROM,
                     [to_email], html_message=html_message, )
