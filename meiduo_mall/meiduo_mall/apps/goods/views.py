from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views import View

from goods.models import GoodsCategory, SKU
from goods.utils import get_breadcrumb


# GET /list/(?P<category_id>\d+)/skus/?page=页码&page_size=页容量&ordering=排序方式
class SKUListView(View):
    def get(self, request, category_id):
        """ 分类商品数据获取 """
        # 1.接收参数并校验
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)
        ordering = request.GET.get('ordering', '-create_time')

        # 2.查询数据库相关数据
        try:
            cat3 = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return JsonResponse({'code': 400,
                                 'message': '分类数据不存在!'})

        # 面包屑导航数据
        try:
            breadcrumb = get_breadcrumb(cat3)
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '获取面包屑导航数据出错!'})

        # 分类SKU商品数据
        try:
            skus = SKU.objects.filter(category_id=category_id,
                                      is_launched=True).order_by(ordering)
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '分类SKU商品数据获取错误!'})

        # 3.对SKU商品进行分页处理
        paginator = Paginator(skus, page_size)
        results = paginator.get_page(page)

        sku_li = []
        # FastDFS 中 nginx 服务器的地址
        nginx_url = 'http://192.168.19.131:8888/'

        for sku in results:
            sku_li.append({
                'id': sku.id,
                'name': sku.name,
                'price': sku.price,
                'comments': sku.comments,
                'default_image_url': nginx_url + sku.default_image.name,
            })

        # 4.返回响应数据
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'breadcrumb': breadcrumb,
                             'count': paginator.num_pages,
                             'list': sku_li, })


# GET /hot/(?P<category_id>\d+)/
class Hot2SKUView(View):
    def get(self, request, category_id):
        """ 获取当前分类下的 TOP2 热销商品数据 """
        # 1.获取三级分类下所有的SKU,按销量降序排序取并前两位
        try:
            skus = SKU.objects.filter(category_id=category_id,
                                      is_launched=True).order_by('-sales')[:2]
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'message': '分类SKU商品数据获取错误'})
        hot_skus = []

        # FastDFS 中 nginx 服务器的地址
        nginx_url = 'http://192.168.19.131:8888/'

        for sku in skus:
            hot_sku = {
                'is': sku.id,
                'name': sku.name,
                'price': sku.price,
                'default_image_url': nginx_url + sku.default_image.name
            }
            hot_skus.append(hot_sku)

        # 返回响应
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'hot_skus': hot_skus})
