import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
# 我們刻意改回「第一頁」的網址，讓程式自己去爬最後一頁在哪裡
# 這樣最準確，不會因為網址參數打錯被導回
ENTRY_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx"
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
                "text": "V4 自動導航版"
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

def get_real_last_page_url(soup, base_url):
    """
    分析頁面上的分頁按鈕，找出最大的頁碼連結
    """
    print("🔍 正在尋找最後一頁的按鈕...")
    max_page = 1
    target_url = None
    
    # 抓取所有連結
    links = soup.find_all("a", href=True)
    
    for link in links:
        txt = link.get_text(strip=True)
        href = link['href']
        
        # 情況1: 連結是數字 (例如 "23")
        if txt.isdigit():
            page_num = int(txt)
            if page_num > max_page:
                max_page = page_num
                target_url = href
        
        # 情況2: 連結是 ">>" 或 "Last" (通常代表最後一頁)
        elif ">>" in txt or "Last" in txt or "最後一頁" in txt:
            print(f"🎯 找到【最後一頁】按鈕，直接鎖定！")
            target_url = href
            # 通常這就是最大頁了，但不一定是絕對路徑，稍後處理
            break
            
    if target_url:
        # 處理相對路徑
        if not target_url.startswith("http"):
            target_url = "https://stocks.ddns.net" + target_url
        print(f"🚀 偵測到最後一頁 (Page {max_page})，網址: {target_url}")
        return target_url
    else:
        print("⚠️ 找不到分頁按鈕，假設目前就是最後一頁")
        return base_url

def main():
    print(f"🚀 V4 啟動檢查: {datetime.now()}")
    
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    # 步驟 1: 先進入入口頁面 (通常是第一頁)
    print(f"1️⃣ 進入入口頁面: {ENTRY_URL}")
    try:
        session = requests.Session()
        res = session.get(ENTRY_URL, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        
        if res.status_code != 200:
            print(f"❌ 入口網頁讀取失敗: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # 步驟 2: 尋找並跳轉到「真正的最後一頁」
        real_target_url = get_real_last_page_url(soup, ENTRY_URL)
        
        # 如果計算出的網址跟入口不一樣，就跳轉
        if real_target_url != ENTRY_URL:
            print(f"2️⃣ 跳轉至最後一頁...")
            res = session.get(real_target_url, headers=HEADERS, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")
        else:
            print(f"2️⃣ 目前已在目標頁面，無需跳轉")

        # 步驟 3: 精準鎖定 Mikeon88 (V3 的邏輯)
        # 尋找所有 id 包含 "lnkName" 的連結 (作者名)
        author_links = soup.find_all("a", id=re.compile("lnkName"))
        
        found_posts = []
        print(f"🔍 開始掃描頁面上的發言者...")

        for author in author_links:
            author_name = author.get_text(strip=True)
            
            # 鎖定 mikeon88
            if "mikeon88" in author_name.lower():
                # 往上找容器
                container = author
                post_content = "無內容"
                post_time = "無時間"
                
                for _ in range(5):
                    if container.parent:
                        container = container.parent
                        
                        # 找內容
                        body_div = container.find("div", class_="post-body")
                        if body_div:
                            post_content = body_div.get_text("\n", strip=True)
                        
                        # 找時間
                        time_span = container.find("span", class_="local-time")
                        if time_span:
                            post_time = time_span.text.strip()
                        
                        if body_div: break
                    else: break
                
                if post_content != "無內容":
                    # 這裡多做一個檢查：如果是 2023 年的舊文，且頁面上有其他新文，我們不要這一篇
                    # 但簡單起見，我們先全部收集起來，最後只取「最後一個」
                    found_posts.append({"time": post_time, "content": post_content})

        if not found_posts:
            print("💤 本頁沒有 Mikeon88 的發言")
            save_status(last_fingerprint)
            return

        # 步驟 4: 取得「最後一則」 (The Latest Post)
        # 因為論壇通常是由舊到新排序 (樓層制)，所以 List 的最後一個就是最新的
        latest = found_posts[-1]
        
        print(f"🔎 鎖定最後一則發言 (共找到 {len(found_posts)} 則)")
        print(f"📅 時間: {latest['time']}")
        print(f"📝 內容開頭: {latest['content'][:20]}...")

        # 建立指紋
        current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
        
        if current_fingerprint != last_fingerprint:
            print(f"🎉 發現新貼文 (或初次執行)！發送通知...")
            send_discord_notify(latest['content'], latest['time'], real_target_url)
            save_status(current_finger
