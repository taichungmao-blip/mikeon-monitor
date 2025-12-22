import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
# 1. 建立模擬環境 (模擬你的截圖結構)
# ==========================================
def create_mock_html():
    html_content = """
    <!DOCTYPE html>
    <html>
    <body>
        <h2>模擬 V10/V11 爬蟲目標列表</h2>
        
        <div class="post-item-container">
            <h4>
                <a href="https://example.com/post/123" id="ctl00_link_01">V11 測試文章標題</a>
            </h4>
            <small class="text-muted">
                <span id="ctl00_hidden_01" style="display:none;">2025-12-13T01:49:42Z</span>
                
                <span class="local-time" data-utc="2025-12-13T01:49:42Z">2025/12/13 10:49:42</span>
            </small>
        </div>

        <hr>

        <div class="post-item-container">
            <h4><a href="https://example.com/post/456">第二篇文章</a></h4>
            <small class="text-muted">
                <span style="display:none;">2025-12-14...</span>
                <span class="local-time" data-utc="2025-12-14...">2025/12/14 11:00:00</span>
            </small>
        </div>
    </body>
    </html>
    """
    with open("mock_page.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    return os.path.abspath("mock_page.html")

# ==========================================
# 2. V11 核心抓取邏輯 (請將這段應用到你的主程式)
# ==========================================
def run_test():
    # 設定瀏覽器 (無頭模式可選)
    options = Options()
    # options.add_argument("--headless") 
    
    print("🚀 V11 測試啟動...")
    driver = webdriver.Chrome(options=options)
    
    try:
        # 載入本地模擬頁面
        file_path = create_mock_html()
        driver.get(f"file:///{file_path}")
        time.sleep(1) # 等待渲染

        # 模擬：找到所有文章區塊 (假設每篇文章都被包在 div 裡)
        # 注意：你需要根據實際網站調整最外層的尋找方式，例如 find_elements(By.XPATH, "//tr") 或 div class
        posts = driver.find_elements(By.CSS_SELECTOR, ".post-item-container")

        print(f"🔍 找到 {len(posts)} 篇文章，開始解析...\n")

        for index, row in enumerate(posts, 1):
            print(f"--- 解析第 {index} 篇 ---")
            
            # ---------------------------------------------------
            # ✅ 修正點 1: 抓取時間 (避開 display:none)
            # ---------------------------------------------------
            try:
                # 使用 CSS Selector 直接找 class="local-time"
                # "." 代表從當前 row 節點往下找
                time_el = row.find_element(By.CSS_SELECTOR, ".local-time")
                post_time = time_el.text
                
                # 如果文字是空的 (有些瀏覽器行為不同)，改抓屬性
                if not post_time:
                    post_time = time_el.get_attribute("data-utc") + " (來自屬性)"
            except Exception as e:
                post_time = "❌ 抓取失敗"

            # ---------------------------------------------------
            # ✅ 修正點 2: 抓取連結 (抓 href 屬性)
            # ---------------------------------------------------
            try:
                # 假設連結是標題 (h4 下的 a) 或直接是 row 下的 a
                # 這裡使用 tag name "a" 搜尋該區塊內的第一個連結
                link_el = row.find_element(By.TAG_NAME, "a")
                post_title = link_el.text
                post_link = link_el.get_attribute("href") # 關鍵：要抓 href 屬性！
            except:
                post_title = "未知標題"
                post_link = "❌ 找不到連結"

            # ---------------------------------------------------
            # 🖨️ 結果輸出
            # ---------------------------------------------------
            print(f"📅 發言時間: {post_time}")
            print(f"📝 文章標題: {post_title}")
            print(f"🔗 來源連結: {post_link}")
            print("-----------------------")

    finally:
        driver.quit()
        # 清除測試檔案
        if os.path.exists("mock_page.html"):
            os.remove("mock_page.html")
        print("\n✅ 測試結束")

if __name__ == "__main__":
    run_test()
