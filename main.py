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
            "color": 10181046, # 紫色，代表深度爬取
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "來源連結", "value": f"[點擊前往]({url})", "inline": True}
            ],
            "footer": {
                "text": "V7 PostBack 模擬版"
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

def get_hidden_fields(soup):
    """抓取 ASP.NET 的關鍵隱藏欄位 (ViewState)"""
    data = {}
    for item in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        element = soup.find("input", {"id": item})
        if element:
            data[item] = element.get("value")
    return data

def get_last_page_content(session):
    """
    模擬點擊「>>」按鈕，發送 POST 請求獲取最後一頁
    """
    print("1️⃣ 進入入口頁面獲取 ViewState...")
    res = session.get(BASE_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(res.text, "html.parser")
    
    # 嘗試尋找「最後一頁」的按鈕
    # 常見文字: ">>", "Last", "末頁", 或 title="最後一頁"
    target_link = None
    
    # 策略 A: 找文字為 >> 的連結
    target_link = soup.find("a", string=re.compile(r">>|Last|末頁"))
    
    # 策略 B: 如果找不到，找 title 包含 "末頁" 或 "Last"
    if not target_link:
        target_link = soup.find("a", title=re.compile(r"末頁|Last|End"))

    if not target_link:
        print("⚠️ 找不到翻頁按鈕，假設目前只有一頁")
        return soup

    # 解析 __doPostBack('target', 'argument')
    href = target_link.get("href", "")
    print(f"🎯 找到翻頁按鈕: {href}")
    
    match = re.search(r"__doPostBack\(['\"]([^'\"]*)['\"],\s*['\"]([^'\"]*)['\"]\)", href)
    if match:
        event_target = match.group(1)
        event_argument = match.group(2)
        
        # 準備 POST 資料
        payload = get_hidden_fields(soup)
        payload["__EVENTTARGET"] = event_target
        payload["__EVENTARGUMENT"] = event_argument
        
        print(f"🚀 發送 POST 請求模擬翻頁 (Target: {event_target})...")
        post_res = session.post(BASE_URL, data=payload, headers=HEADERS, timeout=20)
        
        if post_res.status_code == 200:
            print("✅ 翻頁成功！")
            return BeautifulSoup(post_res.text, "html.parser")
        else:
            print(f"❌ 翻頁失敗: {post_res.status_code}")
            return soup
    else:
        print("❌ 無法解析 PostBack 參數")
        return soup

def extract_time(container):
    time_span = container.find("span", class_="local-time")
    if time_span: return time_span.text.strip()
    text = container.get_text()
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2}', text)
    if match: return match.group(0)
    return "未知時間"

def main():
    print(f"🚀 V7 啟動檢查: {datetime.now()}")
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    session = requests.Session()
    
    # 使用 PostBack 技術獲取最後一頁
    soup = get_last_page_content(session)

    # 搜尋 Mikeon88
    author_links = soup.find_all("a", id=re.compile("lnkName"))
    found_posts = []
    print(f"🔍 掃描頁面發言...")

    for author in author_links:
        author_name = author.get_text(strip=True)
        if "mikeon88" in author_name.lower():
            container = author
            post_content = "無內容"
            post_time = "無時間"
            
            for _ in range(5):
                if container.parent:
                    container = container.parent
                    body_div = container.find("div", class_="post-body")
                    if body_div:
                        post_content = body_div.get_text("\n", strip=True)
                    t = extract_time(container)
                    if t != "未知時間": post_time = t
                    if body_div: break
                else: break
            
            if post_content != "無內容":
                found_posts.append({"time": post_time, "content": post_content})

    if not found_posts:
        print("💤 本頁沒有 Mikeon88 的發言")
        save_status(last_fingerprint)
        return

    # 鎖定最新發言
    latest = found_posts[-1]
    print(f"🔎 最新發言時間: {latest['time']}")
    print(f"📝 內容預覽: {latest['content'][:30]}...")
    
    current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
    
    if current_fingerprint != last_fingerprint:
        print(f"🎉 發現新內容！發送通知...")
        # 注意：PostBack 頁面沒有獨立網址，我們連結給首頁即可，使用者點進去還是要自己翻
        # 或是我們可以嘗試組出 goto 網址，但先求穩
        send_discord_notify(latest['content'], latest['time'], BASE_URL)
        save_status(current_fingerprint)
    else:
        print("💤 內容與上次相同，跳過通知")
        save_status(last_fingerprint)

if __name__ == "__main__":
    main()
