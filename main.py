import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
# 初始設定 (如果 status.json 不存在會用這個)
DEFAULT_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?page=23"
STATUS_FILE = "status.json"

# 從 GitHub Secrets 讀取 Webhook (稍後設定)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# ==============================================

def send_discord_notify(message_content, post_time, url):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 未設定 Discord Webhook，跳過通知")
        return

    preview = message_content[:200] + "..." if len(message_content) > 200 else message_content
    data = {
        "username": "Mikeon88 追蹤器",
        "embeds": [{
            "title": "🚨 Mikeon88 有新發言！",
            "description": preview,
            "url": url,
            "color": 3066993, 
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "連結", "value": f"[前往查看]({url})", "inline": True}
            ]
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ Discord 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_url": DEFAULT_URL, "last_fingerprint": ""}

def save_status(url, fingerprint):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"current_url": url, "last_fingerprint": fingerprint}, f, ensure_ascii=False, indent=4)

def check_for_next_page(soup, current_url):
    try:
        match = re.search(r'page=(\d+)', current_url)
        if not match: return None
        current_page = int(match.group(1))
        
        page_links = soup.find_all("a", href=True)
        for link in page_links:
            txt = link.text.strip()
            if txt.isdigit() and int(txt) > current_page:
                new_href = link['href']
                if not new_href.startswith("http"):
                    return "https://stocks.ddns.net" + new_href
                return new_href
    except:
        pass
    return None

def main():
    print(f"🚀 啟動檢查: {datetime.now()}")
    
    # 1. 讀取上次的狀態 (頁數與最後一篇文)
    status = load_status()
    current_url = status["current_url"]
    last_fingerprint = status["last_fingerprint"]
    
    print(f"🎯 目標網址: {current_url}")

    try:
        res = requests.get(current_url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print("❌ 網頁讀取失敗")
            return

        soup = BeautifulSoup(res.text, "html.parser")

        # 2. 檢查有沒有下一頁 (自動翻頁功能)
        next_page = check_for_next_page(soup, current_url)
        if next_page:
            print(f"🚀 發現新頁面！切換至: {next_page}")
            current_url = next_page
            # 重新讀取新頁面
            res = requests.get(current_url, headers=HEADERS)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")

        # 3. 抓取內容
        post_bodies = soup.find_all("div", class_="post-body")
        found_posts = []

        for body in post_bodies:
            # 這裡沿用之前的「往父層找 mikeon88」的邏輯
            container = body
            is_target = False
            post_time = "未知時間"
            
            for _ in range(3):
                if container.parent:
                    container = container.parent
                    author = container.find("a", string=re.compile("mikeon88", re.I))
                    if author:
                        is_target = True
                        time_obj = container.find("span", class_="local-time")
                        if time_obj: post_time = time_obj.text.strip()
                        break
                else: break
            
            if is_target:
                content = body.get_text("\n", strip=True)
                found_posts.append({"time": post_time, "content": content})

        if not found_posts:
            print("💤 本頁無相關發言")
            # 即使沒發言，如果網址變了(翻頁)，也要存檔
            save_status(current_url, last_fingerprint) 
            return

        # 4. 比對最新一篇
        latest = found_posts[-1]
        current_fingerprint = f"{latest['time']}_{latest['content'][:20]}"

        if current_fingerprint != last_fingerprint:
            print(f"🎉 發現新貼文！")
            send_discord_notify(latest['content'], latest['time'], current_url)
            # 更新狀態
            save_status(current_url, current_fingerprint)
        else:
            print("💤 無新發言")
            # 確保翻頁狀態被保存
            save_status(current_url, last_fingerprint)

    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
