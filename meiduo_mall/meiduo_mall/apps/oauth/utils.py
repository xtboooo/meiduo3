"""
xtbo97
"""
from django.conf import settings
from itsdangerous import TimedJSONWebSignatureSerializer, BadData


def generate_secret_openid(openid):
    """ 对传入的 openid 进行加密处理，返回加密之后的内容 """
    # settings.SECRET_KEY: 加密使用的秘钥
    # 解密过期时间: 10min = 600s
    serializer = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                                 expires_in=600, )

    # 待加密的数据
    data = {'openid': openid}

    # 数据加密操作
    secret_openid = serializer.dumps(data).decode()

    # 返回加密后的openid
    return secret_openid


def check_secret_openid(secret_openid):
    """ 对加密的 openid 进行解密 """
    # 创建对象
    serializer = TimedJSONWebSignatureSerializer(settings.SECRET_KEY)

    try:
        # 进行解密操作
        data = serializer.loads(secret_openid)
    except BadData:
        # 解密出错,返回None
        return None
    else:
        # 获取解密之后的openid并返回
        return data.get('openid')
