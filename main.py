from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import tkinter as tk
from tkinter import scrolledtext
import threading


class TicketGrabber:
    def __init__(self, url, status_callback=None):
        """
        初始化搶票程式

        Args:
            url: 購票網站網址
            status_callback: 狀態回調函數，用於更新 UI
        """
        self.url = url
        self.status_callback = status_callback
        self.driver = None
        self.wait = None

    def _update_status(self, message, status_type="info"):
        """
        更新狀態訊息

        Args:
            message: 狀態訊息
            status_type: 狀態類型 (info, success, error)
        """
        if self.status_callback:
            self.status_callback(message, status_type)
        print(message)

    def _init_driver(self): 
        """初始化瀏覽器驅動"""
        if self.driver is None:
            self._update_status("Initializing browser...")
            try:
                # 使用 webdriver-manager 自動管理 ChromeDriver
                service = Service(ChromeDriverManager().install())

                # 設定 Chrome 選項
                chrome_options = Options()
                # 如果需要無頭模式（無 GUI），取消下面的註解
                # chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")

                # 初始化 Chrome 瀏覽器
                self.driver = webdriver.Chrome(
                    service=service, options=chrome_options)
                # 設定頁面載入超時時間
                self.driver.implicitly_wait(10)
                self.wait = WebDriverWait(self.driver, 10)
                self._update_status(
                    "Browser initialized successfully", "success")
            except Exception as e:
                error_msg = str(e)
                if "executable needs to be in PATH" in error_msg or "chromedriver" in error_msg.lower():
                    self._update_status(
                        "ChromeDriver error. Please install Chrome browser and dependencies.", "error")
                    self._update_status(
                        "Run: sudo apt-get install -y chromium-browser chromium-chromedriver libnss3", "error")
                elif "chrome not found" in error_msg.lower() or "browser binary" in error_msg.lower():
                    self._update_status(
                        "Chrome browser not found. Please install Chrome or Chromium.", "error")
                    self._update_status(
                        "Run: sudo apt-get install -y chromium-browser", "error")
                else:
                    self._update_status(
                        f"Browser initialization failed: {error_msg}", "error")
                raise

    def open_page(self):
        """開啟購票頁面"""
        self._update_status("Opening ticket page...")
        if self.driver is None:
            self._init_driver()
        self.driver.get(self.url)
        self._update_status(f"Page opened: {self.url}", "success")

    def click_buy_now(self, button_text="立即購票", button_selector="li.buy a"):
        """
        點選「立即購票」按鈕：高頻率偵測，出現立即點擊
        """
        try:
            self._update_status(f"Looking for '{button_text}' button...")

            # 建立專屬的 WebDriverWait，將輪詢頻率 (poll_frequency) 縮短為 0.1 秒 (預設為 0.5 秒)
            # 這樣一出現就能在 0.1 秒內反應
            fast_wait = WebDriverWait(self.driver, 10, poll_frequency=0.1)

            if button_selector:
                # 根據您的 HTML 結構，直接鎖定 <li class="buy"> 下的 <a> 標籤
                buy_button = fast_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, button_selector))
                )
            else:
                # 備用方案：透過 XPath 精準匹配截圖中的 <div> 結構
                xpath = f"//li[contains(@class, 'buy')]//a[.//div[contains(text(), '{button_text}')]]"
                buy_button = fast_wait.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )

            # 搶票關鍵：直接使用 JavaScript 執行點擊
            # 這能跳過 UI 渲染、不用 scrollIntoView，也不會遇到 "element not interactable" 錯誤
            self.driver.execute_script("arguments[0].click();", buy_button)
            
            self._update_status(f"Clicked '{button_text}' button instantly", "success")
            
            # 絕對不要在這裡使用 time.sleep(2)！
            # 應該將等待下一個頁面載入的邏輯交給下一個步驟 (例如 wait_for_session_list) 去處理
            return True

        except TimeoutException:
            self._update_status(f"Could not find '{button_text}' button", "error")
            return False
        except Exception as e:
            self._update_status(f"Error clicking '{button_text}' button: {str(e)}", "error")
            return False

    def wait_for_session_list(self, timeout=10):
        """
        等待場次列表出現

        Args:
            timeout: 等待超時時間（秒）
        """
        try:
            self._update_status("Waiting for session list to load...")
            # 這裡需要根據實際網站的場次列表選擇器來調整
            # 例如：等待場次容器出現
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "session-list"))
            )
            self._update_status("Session list loaded", "success")
            return True
        except TimeoutException:
            self._update_status("Session list loading timeout", "error")
            return False

    def select_session(self, session_index=0, session_text=None):
        """
        選擇場次（可選功能，如果您需要選擇特定場次）

        Args:
            session_index: 場次索引（從 0 開始）
            session_text: 場次文字（例如："2024-01-01 19:00"）
        """
        try:
            if session_text:
                # 透過文字選擇場次
                session = self.driver.find_element(
                    By.XPATH, f"//div[contains(text(), '{session_text}')]"
                )
                session.click()
                self._update_status(
                    f"Selected session: {session_text}", "success")
            else:
                # 透過索引選擇場次
                sessions = self.driver.find_elements(
                    By.CLASS_NAME, "session-item")
                if sessions and session_index < len(sessions):
                    sessions[session_index].click()
                    self._update_status(
                        f"Selected session #{session_index + 1}", "success")
                else:
                    self._update_status(
                        f"Could not find session at index {session_index}", "error")
                    return False


        except Exception as e:
            self._update_status(f"Error selecting session: {str(e)}", "error")
            return False

    def click_order_now(self, button_text="立即訂購", button_selector="#gameList button.btn-primary"):
        """
        點選「立即訂購」按鈕：改為直接擷取 data-href 並強制跳轉，避開前端事件綁定的時間差
        """
        try:
            self._update_status(f"Looking for '{button_text}' button...")

            # 維持高頻率偵測
            fast_wait = WebDriverWait(self.driver, 10, poll_frequency=0.1)

            if button_selector:
                order_button = fast_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, button_selector))
                )
            else:
                xpath = f"//div[@id='gameList']//button[contains(text(), '{button_text}')]"
                order_button = fast_wait.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )

            # ====== 搶票極速關鍵：不點擊，直接抓網址跳轉 ======
            # 取得 data-href 裡面的購票區域網址
            target_url = order_button.get_attribute("data-href")
            
            if target_url:
                self._update_status(f"Intercepted URL! Jumping directly to: {target_url}", "success")
                # 使用 JavaScript 強制瀏覽器改變網址，速度最快
                self.driver.execute_script(f"window.location.href='{target_url}';")
            else:
                # 備用方案：萬一這場沒用到 data-href，再退回使用 JS 點擊
                self._update_status("No data-href found, using JS click as fallback.", "info")
                self.driver.execute_script("arguments[0].click();", order_button)
            # =================================================
            
            return True

        except TimeoutException:
            self._update_status(f"Could not find '{button_text}' button", "error")
            return False
        except Exception as e:
            self._update_status(f"Error acting on '{button_text}' button: {str(e)}", "error")
            return False

    def run_first_stage(self):
        """執行第一階段的搶票流程"""
        try:
            self.open_page()

            if not self.click_buy_now():
                return False

            # === 新增：處理 target="_new" 開啟新分頁的狀況 ===
            # 等待新分頁出現 (原本只有 1 個，現在應該要有 2 個)
            WebDriverWait(self.driver, 5, poll_frequency=0.1).until(
                lambda d: len(d.window_handles) > 1
            )
            # 切換到最新開啟的分頁
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self._update_status("Switched to new tab", "info")
            # ============================================

            if not self.wait_for_session_list():
                return False

            if not self.click_order_now():
                return False

            self._update_status("First stage completed!", "success")
            return True

        except Exception as e:
            self._update_status(f"Error during execution: {str(e)}", "error")
            return False

    def close(self):
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            self._update_status("Browser closed", "info")


class TicketGrabberGUI:
    def __init__(self, root):
        """
        初始化 GUI 介面

        Args:
            root: tkinter 根視窗
        """
        self.root = root
        self.root.title("Ticket Grabber")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # 設定支援中文的字體
        self._setup_fonts()

        # 執行狀態
        self.is_running = False
        self.grabber = None

        # 建立 UI
        self._create_widgets()

    def _setup_fonts(self):
        """設定支援中文的字體"""
        # 嘗試使用系統中文字體
        chinese_fonts = [
            "Microsoft JhengHei",      # Windows 微軟正黑體
            "Microsoft YaHei",         # Windows 微軟雅黑
            "SimHei",                  # Windows 黑體
            "Noto Sans CJK SC",        # Linux Noto 字體
            "WenQuanYi Micro Hei",     # Linux 文泉驛微米黑
            "WenQuanYi Zen Hei",       # Linux 文泉驛正黑
            "DejaVu Sans",             # Linux DejaVu Sans
            "AR PL UMing CN",          # Linux 中文字體
            "AR PL UKai CN",           # Linux 中文字體
        ]

        # 嘗試找到可用的中文字體
        self.title_font = None
        self.default_font = None
        self.small_font = None
        self.log_font = None

        import tkinter.font as tkfont
        available_fonts = list(tkfont.families())

        # 尋找標題字體（較大）
        for font_name in chinese_fonts:
            if font_name in available_fonts:
                self.title_font = (font_name, 20, "bold")
                break

        if self.title_font is None:
            # 如果找不到，使用系統預設字體
            self.title_font = ("TkDefaultFont", 20, "bold")

        # 尋找預設字體（中等）
        for font_name in chinese_fonts:
            if font_name in available_fonts:
                self.default_font = (font_name, 12)
                break

        if self.default_font is None:
            self.default_font = ("TkDefaultFont", 12)

        # 尋找小字體（用於狀態）
        for font_name in chinese_fonts:
            if font_name in available_fonts:
                self.small_font = (font_name, 10)
                break

        if self.small_font is None:
            self.small_font = ("TkDefaultFont", 10)

        # 日誌字體（等寬字體）
        monospace_fonts = ["Consolas", "Courier New",
                           "Monaco", "DejaVu Sans Mono", "Courier"]
        for font_name in monospace_fonts:
            if font_name in available_fonts:
                self.log_font = (font_name, 10)
                break

        if self.log_font is None:
            self.log_font = ("TkFixedFont", 10)

        # 設定系統預設字體以支援中文
        try:
            # 設定 Tk 預設字體
            default_font_name = None
            for font_name in chinese_fonts:
                if font_name in available_fonts:
                    default_font_name = font_name
                    break

            if default_font_name:
                self.root.option_add("*Font", (default_font_name, 12))
        except:
            pass

    def _create_widgets(self):
        """建立 UI 元件"""
        # 標題
        title_label = tk.Label(
            self.root,
            text="Ticket Grabber",
            font=self.title_font,
            pady=10
        )
        title_label.pack()

        # 網址輸入區
        url_frame = tk.Frame(self.root, pady=10)
        url_frame.pack(fill=tk.X, padx=20)

        url_label = tk.Label(url_frame, text="Ticket URL:",
                             font=self.default_font)
        url_label.pack(anchor=tk.W)

        self.url_entry = tk.Entry(url_frame, font=self.default_font)
        self.url_entry.pack(fill=tk.X, pady=5)
        self.url_entry.insert(0, "https://tixcraft.com/activity/detail/26_kodaline")

        # 按鈕區
        button_frame = tk.Frame(self.root, pady=10)
        button_frame.pack(fill=tk.X, padx=20)

        self.execute_button = tk.Button(
            button_frame,
            text="Execute First Stage",
            font=(self.default_font[0], self.default_font[1], "bold"),
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=10,
            command=self._execute_first_stage,
            cursor="hand2"
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(
            button_frame,
            text="Stop",
            font=self.default_font,
            bg="#f44336",
            fg="white",
            padx=20,
            pady=10,
            command=self._stop_execution,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # 狀態標籤
        status_frame = tk.Frame(self.root, pady=5)
        status_frame.pack(fill=tk.X, padx=20)

        status_label = tk.Label(
            status_frame, text="Status:", font=self.default_font)
        status_label.pack(anchor=tk.W)

        self.status_label = tk.Label(
            status_frame,
            text="Ready...",
            font=self.small_font,
            bg="#f0f0f0",
            anchor=tk.W,
            relief=tk.SUNKEN,
            padx=10,
            pady=5
        )
        self.status_label.pack(fill=tk.X, pady=5)

        # 日誌顯示區
        log_frame = tk.Frame(self.root, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        log_title = tk.Label(
            log_frame, text="Execution Log:", font=self.default_font)
        log_title.pack(anchor=tk.W)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=self.log_font,
            bg="#1e1e1e",
            fg="#d4d4d4",
            wrap=tk.WORD,
            padx=10,
            pady=10
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 初始化日誌
        self._add_log(
            "Ready. Please enter the ticket URL and click 'Execute First Stage'", "info")

    def _update_status_label(self, message):
        """
        更新狀態標籤

        Args:
            message: 狀態訊息
        """
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def _add_log(self, message, log_type="info"):
        """
        添加日誌訊息

        Args:
            message: 日誌訊息
            log_type: 日誌類型 (info, success, error)
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        # 根據類型設定顏色
        color_map = {
            "info": "#569cd6",      # 藍色
            "success": "#4ec9b0",   # 綠色
            "error": "#f48771"      # 紅色
        }
        color = color_map.get(log_type, "#d4d4d4")

        # 插入日誌
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", log_type)

        # 設定標籤顏色
        self.log_text.tag_config("timestamp", foreground="#858585")
        self.log_text.tag_config("info", foreground=color_map["info"])
        self.log_text.tag_config("success", foreground=color_map["success"])
        self.log_text.tag_config("error", foreground=color_map["error"])

        # 自動滾動到底部
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _status_callback(self, message, status_type="info"):
        """
        狀態回調函數，用於更新 UI

        Args:
            message: 狀態訊息
            status_type: 狀態類型
        """
        # 使用 lambda 與 after 確保 UI 更新的動作被推回「主執行緒」執行，避免 Mac 系統崩潰
        self.root.after(0, lambda: self._update_status_label(message))
        self.root.after(0, lambda: self._add_log(message, status_type))

    def _execute_first_stage(self):
        """執行第一階段流程（在背景執行緒中執行）"""
        url = self.url_entry.get().strip()

        if not url:
            self._add_log("Please enter a ticket URL!", "error")
            return

        if not url.startswith(("http://", "https://")):
            self._add_log(
                "Invalid URL format. Please start with http:// or https://", "error")
            return

        if self.is_running:
            self._add_log(
                "Program is already running, please wait...", "error")
            return

        # 更新 UI 狀態
        self.is_running = True
        self.execute_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)

        # 在背景執行緒中執行
        thread = threading.Thread(
            target=self._run_first_stage_thread, args=(url,))
        thread.daemon = True
        thread.start()

    def _run_first_stage_thread(self, url):
        """
        在背景執行緒中執行第一階段

        Args:
            url: 購票網址
        """
        try:
            # 建立 TicketGrabber 實例
            self.grabber = TicketGrabber(
                url, status_callback=self._status_callback)

            # 執行第一階段
            success = self.grabber.run_first_stage()

            if success:
                self._status_callback(
                    "All steps completed successfully!", "success")
            else:
                self._status_callback(
                    "An error occurred during execution, please check the log", "error")

        except Exception as e:
            self._status_callback(f"Execution failed: {str(e)}", "error")
        finally:
            # 恢復 UI 狀態
            self.root.after(0, self._reset_ui_state)

    def _reset_ui_state(self):
        """重置 UI 狀態"""
        self.is_running = False
        self.execute_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.NORMAL)

    def _stop_execution(self):
        """停止執行"""
        if self.grabber and self.grabber.driver:
            try:
                self.grabber.close()
                self._status_callback("Execution stopped", "info")
            except Exception as e:
                self._status_callback(
                    f"Error while stopping: {str(e)}", "error")

        self._reset_ui_state()

    def on_closing(self):
        """視窗關閉時的處理"""
        if self.is_running:
            self._stop_execution()
        if self.grabber and self.grabber.driver:
            try:
                self.grabber.close()
            except:
                pass
        self.root.destroy()


# 主程式
if __name__ == "__main__":
    root = tk.Tk()
    app = TicketGrabberGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
