from django.core.cache import cache
from django.http import JsonResponse
from django.views import View

from areas.models import Area


# GET /areas/
class ProvinceAreasView(View):
    def get(self, request):
        """ 获取所有省级地区信息 """
        # 1.查询数据库所有省级地区信息
        # 先尝试从缓存中获取省级地区数据
        cache_provinces = cache.get('provinces')
        if not cache_provinces:
            try:
                provinces = Area.objects.filter(parent_id=None).values('id', 'name')
                provinces = list(provinces)

                # 缓存省级地区数据
                cache.set('provinces', provinces, 3600)
            except Exception as e:
                return JsonResponse({'code': 400,
                                     'message': '省级信息获取错误!'})
        else:
            provinces = cache_provinces

        # 2.组织数据信息并返回响应
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'provinces': provinces})


# GET /areas/(?P<pk>\d+)/
class SubAreasView(View):
    def get(self, request, pk):
        """ 获取指定地区的下级地区信息 """
        # 1.根据pk获取指定地区的下级地区信息
        # 先尝试从缓存中获取指定地区的下级地区数据
        cache_subs = cache.get('sub_areas_%s' % pk)
        if not cache_subs:
            try:
                subs_li = Area.objects.filter(parent_id=pk).values('id', 'name')
                subs_li = list(subs_li)

                # 缓存指定地区的下级地区数据
                cache.set('sub_areas_%s' % pk, subs_li, 3600)

            except Exception as e:
                return JsonResponse({'code': 400,
                                     'message': '子级地区信息获取错误!'})
        else:
            # 直接使用缓存中的数据
            subs_li = cache_subs

        # 2.组织数据并返回
        return JsonResponse({'code': 0,
                             'message': 'OK',
                             'subs': subs_li, })
