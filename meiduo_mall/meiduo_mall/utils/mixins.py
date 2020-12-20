"""
xtbo97
"""
from django.http import JsonResponse


def login_required(view_func):
    """ 登陆验证装饰器函数 """

    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            # 如果用户已登录,调用对应的view视图
            return view_func(request, *args, **kwargs)
        else:
            # 如果用户未登录,直接返回未登陆提示
            return JsonResponse({'code': 400,
                                 'message': '用户未登录!'})

    return wrapper


class LoginRequiredMixin(object):
    """ 登陆验证Mixin扩展类 """

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        # 调用登陆验证装饰器函数
        return login_required(view)
