"""
Upstox Account Balance Fetcher
Fetches account funds/balance from Upstox trading account
Replaces Angel One logic with Upstox API
"""

from datetime import datetime, timedelta
import pandas as pd
import upstox_client
from upstox_client.rest import ApiException
import requests
import json
import os
import time
import gzip
import sys
import math
import webbrowser
from openpyxl import load_workbook

class UpstoxAccountFetcher:
    def __init__(self):
        # Upstox Credentials
        # REPLACE THESE WITH YOUR ACTUAL UPSTOX CREDENTIALS
        self.API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
        self.API_SECRET = "2on3ns8j9a"
        self.REDIRECT_URI = "https://account.upstox.com/developer/apps/createapp"
        self.ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBQzY3MjciLCJqdGkiOiI2OTUyMGZjOTdmNWZjYjBjNGFkZmNmNmIiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk4NTY3MywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.j7uPFjzzN58ZMiXhapuzZ_-zyPHBv9bMztxfrulYxWk"  # If you already have a valid token
        
        self.api_client = None
        self.session_generated = False
        self.instrument_df = None
        
        self.connect()
    
    def connect(self):
        """Connect to Upstox"""
        try:
            # Configure OAuth2 access token for authorization: OAUTH2
            configuration = upstox_client.Configuration()
            
            # If plain access token is provided, use it
            if self.ACCESS_TOKEN and self.ACCESS_TOKEN != "YOUR_ACCESS_TOKEN":
                configuration.access_token = self.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(configuration)
                self.session_generated = True
                print("✅ [SUCCESS] Connected to Upstox (using provided Access Token)!")
            else:
                # Login flow (Manual for now as Upstox requires 2FA compliant login flow)
                print("⚠️  [WARNING] No Access Token provided.")
                print(f"Please generate an access token using your API Key: {self.API_KEY}")
                print(f"1. Visit: https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={self.API_KEY}&redirect_uri={self.REDIRECT_URI}")
                print("2. Login and get the 'code' from the URL")
                
                code = input("Enter the code from URL: ").strip()
                
                if code:
                    # Exchange code for access token
                    url = 'https://api.upstox.com/v2/login/authorization/token'
                    headers = {
                        'accept': 'application/json',
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }
                    data = {
                        'code': code,
                        'client_id': self.API_KEY,
                        'client_secret': self.API_SECRET,
                        'redirect_uri': self.REDIRECT_URI,
                        'grant_type': 'authorization_code',
                    }
                    
                    response = requests.post(url, headers=headers, data=data)
                    json_response = response.json()
                    
                    if 'access_token' in json_response:
                        self.ACCESS_TOKEN = json_response['access_token']
                        configuration.access_token = self.ACCESS_TOKEN
                        self.api_client = upstox_client.ApiClient(configuration)
                        self.session_generated = True
                        print("✅ [SUCCESS] Connected to Upstox!")
                        print(f"🔑 Access Token (Save this): {self.ACCESS_TOKEN}")
                    else:
                        print(f"❌ [ERROR] Login failed: {json_response}")
                else:
                    print("❌ [ERROR] No code provided")

        except Exception as e:
            print(f"❌ [ERROR] Connection failed: {e}")
    
    def refresh_token(self):
        """Refresh the access token by going through OAuth flow"""
        print("\n" + "="*60)
        print("  🔑 TOKEN REFRESH")
        print("="*60)
        
        # Generate authorization URL
        auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={self.API_KEY}&redirect_uri={self.REDIRECT_URI}"
        
        print("\n📋 Opening authorization URL in browser...")
        print(f"\n🔗 If browser doesn't open, visit this URL:")
        print(f"   {auth_url}")
        
        # Try to open browser
        try:
            webbrowser.open(auth_url)
            print("\n✅ Browser opened!")
        except:
            print("\n⚠️  Could not open browser automatically.")
        
        print("\n" + "-"*60)
        print("After login, copy the 'code' from the redirect URL")
        print("-"*60)
        
        code = input("\n🔐 Paste the code: ").strip()
        
        if not code:
            print("❌ No code provided.")
            return False
        
        # Exchange code for token
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
                
                # Update API client with new token
                configuration = upstox_client.Configuration()
                configuration.access_token = self.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(configuration)
                self.session_generated = True
                
                print("\n✅ Token refreshed successfully!")
                print(f"\n🔑 New Token:\n{self.ACCESS_TOKEN}")
                
                # Auto-update the script file
                self._update_token_in_file(self.ACCESS_TOKEN)
                
                return True
            else:
                print(f"\n❌ Error: {result}")
                return False
                
        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return False
    
    def _update_token_in_file(self, new_token):
        """Update ACCESS_TOKEN in this script file"""
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
            
            print(f"\n💾 Token saved to script file!")
        except Exception as e:
            print(f"\n⚠️ Could not auto-save token: {e}")
            print("   Please manually update ACCESS_TOKEN in the script.")
    
    def get_funds(self):
        """Fetch account funds/balance from Upstox"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Upstox")
            return None
        
        try:
            api_instance = upstox_client.UserApi(self.api_client)
            # Fetch funds for Equity/SEC segment
            api_response = api_instance.get_user_fund_margin(api_version='2.0', segment='SEC')
            
            if api_response and api_response.status == 'success':
                funds_data = api_response.data
                
                print("\n" + "="*60)
                print("💰 UPSTOX ACCOUNT BALANCE")
                print("="*60)
                print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-"*60)
                
                # Extract details
                # It seems funds_data might be a dict or object depending on serialization
                # The error said 'dict' object has no attribute 'equity'
                
                if isinstance(funds_data, dict):
                     equity_funds = funds_data.get('equity')
                else:
                     equity_funds = getattr(funds_data, 'equity', None)
                
                if equity_funds:
                     available_cash = getattr(equity_funds, 'available_margin', 0)
                     used_margin = getattr(equity_funds, 'used_margin', 0)
                     payin = getattr(equity_funds, 'payin_amount', 0)
                     span_margin = getattr(equity_funds, 'span_margin', 0)
                     exposure_margin = getattr(equity_funds, 'exposure_margin', 0)
                else:
                     available_cash = 0
                     used_margin = 0
                     payin = 0
                     span_margin = 0
                     exposure_margin = 0

                print(f"💵 Available Margin   : ₹{available_cash}")
                print(f"📊 Used Margin        : ₹{used_margin}")
                print(f"📥 Payin Amount       : ₹{payin}")
                print(f"📉 Span Margin        : ₹{span_margin}")
                print(f"📈 Exposure Margin    : ₹{exposure_margin}")
                
                print("-"*60)
                print("="*60)
                
                return {
                    'availablecash': available_cash,
                    'net': available_cash, 
                    'utiliseddebits': used_margin
                }
            else:
                print(f"❌ [ERROR] Failed to fetch funds")
                return None
                
        except ApiException as e:
            print(f"❌ [ERROR] Exception while fetching funds: {e}")
            return None
    
    def get_profile(self):
        """Fetch user profile details"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Upstox")
            return None
        
        try:
            api_instance = upstox_client.UserApi(self.api_client)
            api_response = api_instance.get_profile(api_version='2.0')
            
            if api_response and api_response.status == 'success':
                profile_data = api_response.data
                
                print("\n" + "="*60)
                print("👤 USER PROFILE")
                print("="*60)
                
                # Use getattr with defaults to safely access fields
                print(f"📛 Name      : {getattr(profile_data, 'user_name', 'N/A')}")
                print(f"📧 Email     : {getattr(profile_data, 'email', 'N/A')}")
                print(f"📱 Mobile    : {getattr(profile_data, 'mobile', getattr(profile_data, 'phone', 'N/A'))}")
                print(f"🆔 Client ID : {getattr(profile_data, 'user_id', 'N/A')}")
                print(f"🏢 Broker    : Upstox")
                print(f"💹 Exchanges : {getattr(profile_data, 'exchanges', 'N/A')}")
                
                print("="*60)
                
                return profile_data
            else:
                print(f"❌ [ERROR] Failed to fetch profile")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching profile: {e}")
            return None
    
    def get_holdings(self):
        """Fetch current long term holdings"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Upstox")
            return None
        
        try:
            api_instance = upstox_client.PortfolioApi(self.api_client)
            api_response = api_instance.get_holdings(api_version='2.0')
            
            if api_response and api_response.status == 'success':
                holdings_data = api_response.data
                
                print("\n" + "="*60)
                print("📊 PORTFOLIO HOLDINGS")
                print("="*60)
                
                if holdings_data:
                    total_value = 0
                    total_pnl = 0
                    
                    for holding in holdings_data:
                        symbol = holding.trading_symbol
                        qty = holding.quantity
                        avg_price = float(holding.average_price)
                        ltp = float(holding.last_price)
                        pnl = float(holding.pnl)
                        current_value = ltp * qty
                        
                        total_value += current_value
                        total_pnl += pnl
                        
                        print(f"\n📌 {symbol}")
                        print(f"   Qty: {qty} | Avg: ₹{avg_price:.2f} | LTP: ₹{ltp:.2f}")
                        print(f"   Value: ₹{current_value:.2f} | P&L: ₹{pnl:.2f}")
                    
                    print("\n" + "-"*60)
                    print(f"💼 Total Portfolio Value : ₹{total_value:.2f}")
                    print(f"📈 Total P&L             : ₹{total_pnl:.2f}")
                else:
                    print("📭 No holdings found in portfolio")
                
                print("="*60)
                
                return holdings_data
            else:
                print(f"❌ [ERROR] Failed to fetch holdings")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching holdings: {e}")
            return None
    
    def get_positions(self):
        """Fetch current open positions"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Upstox")
            return None
        
        try:
            api_instance = upstox_client.PortfolioApi(self.api_client)
            api_response = api_instance.get_positions(api_version='2.0')
            
            if api_response and api_response.status == 'success':
                positions_data = api_response.data
                
                print("\n" + "="*60)
                print("📈 OPEN POSITIONS")
                print("="*60)
                
                if positions_data:
                    for pos in positions_data:
                        symbol = pos.trading_symbol
                        qty = pos.quantity
                        buy_val = float(pos.buy_amount)
                        sell_val = float(pos.sell_amount)
                        pnl = float(pos.pnl)
                        
                        print(f"\n📌 {symbol}")
                        print(f"   Net Qty: {qty} | Buy Val: ₹{buy_val:.2f} | Sell Val: ₹{sell_val:.2f}")
                        print(f"   P&L: ₹{pnl:.2f}")
                else:
                    print("📭 No open positions found")
                
                print("="*60)
                
                return positions_data
            else:
                print(f"❌ [ERROR] Failed to fetch positions")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching positions: {e}")
            return None
    
    def get_complete_account_summary(self):
        """Get complete account summary"""
        print("\n" + "🔄"*30)
        print("  FETCHING COMPLETE ACCOUNT SUMMARY (UPSTOX)")
        print("🔄"*30)
        
        self.get_profile()
        funds = self.get_funds()
        self.get_holdings()
        self.get_positions()
        
        return funds
    
    # =========================================================================
    # OPTION CHAIN / INSTRUMENTS Logic for UPSTOX
    # =========================================================================
    
    def download_instrument_master(self):
        """Download instrument master from Upstox (NSE & NFO)"""
        try:
            print("🔄 Downloading Instrument Keys (this might take a while)...")
            # For Upstox, instruments are in separate files. We need NSE_FO for Options and NSE_EQ for Index LTP
            
            # 1. Download NSE FO (Futures & Options)
            url_fo = "https://assets.upstox.com/feed/instruments/NSE_FO.json.gz"
            # 2. Download NSE EQ (Indices like NIFTY 50 are here or in Index dataset)
            # Actually Upstox has 'NSE_INDEX' usually or part of NSE_EQ.
            # Let's try to get 'instrument keys' via an API if possible or download the big file.
            # Using the JSON file is standard recommendations.
            
            # Using a simplified approach: Download and keep in memory (Might be large)
            # Better: use a temporary file or filter while streaming if possible. 
            # For this script we will download NSE_FO.json.gz
            
            # Check if file exists to save bandwidth (basic caching)
            fo_file = "NSE_FO.json"
            
            # We will use pandas to read json
            # Note: Upstox files are .json.gz
            
            import gzip
            import shutil
            
            # Simple caching mechanism
            if os.path.exists(fo_file) and (datetime.now().timestamp() - os.path.getmtime(fo_file) < 86400):
                print("✅ Using cached Instrument Master")
                with open(fo_file, 'r') as f:
                    data = json.load(f)
            else:
                 # Download NSE_FO
                 print("⬇️ Downloading NSE_FO.json.gz...")
                 headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
                 r = requests.get(url_fo, headers=headers)
                 if r.status_code == 200:
                     # Decompress
                     data = json.loads(gzip.decompress(r.content))
                     # Save for cache
                     with open(fo_file, 'w') as f:
                         json.dump(data, f)
                 else:
                     print(f"❌ Failed to download instrument file (Status: {r.status_code})")
                     print(f"⚠️  Detailed Error: {r.text[:100]}")
                     print(f"💡 ACTION REQUIRED: Please manually download the file from:")
                     print(f"   {url_fo}")
                     print(f"   And save it as '{fo_file}' in the current directory.")
                     return False

            self.instrument_df = pd.DataFrame(data)
            
            # Filter for NIFTY Options
            # Upstox structure: { 'instrument_key': ..., 'trading_symbol': ..., 'name': 'NIFTY', ... }
            
            print(f"✅ [SUCCESS] Instrument Master loaded: {len(self.instrument_df)} instruments")
            return True
            
        except Exception as e:
            print(f"❌ [ERROR] Instrument master download failed: {e}")
            return False

    def get_nifty_ltp(self):
        """Get current NIFTY 50 LTP"""
        try:
            # We need the instrument key for NIFTY 50. Usually 'NSE_INDEX|Nifty 50'
            instrument_key = "NSE_INDEX|Nifty 50"
            
            api_instance = upstox_client.MarketQuoteApi(self.api_client)
            api_response = api_instance.ltp(instrument_key, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                data = api_response.data
                # structure: {'NSE_INDEX:Nifty 50': {'last_price': 24000.0, ...}}
                # Upstox might return key with colon or pipe
                
                # Try exact match first
                if instrument_key in data:
                    return float(data[instrument_key].last_price)
                
                # Try colon version
                alt_key = instrument_key.replace('|', ':')
                if alt_key in data:
                    return float(data[alt_key].last_price)
                    
                # Fallback: return first item
                if data:
                    return float(list(data.values())[0].last_price)

            return None
        except Exception as e:
            print(f"❌ [ERROR] Failed to get NIFTY LTP: {e}")
            return None


    def get_nifty_option_chain(self):
        """Fetch NIFTY option chain via API (No file download needed)"""
        try:
           url = "https://api.upstox.com/v2/option/contract"
           params = {"instrument_key": "NSE_INDEX|Nifty 50"}
           headers = {
               "Authorization": f"Bearer {self.ACCESS_TOKEN}",
               "Accept": "application/json"
           }
           
           print("🔄 Fetching Option Chain from API...")
           response = requests.get(url, headers=headers, params=params)
           
           if response.status_code == 200:
               data = response.json()
               if 'data' in data:
                   self.option_chain_data = data['data']
                   print(f"✅ Loaded {len(self.option_chain_data)} option contracts")
                   return True
           
           print(f"❌ Failed to fetch option chain: {response.text}")
           return False
           
        except Exception as e:
            print(f"❌ [ERROR] Option chain fetch failed: {e}")
            return False

    def find_option_contract(self, strike, option_type):
        """Find option contract for given strike and type (CE/PE)"""
        try:
            if not hasattr(self, 'option_chain_data') or not self.option_chain_data:
                if not self.get_nifty_option_chain():
                    return None
            
            # Filter logic using dict list instead of DataFrame
            today = datetime.now().date()
            
            candidates = []
            for contract in self.option_chain_data:
                # Check strike and type
                if contract.get('strike_price') == float(strike) and \
                   contract.get('instrument_type') == option_type:
                       
                       expiry_str = contract.get('expiry') # YYYY-MM-DD
                       if expiry_str:
                           exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                           if exp_date >= today:
                               candidates.append({
                                   'contract': contract,
                                   'expiry': exp_date
                               })
                               
            if not candidates:
                print(f"❌ No contract found for {strike} {option_type}")
                return None
            
            # Sort by expiry (nearest first)
            candidates.sort(key=lambda x: x['expiry'])
            
            best = candidates[0]['contract']
            expiry_date = candidates[0]['expiry']
            
            print(f"✅ Found: {best['trading_symbol']} (Expiry: {expiry_date})")
            
            return {
                'symbol': best['trading_symbol'],
                'token': best['instrument_key'],
                'strike': strike,
                'expiry': expiry_date,
                'lot_size': best.get('lot_size', 1)
            }
            
        except Exception as e:
             print(f"❌ [ERROR] Finding option contract failed: {e}")
             return None

    # ... (skipping some lines to option_chain_buy)



    def get_option_ltp(self, symbol, token):
        """Get LTP using instrument key"""
        try:
            api_instance = upstox_client.MarketQuoteApi(self.api_client)
            api_response = api_instance.ltp(token, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                data = api_response.data
                
                if token in data:
                    return float(data[token].last_price)
                
                alt_key = token.replace('|', ':')
                if alt_key in data:
                    return float(data[alt_key].last_price)
                
                if data:
                    return float(list(data.values())[0].last_price)
            return None
        except Exception as e:
            print(f"❌ [ERROR] Failed to get option LTP: {e}")
            return None

    def place_option_order(self, symbol, token, quantity, order_type="BUY"):
        """Place option order"""
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product='D', # Delivery or I for Intraday? Script used 'INTRADAY'
                validity='DAY',
                price=0.0,
                tag='algo_order',
                instrument_token=token,
                order_type='MARKET',
                transaction_type=order_type,
                disclosed_quantity=0,
                trigger_price=0.0,
                is_amo=False
            )
            
            # Fix Product type
            body.product = 'I' # Intraday
            
            print(f"\n🚀 Placing {order_type} Order: {symbol} Qty: {quantity}")
            
            api_response = api_instance.place_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                order_id = api_response.data.order_id
                print(f"✅ Order Placed! ID: {order_id}")
                return True
            else:
                print(f"❌ Order Failed: {api_response}")
                return False
                
        except Exception as e:
            print(f"❌ [ERROR] Place Order Failed: {e}")
            return False

    def place_stoploss_order_with_id(self, symbol, token, quantity, stoploss_price, trigger_price):
        """Place Stop Loss Limit Order"""
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product='I',
                validity='DAY',
                price=float(stoploss_price),
                trigger_price=float(trigger_price),
                instrument_token=token,
                order_type='SL', # Stop Loss Limit
                transaction_type='SELL', # Assume SL for Buy is Sell
                tag='sl_order',
            )
            
            print(f"\n📉 Placing SL Order: {symbol} @ ₹{stoploss_price} (Trig: {trigger_price})")
            
            api_response = api_instance.place_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                order_id = api_response.data.order_id
                print(f"✅ SL Order Placed! ID: {order_id}")
                return order_id
            else:
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] SL Order Failed: {e}")
            return None

    def place_target_order(self, symbol, token, quantity, target_price):
        """Place Target (Limit) Order"""
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product='I',
                validity='DAY',
                price=float(target_price),
                instrument_token=token,
                order_type='LIMIT',
                transaction_type='SELL',
                tag='target_order',
            )
            
            print(f"\n📈 Placing Target Order: {symbol} @ ₹{target_price}")
            
            api_response = api_instance.place_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                print(f"✅ Target Order Placed! ID: {api_response.data.order_id}")
                return True
            else:
                return False
        except Exception as e:
            print(f"❌ [ERROR] Target Order Failed: {e}")
            return False

    def modify_stoploss_order(self, order_id, symbol, token, quantity, new_price, new_trigger_price):
        """Modify SL Order"""
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            
            body = upstox_client.ModifyOrderRequest(
                quantity=quantity,
                order_id=order_id,
                order_type='SL',
                price=float(new_price),
                trigger_price=float(new_trigger_price),
                validity='DAY',
                disclosed_quantity=0
            )
            
            api_response = api_instance.modify_order(body, api_version='2.0')
            
            if api_response and api_response.status == 'success':
                print(f"✅ SL Modified to ₹{new_price}")
                return True
            return False
            
        except Exception as e:
            print(f"❌ [ERROR] Modify Order Failed: {e}")
            return False

    def get_order_status(self, order_id):
        """Check order status"""
        try:
            api_instance = upstox_client.OrderApi(self.api_client)
            # Fetch order history or details
            # getting order book and finding id is safest
            api_response = api_instance.get_order_details(api_version='2.0', order_id=order_id)
             # Wait, get_order_details returns a list of trails? Or use get_order_book
            
            # Simpler: Get Order History for this ID?
            # get_order_history(order_id)
            
            history_response = api_instance.get_order_history(order_id, api_version='2.0')
            if history_response and history_response.status == 'success':
                # The last element is the latest state
                data = history_response.data
                if data:
                    latest = data[-1]
                    return {
                        'status': latest.status, # e.g. 'complete', 'rejected', 'open'
                        'price': float(latest.execution_price) if latest.execution_price else 0.0,
                    }
            return None
        except Exception as e:
             # print(e)
             return None

    # Trailing Stop Loss Logic (Copied from original, relies on methods above)
    def calculate_trailing_sl(self, entry_price, current_price, current_sl):
        # Same logic as original
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        if profit_percent < 7:
            initial_sl = round(entry_price * 0.90, 2)
            return initial_sl, False
        
        if profit_percent >= 7:
             steps_above_7 = int((profit_percent - 7) / 5)
             locked_profit_percent = 3 + (steps_above_7 * 5)
             new_sl = round(entry_price * (1 + locked_profit_percent / 100), 2)
             if new_sl > current_sl:
                 return new_sl, True
        return current_sl, False

    def trailing_stoploss_monitor(self, symbol, token, quantity, entry_price, sl_order_id):
        # Replicated logic
        print("\n" + "="*60)
        print("  🔄 TRAILING STOP LOSS MONITOR STARTED")
        print("="*60)
        current_sl = round(entry_price * 0.90, 2)
        
        last_profit_milestone = -10
        check_interval = 3
        
        try:
            while True:
                current_price = self.get_option_ltp(symbol, token)
                if not current_price:
                    time.sleep(check_interval)
                    continue
                
                profit_percent = ((current_price - entry_price) / entry_price) * 100
                
                # Check status
                status = self.get_order_status(sl_order_id)
                if status and status['status'] in ['complete', 'filled', 'rejected', 'cancelled']:
                    print("🛑 Order exited or cancelled.")
                    break
                
                new_sl, should_modify = self.calculate_trailing_sl(entry_price, current_price, current_sl)
                
                current_milestone = int(profit_percent / 2) * 2
                if current_milestone != last_profit_milestone:
                     print(f"LTP: {current_price} | Profit: {profit_percent:.2f}% | SL: {current_sl}")
                     last_profit_milestone = current_milestone

                if should_modify:
                    trigger = round(new_sl + 0.05, 2)
                    if self.modify_stoploss_order(sl_order_id, symbol, token, quantity, new_sl, trigger):
                        current_sl = new_sl
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("Monitor stopped.")

    def option_chain_buy(self):
        # Similar flow to original, reusing Upstox methods
        print("\n" + "="*60)
        print("  📈 UPSTOX OPTION CHAIN BUY")
        print("="*60)
        
        nifty_ltp = self.get_nifty_ltp()
        if not nifty_ltp:
            print("❌ NIFTY LTP Failed")
            return
            
        print(f"NIFTY LTP: {nifty_ltp}")
        
        choice = input("1. CALL / 2. PUT: ").strip()
        option_type = "CE" if choice == "1" else "PE" if choice == "2" else None
        
        if not option_type: return
        
        atm = round(nifty_ltp / 50) * 50
        print(f"ATM: {atm}")
        
        strike = input(f"Strike [{atm}]: ").strip()
        strike = int(strike) if strike else atm
        
        contract = self.find_option_contract(strike, option_type)
        if not contract: return
        
        print(f"Found: {contract['symbol']}")
        ltp = self.get_option_ltp(contract['symbol'], contract['token'])
        print(f"Price: {ltp}")
        
        lot_size = int(contract.get('lot_size', 1))
        # Auto-buy with lot size
        print(f"Qty: {lot_size} (Auto-selected)")
        
        if input("Confirm Buy? (y/n): ").lower() == 'y':  
             if self.place_option_order(contract['symbol'], contract['token'], lot_size, "BUY"):
                # Wait + SL Logic could go here (Simplified for now)
                print("Order Sent.")
                
    def find_affordable_options_with_balance(self):
         # Similar logic, just call get_funds
         pass

    def get_option_greeks(self, instrument_key, expiry_date):
        """Fetch option chain with Greeks from Upstox API"""
        try:
            url = "https://api.upstox.com/v2/option/chain"
            params = {
                "instrument_key": instrument_key,
                "expiry_date": expiry_date
            }
            headers = {
                "Authorization": f"Bearer {self.ACCESS_TOKEN}",
                "Accept": "application/json"
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('data', [])
            return None
        except Exception as e:
            print(f"❌ [ERROR] Greeks fetch failed: {e}")
            return None

    def calculate_rho(self, S, K, T, r, sigma, option_type='CE'):
        """
        Calculate Rho using Black-Scholes formula
        S: Spot price (NIFTY LTP)
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (RBI repo rate ~ 6.5% = 0.065)
        sigma: Implied Volatility (as decimal, e.g., 0.06 for 6%)
        option_type: 'CE' for Call, 'PE' for Put
        
        Returns: Rho per 1% change in interest rate
        """
        try:
            if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
                return 0.0
            
            # Calculate d1 and d2
            d1 = (math.log(S / K) + (r + (sigma ** 2) / 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Normal CDF using error function
            def norm_cdf(x):
                return 0.5 * (1 + math.erf(x / math.sqrt(2)))
            
            if option_type == 'CE':
                # Call Rho = K * T * e^(-r*T) * N(d2) / 100 (for 1% rate change)
                rho = (K * T * math.exp(-r * T) * norm_cdf(d2)) / 100
            else:
                # Put Rho = -K * T * e^(-r*T) * N(-d2) / 100
                rho = -(K * T * math.exp(-r * T) * norm_cdf(-d2)) / 100
            
            return rho
        except Exception as e:
            return 0.0

    def live_greeks_monitor(self):
        """Live monitor showing NIFTY, ATM CE/PE with Greeks - refreshes every 5 seconds"""
        print("\n" + "="*80)
        print("  📊 LIVE GREEKS MONITOR (Press Ctrl+C to stop)")
        print("  📁 Data will be saved to 'greeks_data.csv'")
        print("="*80)
        
        # Create date-wise folder for data
        today_str = datetime.now().strftime('%Y-%m-%d')
        data_folder = os.path.join("greeks_data", today_str)
        os.makedirs(data_folder, exist_ok=True)
        
        # Create/Initialize CSV file
        csv_file = os.path.join(data_folder, "greeks_data.csv")
        file_exists = os.path.exists(csv_file)
        
        if not file_exists:
            with open(csv_file, 'w') as f:
                f.write("Timestamp,NIFTY_LTP,ATM_Strike,Expiry,Option,LTP,IV,Delta,Gamma,Theta,Vega,Rho,OI,OI_Change,Volume\n")
            print(f"📁 Created new file: {csv_file}")
        
        try:
            while True:
                # Clear screen effect
                print("\033[2J\033[H", end="")
                
                # Get NIFTY LTP
                nifty_ltp = self.get_nifty_ltp()
                if not nifty_ltp:
                    print("❌ Failed to fetch NIFTY LTP")
                    time.sleep(5)
                    continue
                
                # Calculate ATM strike
                atm = round(nifty_ltp / 50) * 50
                
                # Get nearest expiry from option chain data (already fetched)
                if not hasattr(self, 'option_chain_data') or not self.option_chain_data:
                    self.get_nifty_option_chain()
                
                # Find nearest expiry
                today = datetime.now().date()
                expiries = set()
                for contract in getattr(self, 'option_chain_data', []):
                    exp_str = contract.get('expiry')
                    if exp_str:
                        expiries.add(exp_str)
                
                if expiries:
                    sorted_expiries = sorted(expiries)
                    # Find first expiry >= today
                    expiry_str = sorted_expiries[0]
                    for exp in sorted_expiries:
                        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                        if exp_date >= today:
                            expiry_str = exp
                            break
                else:
                    # Fallback
                    expiry_str = "2025-12-30"
                
                # Fetch option chain with Greeks
                chain_data = self.get_option_greeks("NSE_INDEX|Nifty 50", expiry_str)
                
                print("="*80)
                print(f"  📈 NIFTY 50: ₹{nifty_ltp:.2f}   |   ATM Strike: {atm}   |   Expiry: {expiry_str}")
                print("="*80)
                
                if not chain_data:
                    print("⏳ Fetching Greeks data...")
                    time.sleep(5)
                    continue
                
                # Find ATM CE and PE
                atm_ce = None
                atm_pe = None
                
                for item in chain_data:
                    if item.get('strike_price') == atm:
                        if item.get('call_options'):
                            atm_ce = item['call_options']
                        if item.get('put_options'):
                            atm_pe = item['put_options']
                
                # Display header
                print(f"\n{'Option':<18} {'LTP':>7} {'IV':>7} {'Delta':>7} {'Gamma':>9} {'Theta':>8} {'Vega':>7} {'Rho':>7} {'OI':>11} {'OI Chg':>10} {'Volume':>11}")
                print("-"*120)
                
                # Display CE data
                if atm_ce:
                    greeks = atm_ce.get('option_greeks', {})
                    market = atm_ce.get('market_data', {})
                    ltp = market.get('ltp', 0)
                    iv = greeks.get('iv', 0) if greeks.get('iv') else 0
                    delta = greeks.get('delta', 0)
                    gamma = greeks.get('gamma', 0)
                    theta = greeks.get('theta', 0)
                    vega = greeks.get('vega', 0)
                    # Calculate Rho using Black-Scholes
                    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                    expiry_datetime = expiry_date.replace(hour=15, minute=30)  # Expiry at 3:30 PM
                    time_remaining = expiry_datetime - datetime.now()
                    days_to_expiry = max(time_remaining.total_seconds() / 86400 + 0.07, 0.01)  # +0.07 buffer to match Upstox
                    T = days_to_expiry / 365  # Time in years
                    r = 0.065  # RBI repo rate 6.5%
                    sigma = iv / 100 if iv else 0.10  # IV as decimal
                    rho = self.calculate_rho(nifty_ltp, atm, T, r, sigma, 'CE')
                    oi = market.get('oi', 0)
                    prev_oi = market.get('prev_oi', 0)
                    oi_change = oi - prev_oi if prev_oi else 0
                    volume = market.get('volume', 0)
                    print(f"{'NIFTY ' + str(atm) + ' CE':<18} {ltp:>7.2f} {iv:>6.2f}% {delta:>7.4f} {gamma:>9.6f} {theta:>8.4f} {vega:>7.4f} {rho:>7.4f} {oi:>11.0f} {oi_change:>+10.0f} {volume:>11.0f}")
                else:
                    print(f"{'NIFTY ' + str(atm) + ' CE':<18} {'--':>7} {'--':>7} {'--':>7} {'--':>9} {'--':>8} {'--':>7} {'--':>7} {'--':>11} {'--':>10} {'--':>11}")
                
                # Display PE data
                if atm_pe:
                    greeks = atm_pe.get('option_greeks', {})
                    market = atm_pe.get('market_data', {})
                    ltp = market.get('ltp', 0)
                    iv = greeks.get('iv', 0) if greeks.get('iv') else 0
                    delta = greeks.get('delta', 0)
                    gamma = greeks.get('gamma', 0)
                    theta = greeks.get('theta', 0)
                    vega = greeks.get('vega', 0)
                    # Calculate Rho using Black-Scholes
                    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                    expiry_datetime = expiry_date.replace(hour=15, minute=30)  # Expiry at 3:30 PM
                    time_remaining = expiry_datetime - datetime.now()
                    days_to_expiry = max(time_remaining.total_seconds() / 86400 + 0.07, 0.01)  # +0.07 buffer to match Upstox
                    T = days_to_expiry / 365  # Time in years
                    r = 0.065  # RBI repo rate 6.5%
                    sigma = iv / 100 if iv else 0.10  # IV as decimal
                    rho = self.calculate_rho(nifty_ltp, atm, T, r, sigma, 'PE')
                    oi = market.get('oi', 0)
                    prev_oi = market.get('prev_oi', 0)
                    oi_change = oi - prev_oi if prev_oi else 0
                    volume = market.get('volume', 0)
                    print(f"{'NIFTY ' + str(atm) + ' PE':<18} {ltp:>7.2f} {iv:>6.2f}% {delta:>7.4f} {gamma:>9.6f} {theta:>8.4f} {vega:>7.4f} {rho:>7.4f} {oi:>11.0f} {oi_change:>+10.0f} {volume:>11.0f}")
                else:
                    print(f"{'NIFTY ' + str(atm) + ' PE':<18} {'--':>7} {'--':>7} {'--':>7} {'--':>9} {'--':>8} {'--':>7} {'--':>7} {'--':>11} {'--':>10} {'--':>11}")
                
                print("-"*120)
                
                # Save to CSV with calculated Rho
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(csv_file, 'a') as f:
                    if atm_ce:
                        ce_greeks = atm_ce.get('option_greeks', {})
                        ce_market = atm_ce.get('market_data', {})
                        ce_oi = ce_market.get('oi', 0)
                        ce_prev_oi = ce_market.get('prev_oi', 0)
                        ce_oi_change = ce_oi - ce_prev_oi if ce_prev_oi else 0
                        # Calculate CE Rho for CSV
                        ce_iv = ce_greeks.get('iv', 0) if ce_greeks.get('iv') else 0
                        ce_sigma = ce_iv / 100 if ce_iv else 0.10
                        expiry_date_csv = datetime.strptime(expiry_str, "%Y-%m-%d")
                        expiry_dt = expiry_date_csv.replace(hour=15, minute=30)
                        time_rem = expiry_dt - datetime.now()
                        days_exp = max(time_rem.total_seconds() / 86400 + 0.07, 0.01)  # +0.07 buffer
                        T_csv = days_exp / 365
                        ce_rho = self.calculate_rho(nifty_ltp, atm, T_csv, 0.065, ce_sigma, 'CE')
                        f.write(f"{timestamp},{nifty_ltp},{atm},{expiry_str},CE,{ce_market.get('ltp', 0)},{ce_iv:.2f},{ce_greeks.get('delta', 0):.4f},{ce_greeks.get('gamma', 0):.6f},{ce_greeks.get('theta', 0):.4f},{ce_greeks.get('vega', 0):.4f},{ce_rho:.4f},{ce_oi:.0f},{ce_oi_change:.0f},{ce_market.get('volume', 0):.0f}\n")
                    if atm_pe:
                        pe_greeks = atm_pe.get('option_greeks', {})
                        pe_market = atm_pe.get('market_data', {})
                        pe_oi = pe_market.get('oi', 0)
                        pe_prev_oi = pe_market.get('prev_oi', 0)
                        pe_oi_change = pe_oi - pe_prev_oi if pe_prev_oi else 0
                        # Calculate PE Rho for CSV
                        pe_iv = pe_greeks.get('iv', 0) if pe_greeks.get('iv') else 0
                        pe_sigma = pe_iv / 100 if pe_iv else 0.10
                        pe_rho = self.calculate_rho(nifty_ltp, atm, T_csv, 0.065, pe_sigma, 'PE')
                        f.write(f"{timestamp},{nifty_ltp},{atm},{expiry_str},PE,{pe_market.get('ltp', 0)},{pe_iv:.2f},{pe_greeks.get('delta', 0):.4f},{pe_greeks.get('gamma', 0):.6f},{pe_greeks.get('theta', 0):.4f},{pe_greeks.get('vega', 0):.4f},{pe_rho:.4f},{pe_oi:.0f},{pe_oi_change:.0f},{pe_market.get('volume', 0):.0f}\n")
                
                print(f"\n⏱️  Last updated: {datetime.now().strftime('%H:%M:%S')}   |   Refreshing in 5 seconds...")
                print(f"💾 Data saved to: {csv_file}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped.")
            
            # Convert CSV to Excel - APPEND to existing file if it exists
            try:
                excel_file = os.path.join(data_folder, "greeks_data.xlsx")
                df_new = pd.read_csv(csv_file)
                
                if os.path.exists(excel_file):
                    # Append to existing Excel file
                    try:
                        df_existing = pd.read_excel(excel_file)
                        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                        # Remove duplicates based on Timestamp column
                        df_combined = df_combined.drop_duplicates(subset=['Timestamp', 'Option'], keep='last')
                        df_combined.to_excel(excel_file, index=False, sheet_name='Greeks Data')
                        print(f"📊 Excel file updated (appended): {excel_file}")
                        print(f"   Total rows: {len(df_combined)}")
                    except Exception as e:
                        # If reading fails, just overwrite
                        df_new.to_excel(excel_file, index=False, sheet_name='Greeks Data')
                        print(f"📊 Excel file saved: {excel_file}")
                else:
                    # Create new Excel file
                    df_new.to_excel(excel_file, index=False, sheet_name='Greeks Data')
                    print(f"📊 Excel file created: {excel_file}")
            except Exception as e:
                print(f"⚠️ Could not save Excel file: {e}")


def main():
    print("UPSTOX AUTO TRADER")
    fetcher = UpstoxAccountFetcher()
    
    # Auto-refresh token if not connected
    if not fetcher.session_generated:
        print("\n⚠️ Not connected. Starting auto token refresh...")
        fetcher.refresh_token()
    
    while True:
        # Simple Menu (Removed manual Refresh Token option)
        print("\n1. Account Summary\n2. Buy Option\n3. Live Greeks Monitor\n4. Exit")
        c = input("Choice: ")
        
        if not fetcher.session_generated:
            print("\n⚠️ Session expired. Auto-refreshing token...")
            fetcher.refresh_token()
            continue
            
        if c == '1': fetcher.get_complete_account_summary()
        elif c == '2': fetcher.option_chain_buy()
        elif c == '3': fetcher.live_greeks_monitor()
        elif c == '4': break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Script interrupted by user. Exiting...")
        sys.exit(0)
