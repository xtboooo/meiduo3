import json
import re

from django.contrib.auth import login
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views import View
from django_redis import get_redis_connection

from users.models import User

import logging

logger = logging.getLogger('django')


# GET /usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/
class UsernameCountView(View):
    def get(self, request, username):
        """ 判断注册用户名是否重复 """
        # 1.查询数据可以判断username是否存在
        try:
            count = User.objects.filter(username=username).count()
        except Exception as e:
            # print(e)
            return JsonResponse({'code': 400,
                                 'message': '操作数据库失败'})

        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'count': count, })


# GET /mobiles/(?P<mobile>1[3-9]\d{9})/count/
class MobileCountView(View):
    def get(self, request, mobile):
        """ 判断手机号是否重复注册 """
        # 1.查询数据库判断mobile是否存在
        try:
            count = User.objects.filter(mobile=mobile).count()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '操作数据库失败!'})
        # 2.返回响应数据
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'count': count})


# POST /register/
class RegisterView(View):
    def post(self, request):
        """ 注册用户信息保存 """
        # 1.获取参数并进行保存
        req_data = json.loads(request.body)
        username = req_data.get('username')
        password = req_data.get('password')
        password2 = req_data.get('password2')
        mobile = req_data.get('mobile')
        allow = req_data.get('allow')
        sms_code = req_data.get('sms_code')

        if not all([username, password, password2, mobile, allow, sms_code]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数'})

        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return JsonResponse({'code': 400,
                                 'message': 'username格式错误!'})

        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return JsonResponse({'code': 400,
                                 'message': 'password格式错误!'})

        if password != password2:
            return JsonResponse({'code': 400,
                                 'message': '两次密码不一致!'})

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'message': '手机号格式错误!'})

        if not allow:
            return JsonResponse({'code': 400,
                                 'message': '请统一协议'})

        # 短信验证码检验
        redis_conn = get_redis_connection('verify_code')
        sms_code_redis = redis_conn.get('sms_%s' % mobile)

        if not sms_code_redis:
            return JsonResponse({'code': 400,
                                 'message': '短信验证码过期'})

        if sms_code != sms_code_redis:
            return JsonResponse({'code': 400,
                                 'message': '短信验证码错误!'})

        # 保存新增用户数据到数据库
        try:
            user = User.objects.create_user(username=username,
                                            password=password,
                                            mobile=mobile, )
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'message': '数据库保存错误!'})
        # 只要调用login方法,传入request和user对象
        # login 方法就会将user用户的信息存储到session
        login(request, user)

        # 返回响应数据
        return JsonResponse({'code': 0,
                             'message': 'OK'})


# GET /csrf_token/
class CSRFTokenView(View):
    def get(self, request):
        """ 获取csrf_token的值"""
        # 1.生成csrf_token的值
        csrf_token = get_token(request)

        # 2.将csrf_token的值返回
        return JsonResponse({'code': 400,
                             'message': 'OK',
                             'csrf_token': csrf_token})


