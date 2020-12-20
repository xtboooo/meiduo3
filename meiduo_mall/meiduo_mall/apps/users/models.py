from django.db import models
from django.contrib.auth.models import AbstractUser


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
