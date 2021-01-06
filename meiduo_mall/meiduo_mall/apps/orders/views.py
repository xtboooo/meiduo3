import json
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.db import transaction

from meiduo_mall.utils.mixins import LoginRequiredMixin
from carts.utils import CartHelper
from goods.models import SKU
from orders.models import OrderInfo, OrderGoods
from users.models import Address


# GET /orders/settlement/
class OrderSettlementView(LoginRequiredMixin, View):
    def get(self, request):
        """订单结算页面"""
        # ① 获取当前用户的收货地址信息
        addresses = Address.objects.filter(user=request.user, is_delete=False)

        # ② 从redis中获取用户所要结算的商品信息
        try:
            cart_helper = CartHelper(request)
            cart_dict = cart_helper.get_redis_select_cart()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '获取购物车数据失败'})

        # ③ 查询数据库获取对应的商品数据
        # 商品数据
        sku_li = []

        try:
            skus = SKU.objects.filter(id__in=cart_dict.keys())

            for sku in skus:
                sku_li.append({
                    'id': sku.id,
                    'name': sku.name,
                    'default_image_url': 'http://192.168.19.131:8888/' + sku.default_image.name,
                    'price': sku.price,
                    'count': cart_dict[sku.id]
                })
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '获取商品数据失败'})

        # 订单运费
        freight = Decimal(10.00)

        # 地址信息
        address_li = []
        try:
            for address in addresses:
                address_li.append({
                    'id': address.id,
                    'province': address.province.name,
                    'city': address.city.name,
                    'district': address.district.name,
                    'place': address.place,
                    'receiver': address.receiver,
                    'mobile': address.mobile,
                })
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '信息地址获取有误!'})

        # ④ 组织并返回响应数据
        context = {
            'addresses': address_li,
            'skus': sku_li,
            'freight': freight,
            'nowsite': request.user.default_address_id,
        }
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'context': context})


# POST /orders/commit/
class OrderCommitView(LoginRequiredMixin, View):
    def post(self, request):
        """订单创建"""
        # ① 获取参数并进行校验
        req_data = json.loads(request.body)
        address_id = req_data.get('address_id')
        pay_method = req_data.get('pay_method')

        if not all([address_id, pay_method]):
            return JsonResponse({'code': 400, 'message': '缺少必传参数'})

        # 地址是否存在
        try:
            address = Address.objects.get(id=address_id, is_delete=False, user=request.user)
        except Address.DoesNotExist:
            return JsonResponse({'code': 400, 'message': '地址信息有误'})

        # 1：货到付款 2：支付宝
        if pay_method not in (1, 2):
            return JsonResponse({'code': 400, 'message': '支付方式有误'})

        # ② 组织订单数据
        user = request.user
        # 生成订单id
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + '%09d' % user.id

        # total_count和total_amount
        total_count = 0
        total_amount = 0
        # 订单状态
        if pay_method == 1:
            # 货到付款：待发货
            status = 2
        else:
            # 支付宝：待支付
            status = 1

        # 运费(此处固定)
        freight = Decimal(10.00)

        with transaction.atomic():
            # 设置数据库操作时，事务中的保存点
            sid = transaction.savepoint()

            # ③ 向 tb_order_info 数据表中添加一行记录
            try:
                order = OrderInfo.objects.create(order_id=order_id,
                                                 user=user,
                                                 address=address,
                                                 total_count=total_count,
                                                 total_amount=total_amount,
                                                 pay_method=pay_method,
                                                 status=status,
                                                 freight=freight)
            except Exception as e:
                return JsonResponse({'code': 400,
                                     'message': '保存数据出错'})

            # ④ 遍历用户要购买的商品记录，循环向 tb_order_goods 表中添加记录
            # 从 redis 中获取用户要购买的商品信息
            cart_helper = CartHelper(request)
            cart_dict = cart_helper.get_redis_select_cart()
            sku_ids = cart_dict.keys()

            for sku_id in sku_ids:
                for i in range(3):
                    sku = SKU.objects.get(id=sku_id)
                    count = cart_dict[sku.id]

                    # 记录原始库存和销量
                    origin_stock = sku.stock
                    origin_sales = sku.sales

                    # 打印下单提示信息
                    print('下单用户：%s 商品库存：%d 购买数量：%d 尝试第 %d 次' % (
                        user.username, sku.stock, count, i + 1))

                    # 判断库存是否充足
                    if count > sku.stock:
                        # 数据库操作时，撤销事务中指定保存点之后的操作
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 400,
                                             'message': '商品库存不足'})

                    # 进行休眠操作，让 CPU 调度其它进程或线程，模拟订单并发问题
                    import time
                    time.sleep(10)

                    # 减少SKU商品库存、增加销量
                    new_stock = sku.stock - count
                    new_sales = sku.sales + count

                    # 注意：update 方法返回的是被更新的行数
                    # update tb_sku set stock=<new_stock>, sales=<news_sales>
                    # where id=<sku_id> and stock=<origin_stock>;

                    res = SKU.objects.filter(id=sku_id,
                                             stock=origin_stock).update(stock=new_stock,
                                                                        sales=new_sales)

                    if res == 0:
                        if i == 2:
                            # 尝试下单更新了 3 次，仍然失败，报下单失败错误
                            # 数据库操作时，撤销事务中指定保存点之后的操作
                            transaction.savepoint_rollback(sid)
                            return JsonResponse({'code': 400,
                                                 'message': '下单失败'})
                        # 更新失败,重新进行尝试
                        continue

                    # 增加对应SPU商品的销量
                    sku.spu.sales += count
                    sku.spu.save()

                    # 保存订单商品信息
                    try:
                        OrderGoods.objects.create(order=order,
                                                  sku=sku,
                                                  count=count,
                                                  price=sku.price)
                    except Exception as e:
                        return JsonResponse({'code': 400,
                                             'message': '保存数据出错'})

                    # 累加计算订单商品的总数量和总价格
                    total_count += total_count
                    total_amount += count * sku.price

                    # 更新成功,退出循环
                    break

            total_amount += freight
            order.total_count = total_count
            order.total_amount = total_amount
            order.save()

        # ⑤ 清除用户购物车中已购买的记录
        cart_helper.clear_redis_selected_cart()

        # ⑥ 返回响应
        return JsonResponse({'code': 0,
                             'message': '下单成功',
                             'order_id': order_id})
