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

# 添加process_tts函数，用于被主控文件调用
def process_tts(token, test_text, story_title=None, sentence_number=None, total_sentences=None):
    """
    处理文本到语音的转换
    
    使用阿里云语音合成服务将文本转换为语音，并返回音频数据。
    
    Args:
        token (str): 阿里云语音合成服务的访问Token
        test_text (list): 要转换的文本列表
        story_title (str, optional): 故事标题，用于控制台输出
        sentence_number (int, optional): 当前句子编号，用于控制台输出
        total_sentences (int, optional): 总句子数，用于控制台输出
        
    Returns:
        bytes: 生成的WAV音频数据
    """
    # 创建一个内存缓冲区来存储音频数据
    import io
    audio_buffer = io.BytesIO()
    
    # 创建一个事件标志，用于通知合成完成
    completed = False
    
    try:
        # 在控制台显示生成信息
        if story_title and sentence_number and total_sentences:
            print(f"生成语音: 【{story_title}】 {sentence_number}/{total_sentences}: {test_text[0]}")

        def test_on_data(data, *args):
            """数据回调函数，处理接收到的音频数据"""
            nonlocal audio_buffer
            audio_buffer.write(data)

        def test_on_message(message, *args):
            """消息回调函数，处理接收到的消息"""
            # 只在调试模式下打印消息
            if "debug" in str(message).lower():
                print("on message=>{}".format(message))

        def test_on_close(*args):
            """关闭回调函数，处理连接关闭事件"""
            nonlocal completed
            completed = True

        def test_on_error(message, *args):
            """错误回调函数，处理错误事件"""
            nonlocal completed
            completed = True
            error_msg = str(message)
            print(f"语音合成错误: {error_msg}")
            
            # 处理特定错误码
            if "418" in error_msg:
                print("错误418: 语音克隆服务未正确配置或未激活")
                print("请检查：")
                print("1. 是否已在阿里云控制台开通语音克隆服务")
                print("2. 音频样本是否符合要求（WAV格式，16kHz采样率，30秒以上）")
                print("3. AccessKey是否有语音克隆服务的权限")
                print("4. 是否使用了正确的克隆语音ID")
            elif "401" in error_msg:
                print("错误401: Token无效或已过期")
                print("请重新获取Token")
            elif "403" in error_msg:
                print("错误403: 没有访问权限")
                print("请检查AccessKey权限配置")
            elif "40002001" in error_msg:
                print("错误40002001: 下载音频文件失败")
                print("请检查：")
                print("1. OSS中的音频文件是否存在")
                print("2. OSS的访问权限是否正确设置")
                print("3. 音频文件的URL是否可以正常访问")
                print("4. 音频文件格式是否符合要求（WAV格式，16kHz采样率）")

        # 获取appkey
        appkey = os.getenv('ALIYUN_APPKEY')
        if not appkey:
            print("错误：未找到ALIYUN_APPKEY环境变量")
            return None

        # 使用克隆语音ID
        # 使用最新创建的语音模型ID
        voice_id = "cosyvoice-mysound01-85804c0"
        
        # 初始化语音合成SDK
        sdk = NlsStreamInputTtsSynthesizer(
            # 由于目前阶段大模型音色只在北京地区服务可用，因此需要调整url到北京
            url="wss://nls-gateway-cn-beijing.aliyuncs.com/ws/v1",
            token=token,                                            # 访问Token
            appkey=appkey,                                          # 应用的AppKey
            on_data=test_on_data,                                   # 数据回调函数
            on_close=test_on_close,                                 # 关闭回调函数
            on_error=test_on_error,                                 # 错误回调函数
            callback_args=[]                                        # 回调函数的额外参数
        )

        # 开始语音合成，设置参数
        sdk.startStreamInputTts(
            voice=voice_id,             # 使用克隆的语音ID
            aformat="wav",               # 音频格式
            sample_rate=24000,           # 采样率
            volume=50,                   # 音量，范围0-100
            speech_rate=0,               # 语速，0表示正常语速
            pitch_rate=0                 # 音调，0表示正常音调
        )
        
        # 发送文本进行合成
        sdk.sendStreamInputTts(test_text[0])
        
        # 停止合成
        sdk.stopStreamInputTts()
        
        # 关闭SDK连接
        sdk.shutdown()

        # 获取合成的音频数据
        audio_data = audio_buffer.getvalue()

        # 检查音频数据是否有效
        if len(audio_data) > 0:
            print("语音合成成功")
            return audio_data
        else:
            print("语音合成失败：未生成音频数据")
            return None

    except Exception as e:
        print(f"语音合成过程出错: {str(e)}")
        return None
    finally:
        # 确保关闭SDK连接
        try:
            sdk.shutdown()
        except:
            pass

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