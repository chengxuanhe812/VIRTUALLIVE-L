"""
千问大模型回复生成模块
使用千问大模型对直播间用户评论生成回复
"""

import os
from datetime import datetime
import re
import time
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, List, Tuple

# 加载环境变量
load_dotenv()

# 初始化OpenAI客户端（用于调用千问API）
client = OpenAI(
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 全局变量，用于存储所有回复
# 格式: [(timestamp, comment, response), ...]
RESPONSES_HISTORY: List[Tuple[datetime, str, str]] = []

# 最新回复
LATEST_RESPONSE: Dict[str, str] = {
    "comment": "",
    "response": "",
    "timestamp": ""
}

def get_response_from_qianwen(comment, system_prompt=None):
    """
    从千问大模型获取对用户评论的回复
    
    调用千问API获取对用户评论的回复。
    
    Args:
        comment (str): 用户评论
        system_prompt (str, optional): 系统提示词，用于指导模型回复的风格和内容
        
    Returns:
        str: 模型生成的回复
    """
    if system_prompt is None:
        system_prompt = "你是一个友好、幽默的直播助手，负责回答直播间观众的问题和评论。回复要简洁、有趣，不超过50个字。"
    
    try:
        # 调用千问API
        completion = client.chat.completions.create(
            model="qwen-plus",  # 可按需更换模型名称
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': comment}
            ],
            stream=False
        )
        
        # 获取回复内容
        response = completion.choices[0].message.content
        return response
    
    except Exception as e:
        print(f"调用千问API时发生错误: {str(e)}")
        return f"抱歉，我暂时无法回答这个问题。错误信息: {str(e)}"

def store_response(comment, response):
    """存储评论和回复到全局变量"""
    global RESPONSES_HISTORY, LATEST_RESPONSE
    
    # 获取当前时间
    now = datetime.now()
    
    # 更新最新回复
    LATEST_RESPONSE = {
        "comment": comment,
        "response": response,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 添加到历史记录
    RESPONSES_HISTORY.append((now, comment, response))
    
    # 如果历史记录过长，保留最近的100条
    if len(RESPONSES_HISTORY) > 100:
        RESPONSES_HISTORY = RESPONSES_HISTORY[-100:]

def process_live_comment(comment, system_prompt=None):
    """处理直播评论并获取回复"""
    # 从千问获取回复
    response = get_response_from_qianwen(comment, system_prompt)
    
    # 存储回复
    store_response(comment, response)
    
    # 返回回复内容
    return response

def get_latest_response():
    """获取最新的回复"""
    global LATEST_RESPONSE
    return LATEST_RESPONSE

def get_response_history(limit=None):
    """获取历史回复记录"""
    global RESPONSES_HISTORY
    
    # 如果指定了限制，返回最近的n条记录
    if limit and isinstance(limit, int) and limit > 0:
        return RESPONSES_HISTORY[-limit:]
    
    # 否则返回所有记录
    return RESPONSES_HISTORY

def clear_response_history():
    """清空回复历史记录"""
    global RESPONSES_HISTORY, LATEST_RESPONSE
    RESPONSES_HISTORY = []
    LATEST_RESPONSE = {
        "comment": "",
        "response": "",
        "timestamp": ""
    }

if __name__ == "__main__":
    print("此模块不应直接运行，请通过main.py启动程序") 