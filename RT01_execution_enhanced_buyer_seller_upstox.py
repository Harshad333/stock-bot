"""
ENHANCED BUYER/SELLER DETECTION - UPSTOX VERSION
Converted from Angel One SmartAPI to Upstox API
Logic remains unchanged, only broker integration modified
"""

import datetime
import pandas as pd
import numpy as np
import upstox_client
from upstox_client.rest import ApiException
import time
import os
import requests
import threading
import json
import gzip
import math
import webbrowser
import pyotp
from openpyxl import Workbook, load_workbook
from urllib.parse import urlparse, parse_qs

# Upstox TOTP auto-login package
try:
    from upstox_totp import UpstoxTOTP
    UPSTOX_TOTP_AVAILABLE = True
except ImportError:
    UPSTOX_TOTP_AVAILABLE = False
    print("⚠️ upstox-totp not installed. Run: pip install upstox-totp")

# Selenium imports for fallback auto-login
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class EnhancedBuyerSellerDetectionUpstox:
    def __init__(self):
        # Upstox Credentials
        self.API_KEY = "462f6c2f-010f-43c2-9850-537e9d8db66e"
        self.API_SECRET = "acd00t5bnu"  # UPDATE THIS with correct API Secret
        self.REDIRECT_URI = "https://www.google.com/"
        self.ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBQzY3MjciLCJqdGkiOiI2OTZiYWNiNTNkODJjNDc2OGI2OGNiMzUiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2ODY2NDI0NSwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY4Njg3MjAwfQ.J90FRWH9-VwWxeRJDqGZthxKiKuVwzA96myhULFs0AY"
        
        # ======= AUTO-LOGIN CREDENTIALS (FILL THESE FOR AUTOMATIC LOGIN) =======
        # Option 1: Fill mobile + PIN only → Script will ask for OTP from email/SMS
        # Option 2: Fill mobile + PIN + TOTP_SECRET → Fully automatic, no manual input
        self.UPSTOX_MOBILE = "9921316390"      # Your registered mobile number (e.g., "9876543210")
        self.UPSTOX_PIN = "602633"         # Your 6-digit Upstox PIN (e.g., "123456")
        self.TOTP_SECRET = "N3CPE5KR57VMK7JEYP46JSHQLFGQZ5PA"        # Optional: TOTP Secret for fully automatic login
        # To get TOTP_SECRET: Upstox App → Profile → Settings → Security → 2FA → Show Secret Key
        # =========================================================================
        
        # Token Storage
        self.TOKEN_FILE = "upstox_token.json"
        
        self.api_client = None
        self.session_generated = False
        
        # Detection thresholds (UNCHANGED)
        self.buyer_seller_threshold = 0.35
        self.strong_signal_threshold = 0.55
        self.volume_threshold = 1.5
        self.momentum_threshold = 0.15
        self.buying_pressure_threshold = 0.55
        
        # TRADING SETTINGS (UNCHANGED)
        self.ENABLE_TRADING = True
        self.ORDER_QUANTITY = 75
        self.stop_loss_percent = 10
        self.target_percent = 30
        
        # TRAILING SL SETTINGS (UNCHANGED)
        self.trail_activation_percent = 10
        self.trail_lock_percent = 3
        self.trail_step_percent = 5
        
        # TRACKING
        self.active_positions = {}
        self.active_sl_orders = {}
        self.instrument_df = None
        self.trade_log_file = "RT01_Trade_Log_Upstox.xlsx"
        self.state_file = "RT01_Trade_State_Upstox.json"
        self.rejected_trades_file = "RT01_Rejected_Trades.csv"  # Rejected trades log
        self.current_trade_row = None
        self.fast_contract_map = {}
        self.option_chain_data = None
        
        # LAST TRADE TRACKING (for RSI validation)
        self.last_trade_type = None  # 'CE' or 'PE'
        self.last_trade_close_time = None  # datetime when trade closed
        self.cooling_time_minutes = 5  # 5 minute cooling period
        self.last_trade_state_file = "RT01_Last_Trade_State.json"  # State persistence file
        
        self.connect()
        
        # Auto-refresh token if not connected
        if not self.session_generated:
            print("\n⚠️ Not connected. Starting auto token refresh...")
            self._refresh_token()
        
        if self.session_generated:
            self.display_funds()
            threading.Thread(target=self.download_instrument_master).start()
            self.sync_state_from_broker()
            self.sync_last_trade_from_broker()  # Sync last trade info from broker
    
    def connect(self):
        """Connect to Upstox - Auto-login with TOTP or saved token"""
        try:
            configuration = upstox_client.Configuration()
            
            # Step 1: Try to load saved token from file
            saved_token = self._load_saved_token()
            if saved_token:
                self.ACCESS_TOKEN = saved_token
            
            # Step 2: If no token, try TOTP auto-login
            if not self.ACCESS_TOKEN:
                print("[CONNECT] No token found, attempting TOTP auto-login...")
                if self._auto_login_with_totp():
                    return
                else:
                    print("[CONNECT] TOTP login failed, will try manual refresh...")
                    self.session_generated = False
                    return
            
            # Step 3: Verify token
            configuration.access_token = self.ACCESS_TOKEN
            self.api_client = upstox_client.ApiClient(configuration)
            
            try:
                api_instance = upstox_client.UserApi(self.api_client)
                api_response = api_instance.get_profile(api_version='2.0')
                if api_response and api_response.status == 'success':
                    self.session_generated = True
                    self._save_token(self.ACCESS_TOKEN)  # Save valid token
                    print("[SUCCESS] Enhanced Detection System (UPSTOX) Connected!")
                else:
                    print("[WARN] Token may be invalid. Will try TOTP auto-login...")
                    if self._auto_login_with_totp():
                        return
                    self.session_generated = False
            except Exception as e:
                if "401" in str(e) or "Unauthorized" in str(e):
                    print("[WARN] Token expired (401). Trying TOTP auto-login...")
                    if self._auto_login_with_totp():
                        return
                else:
                    print(f"[WARN] Token verification failed: {e}")
                self.session_generated = False
                
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            self.session_generated = False
    
    def _refresh_token(self):
        """Refresh token flow with auto-save"""
        print("\n" + "="*60)
        print("  🔑 TOKEN REFRESH")
        print("="*60)
        
        auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={self.API_KEY}&redirect_uri={self.REDIRECT_URI}"
        print(f"\n🔗 Opening browser for authorization...")
        print(f"   URL: {auth_url}")
        webbrowser.open(auth_url)
        
        print("\n" + "-"*60)
        print("After login, copy the 'code' from the redirect URL")
        print("-"*60)
        
        code = input("\n🔐 Paste the code: ").strip()
        if not code:
            print("❌ No code provided.")
            return False
        
        print("\n🔄 Exchanging code for access token...")
        
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "code": code,
            "client_id": self.API_KEY,
            "client_secret": self.API_SECRET,
            "redirect_uri": self.REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data)
            result = response.json()
            
            if "access_token" in result:
                self.ACCESS_TOKEN = result["access_token"]
                configuration = upstox_client.Configuration()
                configuration.access_token = self.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(configuration)
                self.session_generated = True
                
                print("\n✅ Token refreshed successfully!")
                print(f"\n🔑 New Token:\n{self.ACCESS_TOKEN}")
                
                # Auto-update token in script file
                self._update_token_in_file(self.ACCESS_TOKEN)
                return True
            else:
                print(f"\n❌ Error: {result}")
                return False
        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return False
    
    def _update_token_in_file(self, new_token):
        """Auto-save new token to this script file"""
        try:
            import re
            script_path = os.path.abspath(__file__)
            
            with open(script_path, 'r') as f:
                content = f.read()
            
            pattern = r'self\.ACCESS_TOKEN\s*=\s*"[^"]*"'
            replacement = f'self.ACCESS_TOKEN = "{new_token}"'
            
            new_content = re.sub(pattern, replacement, content, count=1)
            
            with open(script_path, 'w') as f:
                f.write(new_content)
            
            print(f"\n💾 Token auto-saved to script file!")
        except Exception as e:
            print(f"\n⚠️ Could not auto-save token: {e}")
            print("   Please manually update ACCESS_TOKEN in the script.")

    def _load_saved_token(self):
        """Load saved token from file if valid for today"""
        try:
            if not os.path.exists(self.TOKEN_FILE):
                return None
            
            with open(self.TOKEN_FILE, 'r') as f:
                data = json.load(f)
            
            # Check if token is from today
            saved_date = data.get('date', '')
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            if saved_date == today and data.get('access_token'):
                print(f"[TOKEN] Found saved token from today ({today})")
                return data.get('access_token')
            else:
                print(f"[TOKEN] Saved token is from {saved_date}, need fresh login")
                return None
                
        except Exception as e:
            print(f"[TOKEN] Error loading saved token: {e}")
            return None
    
    def _save_token(self, token):
        """Save token to file with today's date"""
        try:
            data = {
                'date': datetime.datetime.now().strftime('%Y-%m-%d'),
                'access_token': token,
                'saved_at': datetime.datetime.now().isoformat()
            }
            with open(self.TOKEN_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[TOKEN] Saved to {self.TOKEN_FILE}")
        except Exception as e:
            print(f"[TOKEN] Error saving token: {e}")
    
    def _auto_login_with_totp(self):
        """
        Automatic login using upstox-totp package
        This is the recommended approach for fully automatic login
        Falls back to Selenium if package login fails
        """
        print("\n" + "="*60)
        print("  🤖 AUTO-LOGIN (upstox-totp)")
        print("="*60)
        
        # Method 1: Try upstox-totp package (recommended)
        if UPSTOX_TOTP_AVAILABLE and self.UPSTOX_MOBILE and self.UPSTOX_PIN and self.TOTP_SECRET:
            try:
                print("[LOGIN] Using upstox-totp package...")
                
                # Set environment variables for upstox-totp (using correct var names)
                os.environ['UPSTOX_USERNAME'] = self.UPSTOX_MOBILE
                os.environ['UPSTOX_PASSWORD'] = self.UPSTOX_PIN  # Password is PIN for Upstox
                os.environ['UPSTOX_PIN_CODE'] = self.UPSTOX_PIN
                os.environ['UPSTOX_TOTP_SECRET'] = self.TOTP_SECRET
                os.environ['UPSTOX_CLIENT_ID'] = self.API_KEY
                os.environ['UPSTOX_CLIENT_SECRET'] = self.API_SECRET
                os.environ['UPSTOX_REDIRECT_URI'] = self.REDIRECT_URI
                os.environ['UPSTOX_DEBUG'] = 'false'
                
                # Initialize upstox-totp client
                upx = UpstoxTOTP()
                
                # Generate access token
                print("[LOGIN] Generating access token...")
                response = upx.app_token.get_access_token()
                
                if response.success and response.data:
                    self.ACCESS_TOKEN = response.data.access_token
                    configuration = upstox_client.Configuration()
                    configuration.access_token = self.ACCESS_TOKEN
                    self.api_client = upstox_client.ApiClient(configuration)
                    self.session_generated = True
                    
                    print(f"\n✅ Auto-login successful!")
                    print(f"   User: {response.data.user_name} ({response.data.user_id})")
                    if hasattr(response.data, 'email'):
                        print(f"   Email: {response.data.email}")
                    
                    self._save_token(self.ACCESS_TOKEN)
                    self._update_token_in_file(self.ACCESS_TOKEN)
                    return True
                else:
                    print(f"[LOGIN] upstox-totp failed: {response}")
                    
            except Exception as e:
                print(f"[LOGIN] upstox-totp error: {e}")
                import traceback
                traceback.print_exc()
        
        # Method 2: Fallback to Selenium browser automation
        print("\n[LOGIN] Falling back to Selenium browser automation...")
        return self._selenium_auto_login()
    
    def _selenium_auto_login(self):
        """
        Fallback: Selenium-based browser automation for Upstox login
        Upstox Login Flow: Mobile → OTP/TOTP → PIN
        """
        if not SELENIUM_AVAILABLE:
            print("\n❌ Selenium not installed!")
            print("   Run: pip install selenium")
            return False
        
        if not self.UPSTOX_MOBILE or not self.UPSTOX_PIN:
            print("\n❌ Login credentials not configured!")
            print("   Please fill these in the script:")
            print("   - UPSTOX_MOBILE: Your registered mobile number")
            print("   - UPSTOX_PIN: Your 6-digit PIN")
            print("   - TOTP_SECRET: TOTP secret from Upstox app")
            return False
        
        driver = None
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1280,800")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            print("[LOGIN] Starting Chrome browser...")
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            wait = WebDriverWait(driver, 30)
            
            # Navigate to authorization URL
            auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={self.API_KEY}&redirect_uri={self.REDIRECT_URI}"
            print(f"[LOGIN] Opening authorization URL...")
            driver.get(auth_url)
            time.sleep(2)
            
            # Enter mobile number
            print(f"[LOGIN] Entering mobile number: {self.UPSTOX_MOBILE[:4]}****")
            mobile_input = wait.until(EC.presence_of_element_located((By.ID, "mobileNum")))
            mobile_input.clear()
            mobile_input.send_keys(self.UPSTOX_MOBILE)
            time.sleep(0.5)
            
            get_otp_btn = wait.until(EC.element_to_be_clickable((By.ID, "getOtp")))
            get_otp_btn.click()
            print("[LOGIN] OTP requested...")
            time.sleep(3)
            
            # Enter OTP (TOTP or manual)
            if self.TOTP_SECRET:
                print("[LOGIN] Generating TOTP code...")
                totp = pyotp.TOTP(self.TOTP_SECRET)
                otp_code = totp.now()
                print(f"[LOGIN] TOTP code: {otp_code}")
            else:
                print("\n" + "-"*50)
                print("📱 CHECK YOUR EMAIL/SMS FOR OTP")
                print("-"*50)
                otp_code = input("Enter OTP: ").strip()
                if not otp_code:
                    print("❌ No OTP provided")
                    driver.quit()
                    return False
            
            otp_input = wait.until(EC.presence_of_element_located((By.ID, "otpNum")))
            otp_input.clear()
            otp_input.send_keys(otp_code)
            time.sleep(0.5)
            
            continue_btn = wait.until(EC.element_to_be_clickable((By.ID, "continueBtn")))
            continue_btn.click()
            print("[LOGIN] OTP submitted...")
            time.sleep(3)
            
            # Enter PIN
            print(f"[LOGIN] Entering PIN...")
            pin_input = wait.until(EC.presence_of_element_located((By.ID, "pinCode")))
            pin_input.clear()
            pin_input.send_keys(self.UPSTOX_PIN)
            time.sleep(0.5)
            
            login_btn = wait.until(EC.element_to_be_clickable((By.ID, "pinContinueBtn")))
            login_btn.click()
            print("[LOGIN] PIN submitted...")
            time.sleep(3)
            
            # Wait for redirect and capture authorization code
            print("[LOGIN] Waiting for authorization redirect...")
            max_wait = 30
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                current_url = driver.current_url
                
                if self.REDIRECT_URI.split("?")[0] in current_url and "code=" in current_url:
                    parsed = urlparse(current_url)
                    params = parse_qs(parsed.query)
                    
                    if 'code' in params:
                        auth_code = params['code'][0]
                        print(f"[LOGIN] Got authorization code: {auth_code[:20]}...")
                        driver.quit()
                        return self._exchange_code_for_token(auth_code)
                
                if "#code=" in current_url:
                    code = current_url.split("#code=")[1].split("&")[0]
                    print(f"[LOGIN] Got authorization code: {code[:20]}...")
                    driver.quit()
                    return self._exchange_code_for_token(code)
                
                time.sleep(1)
            
            print(f"[LOGIN] Timeout. Current URL: {driver.current_url}")
            driver.quit()
            return False
            
        except Exception as e:
            print(f"\n❌ Selenium login error: {e}")
            if driver:
                driver.quit()
            return False
    
    def _exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        print("[TOKEN] Exchanging code for access token...")
        
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "code": code,
            "client_id": self.API_KEY,
            "client_secret": self.API_SECRET,
            "redirect_uri": self.REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data)
            result = response.json()
            
            if "access_token" in result:
                self.ACCESS_TOKEN = result["access_token"]
                configuration = upstox_client.Configuration()
                configuration.access_token = self.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(configuration)
                self.session_generated = True
                
                print("\n✅ Auto-login successful!")
                self._save_token(self.ACCESS_TOKEN)
                return True
            else:
                print(f"\n❌ Token exchange failed: {result}")
                return False
        except Exception as e:
            print(f"\n❌ Token exchange error: {e}")
            return False


    def display_funds(self):
        """Fetch and display account balance - UPSTOX VERSION"""
        try:
            api_instance = upstox_client.UserApi(self.api_client)
            api_response = api_instance.get_user_fund_margin(api_version='2.0', segment='SEC')
            
            if api_response and api_response.status == 'success':
                funds_data = api_response.data
                
                if isinstance(funds_data, dict):
                    equity_funds = funds_data.get('equity', {})
                else:
                    equity_funds = getattr(funds_data, 'equity', None)
                
                if equity_funds:
                    if isinstance(equity_funds, dict):
                        available_margin = equity_funds.get('available_margin', 0)
                        used_margin = equity_funds.get('used_margin', 0)
                    else:
                        available_margin = getattr(equity_funds, 'available_margin', 0)
                        used_margin = getattr(equity_funds, 'used_margin', 0)
                else:
                    available_margin = 0
                    used_margin = 0
                
                print(f"\n[ACCOUNT BALANCE - UPSTOX]")
                print("=" * 30)
                print(f"Available Margin: Rs.{available_margin:,.2f}")
                print(f"Used Margin:      Rs.{used_margin:,.2f}")
                print("=" * 30)
            else:
                print("[WARN] Could not fetch account balance")
                
        except Exception as e:
            print(f"[ERROR] Fund fetch failed: {e}")
    
    def sync_state_from_broker(self):
        """Reconstruct state from Broker - UPSTOX VERSION"""
        try:
            print("\n[SYNC] Checking Open Positions from Upstox...")
            
            api_instance = upstox_client.PortfolioApi(self.api_client)
            pos_response = api_instance.get_positions(api_version='2.0')
            
            if not pos_response or pos_response.status != 'success':
                print("[SYNC] No position data available")
                return
            
            positions_data = pos_response.data if pos_response.data else []
            open_positions = [p for p in positions_data if int(getattr(p, 'quantity', 0)) != 0]
            
            if not open_positions:
                print("[SYNC] No open positions found.")
                return
            
            # Fetch Order Book for SL orders
            order_api = upstox_client.OrderApi(self.api_client)
            order_book_resp = order_api.get_order_book(api_version='2.0')
            pending_sl_orders = {}
            
            if order_book_resp and order_book_resp.status == 'success':
                for order in (order_book_resp.data or []):
                    status = getattr(order, 'status', '')
                    order_type = getattr(order, 'order_type', '')
                    if 'trigger pending' in status.lower() and 'SL' in order_type.upper():
                        token = getattr(order, 'instrument_token', '')
                        pending_sl_orders[token] = {
                            'id': getattr(order, 'order_id', ''),
                            'trigger_price': float(getattr(order, 'trigger_price', 0))
                        }
            
            print(f"[SYNC] Found {len(open_positions)} Open Positions. Restoring state...")
            
            for pos in open_positions:
                token = getattr(pos, 'instrument_token', '')
                symbol = getattr(pos, 'trading_symbol', '')
                net_qty = int(getattr(pos, 'quantity', 0))
                entry_price = float(getattr(pos, 'average_price', 0))
                
                current_sl_price = 0
                sl_order_id = None
                
                if token in pending_sl_orders:
                    sl_data = pending_sl_orders[token]
                    current_sl_price = sl_data['trigger_price']
                    sl_order_id = sl_data['id']
                    main_order_id = f"SYNC_{token}"
                    self.active_sl_orders[main_order_id] = sl_order_id
                    print(f"   + Linked Broker SL Order: {sl_order_id} @ {current_sl_price}")
                else:
                    current_sl_price = entry_price * (1 - self.stop_loss_percent/100)
                    print(f"   ! No Broker SL found. Using Virtual SL: {current_sl_price}")
                
                main_order_id = f"SYNC_{token}"
                
                self.active_positions[main_order_id] = {
                    'symbol': symbol,
                    'token': token,
                    'entry_time': datetime.datetime.now(),
                    'quantity': net_qty,
                    'entry_price': entry_price,
                    'sl_price': current_sl_price,
                    'target_price': entry_price * (1 + self.target_percent/100),
                    'target_stage': 0,
                    'highest_price': entry_price,
                    'trail_active': False
                }
                
                print(f"   => Resumed Trade: {symbol} | Entry: {entry_price} | Qty: {net_qty}")
                
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    def sync_last_trade_from_broker(self):
        """
        Sync last trade info from broker's trade history (today only)
        This ensures RSI validation works correctly even after script restart
        """
        try:
            today = datetime.datetime.now().date()
            print(f"\n[LAST TRADE SYNC] Fetching today's trade history from Upstox...")
            
            # First, try to load from saved state file
            if self._load_last_trade_state():
                print("[LAST TRADE SYNC] Loaded from saved state file")
                return
            
            # Fetch trade history from broker
            api_instance = upstox_client.OrderApi(self.api_client)
            trade_response = api_instance.get_trade_history(api_version='2.0')
            
            if not trade_response or trade_response.status != 'success':
                print("[LAST TRADE SYNC] No trade history available from broker")
                return
            
            trades_data = trade_response.data if trade_response.data else []
            
            if not trades_data:
                print("[LAST TRADE SYNC] No trades found for today")
                return
            
            # Filter NIFTY option trades (CE/PE) that are SELL (exit trades)
            nifty_exit_trades = []
            for trade in trades_data:
                trading_symbol = getattr(trade, 'trading_symbol', '')
                transaction_type = getattr(trade, 'transaction_type', '')
                trade_time_str = getattr(trade, 'order_timestamp', '') or getattr(trade, 'exchange_timestamp', '')
                
                # Check if it's a NIFTY option and SELL transaction (exit)
                if 'NIFTY' in trading_symbol and transaction_type == 'SELL':
                    if 'CE' in trading_symbol or 'PE' in trading_symbol:
                        try:
                            # Parse trade time
                            if trade_time_str:
                                if isinstance(trade_time_str, str):
                                    trade_time = datetime.datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
                                else:
                                    trade_time = trade_time_str
                                
                                # Check if it's today's trade
                                if trade_time.date() == today:
                                    trade_type = 'CE' if 'CE' in trading_symbol else 'PE'
                                    nifty_exit_trades.append({
                                        'symbol': trading_symbol,
                                        'type': trade_type,
                                        'time': trade_time,
                                        'price': float(getattr(trade, 'average_price', 0))
                                    })
                        except Exception as e:
                            print(f"[LAST TRADE SYNC] Error parsing trade: {e}")
                            continue
            
            if not nifty_exit_trades:
                print("[LAST TRADE SYNC] No NIFTY option exit trades found for today")
                return
            
            # Sort by time descending to get the most recent trade
            nifty_exit_trades.sort(key=lambda x: x['time'], reverse=True)
            last_trade = nifty_exit_trades[0]
            
            # Set the last trade info
            self.last_trade_type = last_trade['type']
            self.last_trade_close_time = last_trade['time']
            
            # Remove timezone info for local comparison
            if self.last_trade_close_time.tzinfo is not None:
                self.last_trade_close_time = self.last_trade_close_time.replace(tzinfo=None)
            
            print(f"[LAST TRADE SYNC] ✅ Found last trade from broker:")
            print(f"   Type: {self.last_trade_type}")
            print(f"   Symbol: {last_trade['symbol']}")
            print(f"   Time: {self.last_trade_close_time.strftime('%H:%M:%S')}")
            print(f"   Price: ₹{last_trade['price']:.2f}")
            
            # Save state to file
            self._save_last_trade_state()
            
        except Exception as e:
            print(f"[LAST TRADE SYNC ERROR] {e}")
            print("[LAST TRADE SYNC] Will start fresh without last trade info")

    def _save_last_trade_state(self):
        """Save last trade state to file for persistence"""
        try:
            today = datetime.datetime.now().date().isoformat()
            state = {
                'date': today,
                'last_trade_type': self.last_trade_type,
                'last_trade_close_time': self.last_trade_close_time.isoformat() if self.last_trade_close_time else None
            }
            
            with open(self.last_trade_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"[STATE SAVED] Last trade state saved to {self.last_trade_state_file}")
            
        except Exception as e:
            print(f"[STATE SAVE ERROR] {e}")

    def _load_last_trade_state(self):
        """Load last trade state from file (only if same day)"""
        try:
            if not os.path.exists(self.last_trade_state_file):
                return False
            
            with open(self.last_trade_state_file, 'r') as f:
                state = json.load(f)
            
            # Check if state is from today
            today = datetime.datetime.now().date().isoformat()
            if state.get('date') != today:
                print(f"[STATE LOAD] State is from {state.get('date')}, not today. Starting fresh.")
                # Delete old state file
                os.remove(self.last_trade_state_file)
                return False
            
            # Load state
            self.last_trade_type = state.get('last_trade_type')
            close_time_str = state.get('last_trade_close_time')
            if close_time_str:
                self.last_trade_close_time = datetime.datetime.fromisoformat(close_time_str)
            
            if self.last_trade_type:
                print(f"[STATE LOADED] Last Trade: {self.last_trade_type} at {self.last_trade_close_time.strftime('%H:%M:%S') if self.last_trade_close_time else 'N/A'}")
                return True
            
            return False
            
        except Exception as e:
            print(f"[STATE LOAD ERROR] {e}")
            return False

    def get_tick_data(self):
        """Get real-time tick data - UPSTOX VERSION (Intraday API)"""
        try:
            # Upstox Intraday Candle API (works for live market)
            instrument_key = "NSE_INDEX|Nifty 50"
            interval = "1minute"
            
            # Use intraday endpoint for current day's live data
            url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/{interval}"
            headers = {
                "Authorization": f"Bearer {self.ACCESS_TOKEN}",
                "Accept": "application/json"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and data.get('data', {}).get('candles'):
                    candles = data['data']['candles']
                    # Upstox: [timestamp, open, high, low, close, volume, oi]
                    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    df = df.sort_values('timestamp').reset_index(drop=True)
                    
                    # Take last 30 candles for analysis
                    if len(df) > 30:
                        df = df.tail(30).reset_index(drop=True)
                    
                    return df.dropna()
            
            return None
        except Exception as e:
            print(f"[ERROR] Tick data failed: {e}")
            return None

    def download_instrument_master(self):
        """Download instrument master - UPSTOX VERSION"""
        try:
            print("[INFO] Downloading Upstox instrument master...")
            fo_file = "NSE_FO_upstox.json"
            
            # Try to use cached file first
            if os.path.exists(fo_file) and (datetime.datetime.now().timestamp() - os.path.getmtime(fo_file) < 86400):
                print("[INFO] Using cached Instrument Master")
                with open(fo_file, 'r') as f:
                    data = json.load(f)
                self.instrument_df = pd.DataFrame(data)
                print(f"[SUCCESS] {len(self.instrument_df)} instruments loaded from cache")
                self._build_contract_cache()
                return True
            
            # Try multiple URLs (Upstox sometimes changes these)
            urls_to_try = [
                "https://assets.upstox.com/market-quote/instruments/exchange/NSE_FO.json.gz",
                "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz",
                "https://api.upstox.com/v2/market/instruments/exchange/NSE_FO"
            ]
            
            data = None
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Authorization': f'Bearer {self.ACCESS_TOKEN}'
            }
            
            for url in urls_to_try:
                try:
                    print(f"[INFO] Trying: {url[:50]}...")
                    r = requests.get(url, headers=headers, timeout=30)
                    if r.status_code == 200:
                        if url.endswith('.gz'):
                            data = json.loads(gzip.decompress(r.content))
                        else:
                            data = r.json()
                            if 'data' in data:
                                data = data['data']
                        print(f"[SUCCESS] Downloaded from {url[:50]}...")
                        break
                except Exception as e:
                    print(f"[WARN] Failed: {e}")
                    continue
            
            if data is None:
                print("[ERROR] All download attempts failed.")
                print("[INFO] Creating minimal contract map from option chain...")
                self._fetch_contracts_from_option_chain()
                return True
            
            with open(fo_file, 'w') as f:
                json.dump(data, f)
            
            self.instrument_df = pd.DataFrame(data)
            print(f"[SUCCESS] {len(self.instrument_df)} instruments loaded")
            self._build_contract_cache()
            return True
            
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
            self._fetch_contracts_from_option_chain()
            return True
    
    def _fetch_contracts_from_option_chain(self):
        """Fallback: Fetch contracts from option chain API"""
        try:
            print("[INFO] Fetching NIFTY option chain for contracts...")
            
            # Get NIFTY LTP first
            api_instance = upstox_client.MarketQuoteApi(self.api_client)
            nifty_key = "NSE_INDEX|Nifty 50"
            ltp_response = api_instance.ltp(nifty_key, api_version='2.0')
            
            nifty_ltp = 24000  # Default
            if ltp_response and ltp_response.status == 'success':
                data = ltp_response.data
                if nifty_key in data:
                    nifty_ltp = float(getattr(data[nifty_key], 'last_price', 24000))
            
            print(f"[INFO] NIFTY LTP: {nifty_ltp}")
            
            # Generate strikes around ATM
            atm = round(nifty_ltp / 50) * 50
            strikes = [atm + (i * 50) for i in range(-10, 11)]  # 21 strikes
            
            # Get nearest Thursday expiry
            today = datetime.datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and today.hour >= 15:
                days_until_thursday = 7
            expiry_date = today + datetime.timedelta(days=days_until_thursday)
            expiry_str = expiry_date.strftime("%Y-%m-%d")
            
            print(f"[INFO] Expiry: {expiry_str}")
            
            # Build contract map with expected token format
            for strike in strikes:
                for otype in ['CE', 'PE']:
                    # Upstox token format for NIFTY options
                    # Example: NFO_OPT|NIFTY24DEC25100CE
                    expiry_code = expiry_date.strftime("%d%b%y").upper()
                    symbol = f"NIFTY{expiry_code}{strike}{otype}"
                    token = f"NSE_FO|{symbol}"
                    
                    self.fast_contract_map[(strike, otype)] = {
                        'symbol': symbol,
                        'token': token,
                        'expiry': expiry_str
                    }
            
            print(f"[CACHE] Built {len(self.fast_contract_map)} contracts from option chain")
            
        except Exception as e:
            print(f"[ERROR] Option chain fetch failed: {e}")
    
    def _build_contract_cache(self):
        """Build fast contract cache from instrument DataFrame"""
        try:
            if self.instrument_df is None or self.instrument_df.empty:
                return
            
            print(f"[INFO] Building Fast Contract Map...")
            
            # Filter for NSE_FO NIFTY options
            filtered = self.instrument_df[
                (self.instrument_df['segment'] == 'NSE_FO') &
                (self.instrument_df['underlying_symbol'] == 'NIFTY') &
                (self.instrument_df['instrument_type'].isin(['CE', 'PE']))
            ].copy()
            
            if filtered.empty:
                print("[WARN] No NIFTY options found in instrument master")
                self._fetch_contracts_from_option_chain()
                return
            
            print(f"[INFO] Found {len(filtered)} NIFTY options")
            
            # Parse expiry timestamps (Upstox uses milliseconds)
            filtered['expiry_dt'] = pd.to_datetime(filtered['expiry'], unit='ms', errors='coerce')
            today = datetime.datetime.now()
            future_opts = filtered[filtered['expiry_dt'] >= today]
            
            if future_opts.empty:
                print("[WARN] No future expiry options found")
                self._fetch_contracts_from_option_chain()
                return
            
            min_expiry = future_opts['expiry_dt'].min()
            nearest_opts = future_opts[future_opts['expiry_dt'] == min_expiry]
            
            print(f"[INFO] Nearest expiry: {min_expiry.strftime('%Y-%m-%d')}")
            
            for _, row in nearest_opts.iterrows():
                try:
                    strike = int(float(row.get('strike_price', 0)))
                    if strike == 0:
                        continue
                    tsym = str(row.get('trading_symbol', ''))
                    otype = str(row.get('instrument_type', ''))
                    
                    if otype not in ['CE', 'PE']:
                        continue
                    
                    self.fast_contract_map[(strike, otype)] = {
                        'symbol': tsym,
                        'token': str(row.get('instrument_key', '')),
                        'expiry': min_expiry.strftime('%Y-%m-%d')
                    }
                except:
                    continue
            
            print(f"[CACHE] Indexed {len(self.fast_contract_map)} contracts for nearest expiry")
            
        except Exception as e:
            print(f"[ERROR] Cache build failed: {e}")
            self._fetch_contracts_from_option_chain()

    def find_option_contract(self, strike, option_type):
        """Find option contract - UPSTOX VERSION"""
        try:
            # Fast lookup
            if (strike, option_type) in self.fast_contract_map:
                return self.fast_contract_map[(strike, option_type)]
            
            if self.instrument_df is None:
                print("[WARN] Instrument master not loaded")
                return None
            
            # Slow search
            filtered = self.instrument_df[
                (self.instrument_df['instrument_type'] == 'OPTIDX') &
                (self.instrument_df['name'] == 'NIFTY') &
                (self.instrument_df['strike_price'] == strike) &
                (self.instrument_df['trading_symbol'].str.contains(option_type, na=False))
            ].copy()
            
            if filtered.empty:
                return None
            
            filtered['expiry_dt'] = pd.to_datetime(filtered['expiry'], format='%Y-%m-%d', errors='coerce')
            today = datetime.datetime.now().date()
            filtered = filtered[filtered['expiry_dt'].dt.date >= today]
            
            if filtered.empty:
                return None
            
            filtered = filtered.sort_values('expiry_dt')
            option_row = filtered.iloc[0]
            
            return {
                'symbol': option_row['trading_symbol'],
                'token': option_row['instrument_key'],
                'strike': strike,
                'expiry': option_row['expiry']
            }
            
        except Exception as e:
            print(f"[ERROR] Contract search failed: {e}")
            return None

    def get_option_ltp(self, symbol, token=""):
        """Get option LTP - UPSTOX VERSION"""
        try:
            if not token:
                # Find token from symbol
                for key, val in self.fast_contract_map.items():
                    if val['symbol'] == symbol:
                        token = val['token']
                        break
            
            if not token:
                return None
            
            api_instance = upstox_client.MarketQuoteApi(self.api_client)
            api_response = api_instance.ltp(token, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                data = api_response.data
                if token in data:
                    return float(getattr(data[token], 'last_price', 0))
                alt_key = token.replace('|', ':')
                if alt_key in data:
                    return float(getattr(data[alt_key], 'last_price', 0))
                if data:
                    return float(getattr(list(data.values())[0], 'last_price', 0))
            return None
        except Exception as e:
            print(f"[ERROR] LTP failed: {e}")
            return None

    def round_to_tick(self, price, tick_size=0.05):
        """Round price to nearest tick size"""
        return round(price / tick_size) * tick_size

    def place_order(self, symbol, token, quantity, order_type="BUY", entry_price=None):
        """Place Normal Order - UPSTOX VERSION"""
        try:
            if not self.ENABLE_TRADING:
                print("[PAPER] Order simulated")
                return "SIM_" + str(int(time.time()))
            
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product='I',  # Intraday
                validity='DAY',
                price=0.0,
                instrument_token=token,
                order_type='MARKET',
                transaction_type=order_type,
                disclosed_quantity=0,
                trigger_price=0.0,
                is_amo=False
            )
            
            print(f"[ORDER] {symbol} x {quantity}")
            print(f"  Type: {order_type} MARKET")
            
            api_response = api_instance.place_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                order_id = api_response.data.order_id
                print(f"[SUCCESS] Order ID: {order_id}")
                return order_id
            
            print(f"[ORDER FAILED] {api_response}")
            return None
                
        except Exception as e:
            print(f"[ORDER ERROR] {e}")
            return None

    def place_sl_order(self, main_order_id, sl_price):
        """Place stop loss order - UPSTOX VERSION"""
        if not self.ENABLE_TRADING:
            return "SIM_SL_" + main_order_id
            
        try:
            position = self.active_positions[main_order_id]
            symbol = position['symbol']
            token = position.get('token', '')
            quantity = position['quantity']
            
            sl_price = self.round_to_tick(sl_price)
            trigger_price = self.round_to_tick(sl_price + 0.05)
            
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product='I',
                validity='DAY',
                price=float(sl_price),
                trigger_price=float(trigger_price),
                instrument_token=token,
                order_type='SL',
                transaction_type='SELL',
                disclosed_quantity=0,
                is_amo=False
            )
            
            print(f"[SL ORDER] Placing SL at Rs.{sl_price:.2f} (Trig: Rs.{trigger_price:.2f})")
            api_response = api_instance.place_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                sl_order_id = api_response.data.order_id
                self.active_sl_orders[main_order_id] = sl_order_id
                print(f"[SL SUCCESS] Order ID: {sl_order_id}")
                return sl_order_id
            
            print(f"[SL ERROR] {api_response}")
            return None
            
        except Exception as e:
            print(f"[SL ERROR] {e}")
            return None

    def modify_sl_order(self, sl_order_id, new_sl_price, symbol):
        """Modify SL order - UPSTOX VERSION"""
        if not self.ENABLE_TRADING:
            print(f"[PAPER] SL Modified to {new_sl_price}")
            return True
            
        try:
            new_sl_price = self.round_to_tick(new_sl_price)
            trigger_price = self.round_to_tick(new_sl_price + 0.05)
            
            quantity = 0
            for oid, pos in self.active_positions.items():
                if str(self.active_sl_orders.get(oid)) == str(sl_order_id):
                    quantity = pos['quantity']
                    break
            
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.ModifyOrderRequest(
                quantity=quantity,
                order_id=sl_order_id,
                order_type='SL',
                price=float(new_sl_price),
                trigger_price=float(trigger_price),
                validity='DAY',
                disclosed_quantity=0
            )
            
            print(f"[SL MODIFY] Price: {new_sl_price} | Trigger: {trigger_price}")
            api_response = api_instance.modify_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                return True
            
            print(f"[SL MODIFY REJECTED] {api_response}")
            return False
            
        except Exception as e:
            print(f"[SL MODIFY ERROR] {e}")
            return False

    def exit_position(self, order_id, reason):
        """Exit position - UPSTOX VERSION"""
        try:
            position = self.active_positions[order_id]
            symbol = position['symbol']
            token = position.get('token', '')
            quantity = position['quantity']
            
            print(f"[EXITING] {symbol} Reason: {reason}")
            
            if self.ENABLE_TRADING and reason != "MANUAL_EXIT_BROKER":
                api_instance = upstox_client.OrderApi(self.api_client)
                
                body = upstox_client.PlaceOrderRequest(
                    quantity=quantity,
                    product='I',
                    validity='DAY',
                    price=0.0,
                    instrument_token=token,
                    order_type='MARKET',
                    transaction_type='SELL',
                    disclosed_quantity=0,
                    trigger_price=0.0,
                    is_amo=False
                )
                api_instance.place_order(body, api_version='2.0')
            
            exit_ltp = self.get_option_ltp(symbol, token) or position['entry_price']
            pnl = (exit_ltp - position['entry_price']) * quantity
            
            print(f"[POSITION CLOSED] {reason}")
            print(f"   Exit Price: ₹{exit_ltp:.1f}")
            print(f"   Final P&L: ₹{pnl:+.0f}")
            
            self.finalize_trade_log(order_id, exit_ltp, reason, pnl)
            
            # Update last trade tracking (extract CE/PE from symbol)
            trade_type = 'CE' if 'CE' in symbol else 'PE'
            self.update_last_trade(trade_type)
            
            del self.active_positions[order_id]
            
            # Cancel SL order
            if order_id in self.active_sl_orders and self.ENABLE_TRADING:
                try:
                    sl_order_id = self.active_sl_orders[order_id]
                    api_instance = upstox_client.OrderApi(self.api_client)
                    api_instance.cancel_order(sl_order_id, api_version='2.0')
                    print(f"[SL CANCELLED] Order ID: {sl_order_id}")
                except Exception as e:
                    print(f"[SL CANCEL WARN] {e}")
                del self.active_sl_orders[order_id]
            
            self.save_state()
                    
        except Exception as e:
            print(f"[EXIT ERROR] {e}")

    # =========================================================================
    # ALL DETECTION LOGIC METHODS - UNCHANGED FROM ORIGINAL
    # =========================================================================
    
    def enhanced_buyer_seller_analysis_sensitive(self, df):
        """SENSITIVE analysis with much lower thresholds"""
        if df is None or len(df) < 5:
            return None
        
        df = self.calculate_enhanced_indicators(df)
        latest = df.iloc[-1]
        
        immediate_momentum = self.check_immediate_momentum(df)
        
        methods = {
            'immediate_momentum': immediate_momentum,
            'volume_price_trend': self.detect_volume_price_trend_sensitive(df),
            'candle_body_analysis': self.detect_candle_body_pressure_sensitive(df),
            'momentum_divergence': self.detect_momentum_divergence_sensitive(df),
            'support_resistance': self.detect_sr_pressure_sensitive(df),
            'price_velocity': self.detect_price_velocity(df),
            'movement_diversion': self.detect_movement_diversion(df),
            'operator_activity': self.detect_operator_activity(df),
            'consolidation': self.detect_consolidation(df),
            'trend_strength': self.detect_trend_strength(df)
        }
        
        buyer_score = 0
        seller_score = 0
        
        current_peak = latest.get('is_peak', False)
        current_trough = latest.get('is_trough', False)
        
        peak_penalty = 0.3 if current_peak else 0
        trough_penalty = 0.3 if current_trough else 0
        
        im = methods['immediate_momentum']
        if im['direction'] == 'BUYERS':
            buyer_score += im['confidence'] * 0.30 * (1 - peak_penalty)
        elif im['direction'] == 'SELLERS':
            seller_score += im['confidence'] * 0.30 * (1 - trough_penalty)
        
        vpt = methods['volume_price_trend']
        if vpt['direction'] == 'BUYERS':
            buyer_score += vpt['confidence'] * 0.15
        elif vpt['direction'] == 'SELLERS':
            seller_score += vpt['confidence'] * 0.15
        
        op_act = methods['operator_activity']
        if op_act['direction'] == 'BUYERS':
            buyer_score += op_act['confidence'] * 0.15
        elif op_act['direction'] == 'SELLERS':
            seller_score += op_act['confidence'] * 0.15
        
        pv = methods['price_velocity']
        if pv['direction'] == 'BUYERS':
            buyer_score += pv['confidence'] * 0.15
        elif pv['direction'] == 'SELLERS':
            seller_score += pv['confidence'] * 0.15
        
        cba = methods['candle_body_analysis']
        if cba['direction'] == 'BUYERS':
            buyer_score += cba['confidence'] * 0.10
        elif cba['direction'] == 'SELLERS':
            seller_score += cba['confidence'] * 0.10
        
        md_div = methods['movement_diversion']
        if md_div['direction'] == 'BUYERS':
            buyer_score += md_div['confidence'] * 0.08
        elif md_div['direction'] == 'SELLERS':
            seller_score += md_div['confidence'] * 0.08
        
        md = methods['momentum_divergence']
        if md['direction'] == 'BUYERS':
            buyer_score += md['confidence'] * 0.05
        elif md['direction'] == 'SELLERS':
            seller_score += md['confidence'] * 0.05
        
        sr = methods['support_resistance']
        if sr['direction'] == 'BUYERS':
            buyer_score += sr['confidence'] * 0.02
        elif sr['direction'] == 'SELLERS':
            seller_score += sr['confidence'] * 0.02
        
        if buyer_score > seller_score and buyer_score > 0.13:
            if current_peak:
                direction = 'BUYERS_AT_PEAK'
                confidence = min(buyer_score * 80, 75)
            else:
                direction = 'BUYERS_DOMINATING'
                confidence = min(buyer_score * 100, 95)
        elif seller_score > buyer_score and seller_score > 0.13:
            if current_trough:
                direction = 'SELLERS_AT_TROUGH'
                confidence = min(seller_score * 80, 75)
            else:
                direction = 'SELLERS_DOMINATING'
                confidence = min(seller_score * 100, 95)
        else:
            direction = 'BALANCED'
            confidence = max(buyer_score, seller_score) * 100
        
        # Get consolidation status
        consolidation = methods['consolidation']
        
        return {
            'direction': direction,
            'confidence': confidence,
            'buyer_score': buyer_score,
            'seller_score': seller_score,
            'methods': methods,
            'current_price': latest['close'],
            'timestamp': latest['timestamp'],
            'price_change_5min': latest['close'] - df['close'].iloc[-6] if len(df) >= 6 else 0,
            'at_peak': current_peak,
            'at_trough': current_trough,
            'is_consolidating': consolidation['is_consolidating'],
            'market_state': consolidation['market_state'],
            'atr_percent': consolidation['atr_percent'],
            'adx_value': methods['trend_strength']['adx_value'],
            'trend_status': methods['trend_strength']['trend_status'],
            'trend_direction': methods['trend_strength']['trend_direction'],
            'is_trending': methods['trend_strength']['is_trending']
        }
    
    def check_immediate_momentum(self, df):
        """Check immediate momentum for live moves"""
        try:
            if len(df) < 3:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_3 = df.tail(3)
            price_start = recent_3['close'].iloc[0]
            price_end = recent_3['close'].iloc[-1]
            price_change = price_end - price_start
            price_change_pct = (price_change / price_start) * 100
            
            recent_volume = recent_3['volume'].mean()
            overall_volume = df['volume'].mean()
            volume_ratio = recent_volume / overall_volume if overall_volume > 0 else 1
            
            if abs(price_change) > 20:
                if price_change > 0 and volume_ratio > 1.2:
                    return {'direction': 'BUYERS', 'confidence': min(0.9, 0.6 + abs(price_change_pct) * 10)}
                elif price_change < 0 and volume_ratio > 1.2:
                    return {'direction': 'SELLERS', 'confidence': min(0.9, 0.6 + abs(price_change_pct) * 10)}
            elif abs(price_change) > 10:
                if price_change > 0 and volume_ratio > 1.1:
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                elif price_change < 0 and volume_ratio > 1.1:
                    return {'direction': 'SELLERS', 'confidence': 0.7}
            elif abs(price_change) > 5:
                if price_change > 0 and volume_ratio > 1.05:
                    return {'direction': 'BUYERS', 'confidence': 0.6}
                elif price_change < 0 and volume_ratio > 1.05:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            elif abs(price_change) > 3:
                if price_change > 0 and volume_ratio > 1.02:
                    return {'direction': 'BUYERS', 'confidence': 0.55}
                elif price_change < 0 and volume_ratio > 1.02:
                    return {'direction': 'SELLERS', 'confidence': 0.55}
            elif abs(price_change) > 1:
                if price_change > 0:
                    return {'direction': 'BUYERS', 'confidence': 0.52}
                elif price_change < 0:
                    return {'direction': 'SELLERS', 'confidence': 0.52}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_price_velocity(self, df):
        """Detect price velocity/acceleration"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_5 = df.tail(5)
            time_diff = 5
            price_diff = recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]
            velocity = price_diff / time_diff
            
            if velocity > 2:
                return {'direction': 'BUYERS', 'confidence': min(0.8, 0.5 + abs(velocity) * 0.05)}
            elif velocity < -2:
                return {'direction': 'SELLERS', 'confidence': min(0.8, 0.5 + abs(velocity) * 0.05)}
            elif velocity > 1:
                return {'direction': 'BUYERS', 'confidence': 0.6}
            elif velocity < -1:
                return {'direction': 'SELLERS', 'confidence': 0.6}
            elif velocity > 0.5:
                return {'direction': 'BUYERS', 'confidence': 0.55}
            elif velocity < -0.5:
                return {'direction': 'SELLERS', 'confidence': 0.55}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def calculate_enhanced_indicators(self, df):
        """Calculate enhanced indicators"""
        df['volume_ma'] = df['volume'].rolling(5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        df['price_change'] = df['close'].diff()
        df['price_velocity'] = df['price_change'].rolling(2).mean()
        
        df['is_peak'] = False
        df['is_trough'] = False
        if len(df) >= 3:
            for i in range(1, len(df)-1):
                if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i+1]:
                    df.loc[df.index[i], 'is_peak'] = True
                if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i+1]:
                    df.loc[df.index[i], 'is_trough'] = True
        
        df['body'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['total_range'] = df['high'] - df['low']
        
        df['momentum_2'] = (df['close'] - df['close'].shift(2)) / df['close'].shift(2) * 100
        df['momentum_3'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100
        
        df['resistance'] = df['high'].rolling(10).max()
        df['support'] = df['low'].rolling(10).min()
        
        # ATR Calculation for Consolidation Detection
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_percent'] = (df['atr'] / df['close']) * 100
        
        # RSI Calculation (14-period) for Trade Validation
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # ADX Calculation (14-period) for Trend Strength
        # Step 1: Calculate +DM and -DM
        df['high_diff'] = df['high'].diff()
        df['low_diff'] = df['low'].diff().abs() * -1  # Make negative for comparison
        
        df['plus_dm'] = np.where(
            (df['high_diff'] > 0) & (df['high_diff'] > df['low_diff'].abs()),
            df['high_diff'],
            0
        )
        df['minus_dm'] = np.where(
            (df['low_diff'].abs() > 0) & (df['low_diff'].abs() > df['high_diff']),
            df['low_diff'].abs(),
            0
        )
        
        # Step 2: Smooth +DM, -DM and TR (14-period)
        df['smooth_plus_dm'] = df['plus_dm'].rolling(14).sum()
        df['smooth_minus_dm'] = df['minus_dm'].rolling(14).sum()
        df['smooth_tr'] = df['tr'].rolling(14).sum()
        
        # Step 3: Calculate +DI and -DI
        df['plus_di'] = (df['smooth_plus_dm'] / df['smooth_tr']) * 100
        df['minus_di'] = (df['smooth_minus_dm'] / df['smooth_tr']) * 100
        
        # Step 4: Calculate DX
        df['di_diff'] = abs(df['plus_di'] - df['minus_di'])
        df['di_sum'] = df['plus_di'] + df['minus_di']
        df['dx'] = (df['di_diff'] / df['di_sum']) * 100
        
        # Step 5: Calculate ADX (14-period smoothed average of DX)
        df['adx'] = df['dx'].rolling(14).mean()
        
        return df
    
    def detect_consolidation(self, df, lookback=14):
        """
        Detect if market is in consolidation using ATR
        Low ATR = Consolidation (sideways market)
        High ATR = Trending market
        
        Returns:
            dict with consolidation status and metrics
        """
        try:
            if df is None or len(df) < lookback:
                return {
                    'is_consolidating': False,
                    'atr_percent': 0,
                    'market_state': 'UNKNOWN',
                    'consolidation_strength': 0
                }
            
            latest = df.iloc[-1]
            atr_percent = latest.get('atr_percent', 0)
            
            if pd.isna(atr_percent):
                atr_percent = 0
            
            # ATR Thresholds for NIFTY (adjust as needed)
            # < 0.15% = Strong Consolidation
            # 0.15% - 0.25% = Mild Consolidation
            # 0.25% - 0.40% = Normal Market
            # > 0.40% = High Volatility/Trending
            
            if atr_percent < 0.15:
                is_consolidating = True
                market_state = 'STRONG_CONSOLIDATION'
                consolidation_strength = 1.0
            elif atr_percent < 0.25:
                is_consolidating = True
                market_state = 'MILD_CONSOLIDATION'
                consolidation_strength = 0.7
            elif atr_percent < 0.40:
                is_consolidating = False
                market_state = 'NORMAL_TRENDING'
                consolidation_strength = 0.3
            else:
                is_consolidating = False
                market_state = 'HIGH_VOLATILITY'
                consolidation_strength = 0.0
            
            # Additional check: Price range in last N candles
            recent = df.tail(lookback)
            high_range = recent['high'].max()
            low_range = recent['low'].min()
            avg_price = recent['close'].mean()
            range_percent = ((high_range - low_range) / avg_price) * 100 if avg_price > 0 else 0
            
            # If range is very tight, it's consolidation regardless of ATR
            if range_percent < 0.3:
                is_consolidating = True
                if market_state not in ['STRONG_CONSOLIDATION', 'MILD_CONSOLIDATION']:
                    market_state = 'TIGHT_RANGE_CONSOLIDATION'
                consolidation_strength = max(consolidation_strength, 0.8)
            
            return {
                'is_consolidating': is_consolidating,
                'atr_percent': round(atr_percent, 4),
                'range_percent': round(range_percent, 4),
                'market_state': market_state,
                'consolidation_strength': round(consolidation_strength, 2),
                'atr_value': round(latest.get('atr', 0), 2)
            }
            
        except Exception as e:
            print(f"[ERROR] Consolidation detection failed: {e}")
            return {
                'is_consolidating': False,
                'atr_percent': 0,
                'market_state': 'ERROR',
                'consolidation_strength': 0
            }
    
    def detect_trend_strength(self, df):
        """
        Detect trend strength using ADX indicator
        
        ADX Values:
        0-20:   No trend / Range-bound
        20-25:  Weak trend forming
        25-40:  Strong trend
        40-50:  Very strong trend
        >50:    Extreme / Exhaustion zone
        
        Returns:
            dict with ADX value, trend status, and direction
        """
        try:
            if df is None or len(df) < 30:
                return {
                    'adx_value': 0,
                    'trend_status': 'UNKNOWN',
                    'trend_strength': 0,
                    'trend_direction': 'NEUTRAL',
                    'plus_di': 0,
                    'minus_di': 0,
                    'is_trending': False,
                    'adx_sustained': False
                }
            
            latest = df.iloc[-1]
            adx_value = latest.get('adx', 0)
            plus_di = latest.get('plus_di', 0)
            minus_di = latest.get('minus_di', 0)
            
            if pd.isna(adx_value):
                adx_value = 0
            if pd.isna(plus_di):
                plus_di = 0
            if pd.isna(minus_di):
                minus_di = 0
            
            # Check if ADX > 25 for last 3 candles (sustained trend)
            adx_sustained = False
            if len(df) >= 3:
                last_3_adx = df['adx'].tail(3).dropna()
                if len(last_3_adx) >= 3:
                    adx_sustained = all(adx > 25 for adx in last_3_adx)
            
            # Determine trend status based on ADX
            if adx_value < 20:
                trend_status = 'NO_TREND'
                trend_strength = 0
                is_trending = False
            elif adx_value < 25:
                trend_status = 'WEAK_TREND'
                trend_strength = 0.3
                is_trending = False
            elif adx_value < 40:
                trend_status = 'STRONG_TREND'
                trend_strength = 0.7
                is_trending = True
            elif adx_value < 50:
                trend_status = 'VERY_STRONG_TREND'
                trend_strength = 0.9
                is_trending = True
            else:
                trend_status = 'EXTREME_EXHAUSTION'
                trend_strength = 0.5  # Caution - may reverse
                is_trending = True
            
            # Determine trend direction using +DI and -DI
            if plus_di > minus_di:
                trend_direction = 'BULLISH'
            elif minus_di > plus_di:
                trend_direction = 'BEARISH'
            else:
                trend_direction = 'NEUTRAL'
            
            return {
                'adx_value': round(adx_value, 2),
                'trend_status': trend_status,
                'trend_strength': round(trend_strength, 2),
                'trend_direction': trend_direction,
                'plus_di': round(plus_di, 2),
                'minus_di': round(minus_di, 2),
                'is_trending': is_trending,
                'adx_sustained': adx_sustained
            }
            
        except Exception as e:
            print(f"[ERROR] ADX trend detection failed: {e}")
            return {
                'adx_value': 0,
                'trend_status': 'ERROR',
                'trend_strength': 0,
                'trend_direction': 'NEUTRAL',
                'is_trending': False,
                'adx_sustained': False
            }
    
    def validate_trade_with_rsi(self, new_signal_type, df, is_consolidating):
        """
        Validate trade based on RSI rules:
        
        Rules:
        1. Same Side Trade (CE→CE or PE→PE) in Normal Market:
           - RSI confirmation REQUIRED
           - CE: RSI > 50, PE: RSI < 50
        
        2. Same Side Trade after Consolidation + 5 min cooling:
           - RSI confirmation NOT required
        
        3. Opposite Side Trade (CE→PE or PE→CE):
           - RSI confirmation NOT required
        
        Returns:
            dict with validation result and details
        """
        try:
            # Get current RSI
            latest = df.iloc[-1]
            current_rsi = latest.get('rsi_14', 50)  # Default to 50 if not available
            
            if pd.isna(current_rsi):
                current_rsi = 50
            
            current_time = datetime.datetime.now()
            
            # Determine if this is first trade (no last trade)
            if self.last_trade_type is None:
                return {
                    'is_valid': True,
                    'reason': 'FIRST_TRADE',
                    'rsi_value': round(current_rsi, 2),
                    'rsi_required': False,
                    'last_trade_type': None,
                    'new_signal_type': new_signal_type
                }
            
            # Rule 3: Opposite Side Trade - NO RSI needed
            if self.last_trade_type != new_signal_type:
                return {
                    'is_valid': True,
                    'reason': 'OPPOSITE_SIDE_TRADE',
                    'rsi_value': round(current_rsi, 2),
                    'rsi_required': False,
                    'last_trade_type': self.last_trade_type,
                    'new_signal_type': new_signal_type
                }
            
            # Same Side Trade (CE→CE or PE→PE)
            # Check Rule 2: Consolidation + 5 min cooling
            if is_consolidating and self.last_trade_close_time is not None:
                time_since_last_trade = (current_time - self.last_trade_close_time).total_seconds() / 60
                
                if time_since_last_trade >= self.cooling_time_minutes:
                    return {
                        'is_valid': True,
                        'reason': 'CONSOLIDATION_COOLING_COMPLETE',
                        'rsi_value': round(current_rsi, 2),
                        'rsi_required': False,
                        'last_trade_type': self.last_trade_type,
                        'new_signal_type': new_signal_type,
                        'cooling_time_passed': round(time_since_last_trade, 1)
                    }
            
            # Rule 1: Same Side Trade in Normal Market - RSI confirmation REQUIRED
            if new_signal_type == 'CE':
                rsi_condition_met = current_rsi > 50
                required_condition = 'RSI > 50'
            else:  # PE
                rsi_condition_met = current_rsi < 50
                required_condition = 'RSI < 50'
            
            if rsi_condition_met:
                return {
                    'is_valid': True,
                    'reason': 'RSI_CONFIRMED',
                    'rsi_value': round(current_rsi, 2),
                    'rsi_required': True,
                    'rsi_condition': required_condition,
                    'last_trade_type': self.last_trade_type,
                    'new_signal_type': new_signal_type
                }
            else:
                return {
                    'is_valid': False,
                    'reason': 'RSI_NOT_CONFIRMED',
                    'rsi_value': round(current_rsi, 2),
                    'rsi_required': True,
                    'rsi_condition': required_condition,
                    'last_trade_type': self.last_trade_type,
                    'new_signal_type': new_signal_type
                }
                
        except Exception as e:
            print(f"[ERROR] RSI validation failed: {e}")
            return {
                'is_valid': True,
                'reason': 'VALIDATION_ERROR',
                'rsi_value': 0,
                'rsi_required': False
            }
    
    def update_last_trade(self, trade_type):
        """Update last trade info when a trade closes"""
        self.last_trade_type = trade_type  # 'CE' or 'PE'
        self.last_trade_close_time = datetime.datetime.now()
        print(f"[TRADE TRACKER] Last trade updated: {trade_type} at {self.last_trade_close_time.strftime('%H:%M:%S')}")
        
        # Save to file for persistence
        self._save_last_trade_state()
    
    def validate_adx_rsi_combo(self, df, signal_type):
        """
        ADX + RSI Combo Validation for trade entry
        
        Rules:
        1. ADX must be above 25 for at least 3 candles (sustained trend)
        2. RSI should not be above 70 (overbought) or below 30 (oversold) at entry
        
        Args:
            df: DataFrame with calculated indicators
            signal_type: 'CE' or 'PE'
        
        Returns:
            dict with validation result and details
        """
        try:
            if df is None or len(df) < 3:
                return {
                    'is_valid': False,
                    'reason': 'INSUFFICIENT_DATA',
                    'adx_valid': False,
                    'rsi_valid': False,
                    'adx_value': 0,
                    'rsi_value': 0
                }
            
            latest = df.iloc[-1]
            
            # Get ADX value and sustained check
            adx_value = latest.get('adx', 0)
            if pd.isna(adx_value):
                adx_value = 0
            
            # Check ADX sustained above 25 for 3 candles
            adx_sustained = False
            last_3_adx = df['adx'].tail(3).dropna()
            if len(last_3_adx) >= 3:
                adx_sustained = all(adx > 25 for adx in last_3_adx)
            
            # Get RSI value
            rsi_value = latest.get('rsi_14', 50)
            if pd.isna(rsi_value):
                rsi_value = 50
            
            # Check RSI not in extreme zones (30-70 range is valid)
            rsi_valid = 30 <= rsi_value <= 70
            rsi_zone = 'NORMAL'
            if rsi_value > 70:
                rsi_zone = 'OVERBOUGHT'
            elif rsi_value < 30:
                rsi_zone = 'OVERSOLD'
            
            # Both conditions must pass
            is_valid = adx_sustained and rsi_valid
            
            # Determine reason
            if is_valid:
                reason = 'ADX_RSI_VALID'
            elif not adx_sustained and not rsi_valid:
                reason = 'ADX_NOT_SUSTAINED_AND_RSI_EXTREME'
            elif not adx_sustained:
                reason = 'ADX_NOT_SUSTAINED_3_CANDLES'
            else:
                reason = f'RSI_{rsi_zone}'
            
            return {
                'is_valid': is_valid,
                'reason': reason,
                'adx_valid': adx_sustained,
                'rsi_valid': rsi_valid,
                'adx_value': round(adx_value, 2),
                'rsi_value': round(rsi_value, 2),
                'rsi_zone': rsi_zone,
                'adx_last_3': [round(x, 2) for x in last_3_adx.tolist()] if len(last_3_adx) >= 3 else []
            }
            
        except Exception as e:
            print(f"[ERROR] ADX+RSI validation failed: {e}")
            return {
                'is_valid': False,
                'reason': 'VALIDATION_ERROR',
                'adx_valid': False,
                'rsi_valid': False,
                'adx_value': 0,
                'rsi_value': 0
            }
    
    def detect_volume_price_trend_sensitive(self, df):
        """Volume-Price Trend Analysis"""
        try:
            recent = df.tail(3)
            
            up_candles = recent[recent['close'] > recent['open']]
            down_candles = recent[recent['close'] < recent['open']]
            
            up_volume = up_candles['volume'].sum() if len(up_candles) > 0 else 0
            down_volume = down_candles['volume'].sum() if len(down_candles) > 0 else 0
            
            if up_volume + down_volume > 0:
                buying_pressure = up_volume / (up_volume + down_volume)
                selling_pressure = down_volume / (up_volume + down_volume)
                
                if buying_pressure > 0.40:
                    return {'direction': 'BUYERS', 'confidence': buying_pressure}
                elif selling_pressure > 0.40:
                    return {'direction': 'SELLERS', 'confidence': selling_pressure}
                elif buying_pressure > 0.30:
                    return {'direction': 'BUYERS', 'confidence': buying_pressure * 0.8}
                elif selling_pressure > 0.30:
                    return {'direction': 'SELLERS', 'confidence': selling_pressure * 0.8}
                elif buying_pressure > 0.25:
                    return {'direction': 'BUYERS', 'confidence': buying_pressure * 0.7}
                elif selling_pressure > 0.25:
                    return {'direction': 'SELLERS', 'confidence': selling_pressure * 0.7}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_candle_body_pressure_sensitive(self, df):
        """Candle Body Analysis"""
        try:
            latest = df.iloc[-1]
            
            body_ratio = latest['body'] / latest['total_range'] if latest['total_range'] > 0 else 0
            upper_shadow_ratio = latest['upper_shadow'] / latest['total_range'] if latest['total_range'] > 0 else 0
            lower_shadow_ratio = latest['lower_shadow'] / latest['total_range'] if latest['total_range'] > 0 else 0
            
            if (latest['close'] > latest['open'] and body_ratio > 0.3 and lower_shadow_ratio < 0.4):
                return {'direction': 'BUYERS', 'confidence': 0.7}
            elif (latest['close'] < latest['open'] and body_ratio > 0.3 and upper_shadow_ratio < 0.4):
                return {'direction': 'SELLERS', 'confidence': 0.7}
            elif latest['close'] > latest['open'] and body_ratio > 0.2:
                return {'direction': 'BUYERS', 'confidence': 0.55}
            elif latest['close'] < latest['open'] and body_ratio > 0.2:
                return {'direction': 'SELLERS', 'confidence': 0.55}
            elif (lower_shadow_ratio > 0.3 and body_ratio < 0.5):
                return {'direction': 'BUYERS', 'confidence': 0.6}
            elif (upper_shadow_ratio > 0.3 and body_ratio < 0.5):
                return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_momentum_divergence_sensitive(self, df):
        """Momentum Divergence Analysis"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_momentum = df['momentum_2'].iloc[-1]
            volume_momentum = df['volume_ratio'].iloc[-1]
            
            if recent_momentum > 0.05 and volume_momentum > 1.2:
                return {'direction': 'BUYERS', 'confidence': 0.65}
            elif recent_momentum < -0.05 and volume_momentum > 1.2:
                return {'direction': 'SELLERS', 'confidence': 0.65}
            elif recent_momentum > 0.02:
                return {'direction': 'BUYERS', 'confidence': 0.55}
            elif recent_momentum < -0.02:
                return {'direction': 'SELLERS', 'confidence': 0.55}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_sr_pressure_sensitive(self, df):
        """Support/Resistance Pressure"""
        try:
            latest = df.iloc[-1]
            
            resistance_distance = (latest['resistance'] - latest['close']) / latest['close'] * 100
            support_distance = (latest['close'] - latest['support']) / latest['close'] * 100
            
            if resistance_distance < 0.3 and latest['volume_ratio'] > 1.2:
                if latest['close'] > latest['open']:
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                else:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            elif support_distance < 0.3 and latest['volume_ratio'] > 1.2:
                if latest['close'] > latest['open']:
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                else:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_movement_diversion(self, df):
        """Detect movement diversion patterns"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_5 = df.tail(5)
            
            price_start = recent_5['close'].iloc[0]
            price_end = recent_5['close'].iloc[-1]
            price_change = price_end - price_start
            price_trend = 'UP' if price_change > 5 else 'DOWN' if price_change < -5 else 'FLAT'
            
            recent_volume = recent_5['volume'].mean()
            earlier_volume = df['volume'].iloc[-10:-5].mean() if len(df) >= 10 else recent_volume
            volume_ratio = recent_volume / earlier_volume if earlier_volume > 0 else 1
            volume_trend = 'INCREASING' if volume_ratio > 1.2 else 'DECREASING' if volume_ratio < 0.8 else 'STABLE'
            
            momentum_recent = recent_5['momentum_2'].iloc[-1] if 'momentum_2' in recent_5.columns else 0
            momentum_trend = 'STRONG_UP' if momentum_recent > 0.3 else 'STRONG_DOWN' if momentum_recent < -0.3 else 'WEAK'
            
            if price_trend == 'DOWN' and volume_trend == 'INCREASING' and momentum_trend != 'STRONG_DOWN':
                return {'direction': 'BUYERS', 'confidence': 0.75, 'type': 'BULLISH_DIVERGENCE'}
            elif price_trend == 'UP' and (volume_trend == 'DECREASING' or momentum_trend == 'WEAK'):
                return {'direction': 'SELLERS', 'confidence': 0.70, 'type': 'BEARISH_DIVERGENCE'}
            elif abs(price_change) > 15 and volume_ratio < 0.7:
                direction = 'SELLERS' if price_change > 0 else 'BUYERS'
                return {'direction': direction, 'confidence': 0.65, 'type': 'VOLUME_PRICE_DIVERGENCE'}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'type': 'NO_DIVERGENCE'}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'type': 'ERROR'}
    
    def detect_operator_activity(self, df):
        """Detect operator/institutional activity patterns"""
        try:
            if len(df) < 10:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            latest = df.iloc[-1]
            recent_5 = df.tail(5)
            
            avg_volume = df['volume'].mean()
            recent_volume = recent_5['volume'].mean()
            volume_spike = recent_volume / avg_volume if avg_volume > 0 else 1
            
            price_change_5min = recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]
            
            body_size = abs(latest['close'] - latest['open'])
            avg_body = df['body'].mean() if 'body' in df.columns else 10
            large_candle = body_size / avg_body if avg_body > 0 else 1
            
            operator_score = 0
            operator_signals = []
            
            if volume_spike > 2.0:
                operator_score += 0.8
                operator_signals.append(f"VOL_SPIKE_{volume_spike:.1f}x")
            elif volume_spike > 1.5:
                operator_score += 0.6
                operator_signals.append(f"HIGH_VOL_{volume_spike:.1f}x")
            elif volume_spike > 1.2:
                operator_score += 0.4
                operator_signals.append(f"MILD_VOL_{volume_spike:.1f}x")
            
            if abs(price_change_5min) > 15 and volume_spike > 1.3:
                operator_score += 0.7
                operator_signals.append(f"BIG_MOVE_{abs(price_change_5min):.0f}pts")
            elif abs(price_change_5min) > 8 and volume_spike > 1.2:
                operator_score += 0.5
                operator_signals.append(f"SMALL_MOVE_{abs(price_change_5min):.0f}pts")
            
            if large_candle > 2.5:
                operator_score += 0.6
                operator_signals.append("LARGE_CANDLE")
            
            if volume_spike > 2.5 and abs(price_change_5min) < 15:
                operator_score += 0.6
                operator_signals.append("BLOCK_TRADE")
            
            if operator_score > 0.3:
                if price_change_5min > 2:
                    direction = 'BUYERS'
                elif price_change_5min < -2:
                    direction = 'SELLERS'
                else:
                    direction = 'ACCUMULATION'
                confidence = min(operator_score, 0.9)
            else:
                direction = 'NEUTRAL'
                confidence = 0.5
            
            return {
                'direction': direction,
                'confidence': confidence,
                'volume_spike': volume_spike,
                'signals': operator_signals,
                'operator_score': operator_score
            }
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'signals': []}
    
    def find_pivot_points(self, df):
        """Find pivot points"""
        try:
            if df is None or len(df) < 10:
                return {'prev_support': None, 'next_resistance': None}
            
            current_price = df['close'].iloc[-1]
            
            pivot_highs = []
            for i in range(2, len(df)-2):
                high = df['high'].iloc[i]
                if (high > df['high'].iloc[i-1] and high > df['high'].iloc[i-2] and
                    high > df['high'].iloc[i+1] and high > df['high'].iloc[i+2]):
                    pivot_highs.append({'price': high, 'index': i})
            
            pivot_lows = []
            for i in range(2, len(df)-2):
                low = df['low'].iloc[i]
                if (low < df['low'].iloc[i-1] and low < df['low'].iloc[i-2] and
                    low < df['low'].iloc[i+1] and low < df['low'].iloc[i+2]):
                    pivot_lows.append({'price': low, 'index': i})
            
            prev_support = None
            for pivot in reversed(pivot_lows):
                if pivot['price'] < current_price:
                    prev_support = pivot['price']
                    break
            
            next_resistance = None
            for pivot in reversed(pivot_highs):
                if pivot['price'] > current_price:
                    if next_resistance is None or pivot['price'] < next_resistance:
                        next_resistance = pivot['price']
            
            return {
                'prev_support': prev_support,
                'next_resistance': next_resistance,
                'support_distance': (current_price - prev_support) if prev_support else None,
                'resistance_distance': (next_resistance - current_price) if next_resistance else None
            }
        except:
            return {'prev_support': None, 'next_resistance': None}

    # =========================================================================
    # STATE PERSISTENCE METHODS
    # =========================================================================
    
    def save_state(self):
        """Save active positions to JSON file"""
        try:
            state_data = {}
            for order_id, pos in self.active_positions.items():
                pos_copy = pos.copy()
                if 'entry_time' in pos_copy:
                    pos_copy['entry_time'] = pos_copy['entry_time'].strftime("%Y-%m-%d %H:%M:%S")
                state_data[order_id] = pos_copy
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] State save failed: {e}")

    def load_state(self):
        """Load active positions from JSON file"""
        try:
            if not os.path.exists(self.state_file):
                return
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            count = 0
            for order_id, pos in state_data.items():
                if 'entry_time' in pos:
                    try:
                        pos['entry_time'] = datetime.datetime.strptime(pos['entry_time'], "%Y-%m-%d %H:%M:%S")
                    except:
                        pos['entry_time'] = datetime.datetime.now()
                
                self.active_positions[order_id] = pos
                count += 1
            
            if count > 0:
                print(f"[RESUMED] Restored {count} active trades")
        except Exception as e:
            print(f"[ERROR] State load failed: {e}")

    # =========================================================================
    # TRAILING SL & POSITION MANAGEMENT
    # =========================================================================
    
    def calculate_trailing_sl(self, entry_price, current_price, current_sl):
        """
        Calculate new trailing SL based on profit level
        
        THREE-PHASE TRAILING SL LOGIC (ENHANCED):
        ==========================================
        Phase 1 (7% to 19%): 5% lock, then +5% every 5% step
        Phase 2 (20% to 29%): 18% lock, then +3% every 3% step  
        Phase 3 (30%+): 28% lock, then +2% every 2% step (SUPER TIGHT)
        """
        try:
            profit_percent = ((current_price - entry_price) / entry_price) * 100
            
            # If not yet at 7% profit, keep initial SL
            if profit_percent < 7:
                return current_sl, False
            
            locked_profit_percent = 0
            
            # PHASE 3: Profit >= 30% (Super tight - 2% steps)
            if profit_percent >= 30:
                steps_after_30 = int((profit_percent - 30) / 2)
                locked_profit_percent = 28 + (steps_after_30 * 2)
            
            # PHASE 2: Profit 20% to <30% (Tighter - 3% steps)
            elif profit_percent >= 20:
                steps_after_20 = int((profit_percent - 20) / 3)
                locked_profit_percent = 18 + (steps_after_20 * 3)
            
            # PHASE 1: Profit 7% to <20% (Standard - 5% steps)
            elif profit_percent >= 7:
                steps_above_7 = int((profit_percent - 7) / 5)
                locked_profit_percent = 5 + (steps_above_7 * 5)
            
            new_sl = round(entry_price * (1 + locked_profit_percent / 100), 2)
            new_sl = self.round_to_tick(new_sl)
            
            if new_sl > current_sl:
                return new_sl, True
            
            return current_sl, False
        except Exception as e:
            print(f"[CALC SL ERROR] {e}")
            return current_sl, False

    def update_trailing_sl(self, order_id, current_ltp, pnl_percent):
        """Update Trailing SL"""
        try:
            position = self.active_positions[order_id]
            entry_price = position['entry_price']
            current_sl = position['sl_price']
            
            new_sl, should_modify = self.calculate_trailing_sl(entry_price, current_ltp, current_sl)

            if should_modify and new_sl > current_sl:
                if (new_sl - current_sl) > 0.5:
                    position['sl_price'] = new_sl
                    position['trail_active'] = True
                    
                    self.save_state()
                    
                    print(f"[SL TRAIL] -> Rs.{new_sl:.1f} (Locked: {((new_sl-entry_price)/entry_price)*100:.1f}%)")
                    
                    if order_id in self.active_sl_orders:
                        sl_order_id = self.active_sl_orders[order_id]
                        self.modify_sl_order(sl_order_id, new_sl, position['symbol'])
                    
        except Exception as e:
            print(f"[TRAIL ERROR] {e}")

    def verify_position_status(self):
        """Verify if active positions are still open in broker"""
        if not self.active_positions or not self.ENABLE_TRADING:
            return

        try:
            api_instance = upstox_client.PortfolioApi(self.api_client)
            response = api_instance.get_positions(api_version='2.0')
            
            if not response or response.status != 'success':
                return
                
            positions_data = response.data if response.data else []
            
            real_positions = {}
            for pos in positions_data:
                token = getattr(pos, 'instrument_token', '')
                net_qty = int(getattr(pos, 'quantity', 0))
                real_positions[token] = net_qty
            
            params_to_remove = []
            
            for order_id, position in self.active_positions.items():
                token = position.get('token')
                symbol = position['symbol']
                
                if token in real_positions:
                    net_qty = real_positions[token]
                    if net_qty == 0:
                        print(f"\n[MANUAL EXIT DETECTED] {symbol} closed in broker")
                        params_to_remove.append(order_id)
                else:
                    print(f"\n[MANUAL EXIT DETECTED] {symbol} not found in broker")
                    params_to_remove.append(order_id)
            
            for order_id in params_to_remove:
                self.exit_position(order_id, "MANUAL_EXIT_BROKER")
                
        except Exception as e:
            print(f"[POSITION CHECK ERROR] {e}")

    def manage_active_positions(self):
        """Monitor active positions"""
        if not self.active_positions:
            return

        self.verify_position_status()
        
        if not self.active_positions:
            return
        
        print(f"\n[MONITORING] {len(self.active_positions)} active trades...")
        
        self.check_order_status()
        
        for order_id, position in list(self.active_positions.items()):
            symbol = position['symbol']
            token = position.get('token', '')
            entry_price = position['entry_price']
            target_price = position['target_price']
            
            # Skip invalid positions (entry_price = 0)
            if entry_price <= 0:
                print(f"  [SKIP] {symbol}: Invalid entry price (0) - Close manually in Upstox")
                continue
            
            current_ltp = self.get_option_ltp(symbol, token)
            
            if current_ltp:
                pnl = (current_ltp - entry_price) * position['quantity']
                pnl_percent = ((current_ltp - entry_price) / entry_price) * 100
                
                print(f"  {symbol}: ₹{current_ltp:.1f} | P&L: ₹{pnl:+.0f} ({pnl_percent:+.1f}%) | SL: {position['sl_price']:.1f}")
                
                if current_ltp >= target_price:
                    print(f"\n[TARGET HIT] {symbol}")
                    self.exit_position(order_id, "TARGET_HIT_INTERNAL")
                    return
                
                if current_ltp <= position['sl_price']:
                    print(f"\n[SL HIT] {symbol}")
                    self.exit_position(order_id, "SL_HIT_INTERNAL")
                    return
                
                if current_ltp > position['highest_price']:
                    position['highest_price'] = current_ltp
                
                self.update_trailing_sl(order_id, current_ltp, pnl_percent)
    
    def check_order_status(self):
        """Check if SL orders are executed"""
        try:
            if not self.ENABLE_TRADING:
                return
                
            api_instance = upstox_client.OrderApi(self.api_client)
            order_book_resp = api_instance.get_order_book(api_version='2.0')
            
            if not order_book_resp or order_book_resp.status != 'success':
                return
                
            orders = order_book_resp.data if order_book_resp.data else []
            
            for order_id, position in list(self.active_positions.items()):
                if order_id in self.active_sl_orders:
                    sl_order_id = self.active_sl_orders[order_id]
                    for order in orders:
                        if str(getattr(order, 'order_id', '')) == str(sl_order_id):
                            if getattr(order, 'status', '').lower() == 'complete':
                                print(f"[SL EXECUTED] {position['symbol']}")
                                self.exit_position(order_id, "SL_HIT")
                                return
                                
        except Exception as e:
            print(f"[ORDER STATUS ERROR] {e}")

    # =========================================================================
    # TRADE LOGGING
    # =========================================================================
    
    def log_rejected_trade(self, reason, details):
        """Log rejected potential trades to CSV"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Create file/header if not exists
            if not os.path.exists(self.rejected_trades_file):
                with open(self.rejected_trades_file, 'w') as f:
                    f.write("Timestamp,Reason,Score,Direction,Signal_Type,Velocity,RSI,ADX,Details\n")
            
            # Prepare data
            score = details.get('score', 0)
            direction = details.get('direction', 'UNKNOWN')
            signal_type = details.get('signal_type', 'N/A')
            velocity = details.get('velocity', 'N/A')
            rsi = details.get('rsi', 'N/A')
            adx = details.get('adx', 'N/A')
            extra_details = str(details).replace(',', ';') # Avoid CSV conflict
            
            log_entry = f"{timestamp},{reason},{score},{direction},{signal_type},{velocity},{rsi},{adx},{extra_details}\n"
            
            with open(self.rejected_trades_file, 'a') as f:
                f.write(log_entry)
                
            print(f"[LOG] Rejected trade logged: {reason}")
            
        except Exception as e:
            print(f"[ERROR] Failed to log rejected trade: {e}")

    def log_trade_to_excel(self, order_id, position):
        """Log trade to Excel"""
        try:
            if not os.path.exists(self.trade_log_file):
                wb = Workbook()
                ws = wb.active
                headers = ['Date', 'Time', 'Symbol', 'Strike', 'Type', 'Entry Price',
                          'Qty', 'Initial SL', 'Exit Time', 'Exit Price', 'Exit Reason', 'P&L']
                ws.append(headers)
                wb.save(self.trade_log_file)
            
            wb = load_workbook(self.trade_log_file)
            ws = wb.active
            
            row_data = [
                datetime.datetime.now().strftime("%Y-%m-%d"),
                position['entry_time'].strftime("%H:%M:%S"),
                position['symbol'],
                position.get('strike', 0),
                position.get('option_type', ''),
                position['entry_price'],
                position['quantity'],
                position['sl_price'],
                '', '', '', ''
            ]
            ws.append(row_data)
            self.current_trade_row = ws.max_row
            
            wb.save(self.trade_log_file)
            print(f"[LOGGED] Trade entry saved")
            
        except Exception as e:
            print(f"[LOG ERROR] {e}")

    def finalize_trade_log(self, order_id, exit_price, exit_reason, pnl):
        """Finalize trade log"""
        try:
            if not os.path.exists(self.trade_log_file):
                return
            
            wb = load_workbook(self.trade_log_file)
            ws = wb.active
            
            row = ws.max_row
            
            ws.cell(row=row, column=9, value=datetime.datetime.now().strftime("%H:%M:%S"))
            ws.cell(row=row, column=10, value=exit_price)
            ws.cell(row=row, column=11, value=exit_reason)
            ws.cell(row=row, column=12, value=pnl)
            
            wb.save(self.trade_log_file)
            print(f"[FINALIZED] Trade log updated")
            
        except Exception as e:
            print(f"[FINALIZE ERROR] {e}")

    # =========================================================================
    # TRADE EXECUTION
    # =========================================================================
    
    def execute_trade(self, signal, confidence, current_price):
        """Execute trade based on signal"""
        try:
            atm_strike = round(current_price / 50) * 50
            option_type = "CE" if signal == 'BUY' else "PE"
            contract_strike = atm_strike
            
            print(f"\n[EXECUTING] {atm_strike} {option_type} for {'Bullish' if signal == 'BUY' else 'Bearish'} Signal")
            
            contract = self.find_option_contract(contract_strike, option_type)
            if not contract:
                print("[ERROR] Option contract not found")
                return
            
            print(f"[CONTRACT] {contract['symbol']} ({contract['expiry']})")
            
            order_id = self.place_order(contract['symbol'], contract['token'], self.ORDER_QUANTITY, "BUY")
            
            if order_id:
                print(f"[ORDER STATUS] Checking fill...")
                entry_price = 0
                
                # Try to get fill price
                for attempt in range(25):
                    try:
                        api_instance = upstox_client.OrderApi(self.api_client)
                        order_history = api_instance.get_order_history(order_id, api_version='2.0')
                        
                        if order_history and order_history.status == 'success':
                            orders = order_history.data if order_history.data else []
                            for order in orders:
                                status = getattr(order, 'status', '').lower()
                                if status == 'complete':
                                    avg_price = float(getattr(order, 'average_price', 0))
                                    if avg_price > 0:
                                        entry_price = avg_price
                                        print(f"[FILLED] @ {entry_price}")
                                        break
                        
                        if entry_price > 0:
                            break
                            
                    except Exception as e:
                        pass
                    
                    time.sleep(0.4)
                
                # Fallback to LTP
                if entry_price == 0:
                    for _ in range(10):
                        time.sleep(0.3)
                        price = self.get_option_ltp(contract['symbol'], contract['token'])
                        if price and price > 0:
                            entry_price = price
                            print(f"[LTP FALLBACK] {entry_price}")
                            break
                
                if entry_price == 0:
                    print("[ERROR] Could not get entry price. Using dummy 100.0")
                    entry_price = 100.0
                
                self.active_positions[order_id] = {
                    'symbol': contract['symbol'],
                    'token': contract['token'],
                    'strike': contract_strike,
                    'option_type': option_type,
                    'quantity': self.ORDER_QUANTITY,
                    'entry_time': datetime.datetime.now(),
                    'entry_price': entry_price,
                    'sl_price': entry_price * (1 - self.stop_loss_percent/100),
                    'target_price': entry_price * (1 + self.target_percent/100),
                    'target_stage': 0,
                    'highest_price': entry_price,
                    'trail_active': False
                }
                
                print(f"[POSITION OPENED] ID: {order_id}")
                print(f"   Entry: ₹{entry_price:.1f}")
                print(f"   SL: ₹{self.active_positions[order_id]['sl_price']:.1f}")
                
                self.save_state()
                threading.Thread(target=self.log_trade_to_excel, args=(order_id, self.active_positions[order_id])).start()
                
                # Place SL Order
                sl_price = self.active_positions[order_id]['sl_price']
                sl_order_id = None
                
                for attempt in range(3):
                    sl_order_id = self.place_sl_order(order_id, sl_price)
                    if sl_order_id:
                        print(f"[SL ORDER SUCCESS] {sl_order_id}")
                        break
                    else:
                        print(f"[SL ORDER FAILED] Attempt {attempt+1}/3")
                        if attempt < 2:
                            time.sleep(1)
                
                if not sl_order_id:
                    print(f"\n[CRITICAL] SL ORDER FAILED!")
                    print(f"[EMERGENCY EXIT] Closing position...")
                    self.exit_position(order_id, "SL_PLACEMENT_FAILED")
                    return
                
                target_price = self.active_positions[order_id]['target_price']
                print(f"[TARGET MONITORING] Rs.{target_price:.1f} will be monitored internally")
                
        except Exception as e:
            print(f"[EXECUTION ERROR] {e}")

    # =========================================================================
    # TRADE SCORING & RECOMMENDATIONS
    # =========================================================================
    
    def calculate_trade_score(self, result, trend_filter):
        """Calculate 100-point trade score"""
        try:
            score_breakdown = {}
            total_score = 0
            
            if result['buyer_score'] > result['seller_score']:
                dominant_score = result['buyer_score']
                signal_direction = 'BUY'
            else:
                dominant_score = result['seller_score']
                signal_direction = 'SELL'
            
            # Price Velocity (40 points)
            price_velocity_data = result['methods'].get('price_velocity', {'confidence': 0})
            price_velocity = price_velocity_data['confidence']
            velocity_score = 40 if price_velocity > 0.65 else 0
            score_breakdown['Price Velocity (>0.65)'] = {
                'current': price_velocity, 'required': 0.65,
                'percentage': velocity_score, 'achieved': price_velocity > 0.65,
                'max_points': 40
            }
            total_score += velocity_score
            
            # Dominance (15 points)
            dominance_score = 15 if dominant_score > 0.13 else 0
            score_breakdown['Buyer/Seller Dominance (>0.13)'] = {
                'current': dominant_score, 'required': 0.13,
                'percentage': dominance_score, 'achieved': dominant_score > 0.13,
                'max_points': 15
            }
            total_score += dominance_score
            
            # Candle (10 points)
            candle_data = result['methods'].get('candle_body_analysis', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            candle_confidence = candle_data['confidence']
            candle_score = 10 if (candle_confidence > 0.6 and candle_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Candle Body Analysis (>0.6)'] = {
                'current': candle_confidence, 'required': 0.6,
                'percentage': candle_score, 'achieved': candle_confidence > 0.6,
                'max_points': 10
            }
            total_score += candle_score
            
            # Diversion (10 points)
            diversion_data = result['methods'].get('movement_diversion', {'confidence': 0.5, 'type': 'NO_DIVERGENCE'})
            diversion_type = diversion_data.get('type', 'NO_DIVERGENCE')
            diversion_confidence = diversion_data['confidence']
            diversion_score = 10 if ('DIVERGENCE' in diversion_type and diversion_confidence > 0.65) else 0
            score_breakdown['Movement Diversion'] = {
                'current': diversion_confidence, 'required': 0.65,
                'percentage': diversion_score, 'achieved': diversion_score > 0,
                'max_points': 10
            }
            total_score += diversion_score
            
            # Operator (10 points)
            operator_data = result['methods'].get('operator_activity', {'operator_score': 0, 'direction': 'NEUTRAL'})
            operator_score_raw = operator_data.get('operator_score', 0)
            operator_score = 10 if (operator_score_raw > 0.6 and operator_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Operator Activity'] = {
                'current': operator_score_raw, 'required': 0.6,
                'percentage': operator_score, 'achieved': operator_score_raw > 0.6,
                'max_points': 10
            }
            total_score += operator_score
            
            # Volume (8 points)
            volume_data = result['methods'].get('volume_price_trend', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            volume_confidence = volume_data['confidence']
            volume_score = 8 if (volume_confidence > 0.55 and volume_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Volume Momentum'] = {
                'current': volume_confidence, 'required': 0.55,
                'percentage': volume_score, 'achieved': volume_confidence > 0.55,
                'max_points': 8
            }
            total_score += volume_score
            
            # Timing (7 points)
            current_time = datetime.datetime.now()
            market_hour = current_time.hour
            prime_time = (9 <= market_hour < 11) or (13 <= market_hour < 15)
            timing_score = 7 if prime_time else 0
            score_breakdown['Market Timing'] = {
                'current': market_hour, 'required': 10,
                'percentage': timing_score, 'achieved': prime_time,
                'max_points': 7
            }
            total_score += timing_score
            
            # Consolidation Penalty (-20 points if consolidating)
            consolidation_data = result['methods'].get('consolidation', {'is_consolidating': False, 'market_state': 'UNKNOWN'})
            is_consolidating = consolidation_data.get('is_consolidating', False)
            market_state = consolidation_data.get('market_state', 'UNKNOWN')
            atr_percent = consolidation_data.get('atr_percent', 0)
            consolidation_penalty = -20 if is_consolidating else 0
            score_breakdown['Consolidation (ATR)'] = {
                'current': atr_percent, 'required': 0.25,
                'percentage': consolidation_penalty, 'achieved': not is_consolidating,
                'market_state': market_state,
                'max_points': 0  # Penalty only
            }
            total_score += consolidation_penalty
            
            # ADX Trend Strength (+15 points if strong trend, -10 if no trend)
            trend_data = result['methods'].get('trend_strength', {'adx_value': 0, 'trend_status': 'UNKNOWN', 'is_trending': False, 'trend_direction': 'NEUTRAL'})
            adx_value = trend_data.get('adx_value', 0)
            trend_status = trend_data.get('trend_status', 'UNKNOWN')
            is_trending = trend_data.get('is_trending', False)
            trend_direction = trend_data.get('trend_direction', 'NEUTRAL')
            
            # Check if trend direction matches signal direction
            trend_matches_signal = False
            if signal_direction == 'BUY' and trend_direction == 'BULLISH':
                trend_matches_signal = True
            elif signal_direction == 'SELL' and trend_direction == 'BEARISH':
                trend_matches_signal = True
            
            # Calculate ADX score
            if is_trending and trend_matches_signal:
                adx_score = 15  # Bonus for trending in same direction
            elif is_trending and not trend_matches_signal:
                adx_score = -5  # Penalty for counter-trend trade
            elif adx_value < 20:
                adx_score = -10  # No trend = risky
            else:
                adx_score = 0  # Weak trend = neutral
            
            score_breakdown['ADX Trend (>25)'] = {
                'current': adx_value, 'required': 25,
                'percentage': adx_score, 'achieved': is_trending and trend_matches_signal,
                'trend_status': trend_status,
                'trend_direction': trend_direction,
                'max_points': 15
            }
            total_score += adx_score
            
            # Ensure score doesn't go below 0
            total_score = max(total_score, 0)
            
            if total_score >= 80:
                signal = 'STRONG_TRADE'
            elif total_score >= 65:
                signal = 'MODERATE_TRADE'
            elif total_score >= 50:
                signal = 'WEAK_SIGNAL'
            else:
                signal = 'NO_TRADE'
            
            return {
                'total_score': total_score,
                'signal': signal,
                'direction': signal_direction,
                'breakdown': score_breakdown
            }
            
        except Exception as e:
            print(f"[ERROR] Score calc failed: {e}")
            return {'total_score': 0, 'signal': 'ERROR', 'breakdown': {}}

    def print_quick_alert(self, direction, current_price):
        """Print instant alert"""
        try:
            atm_strike = round(current_price / 50) * 50
            if direction == 'BUY':
                print(f"\n🚀 [INSTANT ALERT] BUY NIFTY {atm_strike} CE !!!")
            else:
                print(f"\n🔻 [INSTANT ALERT] BUY NIFTY {atm_strike} PE !!!")
        except:
            pass

    def generate_trade_recommendation(self, result, trade_score, pivot_points):
        """Generate trade recommendation"""
        try:
            current_price = result['current_price']
            direction = trade_score['direction']
            
            if direction == 'BUY':
                print(f"\n🚀 [CALL BUY RECOMMENDATION]")
                print("=" * 50)
                atm_strike = round(current_price / 50) * 50
                contract = self.find_option_contract(atm_strike, 'CE')
                opt_ltp = self.get_option_ltp(contract['symbol'], contract['token']) if contract else 0
                
                print(f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}")
                print(f"Underlying: NIFTY @ {current_price:.1f}")
                print(f"Recommended: {atm_strike} CE @ ₹{opt_ltp:.1f}")
                
            else:
                print(f"\n🔻 [PUT BUY RECOMMENDATION]")
                print("=" * 50)
                atm_strike = round(current_price / 50) * 50
                contract = self.find_option_contract(atm_strike, 'PE')
                opt_ltp = self.get_option_ltp(contract['symbol'], contract['token']) if contract else 0
                
                print(f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}")
                print(f"Underlying: NIFTY @ {current_price:.1f}")
                print(f"Recommended: {atm_strike} PE @ ₹{opt_ltp:.1f}")
            
            print(f"\nTrade Score: {trade_score['total_score']:.1f}/100")
            
        except Exception as e:
            print(f"[ERROR] Recommendation failed: {e}")

    # =========================================================================
    # MAIN DETECTION LOOP
    # =========================================================================
    
    def run_sensitive_detection(self):
        """Run sensitive buyer/seller detection"""
        print("=" * 80)
        print("ENHANCED OPTIONS TRADING SYSTEM - UPSTOX VERSION")
        print("FILTERS: 65% Score Threshold + 100-Point System")
        print("=" * 80)
        
        while True:
            try:
                current_time = datetime.datetime.now()
                
                # Weekend check (Saturday=5, Sunday=6)
                if current_time.weekday() >= 5:
                    print(f"[{current_time.strftime('%H:%M:%S')}] Weekend - Market Closed. Waiting...")
                    time.sleep(60)
                    continue
                
                # Market hours check (9:15 AM - 3:30 PM)
                if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15):
                    print(f"[{current_time.strftime('%H:%M:%S')}] Pre-Market. Waiting for 9:15 AM...")
                    time.sleep(30)
                    continue
                
                if current_time.hour >= 15 and current_time.minute >= 30:
                    print(f"[{current_time.strftime('%H:%M:%S')}] Market Closed (After 3:30 PM)")
                    time.sleep(60)
                    continue
                
                df = self.get_tick_data()
                
                if df is None or df.empty:
                    print(f"[{current_time.strftime('%H:%M:%S')}] No market data available. Retrying in 10s...")
                    time.sleep(10)
                    continue
                
                result = self.enhanced_buyer_seller_analysis_sensitive(df)
                
                trend_filter = None
                pivot_points = self.find_pivot_points(df)
                
                self.manage_active_positions()
                
                if result:
                    print(f"\n[{current_time.strftime('%H:%M:%S')}] SENSITIVE DETECTION")
                    print("-" * 60)
                    print(f"Direction: {result['direction']}")
                    print(f"Buyer Score: {result['buyer_score']:.3f} (Max: 1.000)")
                    print(f"Seller Score: {result['seller_score']:.3f} (Max: 1.000)")
                    print(f"Score Difference: {abs(result['buyer_score'] - result['seller_score']):.3f}")
                    print(f"Current Price: {result['current_price']:.1f}")
                    print(f"5-Min Price Change: {result['price_change_5min']:+.1f} points")
                    print(f"At Peak: {result.get('at_peak', False)} | At Trough: {result.get('at_trough', False)}")
                    
                    # Pivot Points
                    if pivot_points:
                        print(f"\n[PIVOT POINTS ANALYSIS]")
                        print("-" * 60)
                        current_price = result['current_price']
                        if pivot_points['prev_support']:
                            print(f"Previous Support: {pivot_points['prev_support']:.1f} (Distance: +{pivot_points['support_distance']:.1f} points)")
                        if pivot_points['next_resistance']:
                            print(f"Next Resistance: {pivot_points['next_resistance']:.1f} (Distance: {pivot_points['resistance_distance']:.1f} points)")
                        print(f"Current Price: {current_price:.1f}")
                    
                    # Method Breakdown
                    print(f"\nMethod Breakdown (DEBUG):")
                    total_buyer_contribution = 0
                    total_seller_contribution = 0
                    weights = {
                        'immediate_momentum': 0.30,
                        'volume_price_trend': 0.15, 
                        'operator_activity': 0.15,
                        'price_velocity': 0.15,
                        'candle_body_analysis': 0.10,
                        'movement_diversion': 0.08,
                        'momentum_divergence': 0.05,
                        'support_resistance': 0.02
                    }
                    
                    for method, data in result['methods'].items():
                        # Skip methods with different structure
                        if method in ['consolidation', 'trend_strength']:
                            continue
                        
                        weight = weights.get(method, 0)
                        contribution = data.get('confidence', 0) * weight if data.get('direction', 'NEUTRAL') != 'NEUTRAL' else 0
                        
                        if data.get('direction') == 'BUYERS':
                            total_buyer_contribution += contribution
                            indicator = "🟢 BUYERS"
                        elif data.get('direction') == 'SELLERS':
                            total_seller_contribution += contribution
                            indicator = "🔴 SELLERS"
                        else:
                            indicator = "⚪ NEUTRAL"
                        
                        extra = ""
                        if method == 'movement_diversion' and 'type' in data:
                            extra = f" - {data['type']}"
                        elif method == 'operator_activity' and 'signals' in data:
                            extra = f" - {', '.join(data['signals']) if data['signals'] else 'NONE'}"
                        
                        print(f"  {method}: {indicator} ({data.get('confidence', 0):.2f}) Weight:{weight:.0%} Contrib:{contribution:.3f}{extra}")
                    
                    # Dominance Summary
                    if total_buyer_contribution > total_seller_contribution:
                        overall = f"🟢 BUYERS DOMINATING ({total_buyer_contribution:.3f} vs {total_seller_contribution:.3f})"
                    elif total_seller_contribution > total_buyer_contribution:
                        overall = f"🔴 SELLERS DOMINATING ({total_seller_contribution:.3f} vs {total_buyer_contribution:.3f})"
                    else:
                        overall = f"⚪ BALANCED MARKET ({total_buyer_contribution:.3f} vs {total_seller_contribution:.3f})"
                    
                    print(f"\n[DOMINANCE SUMMARY] {overall}")
                    print(f"\n[SCORE DEBUG]")
                    print(f"Total Buyer Contribution: {total_buyer_contribution:.3f}")
                    print(f"Total Seller Contribution: {total_seller_contribution:.3f}")
                    print(f"Actual Buyer Score: {result['buyer_score']:.3f}")
                    print(f"Actual Seller Score: {result['seller_score']:.3f}")
                    
                    # Trade Scoring System
                    trade_score = self.calculate_trade_score(result, trend_filter)
                    
                    print(f"\n[TRADE SCORING SYSTEM]")
                    print("=" * 105)
                    print(f"| {'COMPONENT':<35} | {'STATUS':<8} | {'VALUE':<12} | {'SCORE':<8} | {'MAX PTS':<8} | {'CONTRIB':<8} |")
                    print("|" + "-" * 103 + "|")
                    
                    for category, score_data in trade_score['breakdown'].items():
                        status = "PASS" if score_data['achieved'] else "FAIL"
                        status_icon = "✅" if score_data['achieved'] else "❌"
                        
                        current = score_data['current']
                        required = score_data['required']
                        
                        # Handle value display
                        if category == 'Consolidation (ATR)':
                             value_display = f"{current:.1f}% (<0.25)"
                        elif category == 'Market Timing':
                             value_display = f"{current:.0f}h"
                        else:
                             value_display = f"{current:.2f} (>{required})"

                        points = score_data['percentage']
                        max_points = score_data.get('max_points', 0)
                        
                        # Handle Max Points for penalty
                        max_pts_display = str(max_points)
                        if max_points == 0 and points < 0:
                             max_pts_display = "0 (PEN)"
                        
                        print(f"| {category:<35} | {status_icon} {status:<4} | {value_display:<12} | {points:>6.1f}   | {max_pts_display:<8} | {points:>7.1f}% |")
                    
                    print("=" * 105)
                    
                    print(f"\nTOTAL TRADE SCORE: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%)")
                    print(f"TRADE THRESHOLD: 65/100 (65%) for signal generation")
                    print(f"TRADE SIGNAL: {trade_score['signal']}")
                    
                    min_trade_score = 65
                    if trade_score['total_score'] >= min_trade_score:
                        print(f"\n[TRADE APPROVED] Score: {trade_score['total_score']:.1f}/100")
                        
                        price_velocity_data = result['methods'].get('price_velocity', {'direction': 'NEUTRAL', 'confidence': 0})
                        velocity_direction = price_velocity_data['direction']
                        velocity_confidence = price_velocity_data['confidence']
                        
                        alert_direction = velocity_direction if (velocity_confidence > 0.5 and velocity_direction in ['BUYERS', 'SELLERS']) else trade_score['direction']
                        if alert_direction == 'BUYERS': alert_direction = 'BUY'
                        elif alert_direction == 'SELLERS': alert_direction = 'SELL'
                        
                        self.print_quick_alert(alert_direction, result['current_price'])
                        
                        if len(self.active_positions) == 0:
                            # Determine signal type (CE or PE)
                            if velocity_direction == 'BUYERS' and velocity_confidence > 0.5:
                                new_signal_type = 'CE'
                            elif velocity_direction == 'SELLERS' and velocity_confidence > 0.5:
                                new_signal_type = 'PE'
                            else:
                                new_signal_type = None
                            
                            if new_signal_type:
                                # RSI Validation - Check if trade is valid
                                is_consolidating = result.get('is_consolidating', False)
                                rsi_validation = self.validate_trade_with_rsi(new_signal_type, df, is_consolidating)
                                
                                # Print RSI Validation Results
                                print(f"\n[RSI VALIDATION]")
                                print("=" * 50)
                                print(f"Last Trade: {rsi_validation.get('last_trade_type', 'None')}")
                                print(f"New Signal: {rsi_validation.get('new_signal_type', new_signal_type)}")
                                print(f"RSI Value: {rsi_validation.get('rsi_value', 0)}")
                                print(f"RSI Required: {'Yes' if rsi_validation.get('rsi_required', False) else 'No'}")
                                print(f"Validation: {rsi_validation.get('reason', 'UNKNOWN')}")
                                print(f"Trade Valid: {'✅ YES' if rsi_validation.get('is_valid', False) else '❌ NO'}")
                                
                                # ADX + RSI Combo Validation
                                adx_rsi_validation = self.validate_adx_rsi_combo(df, new_signal_type)
                                
                                print(f"\n[ADX + RSI COMBO VALIDATION]")
                                print("=" * 50)
                                print(f"ADX Value: {adx_rsi_validation.get('adx_value', 0)}")
                                print(f"ADX Last 3 Candles: {adx_rsi_validation.get('adx_last_3', [])}")
                                print(f"ADX Sustained (>25 for 3 candles): {'✅ YES' if adx_rsi_validation.get('adx_valid', False) else '❌ NO'}")
                                print(f"RSI Value: {adx_rsi_validation.get('rsi_value', 0)}")
                                print(f"RSI Zone: {adx_rsi_validation.get('rsi_zone', 'UNKNOWN')}")
                                print(f"RSI Valid (30-70 range): {'✅ YES' if adx_rsi_validation.get('rsi_valid', False) else '❌ NO'}")
                                print(f"Combo Valid: {'✅ YES' if adx_rsi_validation.get('is_valid', False) else '❌ NO'}")
                                
                                # Both validations must pass
                                if rsi_validation.get('is_valid', False) and adx_rsi_validation.get('is_valid', False):
                                    # Trade is valid - Execute
                                    if new_signal_type == 'CE':
                                        print(f"\n[AUTO TRADE] BUYERS Velocity ({velocity_confidence:.2f}) → BUY CALL (CE)")
                                        self.execute_trade('BUY', trade_score['total_score'], result['current_price'])
                                    else:
                                        print(f"\n[AUTO TRADE] SELLERS Velocity ({velocity_confidence:.2f}) → BUY PUT (PE)")
                                        self.execute_trade('SELL', trade_score['total_score'], result['current_price'])
                                else:
                                    # Trade rejected
                                    reason_msg = "VALIDATION_FAILED"
                                    print(f"\n[TRADE BLOCKED] Validation Failed!")
                                    if not rsi_validation.get('is_valid', False):
                                        reason_msg = rsi_validation.get('reason', 'RSI_INVALID')
                                        print(f"   ❌ RSI Validation Failed: {rsi_validation.get('reason', 'UNKNOWN')}")
                                    
                                    if not adx_rsi_validation.get('is_valid', False):
                                        # Update reason if ADX also failed or is the primary failure
                                        if reason_msg == "VALIDATION_FAILED" or "RSI" not in reason_msg:
                                            reason_msg = adx_rsi_validation.get('reason', 'ADX_RSI_COMBO_FAILED')
                                        else:
                                            reason_msg += f" | {adx_rsi_validation.get('reason', 'ADX_RSI_COMBO_FAILED')}"
                                        print(f"   ❌ ADX+RSI Combo Failed: {adx_rsi_validation.get('reason', 'UNKNOWN')}")
                                    
                                    # LOG REJECTED TRADE
                                    details = {
                                        'score': trade_score['total_score'],
                                        'direction': result['direction'],
                                        'signal_type': new_signal_type,
                                        'velocity': velocity_confidence,
                                        'rsi': rsi_validation.get('rsi_value', 0),
                                        'adx': adx_rsi_validation.get('adx_value', 0)
                                    }
                                    self.log_rejected_trade(f"BLOCK_{reason_msg}", details)

                            else:
                                print(f"[NO TRADE] Velocity conditions not met: {velocity_direction} ({velocity_confidence:.2f})")
                                print(f"  Need: BUYERS or SELLERS with confidence > 0.5")
                                # LOG REJECTED TRADE
                                # LOG REJECTED TRADE
                                # Calculate extra stats
                                try:
                                    current_rsi = df.iloc[-1].get('rsi_14', 0) if not df.empty else 0
                                    current_adx = df.iloc[-1].get('adx', 0) if not df.empty else 0
                                except:
                                    current_rsi = 0
                                    current_adx = 0

                                details = {
                                    'score': trade_score['total_score'],
                                    'direction': result['direction'],
                                    'velocity_direction': velocity_direction,
                                    'velocity': velocity_confidence,
                                    'signal_type': 'N/A', # Velocity condition failed, so no signal type
                                    'rsi': current_rsi,
                                    'adx': current_adx
                                }
                                self.log_rejected_trade("BLOCK_VELOCITY_NEUTRAL", details)
                        else:
                            print(f"\n[AUTO TRADE SKIPPED] Position already active")
                        
                        self.generate_trade_recommendation(result, trade_score, pivot_points)
                    else:
                        print(f"\n[TRADE REJECTED] Score: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%) - Need 65%+")
                        print(f"   Missing {65 - trade_score['total_score']:.1f} points for 65% trade signal")
                        
                        # LOG REJECTED TRADE
                        # LOG REJECTED TRADE
                        # Calculate missing details for logging
                        try:
                            # 1. Velocity
                            pv_data = result['methods'].get('price_velocity', {'direction': 'NEUTRAL', 'confidence': 0})
                            vel_conf = pv_data.get('confidence', 0)
                            vel_dir = pv_data.get('direction', 'NEUTRAL')
                            
                            # 2. RSI & ADX
                            current_rsi = df.iloc[-1].get('rsi_14', 0) if not df.empty else 0
                            current_adx = df.iloc[-1].get('adx', 0) if not df.empty else 0
                            
                            # 3. Signal Type
                            sig_type = 'N/A'
                            if vel_dir == 'BUYERS' and vel_conf > 0.5:
                                sig_type = 'CE'
                            elif vel_dir == 'SELLERS' and vel_conf > 0.5:
                                sig_type = 'PE'
                                
                        except Exception as e:
                            print(f"[LOG ERROR] Stats calculation failed: {e}")
                            vel_conf = 0
                            current_rsi = 0
                            current_adx = 0
                            sig_type = 'N/A'

                        details = {
                            'score': trade_score['total_score'],
                            'required': 65,
                            'direction': result['direction'],
                            'breakdown': str(trade_score.get('breakdown', {})).replace(',', ';'),
                            'velocity': vel_conf,
                            'rsi': current_rsi,
                            'adx': current_adx,
                            'signal_type': sig_type
                        }
                        self.log_rejected_trade("BLOCK_LOW_SCORE", details)
                        
                        if result['direction'] == 'BALANCED':
                            print(f"\n[NEUTRAL] MARKET BALANCED - Wait for clearer direction")
                    
                    # Show active positions
                    if self.active_positions:
                        print(f"\n[MONITORING] {len(self.active_positions)} active trades...")
                
                time.sleep(8)
                
            except KeyboardInterrupt:
                print("\n[INFO] Detection stopped by user")
                break
            except Exception as e:
                print(f"[ERROR] Detection error: {e}")
                time.sleep(5)


def main():
    detector = EnhancedBuyerSellerDetectionUpstox()
    if detector.session_generated:
        detector.run_sensitive_detection()
    else:
        print("[ERROR] Failed to connect")


if __name__ == "__main__":
    main()
