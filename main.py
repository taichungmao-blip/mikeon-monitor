import os
import time
import requests
import re
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
# 🛠️ 設定區
# ==========================================
TARGET_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?goto=14104"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "") 

# 檔案名稱 (必須與 yml 檔對應)
HISTORY_FILE = "sent_history.txt"

# ==========================================
# 🔧 核心功能
# ==========================================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def get_history():
    """讀取歷史紀錄"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def append_history(unique_id):
    """將新的 ID 寫入檔案"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{unique_id}\n")

def generate_id(text):
    """產生唯一特徵碼"""
    # 優先抓取時間
    match = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)", text)
    if match:
        return f"TIME_{match.group(1)}"
    # 沒時間則用雜湊
    clean_text = re.sub(r"\s+", "", text)
    return f"HASH_{hashlib.md5(clean_text.encode('utf-8')).hexdigest()}"

def send_notify(full_text, link):
    if not DISCORD_WEBHOOK_URL: return
    data = {
        "embeds": [{
            "title": f"🔔 {full_text.splitlines()[0][:20]}...",
            "description": f"{full_text[:200]}...\n\n🔗 [點擊前往]({link})",
            "color": 5814783,
            "footer": {"text": "Mikeon Monitor V17 (Cloud Save)"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=data)

# ==========================================
# 🏁 主程式
# ==========================================
def main():
    print("🚀 V17 雲端記憶版啟動...")
    
    # 1. 讀取目前的記憶
    history = get_history()
    print(f"📖 讀取到 {len(history)} 筆歷史紀錄")

    driver = get_driver()
    new_items_count = 0

    try:
        driver.get(TARGET_URL)
        time.sleep(5)
        
        # ==========================================
        # 🔄 新增：自動翻頁到最新一頁邏輯
        # ==========================================
        try:
            # 尋找所有可點擊的分頁按鈕 (a 標籤)
            page_links = driver.find_elements(By.CSS_SELECTOR, "a.page-link")
            
            target_element = None
            max_num = 0
            
            for link in page_links:
                text = link.text.strip()
                # 判斷按鈕文字如果是數字，找出最大值
                if text.isdigit():
                    num = int(text)
                    if num > max_num:
                        max_num = num
                        target_element = link
                        
            # 如果有找到可以點擊的數字頁碼，就點擊它
            if target_element:
                print(f"🔄 發現最新頁碼 {max_num}，正在自動點擊跳轉...")
                # 使用 JavaScript 強制點擊，避開畫面遮擋問題
                driver.execute_script("arguments[0].click();", target_element)
                time.sleep(5) # 等待新一頁的內容載入
                
        except Exception as e:
            print(f"⚠️ 翻頁過程發生異常 (或找不到頁碼): {e}")
        # ==========================================

        # 接下來是原本抓取文章的邏輯
        rows = driver.find_elements(By.CSS_SELECTOR, "div.card")

    

        for row in rows:
            text = row.text.strip()
            # 原本的過濾條件
            if len(text) < 5 or any(k in text for k in ["廣告", "Klook"]): continue
            
            # --- 新增的過濾條件：只抓取發文者為 mikeon88 的文章 ---
            lines = text.splitlines()
            if not lines or "mikeon88" not in lines[0]:
                continue
            # -----------------------------------------------------

            uid = generate_id(text)
            
            if uid not in history:
                print(f"🆕 發現新訊: {uid}")
                send_notify(text, TARGET_URL)
                append_history(uid) # 寫入本地檔案
                history.add(uid)
                new_items_count += 1
            else:
                pass # 已讀跳過

        if new_items_count > 0:
            print(f"🎉 新增了 {new_items_count} 筆紀錄 (等待 GitHub 存檔...)")
        else:
            print("💤 沒有新內容")

    except Exception as e:
        print(f"❌ 錯誤: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
