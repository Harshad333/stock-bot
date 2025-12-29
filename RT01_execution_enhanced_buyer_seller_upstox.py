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
from openpyxl import Workbook, load_workbook

class EnhancedBuyerSellerDetectionUpstox:
    def __init__(self):
        # Upstox Credentials (from fetch_account_balance_upstox.py)
        self.API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
        self.API_SECRET = "gs1ge527c7"
        self.REDIRECT_URI = "https://account.upstox.com/developer/apps/createapp"
        self.ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0TkNUUFEiLCJqdGkiOiI2OTUyM2Y2NmEyNWJmMTZmNjE1YTg1ODAiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk5Nzg2MiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.Vw7j3I1LtPlX9Zu-_XhHKKe8k06rc8uxj-O_B612CrU"
        
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
        self.current_trade_row = None
        self.fast_contract_map = {}
        self.option_chain_data = None
        
        self.connect()
        
        # Auto-refresh token if not connected
        if not self.session_generated:
            print("\n⚠️ Not connected. Starting auto token refresh...")
            self._refresh_token()
        
        if self.session_generated:
            self.display_funds()
            threading.Thread(target=self.download_instrument_master).start()
            self.sync_state_from_broker()
    
    def connect(self):
        """Connect to Upstox using OAuth2 Access Token"""
        try:
            configuration = upstox_client.Configuration()
            
            if self.ACCESS_TOKEN and self.ACCESS_TOKEN != "YOUR_ACCESS_TOKEN":
                configuration.access_token = self.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(configuration)
                
                # Verify token by making a test API call
                try:
                    api_instance = upstox_client.UserApi(self.api_client)
                    api_response = api_instance.get_profile(api_version='2.0')
                    if api_response and api_response.status == 'success':
                        self.session_generated = True
                        print("[SUCCESS] Enhanced Detection System (UPSTOX) Connected!")
                    else:
                        print("[WARN] Token may be invalid. Will auto-refresh...")
                        self.session_generated = False
                except Exception as e:
                    if "401" in str(e) or "Unauthorized" in str(e):
                        print("[WARN] Token expired (401). Will auto-refresh...")
                    else:
                        print(f"[WARN] Token verification failed: {e}")
                    self.session_generated = False
            else:
                print("[ERROR] No Access Token provided.")
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
            'operator_activity': self.detect_operator_activity(df)
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
            'at_trough': current_trough
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
        
        return df
    
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
                'percentage': velocity_score, 'achieved': price_velocity > 0.65
            }
            total_score += velocity_score
            
            # Dominance (15 points)
            dominance_score = 15 if dominant_score > 0.13 else 0
            score_breakdown['Buyer/Seller Dominance (>0.13)'] = {
                'current': dominant_score, 'required': 0.13,
                'percentage': dominance_score, 'achieved': dominant_score > 0.13
            }
            total_score += dominance_score
            
            # Candle (10 points)
            candle_data = result['methods'].get('candle_body_analysis', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            candle_confidence = candle_data['confidence']
            candle_score = 10 if (candle_confidence > 0.6 and candle_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Candle Body Analysis (>0.6)'] = {
                'current': candle_confidence, 'required': 0.6,
                'percentage': candle_score, 'achieved': candle_confidence > 0.6
            }
            total_score += candle_score
            
            # Diversion (10 points)
            diversion_data = result['methods'].get('movement_diversion', {'confidence': 0.5, 'type': 'NO_DIVERGENCE'})
            diversion_type = diversion_data.get('type', 'NO_DIVERGENCE')
            diversion_confidence = diversion_data['confidence']
            diversion_score = 10 if ('DIVERGENCE' in diversion_type and diversion_confidence > 0.65) else 0
            score_breakdown['Movement Diversion'] = {
                'current': diversion_confidence, 'required': 0.65,
                'percentage': diversion_score, 'achieved': 'DIVERGENCE' in diversion_type
            }
            total_score += diversion_score
            
            # Operator (10 points)
            operator_data = result['methods'].get('operator_activity', {'operator_score': 0, 'direction': 'NEUTRAL'})
            operator_score_raw = operator_data.get('operator_score', 0)
            operator_score = 10 if (operator_score_raw > 0.6 and operator_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Operator Activity'] = {
                'current': operator_score_raw, 'required': 0.6,
                'percentage': operator_score, 'achieved': operator_score_raw > 0.6
            }
            total_score += operator_score
            
            # Volume (8 points)
            volume_data = result['methods'].get('volume_price_trend', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            volume_confidence = volume_data['confidence']
            volume_score = 8 if (volume_confidence > 0.55 and volume_data['direction'] != 'NEUTRAL') else 0
            score_breakdown['Volume Momentum'] = {
                'current': volume_confidence, 'required': 0.55,
                'percentage': volume_score, 'achieved': volume_confidence > 0.55
            }
            total_score += volume_score
            
            # Timing (7 points)
            current_time = datetime.datetime.now()
            market_hour = current_time.hour
            prime_time = (9 <= market_hour < 11) or (13 <= market_hour < 15)
            timing_score = 7 if prime_time else 0
            score_breakdown['Market Timing'] = {
                'current': market_hour, 'required': 10,
                'percentage': timing_score, 'achieved': prime_time
            }
            total_score += timing_score
            
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
                        weight = weights.get(method, 0)
                        contribution = data['confidence'] * weight if data['direction'] != 'NEUTRAL' else 0
                        
                        if data['direction'] == 'BUYERS':
                            total_buyer_contribution += contribution
                            indicator = "🟢 BUYERS"
                        elif data['direction'] == 'SELLERS':
                            total_seller_contribution += contribution
                            indicator = "🔴 SELLERS"
                        else:
                            indicator = "⚪ NEUTRAL"
                        
                        extra = ""
                        if method == 'movement_diversion' and 'type' in data:
                            extra = f" - {data['type']}"
                        elif method == 'operator_activity' and 'signals' in data:
                            extra = f" - {', '.join(data['signals']) if data['signals'] else 'NONE'}"
                        
                        print(f"  {method}: {indicator} ({data['confidence']:.2f}) Weight:{weight:.0%} Contrib:{contribution:.3f}{extra}")
                    
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
                    print("=" * 50)
                    for category, score_data in trade_score['breakdown'].items():
                        status = "[PASS]" if score_data['achieved'] else "[FAIL]"
                        print(f"{status} {category}: {score_data['current']:.1f}/{score_data['required']:.1f} ({score_data['percentage']:.1f}%)")
                    
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
                            if velocity_direction == 'BUYERS' and velocity_confidence > 0.5:
                                print(f"[AUTO TRADE] BUYERS Velocity ({velocity_confidence:.2f}) → BUY CALL (CE)")
                                self.execute_trade('BUY', trade_score['total_score'], result['current_price'])
                            elif velocity_direction == 'SELLERS' and velocity_confidence > 0.5:
                                print(f"[AUTO TRADE] SELLERS Velocity ({velocity_confidence:.2f}) → BUY PUT (PE)")
                                self.execute_trade('SELL', trade_score['total_score'], result['current_price'])
                            else:
                                print(f"[NO TRADE] Velocity conditions not met: {velocity_direction} ({velocity_confidence:.2f})")
                                print(f"  Need: BUYERS or SELLERS with confidence > 0.5")
                        else:
                            print(f"\n[AUTO TRADE SKIPPED] Position already active")
                        
                        self.generate_trade_recommendation(result, trade_score, pivot_points)
                    else:
                        print(f"\n[TRADE REJECTED] Score: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%) - Need 65%+")
                        print(f"   Missing {65 - trade_score['total_score']:.1f} points for 65% trade signal")
                        
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

