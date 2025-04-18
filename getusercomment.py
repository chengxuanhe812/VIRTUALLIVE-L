"""
抖音直播评论和礼物抓取模块
用于从抖音直播页面抓取实时评论和礼物信息
"""

import asyncio
import os
import threading
import time
import random
import re
import sys
import subprocess
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import concurrent.futures

# 全局变量，用于控制评论监控线程
_monitoring_thread = None
_stop_monitoring = False
_driver = None
_comment_callback = None
_seen_comments = set()

@contextmanager
def suppress_stderr():
    """上下文管理器，用于临时抑制标准错误输出"""
    # 保存当前的标准错误
    original_stderr = sys.stderr
    
    try:
        # 如果是Windows系统
        if sys.platform.startswith('win'):
            # 将标准错误重定向到NUL设备
            with open('NUL', 'w') as devnull:
                sys.stderr = devnull
                yield
        else:
            # 对于Unix/Linux/Mac系统，重定向到/dev/null
            with open('/dev/null', 'w') as devnull:
                sys.stderr = devnull
                yield
    finally:
        # 恢复原始的标准错误
        sys.stderr = original_stderr

def parse_comment(comment):
    """解析评论内容，提取用户名和评论内容"""
    try:
        # 移除可能的空白字符
        comment = comment.strip()
        
        # 如果评论包含多个评论（用换行符分隔），只取第一个
        if '\n' in comment:
            comment = comment.split('\n')[0].strip()
        
        # 检查是否包含"来了"关键词
        if '来了' in comment:
            # 尝试提取用户名（用户名来了）
            username = comment.replace('来了', '').strip()
            if username:
                return username, "来了"
        
        # 尝试多种分隔符
        separators = [':', '：']
        for sep in separators:
            if sep in comment:
                parts = comment.split(sep, 1)
                if len(parts) == 2:
                    username = parts[0].strip()
                    content = parts[1].strip()
                    if username and content:
                        return username, content
        
        # 如果上面的方法都失败，尝试使用正则表达式
        pattern = r'^([^:：]+)[:：](.+)$'
        match = re.match(pattern, comment)
        if match:
            username = match.group(1).strip()
            content = match.group(2).strip()
            if username and content:
                return username, content
        
        # 如果评论中没有分隔符，可能是系统消息或特殊格式
        if '来了' in comment or '进入直播间' in comment:
            return None, None
            
        # 如果无法解析，尝试将整个评论作为内容
        return '匿名用户', comment
        
    except Exception as e:
        print(f"解析评论时出错: {str(e)}")
        return None, None

def parse_gift(comment):
    """解析礼物信息，提取用户名和礼物名称"""
    try:
        # 移除可能的空白字符
        comment = comment.strip()
        
        # 如果评论包含多个评论（用换行符分隔），只取第一个
        if '\n' in comment:
            comment = comment.split('\n')[0].strip()
        
        # 尝试多种礼物格式
        patterns = [
            r'^(.+)送出了(.+)$',
            r'^(.+)赠送(.+)$',
            r'^(.+)送出(.+)$',
            r'^(.+)赠送了(.+)$',
            r'^(.+)送出了(.+)$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, comment)
            if match:
                username = match.group(1).strip()
                gift_name = match.group(2).strip()
                if username and gift_name:
                    return username, gift_name
        
        # 如果无法解析为礼物，返回None
        return None, None
        
    except Exception as e:
        print(f"解析礼物时出错: {str(e)}")
        return None, None

def _initialize_browser():
    """初始化浏览器驱动"""
    global _driver
    
    try:
        # 配置Chrome浏览器选项
        chrome_options = Options()
        
        # 添加无痕模式
        chrome_options.add_argument("--incognito")
        
        # 基本设置
        chrome_options.add_argument('--disable-web-security')  # 禁用网页安全性检查
        chrome_options.add_argument('--allow-running-insecure-content')  # 允许不安全内容
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 禁用自动化控制特征
        chrome_options.add_argument('--disable-infobars')  # 禁用信息栏
        chrome_options.add_argument('--disable-notifications')  # 禁用通知
        chrome_options.add_argument('--disable-popup-blocking')  # 禁用弹出窗口阻止
        chrome_options.add_argument('--disable-save-password-bubble')  # 禁用保存密码提示
        chrome_options.add_argument('--disable-translate')  # 禁用翻译
        chrome_options.add_argument('--no-default-browser-check')  # 禁用默认浏览器检查
        chrome_options.add_argument('--no-first-run')  # 禁用首次运行设置
        
        # 添加性能优化选项
        chrome_options.add_argument('--disable-gpu')  # 禁用GPU加速
        chrome_options.add_argument('--no-sandbox')  # 禁用沙箱模式
        chrome_options.add_argument('--disable-dev-shm-usage')  # 禁用/dev/shm使用
        chrome_options.add_argument('--disable-software-rasterizer')  # 禁用软件光栅化
        chrome_options.add_argument('--disable-extensions')  # 禁用扩展
        chrome_options.add_argument('--disable-default-apps')  # 禁用默认应用
        chrome_options.add_argument('--disable-sync')  # 禁用同步
        chrome_options.add_argument('--disable-background-networking')  # 禁用后台网络
        chrome_options.add_argument('--disable-background-timer-throttling')  # 禁用后台计时器限制
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')  # 禁用后台窗口遮挡
        chrome_options.add_argument('--disable-breakpad')  # 禁用崩溃报告
        chrome_options.add_argument('--disable-component-extensions-with-background-pages')  # 禁用带后台页面的组件扩展
        chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')  # 禁用特定功能
        chrome_options.add_argument('--disable-ipc-flooding-protection')  # 禁用IPC洪水保护
        chrome_options.add_argument('--disable-renderer-backgrounding')  # 禁用渲染器后台处理
        chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')  # 启用网络服务
        chrome_options.add_argument('--metrics-recording-only')  # 仅记录指标
        chrome_options.add_argument('--no-pings')  # 禁用ping
        chrome_options.add_argument('--window-size=1920,1080')  # 设置窗口大小
        
        # 设置随机User-Agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        # 添加网络相关设置
        chrome_options.add_argument('--dns-prefetch-disable')  # 禁用DNS预读取
        
        # 初始化浏览器驱动
        print("正在初始化Chrome浏览器...")
        try:
            # 使用本地ChromeDriver
            driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
            if not os.path.exists(driver_path):
                print(f"错误: ChromeDriver不存在于路径: {driver_path}")
                return None
                
            service = Service(driver_path)
            _driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 设置页面加载超时
            _driver.set_page_load_timeout(30)
            _driver.set_script_timeout(30)
            
            # 使用CDP命令修改navigator.webdriver标志
            _driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // 修改navigator属性
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // 添加语言和平台
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-CN', 'zh', 'en'],
                    });
                    
                    // 添加插件
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                '''
            })
            
            # 测试网络连接
            print("测试网络连接...")
            try:
                _driver.get("https://www.baidu.com")
                print("网络连接测试成功")
                print("Chrome浏览器初始化成功")
                return _driver
            except Exception as e:
                print(f"网络连接测试失败: {str(e)}")
                print("请检查网络连接或代理设置")
                return None
                
        except Exception as e:
            print(f"初始化Chrome浏览器失败: {str(e)}")
            return None
            
    except Exception as e:
        print(f"初始化浏览器时出错: {str(e)}")
        return None

def _monitor_comments():
    """监控评论的线程函数"""
    global _driver, _stop_monitoring, _seen_comments
    
    _seen_comments = set()  # 重置已处理评论集合
    last_print_time = 0  # 上次打印时间
    print_interval = 5  # 打印间隔（秒）
    retry_count = 0  # 重试计数器
    max_retries = 3  # 最大重试次数
    last_url = None  # 记录最后访问的URL
    
    while not _stop_monitoring:
        try:
            if not _driver:
                print("浏览器未初始化，尝试重新初始化...")
                _driver = _initialize_browser()
                if not _driver:
                    print("浏览器初始化失败，等待后重试...")
                    time.sleep(2)
                    continue
                
                # 如果有上次的URL，尝试重新访问
                if last_url:
                    print(f"尝试重新访问直播间: {last_url}")
                    try:
                        _driver.get(last_url)
                        time.sleep(5)  # 等待页面加载
                    except Exception as e:
                        print(f"重新访问直播间失败: {str(e)}")
                        continue
            
            # 检查页面是否仍然加载
            try:
                # 保存当前URL
                last_url = _driver.current_url
                
                # 检查页面状态
                page_state = _driver.execute_script("return document.readyState")
                if page_state != "complete":
                    print(f"页面未完全加载 (状态: {page_state})，等待加载完成...")
                    time.sleep(2)
                    continue
                
                # 检查是否存在服务器错误提示
                error_elements = _driver.find_elements(By.XPATH, "//*[contains(text(), '服务器开小差了') or contains(text(), '点击刷新重试')]")
                if error_elements:
                    print("检测到服务器错误，尝试刷新页面...")
                    try:
                        _driver.refresh()
                        time.sleep(5)  # 等待页面刷新
                    except Exception as e:
                        print(f"刷新页面失败: {str(e)}")
                        # 如果刷新失败，尝试重新访问
                        try:
                            _driver.get(last_url)
                            time.sleep(5)
                        except:
                            print("刷新页面失败，尝试重新初始化浏览器...")
                            _driver.quit()
                            _driver = None
                            continue
                    
                    retry_count += 1
                    if retry_count >= max_retries:
                        print("达到最大重试次数，重新初始化浏览器...")
                        _driver.quit()
                        _driver = None
                        retry_count = 0
                    continue
                
                # 重置重试计数器
                retry_count = 0
                
            except Exception as e:
                print(f"检查页面状态时出错: {str(e)}")
                if "invalid session id" in str(e):
                    print("浏览器会话已失效，需要重新初始化...")
                    _driver = None
                print("尝试重新加载页面...")
                try:
                    _driver.refresh()
                    time.sleep(5)
                except:
                    print("刷新页面失败，尝试重新初始化浏览器...")
                    _driver.quit()
                    _driver = None
                continue
            
            # 使用JavaScript获取评论元素，改进选择器
            current_time = time.time()
            if current_time - last_print_time >= print_interval:
                print("正在监控评论...")
                # 打印页面结构信息
                try:
                    page_source = _driver.page_source
                    
                    # 尝试多个可能的选择器来定位评论容器
                    selectors = [
                        "div[class*='webcast-chatroom']",
                        "div[class*='chatroom']",
                        "div[class*='chat-list']",
                        "div[class*='message-list']",
                        "div[class*='comment-list']"
                    ]
                    
                    for selector in selectors:
                        elements = _driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            print(f"找到评论容器，使用选择器: {selector}")
                            print(f"容器数量: {len(elements)}")
                            for i, elem in enumerate(elements):
                                print(f"容器 {i+1} 内容: {elem.text[:100]}...")
                            break
                except Exception as e:
                    print(f"检查页面结构时出错: {str(e)}")
                
                last_print_time = current_time
            
            try:
                # 使用更全面的选择器列表
                comments = _driver.execute_script("""
                    const selectors = [
                        'div[class*="webcast-chatroom___list"] div[class*="webcast-chatroom___item"]',
                        'div[class*="webcast-chatroom___list"] div[class*="webcast-chatroom___message"]',
                        'div[class*="webcast-chatroom___list"] div[class*="webcast-chatroom___content"]',
                        'div[class*="webcast-chatroom___list"] div[class*="webcast-chatroom___text"]',
                        'div[class*="chat-message"]',
                        'div[class*="message-item"]',
                        'div[class*="chat-item"]',
                        'div[class*="comment-item"]',
                        'div[class*="chat-list"] div[class*="item"]',
                        'div[class*="chat-list"] div[class*="message"]',
                        'div[class*="webcast-chatroom"] div[class*="item"]',
                        'div[class*="webcast-chatroom"] div[class*="message"]',
                        'div[class*="chatroom"] div[class*="item"]',
                        'div[class*="chatroom"] div[class*="message"]',
                        'div[class*="message-list"] div[class*="item"]',
                        'div[class*="message-list"] div[class*="message"]'
                    ];
                    
                    let comments = [];
                    let debugInfo = [];
                    
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        debugInfo.push(`选择器 ${selector} 找到 ${elements.length} 个元素`);
                        
                        for (const el of elements) {
                            const text = el.textContent.trim();
                            if (text && !text.includes('系统提示') && !text.includes('欢迎来到直播间')) {
                                comments.push(text);
                            }
                        }
                    }
                    
                    return {
                        comments: [...new Set(comments)],
                        debugInfo: debugInfo
                    };
                """)
                
                # 打印调试信息
                if current_time - last_print_time >= print_interval:
                    print("\n调试信息:")
                    for info in comments['debugInfo']:
                        print(info)
                    print(f"找到 {len(comments['comments'])} 条评论\n")
                
                if comments['comments']:
                    for comment_text in comments['comments']:
                        if comment_text not in _seen_comments:
                            _seen_comments.add(comment_text)
                            print(f"发现新评论: {comment_text}")
                            try:
                                # 解析评论
                                username, content = parse_comment(comment_text)
                                if username and content:
                                    print(f"解析评论成功: {username}: {content}")
                                    # 使用线程池执行回调
                                    with concurrent.futures.ThreadPoolExecutor() as executor:
                                        executor.submit(_comment_callback, username, content, "评论")
                                
                                # 解析礼物
                                username, gift_name = parse_gift(comment_text)
                                if username and gift_name:
                                    print(f"解析礼物成功: {username} 送出了 {gift_name}")
                                    # 使用线程池执行回调
                                    with concurrent.futures.ThreadPoolExecutor() as executor:
                                        executor.submit(_comment_callback, username, gift_name, "礼物")
                            except Exception as e:
                                print(f"处理评论时出错: {str(e)}")
                                continue
                
            except Exception as e:
                print(f"获取评论时出错: {str(e)}")
                if "invalid session id" in str(e):
                    print("浏览器会话已失效，需要重新初始化...")
                    _driver = None
                continue
            
            time.sleep(0.5)  # 降低检查频率
            
        except Exception as e:
            print(f"监控评论时出错: {str(e)}")
            if "invalid session id" in str(e):
                print("浏览器会话已失效，需要重新初始化...")
                _driver = None
            time.sleep(2)  # 出错后等待更长时间再重试
            continue

def start_comment_monitoring(live_url, callback_function):
    """启动评论监控线程"""
    global _monitoring_thread, _stop_monitoring, _driver, _comment_callback
    
    print("开始初始化评论监控...")
    
    # 保存回调函数
    _comment_callback = callback_function
    
    # 如果已经有监控线程在运行，先停止它
    if _monitoring_thread and _monitoring_thread.is_alive():
        print("发现已有监控线程在运行，先停止它...")
        stop_comment_monitoring()
    
    # 重置停止标志
    _stop_monitoring = False
    
    # 初始化浏览器
    _driver = _initialize_browser()
    if not _driver:
        print("浏览器初始化失败，无法启动评论监控")
        return False
        
    # 访问直播间
    try:
        print("正在访问直播间...")
        _driver.get(live_url)
        print(f"当前页面URL: {_driver.current_url}")
        
        # 等待页面加载
        print("等待页面加载...")
        WebDriverWait(_driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        print("页面加载完成")
        
        # 打印页面标题和源码长度，用于调试
        print(f"页面标题: {_driver.title}")
        
        print("查找iframe...")
        try:
            # 等待iframe加载
            iframe = WebDriverWait(_driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            print("找到iframe，尝试切换...")
            _driver.switch_to.frame(iframe)
            print("已切换到iframe")
            
            # 等待iframe内容加载
            WebDriverWait(_driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            print("iframe内容加载完成")
            
            # 打印iframe中的元素数量，用于调试
            elements = _driver.find_elements(By.CSS_SELECTOR, "*")
            print(f"iframe中元素数量: {len(elements)}")
            
            # 尝试查找评论区域
            print("尝试查找评论区域...")
            chat_area = _driver.find_elements(By.CSS_SELECTOR, "div[class*='chatroom']")
            if chat_area:
                print("找到评论区域")
            else:
                print("未找到评论区域，尝试其他选择器...")
                chat_area = _driver.find_elements(By.CSS_SELECTOR, "div[class*='chat']")
                if chat_area:
                    print("找到可能的评论区域")
            
        except Exception as e:
            print(f"处理iframe时出错: {str(e)}")
            print("未找到iframe或切换失败，继续在当前页面查找评论...")
            
            # 打印当前页面中的元素数量，用于调试
            elements = _driver.find_elements(By.CSS_SELECTOR, "*")
            print(f"当前页面元素数量: {len(elements)}")
            
    except Exception as e:
        print(f"访问直播间时出错: {str(e)}")
        return False
    
    # 创建并启动新的监控线程
    _monitoring_thread = threading.Thread(
        target=_monitor_comments,
        daemon=True
    )
    _monitoring_thread.start()
    
    # 验证线程是否成功启动
    if _monitoring_thread.is_alive():
        print(f"评论监控线程已成功启动，监控直播间: {live_url}")
        return True
    else:
        print("评论监控线程启动失败")
        return False

def stop_comment_monitoring():
    """停止评论监控线程"""
    global _monitoring_thread, _stop_monitoring, _driver
    
    if not _monitoring_thread or not _monitoring_thread.is_alive():
        print("没有正在运行的评论监控线程")
        return False
    
    print("正在停止评论监控...")
    _stop_monitoring = True
    
    # 确保浏览器已关闭
    if _driver:
        try:
            _driver.quit()
            _driver = None
        except:
            pass
    
    print("评论监控已停止")
    return True

if __name__ == "__main__":
    print("此模块不应直接运行，请通过main.py启动程序") 