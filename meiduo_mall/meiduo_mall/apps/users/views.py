import json
import re

from django.contrib.auth import login, authenticate, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views import View
from django_redis import get_redis_connection

from meiduo_mall.utils.mixins import LoginRequiredMixin

from celery_tasks.email.tasks import send_verify_email
from users.models import User, Address

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
        response = JsonResponse({'code': 0,
                                 'message': 'OK'})

        response.set_cookie('username',
                            user.username,
                            max_age=14 * 24 * 3600)

        return response


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


# POST /login/
class LoginView(View):
    def post(self, request):
        """ 用户登录 """
        # 1.获取参数并进行校验(参数完整性,用户名和密码是否正确)
        req_data = json.loads(request.body)
        username = req_data.get('username')
        password = req_data.get('password')
        remember = req_data.get('remember')

        if not all([username, password]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数!'})

        # 判断客户端传递的username 参数是否符合手机号格式
        if re.match(r'^1[3-9]\d{9}$', username):
            User.USERNAME_FIELD = 'mobile'
        else:
            User.USERNAME_FIELD = 'username'

        # 用户名密码是否正确
        user = authenticate(username=username, password=password)

        if user is None:
            return JsonResponse({'code': 400,
                                 'message': '用户名或密码错误!'})

        # 2.保存登陆用户的状态信息
        login(request, user)

        if not remember:
            # 如果未选择记住登录，浏览器关闭即失效
            request.session.set_expiry(0)

        # 返回响应,登陆成功
        response = JsonResponse({'code': 0,
                                 'message': 'OK', })
        response.set_cookie('username',
                            user.username,
                            max_age=14 * 24 * 3600)
        return response


# DELETE /logout/
class LogoutView(View):
    def delete(self, request):
        """ 退出登录 """
        # 1.请求删除登录用户的session信息
        logout(request)

        # 2.删除cookie中的username
        response = JsonResponse({'code': 0,
                                 'message': 'OK', })
        response.delete_cookie('username')

        # 3.返回响应
        return response


# GET /user/
class UserInfoView(LoginRequiredMixin, View):
    def get(self, request):
        """ 获取登录用户个人信息 """
        # 1.获取登录用户对象
        user = request.user

        # 判断用户是否登陆
        # if not user.is_authenticated:
        #     return JsonResponse({'code': 400,
        #                          'message': '用户未登录!'})

        # 2.返回响应数据
        info = {
            'username': user.username,
            'mobile': user.mobile,
            'email': user.email,
            'email_active': user.email_active,
        }
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'user': info, })


# PUT /user/email/
class UserEmailView(LoginRequiredMixin, View):
    def put(self, request):
        """ 设置用户的个人邮箱 """
        # 1.获取参数并进行校验
        req_data = json.loads(request.body)

        email = req_data.get('email')

        if not email:
            return JsonResponse({'code': 400,
                                 'message': '缺少email参数!'})

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return JsonResponse({'code': 400,
                                 'message': '参数email有误!'})

        # 2.保存用户的个人邮箱设置
        user = request.user
        try:
            user.email = email
            user.save()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '邮箱设置失败!'})

        # Celery异步发送邮箱验证邮件
        verify_url = user.generate_verify_email_url()
        # 发出邮件发送的任务消息
        send_verify_email.delay(email, verify_url)

        # 返回响应
        return JsonResponse({'code': 0,
                             'message': 'OK'})


# PUT /emails/verification/
class EmailVerifyView(View):
    def put(self, request):
        """ 用户邮箱登陆验证 """
        # 1.获取登录的用户token并进行校验
        token = request.GET.get('token')
        if not token:
            return JsonResponse({'code': 400,
                                 'message': '缺少token参数!'})

        # 对用户的信息进行解密
        user = User.check_verify_email_token(token)

        if user is None:
            return JsonResponse({'code': 400,
                                 'message': 'token信息有误!'})

        # 2.设置对应用户的邮箱验证为已验证
        try:
            user.email_active = True
            user.save()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '验证邮箱失败!'})

        # 3.返回响应
        return JsonResponse({'code': 0,
                             'message': 'OK'})


# GET/POST /addresses/
class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        """ 登录⽤用户地址数据获取 """
        # 1.获取当前登录用户
        user = request.user
        # 2.获取当前用户的所有收货地址
        try:
            addresses = Address.objects.filter(user=user, is_delete=False)
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '获取收货地址数据错误!'})

        default_address_id = user.default_address_id
        addresses_li = []
        for address in addresses:
            address = {
                'id': address.id,
                'title': address.title,
                'receiver': address.receiver,
                'province': address.province.name,
                'city': address.city.name,
                'district': address.district.name,
                'province_id': address.province_id,
                'city_id': address.city_id,
                'district_id': address.district_id,
                'place': address.place,
                'mobile': address.mobile,
                'phone': address.phone,
                'email': address.email,
            }
            addresses_li.append(address)

        # 3.组织数据并返回响应
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'default_address_id': default_address_id,
                             'addresses': addresses_li})

    def post(self, request):
        """ 用户收货地址新增 """
        user = request.user
        # 1.判断当前用户收货地址是否超过上限
        try:
            count = Address.objects.filter(user=user, is_delete=False).count()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '获取收获地址出错!'})
        if count >= 20:
            return JsonResponse({'code': 400,
                                 'message': '收货地址超过上限!'})

        # 2.接收参数并进行校验
        req_data = json.loads(request.body)
        title = req_data.get('title')
        receiver = req_data.get('receiver')
        province_id = req_data.get('province_id')
        city_id = req_data.get('city_id')
        district_id = req_data.get('district_id')
        place = req_data.get('place')
        mobile = req_data.get('mobile')
        phone = req_data.get('phone')
        email = req_data.get('email')

        if not all([title, receiver, province_id, city_id, district_id, place, mobile]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数!'})

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'message': '参数mobile有误!'})

        if phone:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', phone):
                return JsonResponse({'code': 400,
                                     'message': '参数phone有误!'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': 400,
                                     'message': '参数email有误!'})

        # 3.保存收货地址数据
        try:
            address = Address.objects.create(user=user, **req_data)
            # 设置默认收货地址
            if not user.default_address:
                user.default_address = address
                user.save()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '新增地址保存失败!'})

        # 4.返回响应
        address_data = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province': address.province.name,
            'city': address.city.name,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'phone': address.phone,
            'email': address.email,
        }
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'address': address_data, })


# PUT/DELETE /addresses/(?P<address_id>\d+)/
class UpdateAddressView(LoginRequiredMixin, View):
    def put(self, request, address_id):
        """ 登录⽤用户指定收货地址修改 """
        user = request.user
        # 1.接收参数并进行校验
        req_data = json.loads(request.body)
        title = req_data.get('title')
        receiver = req_data.get('receiver')
        province_id = req_data.get('province_id')
        city_id = req_data.get('city_id')
        district_id = req_data.get('district_id')
        place = req_data.get('place')
        mobile = req_data.get('mobile')
        phone = req_data.get('phone')
        email = req_data.get('email')

        if not all([title, receiver, province_id, city_id, district_id, place, mobile, ]):
            return JsonResponse({'code': 400,
                                 'message': '缺少必传参数!'})

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'message': '参数mobile有误!'})

        if phone:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', phone):
                return JsonResponse({'code': 400,
                                     'message': '参数phone有误!'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': 400,
                                     'message': '参数email有误!'})
        # 2.修改指定地址的数据并进行保存
        try:
            old_address = Address.objects.get(user=user, id=address_id, is_delete=False)
            old_address.title = title
            old_address.receiver = receiver
            old_address.province_id = province_id
            old_address.city_id = city_id
            old_address.district_id = district_id
            old_address.place = place
            old_address.mobile = mobile
            old_address.phone = phone
            old_address.email = email
            old_address.save()

        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '修改指定地址数据出错!'})

        # 3.返回响应
        new_address = {
            "id": address_id,
            "title": title,
            "receiver": receiver,
            "province": old_address.province.name,
            "city": old_address.city.name,
            "district": old_address.district.name,
            "province_id": province_id,
            "city_id": city_id,
            "district_id": district_id,
            "place": place,
            "mobile": mobile,
            "phone": phone,
            "email": email,
        }
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'address': new_address, })

    def delete(self, request, address_id):
        """ 登录⽤用户指定收货地址删除 """
        user = request.user
        try:
            del_address = Address.objects.get(user=user, id=address_id, is_delete=False)
            del_address.is_delete = True
            del_address.save()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': 'OK', })

        return JsonResponse({'code': 0,
                             'message': 'OK'})


# PUT /addresses/(?P<address_id>\d+)/default/
class UpdateDefaultAddressView(LoginRequiredMixin, View):
    def put(self, request, address_id):
        """ 登录⽤用户默认收货地址设置 """
        user = request.user
        try:
            user.default_address_id = address_id
            user.save()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '设置默认地址出错!'})

        return JsonResponse({'code': 0,
                             'message': 'OK', })
