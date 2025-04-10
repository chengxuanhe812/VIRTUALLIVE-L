#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
from dotenv import load_dotenv
from cosyVoiceTTS import get_token, process_tts
import sounddevice as sd
import soundfile as sf
import io

# 加载环境变量
load_dotenv(override=True)

def test_clone_voice():
    """测试克隆语音是否正常工作"""
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
            
            # 保存音频文件
            with open("test_clone_voice.wav", "wb") as f:
                f.write(audio_data)
            print("音频文件已保存为 test_clone_voice.wav")
        else:
            print("语音生成失败")

    except Exception as e:
        print(f"测试过程中出错：{str(e)}")

if __name__ == "__main__":
    test_clone_voice() 