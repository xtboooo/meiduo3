import random
from django.http import HttpResponse, JsonResponse
from django.views import View

from celery_tasks.sms.tasks import send_sms_code
from django_redis import get_redis_connection
from meiduo_mall.libs.captcha.captcha import captcha
# from meiduo_mall.libs.yuntongxun.ccp_sms import CCP


import logging

logger = logging.getLogger('django')


# GET /image_codes/(?P<uuid>[\w-]+)/
class ImageCodeView(View):
    def get(self, request, uuid):
        """ 获取图片验证码数据 """
        # 1.生成图片验证码数据
        text, image = captcha.generate_captcha()
        print(f'图片验证码为{text}')

        # 2.将图片验证码存储到redis数据库
        redis_conn = get_redis_connection('verify_code')
        redis_conn.set('img_%s' % uuid, text, 300)

        # 3.返回验证码图片数据
        return HttpResponse(image, content_type='image/jpg')


# GET /sms_codes/(?P<mobile>1[3-9]\d{9})/
class SMSCodeView(View):
    def get(self, request, mobile):
        """ 获取短信验证码 """
        redis_conn = get_redis_connection('verify_code')
        send_flag = redis_conn.get('send_flag_%s' % mobile)
        if send_flag:
            return JsonResponse({'code': 400,
                                 'message': '短信验证码发送过于频繁!'})
        # 1.接收参数并进行校验
        image_code = request.GET.get('image_code')
        uuid = request.GET.get('image_code_id')

        if not all([image_code, uuid]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数'})

        # 2.对比图片验证码
        # 获取redis中的图片验证码
        image_code_redis = redis_conn.get('img_%s' % uuid)
        if image_code_redis is None:
            return JsonResponse({'code': 400,
                                 'message': '图片验证码失效!'})
        # 删除图片验证码
        try:
            redis_conn.delete('img_%s' % uuid)
        except Exception as e:
            logger.error(e)

        # 对比图形验证码
        if image_code.lower() != image_code_redis.lower():
            return JsonResponse({'code': 400,
                                 'message': '输入图形验证码有误!'})
        # 生成保存并发送短信验证码
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info('短信验证码为: %s' % sms_code)
        # 创建redis pipeline管道
        pl = redis_conn.pipeline()
        # 将redis请求操作添加到队列
        # 保存短信验证码
        pl.set('sms_%s' % mobile, sms_code, 300)

        # 设置短信发送的标记,有效期为:60s
        pl.set('send_flag_%s' % mobile, 1, 60)

        # 执行redis pipeline请求
        pl.execute()

        # 发出发送短信的任务消息，SMSCodeView这里的作用就是生产者
        send_sms_code.delay(mobile, sms_code)
        # 返回响应结果
        return JsonResponse({'code': 400,
                             'message': '发送短信成功!'})
