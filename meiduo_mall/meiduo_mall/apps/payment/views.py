import os

from alipay import AliPay
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from meiduo_mall.utils.mixins import LoginRequiredMixin

from orders.models import OrderInfo

# GET /payment/(?P<order_id>\d+)/
from payment.models import Payment


class PaymentURLView(LoginRequiredMixin, View):
    def get(self, request, order_id):
        """获取支付宝支付地址"""
        user = request.user
        # ① 获取参数并进行校验
        try:
            order = OrderInfo.objects.get(user=user,
                                          order_id=order_id,
                                          status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'code': 400,
                                 'message': '订单信息有误'})

        # ② 生成支付宝支付地址并返回
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调URL
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'keys/alipay_public_key.pem'),
            sign_type='RSA2',
            debug=settings.ALIPAY_DEBUG,
        )
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),
            subject='美多商城%s' % order_id,
            return_url=settings.ALIPAY_RETURN_URL,
        )
        alipay_url = settings.ALIPAY_URL + '?' + order_string
        print(alipay_url)
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'alipay_url': alipay_url, })


# PUT /payment/status/
class PaymentStatusView(LoginRequiredMixin, View):
    def put(self, request):
        """支付结果信息处理"""
        # ① 获取参数并进行校验
        req_data = request.GET.dict()

        # 签名校验
        signature = req_data.pop('sign')
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调URL
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'keys/alipay_public_key.pem'),
            sign_type='RSA2',
            debug=settings.ALIPAY_DEBUG,
        )
        success = alipay.verify(req_data, signature)

        # ② 订单支付结果处理保存
        if success:
            order_id = req_data.get('out_trade_no')
            trade_id = req_data.get('trade_no')
            try:
                # 保存支付交易编号
                Payment.objects.create(order_id=order_id,
                                       trade_id=trade_id)
            except Exception as e:
                return JsonResponse({'code': 400,
                                     'message': '保存数据出错'})
            try:
                # 修改对应订单的支付状态：2-待发货
                OrderInfo.objects.filter(order_id=order_id,
                                         status=1).update(status=2)
            except Exception as e:
                return JsonResponse({'code': 400,
                                     'message': '保存数据出错'})
            return JsonResponse({'code': 400,
                                 'message': 'OK',
                                 'trade_id': trade_id, })
        # ③ 返回响应
        else:
            # 订单支付失败，返回相应提示
            return JsonResponse({'code': 400,
                                 'message': '支付出错!非法请求!'})
