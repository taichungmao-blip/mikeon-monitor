import os
import time
import requests
import hashlib
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
# 🛠️ 使用者設定區
# ==========================================
TARGET_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?goto=14104"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "") 

# ✅ 強制設定歷史紀錄檔在「當前腳本目錄」，避免存錯地方
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "sent_history.txt")

# ==========================================
# 🔧 系統核心
# ==========================================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def load_history():
    """讀取歷史紀錄 (使用 Set 集合加速比對)"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(content_id):
    """寫入新的 ID"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{content_id}\n")

def extract_time_id(text):
    """
    智慧特徵提取：
    1. 嘗試抓取標準時間格式 (YYYY/MM/DD HH:MM:SS) 作為唯一 ID。
    2. 如果找不到時間，才退而求其次使用文字雜湊 (Hash)。
    """
    # Regex 尋找時間格式：2025/12/13 10:49:42
    match = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})", text)
    if match:
        # 找到時間了！直接用時間當 ID (最準，不會因為改錯字就重發)
        return f"TIME_{match.group(1)}"
    else:
        # 沒找到時間，把所有空白拿掉後做 Hash
        clean_text = re.sub(r"\s+", "", text) # 移除所有空白和換行
        return f"HASH_{hashlib.md5(clean_text.encode('utf-8')).hexdigest()}"

def send_discord_notify(full_text, link):
    if not DISCORD_WEBHOOK_URL:
        return

    # 標題只取第一行或前 20 字
    first_line = full_text.split('\n')[0][:30]
    
    data = {
        "embeds": [{
            "title": f"🔔 {first_line}...",
            "description": f"{full_text[:200]}...\n\n🔗 [點擊前往討論區]({link})",
            "color": 5814783,
            "footer": {"text": "Mikeon Monitor V15 (Smart Dedup)"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ Discord 通知已發送！")
    except Exception as e:
        print(f"❌ Discord 發送失敗: {e}")

# ==========================================
# 🏁 主程式邏輯
# ==========================================
def main():
    print(f"🚀 V15 智慧去重版啟動...")
    print(f"📂 歷史紀錄檔路徑: {HISTORY_FILE}")
    
    sent_history = load_history()
    print(f"📖 系統記憶中已有 {len(sent_history)} 筆資料")

    driver = get_driver()
    
    try:
        driver.get(TARGET_URL)
        print("⏳ 網頁載入中...")
        time.sleep(5) 

        rows = driver.find_elements(By.CSS_SELECTOR, "div.card")
        print(f"🔍 掃描到 {len(rows)} 篇卡片...")

        new_count = 0
        for row in rows:
            try:
                full_text = row.text.strip()
                
                # --- [過濾器] ---
                if len(full_text) < 5: continue
                if any(x in full_text for x in ["廣告", "Klook", "分潤"]):
                    continue
                # ---------------

                # 🌟 [V15 核心升級: 取得唯一 ID]
                unique_id = extract_time_id(full_text)

                # 比對是否已發送過
                if unique_id not in sent_history:
                    print(f"🆕 發現新內容 (ID: {unique_id})")
                    print(f"   內容預覽: {full_text[:20]}...")
                    
                    send_discord_notify(full_text, TARGET_URL)
                    
                    save_history(unique_id)
                    sent_history.add(unique_id)
                    new_count += 1
                else:
                    # 這一行是 Debug 用，確認程式有掃描到但選擇「忽略」
                    # print(f"😴 已讀忽略 (ID: {unique_id})")
                    pass

            except Exception as e:
                continue
        
        if new_count == 0:
            print("💤 沒有發現新內容 (所有文章都在歷史紀錄中)")
        else:
            print(f"🎉 成功處理 {new_count} 則真正的新訊息")

    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
    finally:
        driver.quit()
        print("✅ 監控結束")

if __name__ == "__main__":
    main()
