"""
xtbo97
"""
import os
from collections import OrderedDict

from django.conf import settings
from django.template import loader

from goods.models import GoodsChannel


def generate_static_list_html():
    """ 列表页商品分类静态化操作 """
    print('---generate_static_list_html---')

    # 1.查询数据库获取静态化列表页商品分类所需的数据
    categories = OrderedDict()

    channels = GoodsChannel.objects.order_by('group_id', 'sequence')

    for channel in channels:
        group_id = channel.group_id
        if group_id not in categories:
            categories[group_id] = {
                'channels': [],
                'sub_cats': [],
            }
        # 获取频道对应的一级分类
        cat1 = channel.category

        categories[group_id]['channels'].append({
            'id': cat1.id,
            'name': cat1.name,
            'url': channel.url,
        })

        # 获取一级分类的下级分类(二级分类)
        cat2s = cat1.subs.all()
        for cat2 in cat2s:
            cat2.sub_cats = []

            # 获取二级分类下的下级分类(三级分类)
            cat3s = cat2.subs.all()
            for cat3 in cat3s:
                cat2.sub_cats.append(cat3)
            categories[group_id]['sub_cats'].append(cat2)

        context = {
            'categories': categories,
        }
        template = loader.get_template('list.html')
        static_html = template.render(context)

        # 2.将渲染生成的内容写入生成静态文件
        save_path = os.path.join(settings.GENERATED_STATIC_HTML_FILES_DIR, 'list.html')
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(static_html)
