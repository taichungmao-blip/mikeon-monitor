import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
# 強制指定第 23 頁，移除 goto 參數，確保不跳轉回第一頁
# 這裡直接寫死 Page 23，之後程式會自己處理翻頁
DEFAULT_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?page=23"
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

    # 內容擷取 (預覽)
    preview = message_content[:500] + "..." if len(message_content) > 500 else message_content
    
    data = {
        "username": "Mikeon88 追蹤器",
        "embeds": [{
            "title": "🚨 Mikeon88 有新發言！",
            "description": preview,
            "url": url,
            "color": 15158332, # 紅色，代表緊急/新消息
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "來源連結", "value": f"[點擊前往]({url})", "inline": True}
            ],
            "footer": {
                "text": "V3 精準鎖定版"
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
    return {"current_url": DEFAULT_URL, "last_fingerprint": ""}

def save_status(url, fingerprint):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"current_url": url, "last_fingerprint": fingerprint}, f, ensure_ascii=False, indent=4)

def check_for_next_page(soup, current_url):
    try:
        match = re.search(r'page=(\d+)', current_url)
        if not match: return None
        current_page = int(match.group(1))
        
        # 尋找所有分頁按鈕
        page_links = soup.find_all("a", href=True)
        for link in page_links:
            txt = link.text.strip()
            # 確保是數字且大於當前頁碼
            if txt.isdigit() and int(txt) > current_page:
                new_href = link['href']
                if not new_href.startswith("http"):
                    return "https://stocks.ddns.net" + new_href
                return new_href
    except:
        pass
    return None

def main():
    print(f"🚀 V3 啟動檢查: {datetime.now()}")
    
    status = load_status()
    current_url = status["current_url"]
    last_fingerprint = status["last_fingerprint"]
    
    # 安全檢查：確保網址中沒有奇怪的參數導致跳回第一頁
    if "goto=" in current_url:
        print("⚠️ 偵測到舊的跳轉參數，重置為標準分頁網址...")
        current_url = DEFAULT_URL

    print(f"🎯 鎖定網址: {current_url}")

    try:
        res = requests.get(current_url, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print(f"❌ 網頁讀取失敗: {res.status_code}")
            return

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. 自動翻頁檢查
        next_page = check_for_next_page(soup, current_url)
        if next_page:
            print(f"🚀 發現新頁面 (Page Update)！切換至: {next_page}")
            current_url = next_page
            res = requests.get(current_url, headers=HEADERS)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")

        # =========================================================
        # V3 核心修改：先找人，再找文
        # =========================================================
        
        found_posts = []
        
        # 根據你的截圖1，作者連結有 id="...lnkName"
        # 我們搜尋所有 id 包含 "lnkName" 的 a 標籤
        author_links = soup.find_all("a", id=re.compile("lnkName"))
        
        print(f"🔍 本頁共找到 {len(author_links)} 個發言者，開始過濾 Mikeon88...")

        for author in author_links:
            author_name = author.get_text(strip=True)
            
            # 只有當作者名字真的是 mikeon88 時才處理 (忽略大小寫)
            if "mikeon88" in author_name.lower():
                print("✅ 找到 Mikeon88 本人！正在解析內容...")
                
                # 往上找共同的容器 (通常是 tr 或 table 或 card div)
                # 我們往上找 4 層，每一層都試著找 post-body
                container = author
                post_content = "無法解析內容"
                post_time = "無時間資訊"
                
                for _ in range(5):
                    if container.parent:
                        container = container.parent
                        
                        # 在這個容器裡找內容區塊 (Image 3)
                        body_div = container.find("div", class_="post-body")
                        if body_div:
                            post_content = body_div.get_text("\n", strip=True)
                        
                        # 在這個容器裡找時間 (Image 2)
                        time_span = container.find("span", class_="local-time")
                        if time_span:
                            post_time = time_span.text.strip()
                        
                        # 如果兩者都找到，或是至少找到了內容，就當作成功
                        if body_div:
                            break
                    else:
                        break
                
                if post_content != "無法解析內容":
                    found_posts.append({"time": post_time, "content": post_content})

        # =========================================================

        if not found_posts:
            print("💤 本頁沒有 Mikeon88 的發言")
            save_status(current_url, last_fingerprint)
            return

        # 取得最後一篇 (最新的)
        latest = found_posts[-1]
        
        # 建立指紋
        current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
        
        print(f"🔎 偵測到最新發言時間: {latest['time']}")
        print(f"🔎 內容預覽: {latest['content'][:30]}...")

        # 這裡加一個判斷：如果時間是空的，可能是抓取失敗，為了避免誤報，我們可以選擇不發送，或者強制發送
        # 但既然你之前的截圖是有時間的 (608萬那篇)，這次應該能抓到

        if current_fingerprint != last_fingerprint:
            print(f"🎉 內容與上次不同，發送通知！")
            send_discord_notify(latest['content'], latest['time'], current_url)
            save_status(current_url, current_fingerprint)
        else:
            print("💤 內容與上次相同，跳過通知")
            save_status(current_url, last_fingerprint)

    except Exception as e:
        print(f"❌ 嚴重錯誤: {e}")

if __name__ == "__main__":
    main()
