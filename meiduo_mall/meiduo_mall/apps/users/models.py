from django.db import models
from django.contrib.auth.models import AbstractUser
from itsdangerous import TimedJSONWebSignatureSerializer
from django.conf import settings


class User(AbstractUser):
    """ 用户模型类 """
    # 增加 mobile 字段

    mobile = models.CharField(max_length=11, unique=True, verbose_name='电话号')

    # 增加email_active字段
    # 用于记录邮箱是否激活,默认为False:未激活
    email_active = models.BooleanField(default=False, verbose_name='邮箱验证状态')

    class Meta:
        # 表名
        db_table = 'tb_users'
        verbose_name = '用户'

    def generate_verify_email_url(self):
        """ 生成当前用户的邮件验证链接 """
        serializer = TimedJSONWebSignatureSerializer(settings.SECRET_KEY, 7200)
        # 用户信息加密,生成token
        data = {'user_id': self.id,
                'email': self.email, }
        token = serializer.dumps(data).decode()

        # 生成邮件验证链接地址
        verify_url = settings.EMAIL_VERIFY_URL + token
        return verify_url
