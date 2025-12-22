import os
import time
import requests
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
# 🛠️ 使用者設定區
# ==========================================
TARGET_URL = "https://stocks.ddns.net/Forum/128/mikeon88%E6%8C%81%E8%82%A1%E5%A4%A7%E5%85%AC%E9%96%8B.aspx?goto=14104"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "") 
HISTORY_FILE = "sent_history.txt"

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
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(content_hash):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{content_hash}\n")

def send_discord_notify(full_text, link):
    if not DISCORD_WEBHOOK_URL:
        return

    # 內容截斷處理，標題只顯示前 20 字，內容顯示更多
    title_preview = full_text[:20] + "..." 
    
    data = {
        "embeds": [{
            "title": f"🔔 {title_preview}",
            "description": f"{full_text}\n\n🔗 [點擊前往討論區]({link})",
            "color": 5814783, # 藍綠色
            "footer": {"text": "Mikeon Monitor V14"}
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
    print(f"🚀 V14 監控啟動 (含廣告過濾)...")
    sent_history = load_history()
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
                
                # --- [V14 新增: 垃圾過濾器] ---
                # 1. 過濾太短的內容
                if len(full_text) < 5: continue
                
                # 2. 過濾廣告關鍵字 (可以自己在這裡加)
                ignore_keywords = ["廣告", "Klook", "分潤", "購物價格"]
                is_ad = False
                for keyword in ignore_keywords:
                    if keyword in full_text:
                        is_ad = True
                        break
                
                if is_ad:
                    print(f"🚫 忽略廣告內容: {full_text[:10]}...")
                    continue
                # -----------------------------

                content_hash = hashlib.md5(full_text.encode('utf-8')).hexdigest()

                if content_hash not in sent_history:
                    print(f"🆕 發現新留言: {full_text[:20]}...")
                    send_discord_notify(full_text, TARGET_URL)
                    save_history(content_hash)
                    sent_history.add(content_hash)
                    new_count += 1
                
            except Exception:
                continue
        
        if new_count == 0:
            print("💤 沒有發現新留言 (廣告已過濾)")
        else:
            print(f"🎉 已發送 {new_count} 則新通知")

    except Exception as e:
        print(f"❌ 錯誤: {e}")
    finally:
        driver.quit()
        print("✅ 監控結束")

if __name__ == "__main__":
    main()
