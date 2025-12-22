import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

# ================= 設定區 =================
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
    preview = message_content[:300] + "..." if len(message_content) > 300 else message_content
    
    data = {
        "username": "Mikeon88 追蹤器",
        "embeds": [{
            "title": "🚨 Mikeon88 有新發言！",
            "description": preview,
            "url": url,
            "color": 3066993, 
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "連結", "value": f"[點擊前往查看]({url})", "inline": True}
            ],
            "footer": {
                "text": "已偵測到最新發言"
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
    
    status = load_status()
    current_url = status["current_url"]
    last_fingerprint = status["last_fingerprint"]
    
    print(f"🎯 目標網址: {current_url}")

    try:
        res = requests.get(current_url, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print("❌ 網頁讀取失敗")
            return

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. 自動翻頁檢查
        next_page = check_for_next_page(soup, current_url)
        if next_page:
            print(f"🚀 發現新頁面！切換至: {next_page}")
            current_url = next_page
            res = requests.get(current_url, headers=HEADERS)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, "html.parser")

        # 2. 抓取發言 (加強版深度搜尋)
        post_bodies = soup.find_all("div", class_="post-body")
        found_posts = []

        print(f"🔍 本頁共找到 {len(post_bodies)} 個發言區塊，開始分析...")

        for body in post_bodies:
            container = body
            is_target = False
            post_time = "無時間資訊"
            
            # 關鍵修改：往上找 6 層 (原本只有3層)
            # 這是為了應付多層 Table 巢狀結構
            for i in range(6):
                if container.parent:
                    container = container.parent
                    
                    # 尋找作者 mikeon88
                    author = container.find("a", string=re.compile("mikeon88", re.I))
                    
                    if author:
                        is_target = True
                        # 找到作者後，在同層找時間
                        time_obj = container.find("span", class_="local-time")
                        if time_obj: 
                            post_time = time_obj.text.strip()
                        else:
                            # 備用方案：如果找不到 span，試著找有沒有看起來像日期的文字
                            text_content = container.get_text()
                            date_match = re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2}', text_content)
                            if date_match:
                                post_time = date_match.group(0)
                        
                        # 找到作者就停止往上找
                        break
                else:
                    break
            
            if is_target:
                content = body.get_text("\n", strip=True)
                # 過濾掉太短的像是簽名檔的內容 (可選)
                found_posts.append({"time": post_time, "content": content})

        if not found_posts:
            print("💤 本頁未解析出 Mikeon88 的有效發言 (可能結構更變或不在本頁)")
            save_status(current_url, last_fingerprint)
            return

        # 3. 鎖定「最後一則」 (也就是最新的)
        latest = found_posts[-1]
        
        # 建立指紋：時間 + 內容前20字
        current_fingerprint = f"{latest['time']}_{latest['content'][:20]}"
        
        print(f"🔎 最新一則時間: {latest['time']}")
        print(f"🔎 內容預覽: {latest['content'][:30]}...")

        if current_fingerprint != last_fingerprint:
            # 只有當「指紋」跟上次不一樣時，才發通知
            print(f"🎉 發現新貼文！")
            send_discord_notify(latest['content'], latest['time'], current_url)
            save_status(current_url, current_fingerprint)
        else:
            print("💤 內容與上次相同，無須通知")
            # 雖然沒新文，但也更新一下 url 狀態 (防翻頁 bug)
            save_status(current_url, last_fingerprint)

    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
