#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import base64
import hashlib
import hmac
import requests
import time
import uuid
from urllib import parse
import oss2

class CosyClone:
    @staticmethod
    def _encode_text(text):
        encoded_text = parse.quote_plus(text)
        return encoded_text.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    @staticmethod
    def _encode_dict(dic):
        keys = dic.keys()
        dic_sorted = [(key, dic[key]) for key in sorted(keys)]
        encoded_text = parse.urlencode(dic_sorted)
        return encoded_text.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    @staticmethod
    def cosy_clone(access_key_id, access_key_secret, voicePrefix, audio_url):
        parameters = {'AccessKeyId': access_key_id,
                      'Action': 'CosyVoiceClone',
                      'Format': 'JSON',
                      'RegionId': 'cn-shanghai',
                      'SignatureMethod': 'HMAC-SHA1',
                      'SignatureNonce': str(uuid.uuid1()),
                      'SignatureVersion': '1.0',
                      'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      'Version': '2019-08-19',
                      'VoicePrefix': voicePrefix,
                      'Url': audio_url,
                      }
        # 构造规范化的请求字符串
        query_string = CosyClone._encode_dict(parameters)
        print('规范化的请求字符串: %s' % query_string)
        # 构造待签名字符串
        string_to_sign = 'POST' + '&' + CosyClone._encode_text('/') + '&' + CosyClone._encode_text(query_string)
        print('待签名的字符串: %s' % string_to_sign)
        # 计算签名
        secreted_string = hmac.new(bytes(access_key_secret + '&', encoding='utf-8'),
                                   bytes(string_to_sign, encoding='utf-8'),
                                   hashlib.sha1).digest()
        signature = base64.b64encode(secreted_string)
        print('签名: %s' % signature)
        # 进行URL编码
        signature = CosyClone._encode_text(signature)
        print('URL编码后的签名: %s' % signature)
        # 调用服务
        full_url = 'https://nls-slp.cn-shanghai.aliyuncs.com/?Signature=%s&%s' % (signature, query_string)
        print('url: %s' % full_url)
        # 提交HTTP POST请求
        response = requests.post(full_url)
        print(response.text)
    
    @staticmethod
    def cosy_list(access_key_id, access_key_secret, voice_prefix, page_index=1, page_size=10):
        parameters = {'AccessKeyId': access_key_id,
                      'Action': 'ListCosyVoice',
                      'Format': 'JSON',
                      'RegionId': 'cn-shanghai',
                      'SignatureMethod': 'HMAC-SHA1',
                      'SignatureNonce': str(uuid.uuid1()),
                      'SignatureVersion': '1.0',
                      'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      'Version': '2019-08-19',
                      'VoicePrefix': voice_prefix,
                      'PageIndex': page_index,
                      'PageSize': page_size,
                      }
        # 构造规范化的请求字符串
        query_string = CosyClone._encode_dict(parameters)
        print('规范化的请求字符串: %s' % query_string)
        # 构造待签名字符串
        string_to_sign = 'POST' + '&' + CosyClone._encode_text('/') + '&' + CosyClone._encode_text(query_string)
        print('待签名的字符串: %s' % string_to_sign)
        # 计算签名
        secreted_string = hmac.new(bytes(access_key_secret + '&', encoding='utf-8'),
                                   bytes(string_to_sign, encoding='utf-8'),
                                   hashlib.sha1).digest()
        signature = base64.b64encode(secreted_string)
        print('签名: %s' % signature)
        # 进行URL编码
        signature = CosyClone._encode_text(signature)
        print('URL编码后的签名: %s' % signature)
        # 调用服务
        full_url = 'https://nls-slp.cn-shanghai.aliyuncs.com/?Signature=%s&%s' % (signature, query_string)
        print('url: %s' % full_url)
        # 提交HTTP POST请求
        response = requests.post(full_url)
        print(response.text)


if __name__ == "__main__":
    # 用户信息
    access_key_id = os.getenv('ALIYUN_AK_ID')
    access_key_secret = os.getenv('ALIYUN_AK_SECRET')
    voice_prefix = 'mysound01'  # 修改为只包含英文字母和数字
    audio_url = 'https://my-sound01.oss-cn-shanghai.aliyuncs.com/audio/soundsample01.wav'

    CosyClone.cosy_clone(access_key_id, access_key_secret, voice_prefix, audio_url)
    CosyClone.cosy_list(access_key_id, access_key_secret, voice_prefix)

# 然后使用以下代码上传文件
# 填写您的OSS配置信息
endpoint = 'oss-cn-shanghai.aliyuncs.com'  # 根据您的地域选择
bucket_name = 'my-sound01'  # 修改为您的有效bucket名称

# 创建Bucket实例
auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint, bucket_name)

# 上传文件
# local_file是您本地音频文件的路径
# object_name是上传到OSS后的文件名
local_file = r'C:\Users\86181\Videos\Captures\soundsample01.wav'
object_name = 'audio/soundsample01.wav'

# 上传文件
bucket.put_object_from_file(object_name, local_file)

# 生成文件URL
url = f'https://{bucket_name}.{endpoint}/{object_name}'
print(f'文件URL: {url}')