import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime
import time

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
            "color": 15158332, 
            "fields": [
                {"name": "發言時間", "value": post_time, "inline": True},
                {"name": "來源連結", "value": f"[點擊前往]({url})", "inline": True}
            ],
            "footer": {
                "text": "V9 雙箭頭鎖定版"
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
    data = {}
    for item in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        element = soup.find("input", {"id": item})
        if element:
            data[item] = element.get("value")
    return data

def extract_do_postback_args(href):
    if not href: return None, None
    match = re.search(r"__doPostBack\(['\"]([^'\"]*)['\"],\s*['\"]([^'\"]*)['\"]\)", href)
    if match:
        return match.group(1), match.group(2)
    return None, None

def chase_last_page(session):
    print("1️⃣ 進入入口頁面...")
    res = session.get(BASE_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(res.text, "html.parser")
    
    # 用來記錄已經訪問過的頁面特徵，避免無窮迴圈
    visited_fingerprints = set()
    
    # 預防無窮迴圈，最多翻 10 次
    for hop in range(10):
        # 建立當前頁面的簡單指紋 (例如第一篇文章的內容)，用來判斷是否真的翻頁了
        first_post = soup.find("div", class_="post-body")
        page_fingerprint = first_post.get_text()[:50] if first_post else f"Empty_{hop}"
        
        if page_fingerprint in visited_fingerprints:
            print("⚠️ 偵測到頁面重複，停止翻頁。")
            break
        visited_fingerprints.add(page_fingerprint)

        print(f"🏃 第 {hop + 1} 次搜尋分頁按鈕...")
        
        # 抓取所有 PostBack 連結
        links = soup.find_all("a", href=re.compile(r"__doPostBack"))
        
        target_link = None
        target_desc = ""
        
        #Debug: 印出所有找到的按鈕文字，方便除錯
        # print("   (Debug) 本頁按鈕:", [l.get_text(strip=True) for l in links])

        # 策略：優先找 ">>" 或 "Last" 或 "末頁"
        # 只要文字裡包含 ">" 且不是 "<<" (上一頁)，我們就認為它是往後的
        for link in links:
            txt = link.get_text(strip=True)
            
            # 忽略上一頁/第一頁的按鈕
            if "<" in txt or "First" in txt or "首頁" in txt:
                continue

            # 尋找目標特徵
            # 1. 雙箭頭 (可能中間有空格，或是全形)
            if ">>" in txt or "»" in txt or ">" in txt or "Last" in txt or "末頁" in txt:
                target_link = link
                target_desc = f"找到 [{txt}] 按鈕"
                # 如果找到明確的 >> 就直接選定，不找了
                if ">>" in txt or "Last" in txt:
                    break
        
        # 如果沒找到 >>，才退而求其次找數字
        if not target_link:
            print("   (未發現箭頭，嘗試尋找最大數字...)")
            # 找出目前分頁列中最大的數字
            # 但我們不知道當前是第幾頁，所以這招有風險，
            # 比較安全的做法是：如果有 "..." 就按 "..."
            for link in links:
                if "..." in link.get_text():
                    target_link = link
                    target_desc = "找到 [...] 按鈕"

        # 執行跳轉
        if target_link:
            print(f"🎯 {target_desc}，執行跳轉！")
            target, arg = extract_do_postback_args(target_link['href'])
            
            if target:
                payload = get_hidden_fields(soup)
                payload["__EVENTTARGET"] = target
                payload["__EVENTARGUMENT"] = arg
                
                post_res = session.post(BASE_URL, data=payload, headers=HEADERS, timeout=30)
                if post_res.status_code == 200:
                    soup = BeautifulSoup(post_res.text, "html.parser")
                    print("✅ 跳轉成功 (頁面已更新)")
                    time.sleep(1)
                else:
                    print(f"❌ 跳轉請求失敗: {post_res.status_code}")
                    break
            else:
                break
        else:
            print("🏁 無法找到更多往後的按鈕，判斷已達【最後一頁】")
            break
            
    return soup

def extract_time(container):
    # 優先找 local-time
    time_span = container.find("span", class_="local-time")
    if time_span: return time_span.text.strip()
    
    # 備用：正則表達式
    text = container.get_text()
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2}', text)
    if match: return match.group(0)
    
    return "無時間資訊"

def main():
    print(f"🚀 V9 啟動檢查: {datetime.now()}")
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    session = requests.Session()
    
    # 1. 執行追頁 (PostBack 模擬)
    soup = chase_last_page(session)

    # 2. 搜尋 Mikeon88
    # 這裡改回用 V3 的精確搜尋邏輯 (ID鎖定)
    author_links = soup.find_all("a", id=re.compile("lnkName"))
    found_posts = []
    print(f"🔍 掃描最終頁面發言...")

    for author in author_links:
        author_name = author.get_text(strip=True)
        if "mikeon88" in author_name.lower():
            container = author
            post_content = "無內容"
            post_time = "無時間"
            
            # 往上找 5 層
            for _ in range(5):
                if container.parent:
                    container = container.parent
                    
                    # 抓內容
                    body_div = container.find("div", class_="post-body")
                    if body_div:
                        post_content = body_div.get_text("\n", strip=True)
                    
                    # 抓時間
                    t = extract_time(container)
                    if t != "無時間資訊": post_time = t
                    
                    if body_div: break
                else: break
            
            if post_content != "無內容":
                found_posts.append({"time": post_time, "content": post_content})

    if not found_posts:
        print("💤 本頁沒有 Mikeon88 的發言")
        save_status(last_fingerprint)
        return

    # 3. 鎖定最新發言
    latest = found_posts[-1]
    print(f"🔎 最新發言時間: {latest['time']}")
    print(f"📝 內容預覽: {latest['content'][:30]}...")
    
    current_fingerprint = f"{latest['time']}_{latest['content'][:30]}"
    
    if current_fingerprint != last_fingerprint:
        print(f"🎉 發現新內容！發送通知...")
        send_discord_notify(latest['content'], latest['time'], BASE_URL)
        save_status(current_fingerprint)
    else:
        print("💤 內容與上次相同，跳過通知")
        save_status(last_fingerprint)

if __name__ == "__main__":
    main()
