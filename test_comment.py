from getusercomment import start_comment_monitoring, stop_comment_monitoring, get_all_interactions, clear_interactions
import time

def comment_callback(username, content, interaction_type):
    """评论回调函数，用于实时打印接收到的评论和礼物"""
    if interaction_type == "评论":
        print(f"[评论] {username}: {content}")
    else:
        print(f"[礼物] {username} {content}")

def main():
    # 这里替换为实际的抖音直播间URL
    live_url = "https://live.douyin.com/654549873750"
    
    try:
        print("开始测试评论抓取功能...")
        print(f"正在监控直播间: {live_url}")
        
        # 清空之前的互动记录
        clear_interactions()
        
        # 启动评论监控
        start_comment_monitoring(live_url, comment_callback)
        
        # 持续运行60秒
        print("程序将运行60秒，按Ctrl+C可以提前结束...")
        print("请在此期间发送测试弹幕...")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\n用户中断，正在停止监控...")
    finally:
        # 停止监控
        stop_comment_monitoring()
        
        # 获取所有互动记录
        all_interactions = get_all_interactions()
        print("\n=== 测试结果 ===")
        print(f"总共抓取到 {len(all_interactions)} 条互动记录")
        
        if len(all_interactions) == 0:
            print("\n可能的问题原因：")
            print("1. 直播间可能未在直播中")
            print("2. 直播间可能设置了评论权限")
            print("3. 网络连接问题")
            print("4. 抖音可能更新了页面结构")
            print("5. 可能需要登录才能查看评论")
            print("\n建议：")
            print("1. 确认直播间是否正在直播")
            print("2. 尝试在浏览器中打开直播间，确认是否可以正常看到评论")
            print("3. 检查网络连接是否正常")
            print("4. 尝试使用其他直播间测试")
        
        # 打印所有互动记录
        for interaction in all_interactions:
            if interaction["type"] == "评论":
                print(f"[评论] {interaction['username']}: {interaction['content']}")
            else:
                print(f"[礼物] {interaction['username']} {interaction['content']}")

if __name__ == "__main__":
    main() 