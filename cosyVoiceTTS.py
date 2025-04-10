# coding=utf-8
"""
阿里云语音合成服务模块
将文本转换为语音，使用阿里云的语音合成服务
"""

# 阿里云语音合成服务相关链接
# 示例代码参考文档
# https://help.aliyun.com/zh/isi/developer-reference/stream-input-tts-sdk-quick-start

# 获取appkey和accesstoken的链接
# appkey申请地址: https://nls-portal.console.aliyun.com/applist  
# accesstoken申请地址: https://nls-portal.console.aliyun.com/overview

# 示例代码使用注意事项:
# 1. SDK方法名更新 - 示例代码中的方法名与最新SDK不一致,需参考SDK源码进行修改
# 2. SSL证书缺失 - 需要安装SSL证书才能连接NLS服务
# 3. 声音ID无效 - 示例代码中使用的声音ID不存在,需要更换为有效的声音ID
# 4. 将每句话分别保存为音频文件的能力始终无法实现

import nls
import time
import os
import json
from datetime import datetime
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv

# 加载环境变量文件中的配置，强制重新加载
load_dotenv(override=True)

# 设置打开日志输出
nls.enableTrace(False)

# 配置选项
# 将音频保存进文件
SAVE_TO_FILE = True
# 将音频通过播放器实时播放，需要具有声卡。在服务器上运行请将此开关关闭
PLAY_REALTIME_RESULT = False
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

def get_story_folder():
    """获取story文件夹路径"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    story_folder = os.path.join(current_dir, "story")
    if not os.path.exists(story_folder):
        os.makedirs(story_folder)
    return story_folder

def load_text_from_story_folder():
    """从story文件夹中读取所有txt文件的内容"""
    story_folder = get_story_folder()
    if not os.path.exists(story_folder):
        print("未找到story文件夹，使用默认文本")
        return [
            "这是一个示例故事。",
            "当无法获取到实际故事内容时，将播放这段默认文本。",
            "请确保story文件夹中有有效的文本文件，或检查故事生成服务是否正常工作。"
        ]
    
    text_content = []
    files_processed = 0
    
    # 获取文件夹中所有txt文件
    txt_files = [f for f in os.listdir(story_folder) if f.endswith('.txt')]
    # 按文件的创建时间排序，最新的文件排在前面
    txt_files.sort(key=lambda x: os.path.getctime(os.path.join(story_folder, x)), reverse=True)
    
    # 如果有文件，只处理最新的一个文件
    if txt_files:
        latest_file = txt_files[0]
        file_path = os.path.join(story_folder, latest_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 将内容按句号分割，确保每段都是完整的句子
                sentences = []
                for sentence in content.split('。'):
                    sentence = sentence.strip()
                    if sentence:
                        # 如果句子不以标点符号结尾，添加句号
                        if not sentence[-1] in ['。', '！', '？', '…']:
                            sentence += '。'
                        sentences.append(sentence)
                text_content.extend(sentences)
                files_processed += 1
                print(f"已加载文件: {latest_file}")
        except Exception as e:
            print(f"读取文件 {latest_file} 时出错: {str(e)}")
    
    if not text_content:
        print("所有文件为空，使用默认文本")
        return [
            "这是一个示例故事。",
            "当无法获取到实际故事内容时，将播放这段默认文本。",
            "请确保story文件夹中有有效的文本文件，或检查故事生成服务是否正常工作。"
        ]
    
    return text_content

# 替换原来的 test_text 定义
test_text = load_text_from_story_folder()

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
        voice_id = "siqi"
        
        # 初始化语音合成SDK
        sdk = nls.NlsSpeechSynthesizer(
            url="wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1",  # 使用上海区域的克隆语音服务地址
            token=token,                                            # 访问Token
            appkey=appkey,                                          # 应用的AppKey
            on_data=test_on_data,                                   # 数据回调函数
            on_close=test_on_close,                                 # 关闭回调函数
            on_error=test_on_error,                                 # 错误回调函数
            callback_args=[]                                        # 回调函数的额外参数
        )

        # 开始语音合成，设置参数
        sdk.start(
            text=test_text[0],          # 要合成的文本
            voice=voice_id,             # 使用克隆的语音ID
            aformat="wav",               # 音频格式
            sample_rate=16000,           # 采样率
            volume=50,                   # 音量，范围0-100
            speech_rate=-200,               # 语速，0表示正常语速
            pitch_rate=30                 # 音调，0表示正常音调
        )

        # 等待合成完成
        max_wait = 30  # 最大等待时间，秒
        wait_start = time.time()
        while not completed and time.time() - wait_start < max_wait:
            time.sleep(0.1)

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

if __name__ == "__main__":
    # 首先获取Token
    token = get_token()
    if not token:
        print("Failed to get token. Exiting...")
        exit(1)

    # 获取要处理的文本
    sentences = load_text_from_story_folder()
    if not sentences:
        print("未找到任何文本内容，退出...")
        exit(1)
        
    print(f"共找到 {len(sentences)} 个句子，开始处理...")

    # 为每句话单独处理TTS转换
    for index, text in enumerate(sentences, 1):
        print(f"正在处理第 {index} 句话")
        
        # 每句话单独调用TTS转换
        audio_data = process_tts(token, [text], story_title="示例故事", sentence_number=index, total_sentences=len(sentences))
        
        # 如果需要测试播放，可以临时保存并播放
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        print(f"音频数据大小: {len(audio_data)} 字节")
        print(f"临时保存到: {temp_path}")
        
        # 可以在这里添加播放代码进行测试