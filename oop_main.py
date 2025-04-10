import asyncio
import os
import threading
import time
import sys
import io
from datetime import datetime
from copy_VoiceTTS import process_tts, get_token
import sounddevice as sd
import soundfile as sf
import pygame
import queue
import importlib
import numpy as np
from getusercomment_01 import start_comment_monitoring, stop_comment_monitoring
from getResponseFromQianwen import process_live_comment
from dotenv import load_dotenv

class StoryPlayer:
    def __init__(self):
        # 强制重新加载环境变量
        load_dotenv(override=True)
        
        # 配置参数
        self.use_pygame = False  # 设置为 False 使用虚拟声卡播放
        self.virtual_output_device_id = 17  # CABLE Input (VB-Audio Virtual Cable)
        
        # 初始化 pygame 混音器
        pygame.mixer.init()
        
        # 创建事件和锁
        self.story_paused = threading.Event()
        self.story_paused.clear()
        self.sentence_completed = threading.Event()
        self.sentence_completed.set()
        self.interaction_lock = threading.Lock()
        self.comment_cache_lock = threading.Lock()
        
        # 状态变量
        self.is_processing_interaction = False
        self.global_token = None
        self.comment_cache = []
        
        # 新增：保存被中断的句子信息
        self.interrupted_sentence = None
        self.interrupted_sentence_index = None
        self.interrupted_story_title = None
        
    async def play_audio(self, audio_data):
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
                # 检查是否需要暂停
                if self.story_paused.is_set():
                    print("检测到暂停事件，等待当前音频播放完成...")
                    # 等待当前音频播放完成
                    while pygame.mixer.get_busy():
                        await asyncio.sleep(0.1)
                    break
                await asyncio.sleep(0.1)
            
            # 清理临时文件
            try:
                os.remove(temp_file)
            except:
                pass
                
            # 只有在音频成功播放完成且未被暂停时才设置sentence_completed事件
            if not self.story_paused.is_set():
                self.sentence_completed.set()
                
        except Exception as e:
            print(f"播放音频时出错: {str(e)}")
            print("尝试使用备用播放方法...")
            try:
                # 备用播放方法：使用sounddevice
                with io.BytesIO(audio_data) as audio_buffer:
                    data, samplerate = sf.read(audio_buffer)
                    sd.play(data, samplerate=samplerate)
                    sd.wait()
                
                # 只有在备用方法也成功播放后才设置sentence_completed事件
                if not self.story_paused.is_set():
                    self.sentence_completed.set()
            except Exception as e2:
                print(f"备用播放方法也失败: {str(e2)}")
                print("音频播放失败，请检查系统音频设备")
                # 音频播放失败时，不设置sentence_completed事件
    
    def load_story_files(self, folder_path):
        """从文件夹中读取所有故事文本文件"""
        story_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
        story_files.sort()
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
    
    def split_into_sentences(self, text):
        """将文本分割成句子"""
        sentences = []
        for sentence in text.split('。'):
            sentence = sentence.strip()
            if sentence:
                if not sentence[-1] in ['。', '！', '？', '…']:
                    sentence += '。'
                sentences.append(sentence)
        return sentences
    
    def comment_handler(self, username, comment_text, comment_type="评论"):
        """处理直播间评论的回调函数"""
        # 将评论添加到缓存队列
        with self.comment_cache_lock:
            # 检查是否已存在相同的评论
            if not any(c[0] == username and c[1] == comment_text for c in self.comment_cache):
                self.comment_cache.append((username, comment_text, comment_type))
                print(f"缓存评论: {username}: {comment_text}")
                
                # 设置暂停事件，但等待当前句子播放完成
                if not self.sentence_completed.is_set():
                    print("等待当前句子播放完成...")
                    self.story_paused.set()
                else:
                    # 如果当前句子已经播放完成，立即处理评论
                    print(f"当前句子已播放完成，立即处理评论: {username}: {comment_text}")
                    self.story_paused.set()
                    asyncio.create_task(self.process_comment_cache())
    
    async def process_interaction(self, username, comment_text, comment_type="评论"):
        """处理用户互动"""
        # 使用锁确保同一时间只处理一个互动
        with self.interaction_lock:
            # 设置正在处理互动的标志
            self.is_processing_interaction = True
            
            try:
                # 使用千问AI生成回复
                system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
                if comment_type == "礼物":
                    system_prompt += "这是一个礼物，请表达感谢。"
                
                response = process_live_comment(f"{username}: {comment_text}", system_prompt)
                
                # 只打印评论原文和回复信息
                print(f"回复评论 - {username}: {comment_text} -> {response}")
                
                # 获取token，如果全局token不可用则重新获取
                token = self.global_token
                if not token:
                    token = get_token()
                    if token:
                        # 如果成功获取了新token，更新全局token
                        self.global_token = token
                
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
                    await self.play_audio(audio_data)
                else:
                    print(f"警告: 语音数据生成失败")
                
            except Exception as e:
                print(f"处理互动时出错: {str(e)}")
            finally:
                # 处理完成后，清空评论缓存
                with self.comment_cache_lock:
                    self.comment_cache.clear()
                
                # 重置处理标志
                self.is_processing_interaction = False
                
                # 确保sentence_completed事件被设置
                self.sentence_completed.set()
                
                # 恢复故事播放
                self.story_paused.clear()
    
    async def process_comment_cache(self):
        """处理评论缓存中的评论"""
        # 如果已经在处理互动，直接返回
        if self.is_processing_interaction:
            print("已经在处理互动，跳过")
            return
        
        # 从缓存中获取评论
        with self.comment_cache_lock:
            if not self.comment_cache:
                # 如果缓存为空，清除暂停事件
                print("评论缓存为空，清除暂停事件")
                self.story_paused.clear()
                return
            
            # 获取所有未处理的评论
            comments_to_process = self.comment_cache.copy()
            # 清空缓存，准备接收新评论
            self.comment_cache.clear()
        
        # 按顺序处理每条评论
        for comment in comments_to_process:
            username, comment_text, comment_type = comment
            print(f"处理评论: {username}: {comment_text}")
            await self.process_interaction(username, comment_text, comment_type)
            
            # 处理完一条评论后，检查是否有新评论加入
            with self.comment_cache_lock:
                if self.comment_cache:
                    # 如果有新评论，先处理新评论
                    break
    
    async def play_stories(self):
        """异步播放故事"""
        try:
            # 获取当前目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 获取语音转换token，优先使用全局token
            token = self.global_token or get_token()
            if not token:
                raise Exception("获取token失败")
            
            # 使用story文件夹
            story_folder = os.path.join(current_dir, "story")
            if not os.path.exists(story_folder):
                os.makedirs(story_folder)
                print(f"创建story文件夹: {story_folder}")
            
            # 读取故事文件
            stories = self.load_story_files(story_folder)
            if not stories:
                raise Exception("未找到任何故事文件")
            
            # 处理每个故事
            for story_file, story_content in stories:
                # 使用文件名（不含扩展名）作为故事标识和标题
                story_id = os.path.splitext(story_file)[0]
                story_title = story_id
                
                print(f"\n开始播放故事: 【{story_title}】")
                
                # 将故事分割成句子
                sentences = self.split_into_sentences(story_content)
                
                # 为每个句子生成语音并实时播放
                i = 0
                while i < len(sentences):
                    # 如果有被中断的句子，先处理它
                    if self.interrupted_sentence is not None and self.interrupted_story_title == story_title:
                        sentence = self.interrupted_sentence
                        i = self.interrupted_sentence_index
                        # 清除中断信息
                        self.interrupted_sentence = None
                        self.interrupted_sentence_index = None
                        self.interrupted_story_title = None
                    else:
                        sentence = sentences[i]
                    
                    # 清除sentence_completed事件，表示新句子开始播放
                    self.sentence_completed.clear()
                    
                    # 检查是否需要处理评论
                    if self.story_paused.is_set():
                        # 保存当前句子信息
                        self.interrupted_sentence = sentence
                        self.interrupted_sentence_index = i
                        self.interrupted_story_title = story_title
                        
                        # 处理评论缓存
                        await self.process_comment_cache()
                        continue  # 继续处理被中断的句子
                    
                    print(f"生成第 {i+1}/{len(sentences)} 句语音: {sentence[:30]}...")
                    
                    # 使用TTS生成语音数据
                    audio_data = process_tts(
                        token, 
                        [sentence],
                        story_title=story_title,
                        sentence_number=i+1,
                        total_sentences=len(sentences)
                    )
                    
                    # 播放生成的语音
                    if audio_data:
                        await self.play_audio(audio_data)
                        
                        # 检查是否需要处理评论
                        if self.story_paused.is_set():
                            # 保存当前句子信息
                            self.interrupted_sentence = sentence
                            self.interrupted_sentence_index = i
                            self.interrupted_story_title = story_title
                            
                            # 处理评论缓存
                            await self.process_comment_cache()
                            continue  # 继续处理被中断的句子
                        
                        # 如果成功播放完成且没有被中断，移动到下一句
                        i += 1
                    else:
                        print(f"警告: 第 {i+1} 句语音数据生成失败，跳过")
                        i += 1
                
                # 故事播放完成后的分隔
                print(f"故事 【{story_title}】 播放完成!")
                
        except Exception as e:
            print(f"播放故事时出错：{str(e)}")
    
    async def run(self):
        """运行故事播放器"""
        try:
            # 获取语音转换token并保存到全局变量
            self.global_token = get_token()
            if not self.global_token:
                raise Exception("获取token失败")
            
            # 提示用户输入直播间URL
            print("请输入抖音直播间URL (直接按回车跳过，将不进行评论监控):")
            douyin_live_url = input().strip()
            
            # 如果用户提供了URL，启动直播评论监控
            if douyin_live_url:
                print(f"使用直播间URL: {douyin_live_url}")
                # 确保评论监控成功启动
                if not start_comment_monitoring(douyin_live_url, self.comment_handler):
                    print("评论监控启动失败，请检查URL是否正确")
                    return
                print("评论监控已成功启动")
            else:
                print("跳过评论监控，仅播放故事")
            
            # 创建并启动故事播放任务
            story_task = asyncio.create_task(self.play_stories())
            
            # 等待故事播放任务完成
            await story_task
                
        except Exception as e:
            print(f"运行出错：{str(e)}")
        finally:
            # 如果启动了评论监控，确保停止
            if 'douyin_live_url' in locals() and douyin_live_url:
                stop_comment_monitoring()


if __name__ == "__main__":
    # 创建故事播放器实例并运行
    player = StoryPlayer()
    asyncio.run(player.run()) 