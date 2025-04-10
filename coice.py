# coding=utf-8
#
# Installation instructions for pyaudio:
# APPLE Mac OS X
#   brew install portaudio
#   pip install pyaudio
# Debian/Ubuntu
#   sudo apt-get install python-pyaudio python3-pyaudio
#   or
#   pip install pyaudio
# CentOS
#   sudo yum install -y portaudio portaudio-devel && pip install pyaudio
# Microsoft Windows
#   python -m pip install pyaudio

# 导入本地stream_input_tts模块
from stream_input_tts import NlsStreamInputTtsSynthesizer
import time
import os
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv

# 加载环境变量文件中的配置
load_dotenv(override=True)

# 将音频保存进文件
SAVE_TO_FILE = True
# 将音频通过播放器实时播放，需要具有声卡。在服务器上运行请将此开关关闭
PLAY_REALTIME_RESULT = True
if PLAY_REALTIME_RESULT:
    import pyaudio

def get_token():
    """获取阿里云语音合成服务的访问Token"""
    try:
        # 创建AcsClient实例，用于与阿里云API通信
        client = AcsClient(
            os.getenv('ALIYUN_AK_ID'),        # 阿里云AccessKey ID
            os.getenv('ALIYUN_AK_SECRET'),    # 阿里云AccessKey Secret
            "cn-shanghai"                      # 区域ID，固定为上海区域
        )

        # 创建请求对象
        request = CommonRequest()
        request.set_method('POST')
        request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
        request.set_version('2019-02-28')
        request.set_action_name('CreateToken')
        request.set_protocol_type('https')
        
        # 添加必要的请求头
        request.add_header('Content-Type', 'application/json')
        
        # 发送请求
        response = client.do_action_with_exception(request)
        response = json.loads(response)

        # 检查响应
        if 'Token' in response and 'Id' in response['Token']:
            print("Token获取成功")
            return response['Token']['Id']
        else:
            print(f"获取Token失败: {response}")
            return None

    except Exception as e:
        print(f"获取Token时出错: {str(e)}")
        print("请检查以下内容：")
        print("1. AccessKey ID 和 Secret 是否正确")
        print("2. 是否已在阿里云控制台开通语音合成服务")
        print("3. AccessKey 是否有语音合成服务的访问权限")
        return None

test_text = [
    "流式文本语音合成SDK，",
    "可以将输入的文本",
    "合成为语音二进制数据，",
    "相比于非流式语音合成，",
    "流式合成的优势在于实时性",
    "更强。用户在输入文本的同时",
    "可以听到接近同步的语音输出，",
    "极大地提升了交互体验，",
    "减少了用户等待时间。",
    "适用于调用大规模",
    "语言模型（LLM），以",
    "流式输入文本的方式",
    "进行语音合成的场景。",
]

if __name__ == "__main__":
    if SAVE_TO_FILE:
        file = open("output.wav", "wb")
    if PLAY_REALTIME_RESULT:
        player = pyaudio.PyAudio()
        stream = player.open(
            format=pyaudio.paInt16, channels=1, rate=24000, output=True
        )

    # 配置回调函数
    def test_on_data(data, *args):
        if SAVE_TO_FILE:
            file.write(data)
        if PLAY_REALTIME_RESULT:
            stream.write(data)

    def test_on_message(message, *args):
        print("on message=>{}".format(message))

    def test_on_close(*args):
        print("on_close: args=>{}".format(args))

    def test_on_error(message, *args):
        print("on_error message=>{} args=>{}".format(message, args))

    # 获取token和appkey
    token = get_token()
    appkey = os.getenv('ALIYUN_APPKEY')
    
    if not token or not appkey:
        print("无法获取token或appkey，请检查配置")
        exit(1)
    
    # 使用NlsStreamInputTtsSynthesizer类进行流式语音合成
    print("开始流式语音合成...")
    
    # 创建SDK实例
    sdk = NlsStreamInputTtsSynthesizer(
        # 由于目前阶段大模型音色只在北京地区服务可用，因此需要调整url到北京
        url="wss://nls-gateway-cn-beijing.aliyuncs.com/ws/v1",
        
        token=token,                                            # 动态获取的token
        appkey=appkey,                                          # 从.env文件中获取的appkey
        on_data=test_on_data,
        on_close=test_on_close,
        on_error=test_on_error,
        callback_args=[],
    )
    
    # 开始合成
    sdk.startStreamInputTts(
        voice="cosyvoice-mysound01-85804c0",                   # 语音合成说话人
        aformat="wav",                                          # 合成音频格式
        sample_rate=24000,                                      # 合成音频采样率
        volume=50,                                              # 合成音频的音量
        speech_rate=0,                                          # 合成音频语速
        pitch_rate=0,                                           # 合成音频的音调
    )
    
    # 流式输入文本
    for i, text in enumerate(test_text):
        print(f"输入第{i+1}/{len(test_text)}段文本: {text}")
        sdk.sendStreamInputTts(text)
        # 添加一个小延迟，避免请求过于频繁
        time.sleep(0.1)
    
    # 停止合成
    sdk.stopStreamInputTts()
    
    # 关闭SDK实例
    sdk.shutdown()
    
    # 关闭文件
    if SAVE_TO_FILE:
        file.close()
    
    # 关闭音频流
    if PLAY_REALTIME_RESULT:
        stream.stop_stream()
        stream.close()
        player.terminate()
    
    print("所有文本处理完成")