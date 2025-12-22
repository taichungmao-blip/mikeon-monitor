import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 🛠️ 使用者設定區
# ==========================================
# 1. 目標網址
TARGET_URL = "https://mikeon88.com/..."  # 請確認這是你的目標網址

# 2. Discord Webhook (優先讀取環境變數，沒有則使用預設值)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "你的_DISCORD_WEBHOOK_URL_貼在這裡")

# 3. 爬蟲設定
MAX_PAGES = 10      # 最大翻頁數 (防止無限迴圈)
ROW_SELECTOR = "tr" # 文章列表的每一行 (通常是 tr 或 div.post-item)

# ==========================================
# 🔧 系統核心 (V11: Headless 防崩潰設定)
# ==========================================
def get_driver():
    """設定 Chrome 瀏覽器 (針對 GitHub Actions 優化)"""
    options = Options()
    
    # --- [V11 關鍵修正: 解決 CI/CD 環境崩潰問題] ---
    options.add_argument("--headless=new")  # 無頭模式
    options.add_argument("--no-sandbox")    # Linux/Docker 必備
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") # 確保版面正確
    
    # 偽裝成一般使用者 (User-Agent)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    return webdriver.Chrome(options=options)

def send_discord_notify(title, link, post_time):
    """發送 Discord Embed 美化通知"""
    if "你的_DISCORD" in DISCORD_WEBHOOK_URL or not DISCORD_WEBHOOK_URL:
        # print(f"⚠️ 跳過通知 (Webhook 未設定): {title}")
        return

    data = {
        "embeds": [{
            "title": f"🔔 發現新內容: {title}",
            "description": f"📅 時間: **{post_time}**\n🔗 [點擊前往文章]({link})",
            "color": 3447003,  # 藍色
            "footer": {"text": "Mikeon Monitor V11 (V9 Hybrid)"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"❌ Discord 發送失敗: {e}")

# ==========================================
# 🏁 主程式邏輯
# ==========================================
def main():
    print("🚀 V11 (V9 雙箭頭混合版) 啟動中...")
    driver = get_driver()
    
    try:
        driver.get(TARGET_URL)
        print("⏳ 網頁載入中...")
        time.sleep(5) # 等待初始載入

        current_page = 1
        
        while current_page <= MAX_PAGES:
            print(f"\n📄 --- 正在分析第 {current_page} 頁 ---")
            
            # 1. 抓取文章列表
            rows = driver.find_elements(By.CSS_SELECTOR, ROW_SELECTOR)
            print(f"🔍 掃描到 {len(rows)} 筆資料區塊...")

            for i, row in enumerate(rows):
                try:
                    # =================================================
                    # ✅ [V11 修正: 精準資料解析]
                    # =================================================
                    
                    # 1. 抓時間 (優先找 class="local-time"，避開 display:none)
                    try:
                        time_el = row.find_element(By.CSS_SELECTOR, ".local-time")
                        post_time = time_el.text
                        if not post_time: # 雙重確認
                            post_time = time_el.get_attribute("data-utc")
                    except:
                        # 找不到時間通常代表這是表頭或分隔線
                        continue 

                    # 2. 抓連結與標題 (找 href 屬性)
                    try:
                        link_el = row.find_element(By.TAG_NAME, "a")
                        post_title = link_el.text
                        post_link = link_el.get_attribute("href")
                    except:
                        continue 

                    # 3. 輸出結果與通知
                    print(f"📌 [{post_time}] {post_title}")
                    
                    # 可以在這裡加入你的「已讀判斷」邏輯 (例如比對 last_seen_url)
                    # send_discord_notify(post_title, post_link, post_time)

                except Exception as e:
                    # 忽略單行解析錯誤，繼續下一行
                    continue

            # =================================================
            # 🏹 [V9 核心: 雙箭頭鎖定翻頁邏輯]
            # =================================================
            try:
                print("🔄 尋找 [雙箭頭 >>] 或 [Next] 按鈕...")
                
                # V9 經典 XPath: 同時鎖定 ">>", "Next", "下一頁", ">"
                # 優先級：雙箭頭
