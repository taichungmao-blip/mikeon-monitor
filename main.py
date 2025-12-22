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
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "") # 請確認 GitHub Secrets 或直接填入
HISTORY_FILE = "sent_history.txt" # 用來記錄已發送過的內容

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
    """讀取已發送過的紀錄"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(content_hash):
    """將新內容的特徵碼寫入紀錄"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{content_hash}\n")

def send_discord_notify(full_text, link):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook，跳過通知")
        return

    # 為了美觀，將過長的文字截斷放在標題
    title_preview = full_text[:30] + "..." if len(full_text) > 30 else full_text
    
    data = {
        "embeds": [{
            "title": f"🔔 新留言偵測",
            "description": f"**內容預覽：**\n{full_text}\n\n🔗 [點擊前往討論區]({link})",
            "color": 5814783, # 藍綠色
            "footer": {"text": "Mikeon Monitor V13"}
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
    print(f"🚀 V13 監控啟動 (啟用 Discord + 去重機制)...")
    
    # 1. 讀取歷史紀錄
    sent_history = load_history()
    print(f"📂 目前已記錄 {len(sent_history)} 筆歷史資料")

    driver = get_driver()
    
    try:
        driver.get(TARGET_URL)
        print("⏳ 網頁載入中...")
        time.sleep(5) 

        # 這裡只抓第一頁即可，因為最新的都在最下面或最上面
        # 如果需要翻頁請保留之前的 while 迴圈，但通常監控只需看最新頁
        rows = driver.find_elements(By.CSS_SELECTOR, "div.card")
        print(f"🔍 本頁掃描到 {len(rows)} 篇卡片...")

        new_count = 0
        for row in rows:
            try:
                # [V13 簡化邏輯] 
                # 直接抓取卡片內的全部文字，因為時間已經包含在內文了
                full_text = row.text.strip()
                
                # 過濾空內容或極短內容 (例如分隔線)
                if len(full_text) < 5:
                    continue

                # 產生內容的雜湊值 (Hash) 作為唯一 ID，比對是否發送過
                content_hash = hashlib.md5(full_text.encode('utf-8')).hexdigest()

                # 如果這則內容沒發送過
                if content_hash not in sent_history:
                    print(f"🆕 發現新內容: {full_text[:30]}...")
                    
                    # 發送通知
                    send_discord_notify(full_text, TARGET_URL)
                    
                    # 寫入紀錄防止重複
                    save_history(content_hash)
                    sent_history.add(content_hash)
                    new_count += 1
                else:
                    # print(f"😴 已讀內容，跳過: {full_text[:10]}...")
                    pass

            except Exception as e:
                continue
        
        if new_count == 0:
            print("💤 沒有發現新內容")
        else:
            print(f"🎉 成功處理 {new_count} 則新訊息")

    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
    finally:
        driver.quit()
        print("✅ 監控結束")

if __name__ == "__main__":
    main()
