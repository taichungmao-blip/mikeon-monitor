import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
# 入口網址 (第一頁)
BASE_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx"
STATUS_FILE = "status.json"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# ==============================================

def send_discord_notify(message_content, post_time, url):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 未設定 Discord Webhook")
        return

    preview = message_content[:300] + "..." if len(message_content) > 300 else message_content
    
    data = {
        "username": "Mikeon88 追蹤器",
        "embeds": [{
            "title": "🚨 Mikeon88 有新發言！",
            "description": preview,
            "url": url,
            "color": 15158332, 
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "來源連結", "value": f"[點擊前往]({url})", "inline": True}
            ],
            "footer": {
                "text": "V5 JavaScript 繞道版"
            }
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
    return {"last_fingerprint": ""}

def save_status(fingerprint):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_fingerprint": fingerprint}, f, ensure_ascii=False, indent=4)

def get_max_page_number(soup):
    """
    從分頁列中解析出最大的頁碼數字
    """
    print("🔍 分析分頁結構...")
    max_page = 1
    
    # 策略1：直接看按鈕的文字 (例如 "23")
    links = soup.find_all("a", href=True)
    for link in links:
        txt = link.get_text(strip=True)
        if txt.isdigit():
            val = int(txt)
            if val > max_page:
                max_page = val
    
    # 策略2：如果最後一頁是 "..." 或 "Last"，嘗試從 href 的 JS 參數中挖數字
    # ASP.NET 常見格式: javascript:__doPostBack('...','Page$23')
    for link in links:
        href = link['href']
        if "Page$" in href:
            match = re.search(r"Page\$(\d+)", href)
            if match:
                val = int(match.group(1))
                if val > max_page:
                    max_page = val
                    
    print(f"📊 偵測到最大頁數為: {max_page}")
    return max_page

def main():
    print(f"🚀 V5 啟動檢查: {datetime.now()}")
    
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    # 步驟 1: 進入第一頁
    print(f"1️⃣ 讀取入口頁面...")
    try:
        session = requests.Session()
        res = session.get(BASE_URL, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        
        if res.status_code != 200:
            print(f"❌ 入口網頁讀取失敗: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # 步驟 2: 計算最大頁數並手動組網址
        max_page = get_max_page_number(soup)
        
        # 組合網址 (繞過 JavaScript)
        target_url = f"{BASE_URL}?page={max_page}"
        print(f"2️⃣ 鎖定目標網址: {target_url}")
        
        # 如果目標頁不是第一頁，就進行跳轉
        if max_page > 1:
            print(f"🚀 跳轉至第 {max_page} 頁...")
            res = session.get(target_url, headers=HEADERS, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")

        # 步驟 3: 搜尋 Mikeon88 (V3 精準邏輯)
        author_links = soup.find_all("a", id=re.compile("lnkName"))
        found_posts = []
        print(f"🔍 掃描發言中...")

        for author in author_links:
            author_name = author.get_text(strip=True)
            if "mikeon88" in author_name.lower():
                container = author
                post_content = "無內容"
                post_time = "無時間"
                
                # 往上找容器
                for _ in range(5):
                    if container.parent:
                        container = container.parent
                        body_div = container.find("div", class_="post-body")
                        if body_div:
                            post_content = body_div.get_text("\n", strip=True)
                        time_span = container.find("span", class_="local-time")
                        if time_span:
                            post_time = time_span.text.strip()
                        if body_div: break
                    else: break
                
                if post_content != "無內容":
                    found_posts.append({"time": post_time, "content": post_content})

        if not found_posts:
            print("💤 本頁沒有 Mikeon88 的發言")
            save_status(last_fingerprint)
            return

        # 步驟 4: 鎖定最新發言
        latest = found_posts[-1]
        
        print(f"🔎 最新發言時間: {latest['time']}")
        
        current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
        
        if current_fingerprint != last_fingerprint:
            print(f"🎉 發現新內容！發送通知...")
            send_discord_notify(latest['content'], latest['time'], target_url)
            save_status(current_fingerprint)
        else:
            print("💤 內容與上次相同，跳過通知")
            save_status(last_fingerprint)

    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

if __name__ == "__main__":
    main()
