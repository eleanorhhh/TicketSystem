from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from tkmacosx import Button as MacButton
import time
import tkinter as tk
from tkinter import scrolledtext
import threading
import queue
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

class TicketGrabber:
    def __init__(self, url, status_callback=None):
        self.url = url
        self.status_callback = status_callback
        self.driver = None
        self.wait = None
        self.stop_search = False

    def _update_status(self, message, status_type="info"):
        if self.status_callback:
            self.status_callback(message, status_type)
        print(message)

    def _init_driver(self): 
        if self.driver is None:
            self._update_status("Initializing browser...")
            try:
                service = Service(ChromeDriverManager().install())
                chrome_options = Options()
                chrome_options.page_load_strategy = 'eager'
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.page_load_strategy = 'eager' # 這行是關鍵，讓 Selenium 不必等整個頁面完全載入就開始執行後續動作，大幅提升搶票效率！
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.wait = WebDriverWait(self.driver, 10)
                self._update_status("Browser initialized successfully", "success")
            except Exception as e:
                self._update_status(f"Browser initialization failed: {str(e)}", "error")
                raise

    def open_page(self):
        self._update_status("Opening ticket page...")
        if self.driver is None:
            self._init_driver()
        self.driver.get(self.url)
        self._update_status(f"Page opened: {self.url}", "success")
        #只要開好網站就回傳true ，不需要等什麼按鈕出現，因為我們後面會直接跳過詳情頁
        return True
        
    def wait_for_session_list(self, timeout=1.5):
        try:
            self._update_status("Waiting for session list to load...")
            # ====== 關鍵修正 2：相容練習網站的 CSS ======
            # 官方是 session-list，練習網站是 purchase-section
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".session-list, .purchase-section"))
            )
            self._update_status("Session list loaded", "success")
            return True
        except TimeoutException:
            self._update_status("No session-list found, proceeding...", "info")
            return True 
    
    def click_order_now(self, button_text="立即訂購", button_selector="button.btn-primary, .btn-primary"):
        """3. 專門處理點擊「立即訂購」的 10 秒極速輪詢邏輯"""
        try:
            self._update_status(f"Looking for '{button_text}' button...")
            self.stop_search = False

            start_time = time.perf_counter()
            end_time = time.time() + 10
            
            while time.time() < end_time:
                if self.stop_search:
                    return False
                
                try:
                    # 尋找按鈕
                    try:
                        order_button = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                    except NoSuchElementException:
                        xpath = f"//*[contains(text(), '{button_text}')]"
                        order_button = self.driver.find_element(By.XPATH, xpath)

                    # 嘗試抓取目標網址 (相容兩種寫法)
                    target_url = order_button.get_attribute("data-href")
                    if not target_url:
                        try:
                            parent_a = order_button.find_element(By.XPATH, "./parent::a")
                            target_url = parent_a.get_attribute("href")
                        except NoSuchElementException:
                            pass

                    # 執行跳轉或點擊
                    if target_url:
                        self._update_status(f"Jumping directly to: {target_url}", "success")
                        self.driver.execute_script(f"window.location.href='{target_url}';")
                    else:
                        self.driver.execute_script("arguments[0].click();", order_button)
                        self._update_status(f"Clicked '{button_text}' button via JS", "success")
                    
                    elapsed_time = time.perf_counter() - start_time
                    print(f"[效能測試] 成功觸發 '{button_text}'！耗時: {elapsed_time:.4f} 秒")
                    return True

                except NoSuchElementException:
                    time.sleep(0.05) # 稍微縮短休眠時間，增加輪詢頻率

            self._update_status(f"Timeout: Could not find button '{button_text}'", "error")
            return False
            
        except Exception as e:
            self._update_status(f"Error acting on '{button_text}': {str(e)}", "error")
            return False
        

    def run_first_stage(self):
        """執行第一階段的搶票流程"""
        try:
            # 🚀 終極優化：直接將 /detail/ 替換為 /game/，跳過「立即購票」的渲染與點擊
            if "/activity/detail/" in self.url:
                fast_url = self.url.replace("/activity/detail/", "/activity/game/")
                self.url = fast_url
                self._update_status(f"網址優化！跳過詳情頁，直達場次列表: {fast_url}", "info")

            # 開啟頁面 (此時已經直接在場次列表頁了)
            self.open_page()


            # 直接等待場次列表的 DOM 載入
            if not self.wait_for_session_list():
                return False

            # 接續執行你的搶票邏輯
            if not self.click_order_now():
                return False

            self._update_status("First stage completed!", "success")
            return True

        except Exception as e:
            self._update_status(f"Error during execution: {str(e)}", "error")
            return False
    
    def auto_click_area(self, area_keyword=""):
        """
        自動尋找並點擊指定區域
        """
        try:
            if not area_keyword:
                self._update_status("未設定區域關鍵字，請手動點擊區域", "info")
                return True # 沒有設定關鍵字，直接回傳 True 進入下一階段等待

            self._update_status(f"🎯 正在極速掃描區域: '{area_keyword}'...", "info")
            self.stop_search = False

            start_time = time.perf_counter()
            end_time = time.time() + 5  # 給它 5 秒鐘找區域

            while time.time() < end_time:
                if self.stop_search: return False
                
                try:
                    # 使用 PARTIAL_LINK_TEXT 尋找包含關鍵字的超連結 (最快也最準)
                    try:
                        area_btn = self.driver.find_element(By.PARTIAL_LINK_TEXT, area_keyword)
                    except NoSuchElementException:
                        # 備用方案：用 XPath 找任何包含該文字的可點擊元素
                        xpath = f"//*[contains(text(), '{area_keyword}') and not(contains(@class, 'sold-out'))]"
                        area_btn = self.driver.find_element(By.XPATH, xpath)

                    # 嘗試抓網址直接跳轉
                    target_url = area_btn.get_attribute("href")
                    if target_url and "javascript" not in target_url:
                        self.driver.execute_script(f"window.location.href='{target_url}';")
                    else:
                        # 用 JS 點擊
                        self.driver.execute_script("arguments[0].click();", area_btn)

                    elapsed = time.perf_counter() - start_time
                    self._update_status(f"⚡ 成功狙擊區域 '{area_keyword}'！耗時: {elapsed:.4f} 秒", "success")
                    return True

                except NoSuchElementException:
                    time.sleep(0.05) # 找不到就等 0.05 秒再找一次

            self._update_status(f"⚠️ 找不到區域 '{area_keyword}' (可能已售完)，請手動點選其他區域！", "error")
            return True # 找不到不中斷程式，回傳 True 讓程式繼續監聽 checkbox，等你手動救援

        except Exception as e:
            self._update_status(f"點擊區域發生異常: {str(e)}，請手動點選", "error")
            return True # 發生錯誤一樣不中斷
    
    def auto_fill_checking_page(self, ticket_count="2"):
        """
        自動填寫確認頁面（張數、勾選同意，並綁定 Enter 送出）
        """
        try:
            self._update_status("等待您手動點擊選擇區域...", "info")
            
            # ====== 關鍵修正：更換偵測目標 ======
            # 不要等 select，改為等待「checkbox (同意條款)」出現。
            # 時間我設為 3600 秒，讓你有非常充裕的時間慢慢挑選區域！
            WebDriverWait(self.driver, 3600).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
            )
            
            self._update_status("偵測到驗證碼頁面，正在極速填寫...", "info")
            
            # 為了保險起見，稍微等個 0.1 秒讓 JS 框架完全渲染
            time.sleep(0.1)
            
            # 🚀 使用 JS 進行「降維打擊」
            self.driver.execute_script(f"""
                // 1. 修改張數 
                let selects = document.querySelectorAll('select');
                for(let select of selects) {{
                    // 迴圈找到第一個下拉選單修改後就跳出，避免改到不相干的選項
                    select.value = '{ticket_count}';
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    break; 
                }}

                // 2. 勾選「同意會員服務條款」
                let checkbox = document.querySelector('input[type="checkbox"]');
                if(checkbox && !checkbox.checked) {{
                    checkbox.click();
                }}

                // 3. 尋找驗證碼輸入框並 Focus
                let inputs = document.querySelectorAll('input[type="text"]');
                let captchaInput = null;
                for(let i=0; i<inputs.length; i++) {{
                    if(inputs[i].placeholder.includes('驗證') || inputs[i].className.includes('captcha') || inputs[i].id.includes('verify')) {{
                        captchaInput = inputs[i];
                        break;
                    }}
                }}
                
                // 4. 綁定 Enter 鍵觸發「確認張數」
                if(captchaInput) {{
                    captchaInput.focus(); // 游標自動就位
                    
                    captchaInput.addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') {{
                            e.preventDefault(); // 阻止原本的 Enter 預設行為
                            
                            // 尋找綠色的確認按鈕並點擊
                            let buttons = document.querySelectorAll('button, a.btn');
                            for(let btn of buttons) {{
                                if(btn.innerText.includes('確認張數') || btn.textContent.includes('確認張數')) {{
                                    btn.click();
                                    break;
                                }}
                            }}
                        }}
                    }});
                }}
            """)
            
            self._update_status(f"✅ 已自動選擇 {ticket_count} 張並勾選同意！", "success")
            self._update_status("🔥 請直接在鍵盤輸入驗證碼，打完按 Enter 即可！", "success")
            return True
            
        except Exception as e:
            self._update_status(f"填寫頁面失敗: {str(e)}", "error")
            return False        
        """自動填寫確認頁面（張數、勾選同意，並綁定 Enter 送出）"""
        try:
            self._update_status("等待進入購票確認頁面...", "info")
            
            # 等待下拉選單 <select> 出現，代表頁面已經載入完成
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "select"))
            )
            
            # 🚀 使用 JS 進行「降維打擊」，一次完成所有動作
            self.driver.execute_script(f"""
                // 1. 修改張數
                let select = document.querySelector('select');
                if(select) {{
                    select.value = '{ticket_count}';
                    // 必須觸發 change 事件，前端的 Vue/React 才會知道值改變了
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}

                // 2. 勾選「同意會員服務條款」
                let checkbox = document.querySelector('input[type="checkbox"]');
                if(checkbox && !checkbox.checked) {{
                    checkbox.click();
                }}

                // 3. 尋找驗證碼輸入框並 Focus
                let inputs = document.querySelectorAll('input[type="text"]');
                let captchaInput = null;
                for(let i=0; i<inputs.length; i++) {{
                    if(inputs[i].placeholder.includes('驗證') || inputs[i].className.includes('captcha')) {{
                        captchaInput = inputs[i];
                        break;
                    }}
                }}
                
                // 4. 綁定 Enter 鍵觸發「確認張數」
                if(captchaInput) {{
                    captchaInput.focus(); // 游標自動就位
                    
                    captchaInput.addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') {{
                            e.preventDefault(); // 阻止原本的 Enter 預設行為
                            
                            // 尋找綠色的確認按鈕並點擊
                            let buttons = document.querySelectorAll('button');
                            for(let btn of buttons) {{
                                if(btn.innerText.includes('確認張數') || btn.textContent.includes('確認張數')) {{
                                    btn.click();
                                    break;
                                }}
                            }}
                        }}
                    }});
                }}
            """)
            # ====== 結束計算「自動填寫」耗時 ======
            fill_end_time = time.perf_counter()
            fill_elapsed = fill_end_time - fill_start_time
            self._update_status(f"⚡ 自動填寫完成！純執行耗時: {fill_elapsed:.4f} 秒", "success")
            
            self._update_status(f"✅ 已自動選擇 {ticket_count} 張並勾選同意！", "success")
            self._update_status("🔥 請直接在鍵盤輸入驗證碼，打完按 Enter 即可！", "success")
            return True
            
        except Exception as e:
            self._update_status(f"填寫頁面失敗: {str(e)}", "error")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            self._update_status("Browser closed", "info")


class TicketGrabberGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ticket Grabber")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        self._setup_fonts()
        self.is_running = False
        self.grabber = None
        
        self._create_widgets()
        self.ui_queue = queue.Queue()
        self._process_ui_queue()

    def _process_ui_queue(self):
        try:
            while True:
                func, args = self.ui_queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        self.root.after(100, self._process_ui_queue)

    def _setup_fonts(self):
        self.title_font = ("Microsoft JhengHei", 20, "bold")
        self.default_font = ("Microsoft JhengHei", 12)
        self.small_font = ("Microsoft JhengHei", 10)
        self.log_font = ("Consolas", 10)
        try:
            self.root.option_add("*Font", self.default_font)
        except:
            pass

    def _create_widgets(self):
        title_label = tk.Label(self.root, text="Ticket Grabber", font=self.title_font, pady=10)
        title_label.pack()

        url_frame = tk.Frame(self.root, pady=10)
        url_frame.pack(fill=tk.X, padx=20)
        url_label = tk.Label(url_frame, text="Ticket URL:", font=self.default_font)
        url_label.pack(anchor=tk.W)
        self.url_entry = tk.Entry(url_frame, font=self.default_font)
        self.url_entry.pack(fill=tk.X, pady=5)
        self.url_entry.insert(0, "https://ticket-training.onrender.com/")
        
        # --- 新增：票數設定區塊 ---
        qty_frame = tk.Frame(self.root, pady=5)
        qty_frame.pack(fill=tk.X, padx=20)
        
        qty_label = tk.Label(qty_frame, text="Ticket Quantity (幾張票):", font=self.default_font)
        qty_label.pack(side=tk.LEFT)
        
        self.qty_entry = tk.Entry(qty_frame, font=self.default_font, width=5)
        self.qty_entry.pack(side=tk.LEFT, padx=10)
        self.qty_entry.insert(0, "1") 
        # -------------------------
        
        # --- 新增：區域關鍵字設定區塊 ---
        area_frame = tk.Frame(self.root, pady=5)
        area_frame.pack(fill=tk.X, padx=20)
        
        area_label = tk.Label(area_frame, text="Area Keyword (區域關鍵字，如 '紫2C'):", font=self.default_font)
        area_label.pack(side=tk.LEFT)
        
        self.area_entry = tk.Entry(area_frame, font=self.default_font, width=15)
        self.area_entry.pack(side=tk.LEFT, padx=10)
        self.area_entry.insert(0, "") # 預設留空，留空代表全手動
        # -------------------------

        button_frame = tk.Frame(self.root, pady=10)
        button_frame.pack(fill=tk.X, padx=20)

        self.open_browser_button = MacButton(
            button_frame, text="1. Open Browser (準備)", font=(self.default_font[0], self.default_font[1], "bold"),
            bg="#2196F3", fg="white", activebackground="#0b7dda", disabledbackground="#cccccc",
            padx=15, pady=10, command=self._open_browser_only, borderless=1, cursor="hand2"
        )
        self.open_browser_button.pack(side=tk.LEFT, padx=5)

        self.execute_button = MacButton(
            button_frame, text="2. Start Grabbing (開始搶票)", font=(self.default_font[0], self.default_font[1], "bold"),
            bg="#4CAF50", fg="white", activebackground="#45a049", disabledbackground="#cccccc",
            padx=15, pady=10, command=self._execute_first_stage, borderless=1, cursor="hand2", state=tk.DISABLED
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = MacButton(
            button_frame, text="Stop", font=self.default_font,
            bg="#f44336", fg="white", activebackground="#da190b", disabledbackground="#cccccc",
            padx=15, pady=10, command=self._stop_execution, borderless=1, cursor="hand2", state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        status_frame = tk.Frame(self.root, pady=5)
        status_frame.pack(fill=tk.X, padx=20)
        status_label = tk.Label(status_frame, text="Status:", font=self.default_font)
        status_label.pack(anchor=tk.W)
        self.status_label = tk.Label(status_frame, text="Ready...", font=self.small_font, bg="#f0f0f0", anchor=tk.W, relief=tk.SUNKEN, padx=10, pady=5)
        self.status_label.pack(fill=tk.X, pady=5)

        log_frame = tk.Frame(self.root, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        log_title = tk.Label(log_frame, text="Execution Log:", font=self.default_font)
        log_title.pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(log_frame, font=self.log_font, bg="#1e1e1e", fg="#d4d4d4", wrap=tk.WORD, padx=10, pady=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._add_log("Ready. Please click '1. Open Browser' to prepare.", "info")

    def _update_status_label(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def _add_log(self, message, log_type="info"):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color_map = {"info": "#569cd6", "success": "#4ec9b0", "error": "#f48771"}
        color = color_map.get(log_type, "#d4d4d4")
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", log_type)
        self.log_text.tag_config("timestamp", foreground="#858585")
        self.log_text.tag_config("info", foreground=color_map["info"])
        self.log_text.tag_config("success", foreground=color_map["success"])
        self.log_text.tag_config("error", foreground=color_map["error"])
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _status_callback(self, message, status_type="info"):
        self.ui_queue.put((self._update_status_label, (message,)))
        self.ui_queue.put((self._add_log, (message, status_type)))

    def _set_button_state(self, button, state):
        button.config(state=state)

    def _open_browser_only(self):
        url = self.url_entry.get().strip()
        if not url.startswith(("http://", "https://")):
            self._add_log("Invalid URL format.", "error")
            return
        
        self.open_browser_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=self._open_browser_thread, args=(url,))
        thread.daemon = True
        thread.start()

    def _open_browser_thread(self, url):
        try:
            if self.grabber is None:
                self.grabber = TicketGrabber(url, status_callback=self._status_callback)
            self.grabber.url = url
            self.grabber.open_page()
            self._status_callback("Browser is ready! Please prepare, then click '2. Start Grabbing'.", "success")
            
            self.ui_queue.put((self._set_button_state, (self.execute_button, tk.NORMAL)))
            
        except Exception as e:
            self._status_callback(f"Failed to open browser: {str(e)}", "error")
            self.ui_queue.put((self._set_button_state, (self.open_browser_button, tk.NORMAL)))

    def _execute_first_stage(self):
        if self.is_running: return
        if self.grabber is None or self.grabber.driver is None:
            self._add_log("Please open the browser first!", "error")
            self.open_browser_button.config(state=tk.NORMAL)
            self.execute_button.config(state=tk.DISABLED)
            return

        self.log_text.delete(1.0, tk.END)
        self._add_log("Action triggered! Scanning for buttons instantly...", "info")
        self.is_running = True
        
        self.execute_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._run_first_stage_thread)
        thread.daemon = True
        thread.start()

    def _run_first_stage_thread(self):
        import time # 確保載入計時套件
        try:
            # ====== 啟動「總流程」計時器 ======
            total_start_time = time.perf_counter()
            
            # 確保有抓到張數，預設為 2
            try:
                ticket_qty = self.qty_entry.get().strip()
                if not ticket_qty:
                    ticket_qty = "2"
                area_keyword = self.area_entry.get().strip()
                
            except AttributeError:
                ticket_qty = "2"
                area_keyword = ""
            # 1. 執行第一階段 (跳轉與點擊)
            success = self.grabber.run_first_stage()
            
            if success:
                # 記錄第一階段跳轉的耗時
                stage1_time = time.perf_counter() - total_start_time
                self._status_callback(f"⏱️ 跳過詳情頁並進入選區，耗時: {stage1_time:.4f} 秒", "info")
                
                self.grabber.auto_click_area(area_keyword)
                
                # 2. 啟動自動偵測填寫功能
                fill_success = self.grabber.auto_fill_checking_page(ticket_count=ticket_qty)
                
                if fill_success:
                    # 計算整個腳本從按下按鈕到驗證碼頁面就緒的總時間
                    total_elapsed = time.perf_counter() - total_start_time
                    self._status_callback(f"🎉 流程全部就緒！總共耗時: {total_elapsed:.4f} 秒 (包含您手動選區的時間)", "success")
            else:
                self._status_callback("Execution stopped or error occurred.", "info")
                
        except Exception as e:
            self._status_callback(f"Execution failed: {str(e)}", "error")
        finally:
            self.ui_queue.put((self._reset_ui_state, ()))        

    def _reset_ui_state(self):
        self.is_running = False
        self.url_entry.config(state=tk.NORMAL)
        if self.grabber and self.grabber.driver:
            self.execute_button.config(state=tk.NORMAL)
            self.open_browser_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.execute_button.config(state=tk.DISABLED)
            self.open_browser_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def _stop_execution(self):
        self.is_running = False
        if self.grabber:
            self.grabber.stop_search = True
        self._status_callback("Action stopped. Browser is kept open for next try.", "info")
        self.execute_button.config(state=tk.NORMAL)
        self.open_browser_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)

    def on_closing(self):
        if self.is_running:
            self._stop_execution()
        if self.grabber and self.grabber.driver:
            try:
                self.grabber.close()
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TicketGrabberGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()