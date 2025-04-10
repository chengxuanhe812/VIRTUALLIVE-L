import asyncio
import os
import threading
import time
import sys
import io
from datetime import datetime
from cosyVoiceTTS import process_tts, get_token
import sounddevice as sd
import soundfile as sf
import pygame
import queue
import importlib
import numpy as np
from getusercomment import start_comment_monitoring, stop_comment_monitoring
from getResponseFromQianwen import process_live_comment
from dotenv import load_dotenv

# 强制重新加载环境变量
load_dotenv(override=True)

# 配置参数
USE_PYGAME = False  # 设置为 False 使用虚拟声卡播放，让直播伴侣可以捕获音频
# 注意：请使用 list_devices() 函数查看您系统中的设备列表，找到虚拟声卡的ID
# 对于抖音直播伴侣：请在抖音直播伴侣中选择与此虚拟声卡相同的音频输入设备
VIRTUAL_OUTPUT_DEVICE_ID = 17  # CABLE Input (VB-Audio Virtual Cable), Windows DirectSound

# 初始化 pygame 混音器
pygame.mixer.init()

# 创建一个事件用于控制故事播放和评论处理的协调
story_paused = threading.Event()
story_paused.clear()  # 初始状态为不暂停

# 全局变量，用于存储语音token
global_token = None
# 互动处理锁，防止多个互动同时处理导致冲突
interaction_lock = threading.Lock()
# 当前是否正在处理互动
is_processing_interaction = False

# 新增：评论缓存队列
comment_cache = []
# 新增：评论缓存锁，防止多线程访问冲突
comment_cache_lock = threading.Lock()
# 新增：句子播放完成事件
sentence_completed = threading.Event()
sentence_completed.set()  # 初始状态为已完成

def play_audio_data_virtual(audio_data, device):
    """
    通过虚拟声卡播放音频数据。
    
    使用 sounddevice 和 soundfile 库通过指定的虚拟声卡设备播放内存中的音频数据。
    
    Args:
        audio_data (bytes): WAV格式的音频数据
        device (int): 虚拟声卡设备的ID
    """
    try:
        # 从内存缓冲区读取音频数据
        with io.BytesIO(audio_data) as audio_buffer:
            data, samplerate = sf.read(audio_buffer)
            sd.play(data, samplerate=samplerate, device=device)
            sd.wait()
    except Exception as e:
        print(f"播放音频数据时出错: {str(e)}")

def play_audio_data_pygame(audio_data):
    """
    使用pygame播放内存中的音频数据。
    
    通过pygame库播放内存中的WAV音频数据。
    
    Args:
        audio_data (bytes): WAV格式的音频数据
    """
    try:
        # 创建临时文件对象
        with io.BytesIO(audio_data) as audio_buffer:
            sound = pygame.mixer.Sound(audio_buffer)
            sound.play()
            pygame.time.wait(int(sound.get_length() * 1000))  # 等待音频播放完成
    except Exception as e:
        print(f"播放音频数据时出错: {str(e)}")

async def play_audio(audio_data):
    """异步播放音频数据"""
    try:
        # 创建临时文件
        temp_file = "temp_audio.wav"
        with open(temp_file, "wb") as f:
            f.write(audio_data)
        
        # 加载并播放音频
        sound = pygame.mixer.Sound(temp_file)
        sound.play()
        
        # 等待播放完成
        while pygame.mixer.get_busy():
            await asyncio.sleep(0.1)  # 使用异步等待替代pygame.time.wait
        
        # 清理临时文件
        try:
            os.remove(temp_file)
        except:
            pass
            
        # 只有在音频成功播放后才设置sentence_completed事件
        sentence_completed.set()
            
    except Exception as e:
        print(f"播放音频时出错: {str(e)}")
        print("尝试使用备用播放方法...")
        try:
            # 备用播放方法：使用sounddevice
            import sounddevice as sd
            import soundfile as sf
            import io
            
            # 从内存中读取音频数据
            with io.BytesIO(audio_data) as audio_buffer:
                data, samplerate = sf.read(audio_buffer)
                sd.play(data, samplerate=samplerate)
                sd.wait()
            
            # 只有在备用方法也成功播放后才设置sentence_completed事件
            sentence_completed.set()
        except Exception as e2:
            print(f"备用播放方法也失败: {str(e2)}")
            print("音频播放失败，请检查系统音频设备")
            # 音频播放失败时，不设置sentence_completed事件

def load_story_files(folder_path):
    """
    从文件夹中读取所有故事文本文件。
    
    读取指定文件夹中所有.txt文件的内容，并按文件名排序返回。
    
    Args:
        folder_path (str): 包含故事文本文件的文件夹路径
        
    Returns:
        list: 包含(文件名, 文本内容)元组的列表
    """
    story_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    story_files.sort()  # 按文件名排序
    stories = []
    
    for file in story_files:
        try:
            with open(os.path.join(folder_path, file), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    stories.append((file, content))
        except Exception as e:
            print(f"读取文件 {file} 时出错: {str(e)}")
    
    return stories

def split_into_sentences(text):
    """
    将文本分割成句子。
    
    按句号分割文本，并确保每个句子都以适当的标点符号结尾。
    
    Args:
        text (str): 要分割的文本
        
    Returns:
        list: 分割后的句子列表
    """
    sentences = []
    for sentence in text.split('。'):
        sentence = sentence.strip()
        if sentence:
            # 检查是否以标点符号结尾
            if not sentence[-1] in ['。', '！', '？', '…']:
                sentence += '。'
            sentences.append(sentence)
    return sentences

def comment_handler(username, comment_text, comment_type="评论"):
    """
    处理直播间评论的回调函数
    
    当收到直播间评论时，将评论放入缓存队列
    
    Args:
        username (str): 评论用户名
        comment_text (str): 评论内容
        comment_type (str): 评论类型，默认为"评论"
    """
    global is_processing_interaction
    
    # 将评论添加到缓存队列
    with comment_cache_lock:
        comment_cache.append((username, comment_text, comment_type))
        print(f"缓存评论: {username}: {comment_text}")
        
        # 如果当前句子已播放完成且没有正在处理的互动，立即处理评论
        if sentence_completed.is_set() and not is_processing_interaction:
            print(f"设置暂停事件，准备处理评论: {username}: {comment_text}")
            story_paused.set()
            # 创建异步任务来处理评论
            asyncio.create_task(process_comment_cache())
        else:
            print(f"当前状态 - sentence_completed: {sentence_completed.is_set()}, is_processing_interaction: {is_processing_interaction}")

async def process_interaction(username, comment_text, comment_type="评论"):
    """
    处理用户互动
    
    使用千问AI生成回复，并播放回复语音
    
    Args:
        username (str): 用户名
        comment_text (str): 评论内容
        comment_type (str): 互动类型，默认为"评论"
    """
    global is_processing_interaction, global_token
    
    # 使用锁确保同一时间只处理一个互动
    with interaction_lock:
        # 设置正在处理互动的标志
        is_processing_interaction = True
        
        try:
            # 使用千问AI生成回复
            system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
            if comment_type == "礼物":
                system_prompt += "这是一个礼物，请表达感谢。"
            
            response = process_live_comment(f"{username}: {comment_text}", system_prompt)
            
            # 只打印评论原文和回复信息
            print(f"回复评论 - {username}: {comment_text} -> {response}")
            
            # 获取token，如果全局token不可用则重新获取
            token = global_token
            if not token:
                token = get_token()
                if token:
                    # 如果成功获取了新token，更新全局token
                    global_token = token
            
            if not token:
                print("无法获取语音token，跳过语音生成")
                return
            
            # 使用TTS生成语音数据
            audio_data = process_tts(
                token,
                [response],
                story_title=f"回复{username}",
                sentence_number=1,
                total_sentences=1
            )
            
            # 播放语音回复
            if audio_data:
                await play_audio(audio_data)
            else:
                print(f"警告: 语音数据生成失败")
            
        except Exception as e:
            print(f"处理互动时出错: {str(e)}")
        finally:
            # 处理完成后，清空评论缓存
            with comment_cache_lock:
                comment_cache.clear()
            
            # 重置处理标志
            is_processing_interaction = False
            
            # 确保sentence_completed事件被设置
            sentence_completed.set()
            
            # 恢复故事播放
            story_paused.clear()

# 处理评论缓存的函数
async def process_comment_cache():
    """处理评论缓存中的最新评论"""
    global is_processing_interaction
    
    # 如果已经在处理互动，直接返回
    if is_processing_interaction:
        print("已经在处理互动，跳过")
        return
    
    # 从缓存中获取最新的评论
    with comment_cache_lock:
        if not comment_cache:
            # 如果缓存为空，清除暂停事件
            print("评论缓存为空，清除暂停事件")
            story_paused.clear()
            return
        
        # 获取最新的评论（列表中的最后一项）
        latest_comment = comment_cache[-1]
        username, comment_text, comment_type = latest_comment
        print(f"准备处理评论: {username}: {comment_text}")
    
    # 处理最新的评论
    await process_interaction(username, comment_text, comment_type)

async def play_stories():
    """
    异步播放故事
    
    读取story文件夹中的故事文件，并使用TTS播放
    在播放过程中会检查是否需要暂停以处理评论
    """
    try:
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取语音转换token，优先使用全局token
        token = global_token or get_token()
        if not token:
            raise Exception("获取token失败")
        
        # 使用story文件夹
        story_folder = os.path.join(current_dir, "story")
        if not os.path.exists(story_folder):
            os.makedirs(story_folder)
            print(f"创建story文件夹: {story_folder}")
        
        # 读取故事文件
        stories = load_story_files(story_folder)
        if not stories:
            raise Exception("未找到任何故事文件")
        
        # 处理每个故事
        for story_file, story_content in stories:
            # 使用文件名（不含扩展名）作为故事标识和标题
            story_id = os.path.splitext(story_file)[0]
            story_title = story_id  # 使用文件名作为故事标题显示
            
            print(f"\n开始播放故事: 【{story_title}】")
            
            # 将故事分割成句子
            sentences = split_into_sentences(story_content)
            
            # 为每个句子生成语音并实时播放
            for i, sentence in enumerate(sentences, 1):
                # 清除sentence_completed事件，表示新句子开始播放
                sentence_completed.clear()
                
                # 如果有评论需要处理，先处理评论
                if story_paused.is_set():
                    await process_comment_cache()
                
                print(f"生成第 {i}/{len(sentences)} 句语音: {sentence[:30]}...")
                
                # 使用TTS生成语音数据
                audio_data = process_tts(
                    token, 
                    [sentence],
                    story_title=story_title,
                    sentence_number=i,
                    total_sentences=len(sentences)
                )
                
                # 播放生成的语音
                if audio_data:
                    await play_audio(audio_data)  # 使用await调用异步函数
                    
                    # 等待一小段时间，确保sentence_completed事件被正确处理
                    await asyncio.sleep(0.5)
                    
                    # 检查是否有评论需要处理
                    if story_paused.is_set():
                        await process_comment_cache()
                else:
                    print(f"警告: 第 {i} 句语音数据生成失败，跳过")
                    continue
                
            # 故事播放完成后的分隔
            print(f"故事 【{story_title}】 播放完成!")
            
    except Exception as e:
        print(f"播放故事时出错：{str(e)}")

async def main():
    """
    主函数，协调整个程序的执行流程。
    
    执行以下步骤：
    1. 提示用户输入直播间URL，可选择跳过评论监控
    2. 如果提供URL，启动直播评论监控
    3. 启动故事播放协程
    
    整个过程是异步的，使用asyncio协程实现。
    
    Raises:
        Exception: 如果在执行过程中发生错误
    """
    global global_token
    
    try:
        # 打印环境变量值进行调试
        # print("环境变量 ALIYUN_APPKEY:", os.getenv('ALIYUN_APPKEY'))
        # print("环境变量 ALIYUN_AK_ID:", os.getenv('ALIYUN_AK_ID'))
        # print("环境变量 ALIYUN_AK_SECRET:", os.getenv('ALIYUN_AK_SECRET'))
        
        # 提示用户输入直播间URL
        print("请输入抖音直播间URL (直接按回车跳过，将不进行评论监控):")
        douyin_live_url = input().strip()
        
        # 获取语音转换token并保存到全局变量
        global_token = get_token()
        if not global_token:
            raise Exception("获取token失败")
        
        # 如果用户提供了URL，启动直播评论监控
        if douyin_live_url:
            print(f"使用直播间URL: {douyin_live_url}")
            start_comment_monitoring(douyin_live_url, comment_handler)
        else:
            print("跳过评论监控，仅播放故事")
        
        # 创建并启动故事播放任务
        story_task = asyncio.create_task(play_stories())
        
        # 等待故事播放任务完成
        await story_task
            
    except Exception as e:
        print(f"运行出错：{str(e)}")
    finally:
        # 如果启动了评论监控，确保停止
        if 'douyin_live_url' in locals() and douyin_live_url:
            stop_comment_monitoring()

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
