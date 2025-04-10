import os
from dotenv import load_dotenv
from cosyVoiceTTS import process_tts, get_token
import sounddevice as sd
import soundfile as sf
import pygame
import numpy as np
import io
import time

# 加载环境变量
load_dotenv()

# 初始化 pygame 混音器
pygame.mixer.init()

def test_tts():
    try:
        # 获取token
        print("正在获取token...")
        token = get_token()
        if not token:
            print("获取token失败")
            return

        print(f"获取到token: {token}")

        # 测试文本
        test_text = "你好，这是一个测试。"
        
        # 生成语音
        print("正在生成语音...")
        audio_data = process_tts(
            token,
            [test_text],
            story_title="测试",
            sentence_number=1,
            total_sentences=1
        )

        if audio_data:
            print("语音生成成功，正在播放...")
            # 从内存缓冲区读取音频数据
            with io.BytesIO(audio_data) as audio_buffer:
                data, samplerate = sf.read(audio_buffer)
                sd.play(data, samplerate=samplerate)
                sd.wait()
            print("播放完成！")
        else:
            print("语音生成失败")

    except Exception as e:
        print(f"测试过程中出错：{str(e)}")

if __name__ == "__main__":
    test_tts()