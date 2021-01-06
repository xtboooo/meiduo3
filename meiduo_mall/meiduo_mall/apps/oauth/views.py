import json
import re

from QQLoginTool.QQtool import OAuthQQ
from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.views import View

import logging

from django_redis import get_redis_connection

from carts.utils import CartHelper
from oauth.models import OAuthQQUser
from oauth.utils import generate_secret_openid, check_secret_openid
from users.models import User

logger = logging.getLogger('django')


# GET /qq/authorization/
class QQLoginView(View):
    def get(self, request):
        """ 获取QQ登陆网址 """
        next1 = request.GET.get('next', '/')

        # 创建OAuthQQ对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next1)

        # 获取QQ登陆网址并返回
        login_url = oauth.get_qq_url()

        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'login_url': login_url, })


# /qq/oauth_callback/
class QQUserView(View):
    def get(self, request):
        """ 获取QQ登录用户的openid并进行处理 """
        # 1.获取code
        code = request.GET.get('code')

        # 2.获取QQ登陆用户的openid
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI, )

        try:
            # 根据code获取access_token
            access_token = oauth.get_access_token(code)
            # 根据access_token获取open_id
            openid = oauth.get_open_id(access_token)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'message': 'QQ登陆失败!'})

        # 3.根据openid是否已经和本网站用户进行绑定进行处理
        try:
            qq_user = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 如果未进行绑定,将openid加密后返回
            secret_openid = generate_secret_openid(openid)
            return JsonResponse({'code': 300,
                                 'message': 'OK',
                                 'secret_openid': secret_openid, })
        else:
            # 通过已绑定,保存用户的登录状态
            user = qq_user.user
            login(request, user)

            response = JsonResponse({'code': 0,
                                     'message': 'OK', })

            # 设置cookie
            response.set_cookie('username', user.username,
                                max_age=14 * 24 * 3600)

            # 增加代码：合并购物车数据
            cart_helper = CartHelper(request, response)
            cart_helper.merge_cookie_cart_to_redis()

            # 返回响应
            return response

    def post(self, request):
        """ 绑定QQ登陆用户信息"""
        # 1.获取参数并进行校验
        req_data = json.loads(request.body)

        mobile = req_data.get('mobile')
        password = req_data.get('password')
        sms_code = req_data.get('sms_code')
        secret_openid = req_data.get('secret_openid')

        if not all([mobile, password, sms_code, secret_openid]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数!'})

        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'message': '请输入正确的手机号码!'})

        # 判断密码是否合格
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return JsonResponse({'code': 400,
                                 'message': '请输入8-20位的密码!'})

        # 短信验证码是否正确
        redis_conn = get_redis_connection('verify_code')
        sms_code_redis = redis_conn.get('sms_%s' % mobile)
        if not sms_code_redis:
            return JsonResponse({'code': 400,
                                 'message': '短信验证码已过期!'})

        if sms_code != sms_code_redis:
            return JsonResponse({'code': 400,
                                 'message': '短信验证码错误!'})

        # 对openid进行解密
        openid = check_secret_openid(secret_openid)

        if not openid:
            return JsonResponse({'code': 400,
                                 'message': 'secret_openid有误!'})

        # 2. 绑定QQ登陆用户信息
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            # 注册未绑定用户
            import base64
            # 手机号进行base64编码生成用户名
            username = base64.b64encode(mobile.encode()).decode()
            user = User.objects.create_user(username=username,
                                            password=password,
                                            mobile=mobile, )

        else:
            # 校验密码是否正确
            if not user.check_password(password):
                return JsonResponse({'code': 400,
                                     'message': '登陆密码错误!'})

        try:
            OAuthQQUser.objects.create(openid=openid,
                                       user_id=user.id)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'message': '数据库操作失败!'})

        # 3. 返回响应,登陆成功
        login(request, user)

        response = JsonResponse({'code': 0,
                                 'message': 'OK', })

        # 设置cookie
        response.set_cookie('username', user.username,
                            max_age=14 * 24 * 3600)

        # 增加代码：合并购物车数据
        cart_helper = CartHelper(request, response)
        cart_helper.merge_cookie_cart_to_redis()

        return response
