"""
xtbo97
"""
import os
from collections import OrderedDict

from django.conf import settings
from django.template import loader

from contents.models import Content, ContentCategory
from goods.models import GoodsChannel


def generate_static_index_html():
    """ 网站首页静态化操作 """
    print('---generate_static_index_html---')
    # 1.查询数据库获取静态化首页所需的数据
    categories = OrderedDict()
    channels = GoodsChannel.objects.order_by('group_id', 'sequence')

    for channel in channels:
        group_id = channel.group_id
        if group_id not in categories:
            categories[group_id] = {
                'channels': [],
                'sub_cats': [],
            }

        # 2.获取频道对应的一级分类
        cat1 = channel.category

        categories[group_id]['channels'].append({
            'id': cat1.id,
            'name': cat1.name,
            'url': channel.url,
        })

        # 3.获取一级分类的下级分类(二级分类)
        cat2s = cat1.subs.all()
        for cat2 in cat2s:
            cat2.sub_cats = []

            # 4.获取二级分类的下级分类(三级分类)
            cat3s = cat2.subs.all()
            for cat3 in cat3s:
                cat2.sub_cats.append(cat3)
            categories[group_id]['sub_cats'].append(cat2)

    # 5.首页广告数据获取
    contents = {}
    content_cats = ContentCategory.objects.all()
    for cat in content_cats:
        contents[cat.key] = Content.objects.filter(category=cat,
                                                   status=True).order_by('sequence')

    # 6.加载首页模板文件，进行页面渲染
    context = {
        'categories': categories,
        'contents': contents,
        'nginx_url': 'http://192.168.19.131:8888',
    }

    template = loader.get_template('index.html')
    static_html = template.render(context)

    # 7.将渲染生成的内容写入生成静态文件
    save_path = os.path.join(settings.GENERATED_STATIC_HTML_FILES_DIR, 'index.html')

    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(static_html)