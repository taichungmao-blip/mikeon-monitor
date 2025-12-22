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
                "text": "V10 無盡攀登版"
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

def get_current_page_num(soup):
    """嘗試找出目前頁面是第幾頁"""
    # 方法：通常當前頁碼的按鈕是沒有 href 的，或者有特定 class
    # 我們檢查分頁區塊
    try:
        # 尋找分頁區塊 (通常在 table 或 div 裡)
        # 這裡我們找所有數字按鈕，看看哪個沒有 href (代表是當前頁)
        # 或者被 span 包住的數字
        pager_active = soup.find("span", style=re.compile(r"font-weight:bold|color:Red", re.I))
        if pager_active and pager_active.text.isdigit():
             return int(pager_active.text)
        
        # 備用方案：有些網站當前頁只是純文字，不是連結
        # 我們假設如果找不到當前頁，就回傳 0，讓程式依靠最大數字去跳
        return 0
    except:
        return 0

def chase_last_page(session):
    print("1️⃣ 進入入口頁面...")
    res = session.get(BASE_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(res.text, "html.parser")
    
    current_page = 1
    max_hops = 15 # 增加跳轉次數上限
    
    for hop in range(max_hops):
        # 嘗試識別當前頁
        detected_page = get_current_page_num(soup)
        if detected_page > current_page:
            current_page = detected_page
        
        print(f"🏃 第 {hop + 1} 次跳轉分析 (目前約在 Page {current_page})...")
        
        links = soup.find_all("a", href=re.compile(r"__doPostBack"))
        
        best_link = None
        best_arg_val = -1
        target_type = "None"
        
        # 掃描所有按鈕，尋找最佳跳轉目標
        for link in links:
            target, arg = extract_do_postback_args(link['href'])
            txt = link.get_text(strip=True)
            
            # 解析參數 (格式通常是 Page$11 或 Page$Last)
            if arg and arg.startswith("Page$"):
                val_str = arg.replace("Page$", "")
                
                # 優先級 S: 直接是 Last
                if val_str == "Last" or "Last" in txt or "末頁" in txt:
                    best_link = link
                    target_type = "Last"
                    break # 找到最後一頁，直接鎖定
                
                # 優先級 A: 數字
                if val_str.isdigit():
                    page_num = int(val_str)
                    # 只有當這個數字「大於」我們目前所在的頁數時，才考慮
                    if page_num > current_page and page_num > best_arg_val:
                        best_arg_val = page_num
                        best_link = link
                        target_type = f"Page {page_num}"
            
            # 優先級 B: 只有文字特徵 (>> 或 ...)
            elif ">>" in txt or "..." in txt:
                # 只有當我們還沒找到明確的數字目標時，才把這個當備案
                if target_type == "None":
                    best_link = link
                    target_type = "Next Block"

        # 決策執行
        if best_link:
            print(f"🎯 鎖定目標: [{target_type}]，執行跳轉...")
            target, arg = extract_do_postback_args(best_link['href'])
            
            payload = get_hidden_fields(soup)
            payload["__EVENTTARGET"] = target
            payload["__EVENTARGUMENT"] = arg
            
            post_res = session.post(BASE_URL, data=payload, headers=HEADERS, timeout=30)
            if post_res.status_code == 200:
                soup = BeautifulSoup(post_res.text, "html.parser")
                # 更新當前頁碼紀錄 (如果是跳數字的話)
                if target_type.startswith("Page "):
                    current_page = int(target_type.split()[1])
                elif target_type == "Next Block":
                    current_page += 1 # 預估前進了
                print("✅ 跳轉成功！")
                time.sleep(1)
            else:
                print(f"❌ 跳轉失敗: {post_res.status_code}")
                break
        else:
            print("🏁 無法找到更後面的頁面，判斷已達【終點】")
            break
            
    return soup

def extract_time(container):
    time_span = container.find("span", class_="local-time")
    if time_span: return time_span.text.strip()
    text = container.get_text()
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2}', text)
    if match: return match.group(0)
    return "無時間資訊"

def main():
    print(f"🚀 V10 啟動檢查: {datetime.now()}")
    status = load_status()
    last_fingerprint = status["last_fingerprint"]
    
    session = requests.Session()
    
    # 1. 執行追頁
    soup = chase_last_page(session)

    # 2. 搜尋 Mikeon88
    author_links = soup.find_all("a", id=re.compile("lnkName"))
    found_posts = []
    print(f"🔍 掃描最終頁面發言...")

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
