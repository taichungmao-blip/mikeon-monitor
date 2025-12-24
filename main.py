import os
import time
import requests
import re
import sqlite3
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
# 🛠️ 使用者設定區
# ==========================================
TARGET_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?goto=14104"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "") 

# 設定資料庫路徑 (強制放在腳本同一層目錄)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "monitor.db")

# ==========================================
# 🔧 資料庫核心 (SQLite)
# ==========================================
def init_db():
    """初始化資料庫"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 建立一個簡單的表格來存已發送過的 ID
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

def is_post_exists(conn, unique_id):
    """檢查 ID 是否已存在"""
    c = conn.cursor()
    c.execute("SELECT 1 FROM history WHERE id = ?", (unique_id,))
    return c.fetchone() is not None

def save_post(conn, unique_id):
    """儲存新的 ID"""
    c = conn.cursor()
    try:
        c.execute("INSERT INTO history (id) VALUES (?)", (unique_id,))
        conn.commit()
        # print(f"💾 已寫入資料庫: {unique_id}") # Debug用
    except sqlite3.IntegrityError:
        pass # 已經存在就算了

# ==========================================
# 🔧 爬蟲與通知核心
# ==========================================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def generate_id(text):
    """
    產生唯一 ID (診斷關鍵)：
    優先使用「時間」作為 ID。只要文章裡有時間，ID 就固定，不管內文怎麼變。
    """
    # 1. 嘗試抓時間 (例如 2025/12/13 10:49:42)
    match = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})", text)
    if match:
        return f"TIME_{match.group(1)}"
    
    # 2. 如果沒時間，則針對「去空白後的文字」做 Hash
    # 這樣就算網頁多了一個空白，Hash 也不會變
    clean_text = re.sub(r"\s+", "", text) 
    return f"HASH_{hashlib.md5(clean_text.encode('utf-8')).hexdigest()}"

def send_discord_notify(full_text, link):
    if not DISCORD_WEBHOOK_URL:
        return

    first_line = full_text.split('\n')[0][:30]
    data = {
        "embeds": [{
            "title": f"🔔 {first_line}...",
            "description": f"{full_text[:300]}...\n\n🔗 [點擊前往討論區]({link})",
            "color": 5814783,
            "footer": {"text": "Mikeon Monitor V16 (SQLite)"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ Discord 通知已發送")
    except Exception as e:
        print(f"❌ Discord 發送失敗: {e}")

# ==========================================
# 🏁 主程式邏輯
# ==========================================
def main():
    print(f"🚀 V16 資料庫版啟動...")
    print(f"📂 資料庫路徑: {DB_PATH}")
    
    # 連接資料庫
    conn = init_db()
    
    driver = get_driver()
    
    try:
        driver.get(TARGET_URL)
        print("⏳ 網頁載入中...")
        time.sleep(5) 

        rows = driver.find_elements(By.CSS_SELECTOR, "div.card")
        print(f"🔍 掃描到 {len(rows)} 篇卡片...")

        new_count = 0
        for i, row in enumerate(rows):
            try:
                full_text = row.text.strip()
                
                # --- 過濾器 ---
                if len(full_text) < 5: continue
                if any(x in full_text for x in ["廣告", "Klook", "分潤"]): continue
                # -------------

                # 產生 ID
                unique_id = generate_id(full_text)
                
                # 🔥 診斷輸出：印出 ID 讓你確認
                # 如果 ID 每次都不一樣，代表網頁內容有變動
                # print(f"[{i}] ID: {unique_id}") 

                # 檢查資料庫
                if not is_post_exists(conn, unique_id):
                    print(f"🆕 發現新內容 (ID: {unique_id}) -> 準備通知")
                    print(f"   預覽: {full_text[:15]}...")
                    
                    send_discord_notify(full_text, TARGET_URL)
                    
                    # 寫入資料庫
                    save_post(conn, unique_id)
                    new_count += 1
                else:
                    # 這行證明去重機制有在運作
                    print(f"😴 已讀跳過 (ID: {unique_id})")

            except Exception as e:
                continue
        
        if new_count == 0:
            print("💤 本次無新內容")
        else:
            print(f"🎉 成功處理 {new_count} 則新訊息")

    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
    finally:
        driver.quit()
        conn.close() # 關閉資料庫連線
        print("✅ 監控結束")

if __name__ == "__main__":
    main()
