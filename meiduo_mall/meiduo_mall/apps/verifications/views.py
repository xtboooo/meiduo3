from django.http import HttpResponse
from django.views import View

from django_redis import get_redis_connection
from meiduo_mall.libs.captcha.captcha import captcha


# GET /image_codes/(?P<uuid>[\w-]+)/
class ImageCodeView(View):
    def get(self, request, uuid):
        """ 获取图片验证码数据 """
        # 1.生成图片验证码数据
        text, image = captcha.generate_captcha()

        # 2.将图片验证码存储到redis数据库
        redis_conn = get_redis_connection('verify_code')
        redis_conn.set('img_%s' % uuid, text, 300)

        # 3.返回验证码图片数据
        return HttpResponse(image, content_type='image/jpg')
