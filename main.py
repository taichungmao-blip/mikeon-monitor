import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
BASE_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx"
STATUS_FILE = "status.json"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# 測試用的超大頁碼 (故意超過 23)
OVERSHOOT_PAGE = 200 

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
                "text": "V6 超速跳躍版"
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

def get_real_last_page_number(session):
    """
    使用「超速跳躍法」找出真正的最後一頁
    """
    print(f"🕵️ 嘗試探測最後一頁 (請求 Page {OVERSHOOT_PAGE})...")
    
    target_url = f"{BASE_URL}?page={OVERSHOOT_PAGE}"
    try:
        res = session.get(target_url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 1. 檢查這個頁面有沒有發言？
        # 如果有發言，代表網站自動把我們導向了最後一頁 (Case 1)
        posts = soup.find_all("div", class_="post-body")
        if posts:
            print("🚀 網站自動導向有效頁面，分析分頁中...")
        
        # 2. 不管內容是不是空的，我們都檢查分頁列
        # 當我們請求 Page 200 時，分頁列通常會顯示 [21] [22] [23]
        max_page = 1
        links = soup.find_all("a", href=True)
        for link in links:
            txt = link.get_text(strip=True)
            if txt.isdigit():
                val = int(txt)
                if val > max_page:
                    max_page = val
        
        print(f"📊 偵測到最大頁數為: {max_page}")
        return max_page, soup # 回傳 soup 以便如果已經在最後一頁就不用重抓
        
    except Exception as e:
        print(f"⚠️ 探測失敗: {e}")
        return 1, None

def extract_time(container):
    """
    增強版時間抓取：先找標籤，找不到就用正規表達式掃描全文
    """
    # 方法 1: 標準標籤
    time_span = container.find("span", class_="local-time")
    if time_span:
        return time_span.text.strip()
    
    # 方法 2: 全文掃描 (針對舊文章或結構改變)
    text = container.get_text()
    # 尋找類似 2025/12/13 10:49:42 的格式
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2}', text)
    if match:
        return match.group(0)
    
    return "未知時間"

def main():
    print(f"🚀 V6 啟動檢查: {datetime.now()}")
    
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    session = requests.Session()
    
    # 步驟 1: 找出真正的最後一頁
    real_page, soup_cache = get_real_last_page_number(session)
    
    # 步驟 2: 鎖定目標
    target_url = f"{BASE_URL}?page={real_page}"
    print(f"🎯 鎖定最終目標: {target_url}")
    
    # 如果剛剛探測時拿到的頁面不等於最後一頁，就要重新抓取
    # (例如剛剛探測到分頁列顯示 23，但內容是空的，我們現在要真的去抓 Page 23)
    if not soup_cache or "page=" not in str(real_page): # 簡單判斷，直接重抓最保險
        res = session.get(target_url, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")
    else:
        soup = soup_cache

    # 步驟 3: 搜尋 Mikeon88
    author_links = soup.find_all("a", id=re.compile("lnkName"))
    found_posts = []
    print(f"🔍 掃描 Page {real_page} 的發言...")

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
                    
                    # 嘗試抓取時間 (增強版)
                    t = extract_time(container)
                    if t != "未知時間":
                        post_time = t
                    
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
    print(f"📝 內容預覽: {latest['content'][:30]}...")
    
    current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
    
    if current_fingerprint != last_fingerprint:
        print(f"🎉 發現新內容！發送通知...")
        send_discord_notify(latest['content'], latest['time'], target_url)
        save_status(current_fingerprint)
    else:
        print("💤 內容與上次相同，跳過通知")
        save_status(last_fingerprint)

if __name__ == "__main__":
    main()
