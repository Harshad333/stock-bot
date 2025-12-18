"""
Angel One Account Balance Fetcher
Fetches account funds/balance from Angel One trading account
"""

from datetime import datetime
import pyotp
from SmartApi import SmartConnect
import json
import pandas as pd


class AngelAccountFetcher:
    def __init__(self):
        # Angel One Credentials (from your existing rt01_buy.py)
        self.API_KEY = "9uRi7U23"
        self.CLIENT_ID = "H75840"
        self.MPIN = "6026"
        self.TOTP_SECRET = "WSTVTP65A55FD6KOGJF63LNMLQ"
        
        self.client = None
        self.session_generated = False
        self.connect()
    
    def connect(self):
        """Connect to Angel One"""
        try:
            obj = SmartConnect(api_key=self.API_KEY)
            totp = pyotp.TOTP(self.TOTP_SECRET).now()
            data = obj.generateSession(self.CLIENT_ID, self.MPIN, totp)
            
            if data and data.get('status'):
                self.client = obj
                self.session_generated = True
                print("✅ [SUCCESS] Connected to Angel One!")
            else:
                print(f"❌ [ERROR] Login failed: {data}")
        except Exception as e:
            print(f"❌ [ERROR] Connection failed: {e}")
    
    def get_funds(self):
        """Fetch account funds/balance from Angel One"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Angel One")
            return None
        
        try:
            # Fetch RMS (Risk Management System) limits which contains fund details
            rms_response = self.client.rmsLimit()
            
            if rms_response and rms_response.get('status'):
                funds_data = rms_response.get('data', {})
                
                print("\n" + "="*60)
                print("💰 ANGEL ONE ACCOUNT BALANCE")
                print("="*60)
                print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-"*60)
                
                # Extract and display key fund details
                available_cash = funds_data.get('availablecash', 'N/A')
                net = funds_data.get('net', 'N/A')
                collateral = funds_data.get('collateral', 'N/A')
                utiliseddebits = funds_data.get('utiliseddebits', 'N/A')
                utilisedelmargin = funds_data.get('utilisedelmargin', 'N/A')
                
                print(f"💵 Available Cash     : ₹{available_cash}")
                print(f"💰 Net Balance        : ₹{net}")
                print(f"🏦 Collateral         : ₹{collateral}")
                print(f"📊 Used Debits        : ₹{utiliseddebits}")
                print(f"📈 Used EL Margin     : ₹{utilisedelmargin}")
                
                print("-"*60)
                print("📋 COMPLETE FUND DETAILS:")
                print("-"*60)
                
                # Display all available fund details
                for key, value in funds_data.items():
                    print(f"  {key}: ₹{value}" if isinstance(value, (int, float, str)) else f"  {key}: {value}")
                
                print("="*60)
                
                return funds_data
            else:
                print(f"❌ [ERROR] Failed to fetch funds: {rms_response}")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching funds: {e}")
            return None
    
    def get_profile(self):
        """Fetch user profile details"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Angel One")
            return None
        
        try:
            profile_response = self.client.getProfile(self.client.refresh_token)
            
            if profile_response and profile_response.get('status'):
                profile_data = profile_response.get('data', {})
                
                print("\n" + "="*60)
                print("👤 USER PROFILE")
                print("="*60)
                
                print(f"📛 Name      : {profile_data.get('name', 'N/A')}")
                print(f"📧 Email     : {profile_data.get('email', 'N/A')}")
                print(f"📱 Mobile    : {profile_data.get('mobileno', 'N/A')}")
                print(f"🆔 Client ID : {profile_data.get('clientcode', 'N/A')}")
                print(f"🏢 Broker    : {profile_data.get('broker', 'N/A')}")
                print(f"💹 Exchanges : {profile_data.get('exchanges', 'N/A')}")
                
                print("="*60)
                
                return profile_data
            else:
                print(f"❌ [ERROR] Failed to fetch profile: {profile_response}")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching profile: {e}")
            return None
    
    def get_holdings(self):
        """Fetch current holdings/portfolio"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Angel One")
            return None
        
        try:
            holdings_response = self.client.holding()
            
            if holdings_response and holdings_response.get('status'):
                holdings_data = holdings_response.get('data', [])
                
                print("\n" + "="*60)
                print("📊 PORTFOLIO HOLDINGS")
                print("="*60)
                
                if holdings_data:
                    total_value = 0
                    total_pnl = 0
                    
                    for holding in holdings_data:
                        symbol = holding.get('tradingsymbol', 'N/A')
                        qty = holding.get('quantity', 0)
                        avg_price = float(holding.get('averageprice', 0))
                        ltp = float(holding.get('ltp', 0))
                        pnl = float(holding.get('profitandloss', 0))
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
                print(f"❌ [ERROR] Failed to fetch holdings: {holdings_response}")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching holdings: {e}")
            return None
    
    def get_positions(self):
        """Fetch current open positions"""
        if not self.session_generated:
            print("❌ [ERROR] Not connected to Angel One")
            return None
        
        try:
            positions_response = self.client.position()
            
            if positions_response and positions_response.get('status'):
                positions_data = positions_response.get('data', [])
                
                print("\n" + "="*60)
                print("📈 OPEN POSITIONS")
                print("="*60)
                
                if positions_data:
                    for pos in positions_data:
                        symbol = pos.get('tradingsymbol', 'N/A')
                        qty = pos.get('netqty', 0)
                        buy_val = float(pos.get('buyvalue', 0))
                        sell_val = float(pos.get('sellvalue', 0))
                        pnl = float(pos.get('pnl', 0))
                        
                        print(f"\n📌 {symbol}")
                        print(f"   Net Qty: {qty} | Buy Val: ₹{buy_val:.2f} | Sell Val: ₹{sell_val:.2f}")
                        print(f"   P&L: ₹{pnl:.2f}")
                else:
                    print("📭 No open positions found")
                
                print("="*60)
                
                return positions_data
            else:
                print(f"❌ [ERROR] Failed to fetch positions: {positions_response}")
                return None
                
        except Exception as e:
            print(f"❌ [ERROR] Exception while fetching positions: {e}")
            return None
    
    def get_complete_account_summary(self):
        """Get complete account summary - funds, profile, holdings, positions"""
        print("\n" + "🔄"*30)
        print("  FETCHING COMPLETE ACCOUNT SUMMARY")
        print("🔄"*30)
        
        # Get all account details
        self.get_profile()
        funds = self.get_funds()
        self.get_holdings()
        self.get_positions()
        
        return funds
    
    # =========================================================================
    # OPTION CHAIN BUY LOGIC
    # =========================================================================
    
    def download_instrument_master(self):
        """Download instrument master from Angel One"""
        try:
            import requests
            import pandas as pd
            
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.instrument_df = pd.DataFrame(data)
                
                # Filter for NFO options
                exch_col = 'exch_seg' if 'exch_seg' in self.instrument_df.columns else 'exchange'
                if exch_col in self.instrument_df.columns:
                    self.instrument_df = self.instrument_df[self.instrument_df[exch_col].isin(['NFO', 'NSE'])].copy()
                
                self.instrument_df['strike'] = pd.to_numeric(self.instrument_df['strike'], errors='coerce').fillna(0).astype(int)
                print(f"✅ [SUCCESS] Instrument Master loaded: {len(self.instrument_df)} instruments")
                return True
            else:
                print(f"❌ [ERROR] Failed to download instrument master")
                return False
        except Exception as e:
            print(f"❌ [ERROR] Instrument master download failed: {e}")
            return False
    
    def get_nifty_ltp(self):
        """Get current NIFTY 50 LTP"""
        try:
            response = self.client.ltpData("NSE", "NIFTY 50", "99926000")
            if response and response.get('data') and response['data'].get('ltp'):
                ltp = float(response['data']['ltp'])
                return ltp
        except Exception as e:
            print(f"❌ [ERROR] Failed to get NIFTY LTP: {e}")
        return None
    
    def find_option_contract(self, strike, option_type):
        """Find option contract for given strike and type (CE/PE)"""
        try:
            if not hasattr(self, 'instrument_df') or self.instrument_df is None:
                if not self.download_instrument_master():
                    return None
            
            tradingsymbol_col = 'tradingsymbol' if 'tradingsymbol' in self.instrument_df.columns else 'symbol'
            token_col = 'token' if 'token' in self.instrument_df.columns else 'symboltoken'
            exch_col = 'exch_seg' if 'exch_seg' in self.instrument_df.columns else 'exchange'
            
            # Filter NIFTY options
            filtered_options = self.instrument_df[
                (self.instrument_df['instrumenttype'] == 'OPTIDX') &
                (self.instrument_df[exch_col] == 'NFO') &
                ((self.instrument_df['strike'] == strike) | (self.instrument_df['strike'] == strike * 100)) &
                (self.instrument_df[tradingsymbol_col].str.contains(option_type, na=False)) &
                (self.instrument_df[tradingsymbol_col].str.startswith('NIFTY', na=False)) &
                (~self.instrument_df[tradingsymbol_col].str.contains('BANK|MID|FIN|SENSEX', case=False, na=False))
            ]
            
            if filtered_options.empty:
                print(f"❌ [ERROR] No option found for strike {strike} {option_type}")
                return None
            
            # Get nearest expiry
            from datetime import datetime
            def parse_expiry_date(expiry_str):
                try:
                    return datetime.strptime(expiry_str, '%d%b%Y')
                except:
                    return datetime.strptime(expiry_str, '%d%B%Y')
            
            filtered_options = filtered_options.copy()
            filtered_options['expiry_date'] = filtered_options['expiry'].apply(parse_expiry_date)
            
            # Filter future dates only
            today = datetime.now().date()
            filtered_options = filtered_options[filtered_options['expiry_date'].dt.date > today]
            
            if filtered_options.empty:
                print(f"❌ [ERROR] No future expiry available")
                return None
            
            # Sort by date and get nearest expiry
            filtered_options = filtered_options.sort_values('expiry_date')
            option_row = filtered_options.iloc[0]
            
            return {
                'symbol': option_row[tradingsymbol_col],
                'token': str(option_row[token_col]),
                'strike': strike,
                'expiry': option_row['expiry']
            }
            
        except Exception as e:
            print(f"❌ [ERROR] Failed to find option contract: {e}")
            return None
    
    def get_option_ltp(self, symbol, token):
        """Get current LTP for option"""
        try:
            response = self.client.ltpData("NFO", symbol, token)
            if response and response.get('data') and response['data'].get('ltp'):
                return float(response['data']['ltp'])
        except Exception as e:
            print(f"❌ [ERROR] Failed to get option LTP: {e}")
        return None
    
    def place_option_order(self, symbol, token, quantity, order_type="BUY"):
        """Place option buy order"""
        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": order_type,
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity)
            }
            
            print(f"\n📋 [ORDER DETAILS]")
            print(f"   Symbol: {symbol}")
            print(f"   Type: {order_type}")
            print(f"   Quantity: {quantity}")
            print(f"   Order Type: MARKET")
            
            # Place order
            response = self.client.placeOrder(order_params)
            
            # Debug: Print raw response type and value
            print(f"\n🔍 [DEBUG] Response type: {type(response)}, Value: {response}")
            
            # Handle different response formats from Angel One API
            if isinstance(response, str):
                # If it's a non-empty alphanumeric string, it's likely an order ID (success!)
                if response and len(response) > 5:
                    print(f"\n✅ [SUCCESS] Order placed successfully!")
                    print(f"   Order ID: {response}")
                    return True
                else:
                    print(f"\n❌ [ERROR] Order failed - API returned: {response}")
                    return False
            
            # Handle dictionary response
            if response and isinstance(response, dict):
                if response.get('status'):
                    data = response.get('data', {})
                    # Handle case where data might be a string or orderid directly
                    if isinstance(data, dict):
                        order_id = data.get('orderid', 'N/A')
                    elif isinstance(data, str):
                        order_id = data
                    else:
                        order_id = str(data) if data else 'N/A'
                    print(f"\n✅ [SUCCESS] Order placed successfully!")
                    print(f"   Order ID: {order_id}")
                    return True
                else:
                    error_msg = response.get('message', str(response))
                    print(f"\n❌ [ERROR] Order failed: {error_msg}")
                    return False
            
            print(f"\n❌ [ERROR] Unexpected response format: {response}")
            return False
                
        except Exception as e:
            print(f"\n❌ [ERROR] Failed to place order: {e}")
            return False
    
    def place_stoploss_order(self, symbol, token, quantity, stoploss_price, trigger_price):
        """Place stop loss order (SELL) at specified price"""
        try:
            order_params = {
                "variety": "STOPLOSS",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity),
                "price": str(stoploss_price),
                "triggerprice": str(trigger_price)
            }
            
            print(f"\n📋 [STOP LOSS ORDER DETAILS]")
            print(f"   Symbol: {symbol}")
            print(f"   Type: SELL (Stop Loss)")
            print(f"   Quantity: {quantity}")
            print(f"   Stop Loss Price: ₹{stoploss_price:.2f}")
            print(f"   Trigger Price: ₹{trigger_price:.2f}")
            
            # Place order
            response = self.client.placeOrder(order_params)
            
            print(f"\n🔍 [DEBUG] SL Response type: {type(response)}, Value: {response}")
            
            if isinstance(response, str):
                if response and len(response) > 5:
                    print(f"\n✅ [SUCCESS] Stop Loss order placed successfully!")
                    print(f"   Order ID: {response}")
                    return True
                else:
                    print(f"\n❌ [ERROR] Stop Loss order failed - API returned: {response}")
                    return False
            
            if response and isinstance(response, dict):
                if response.get('status'):
                    data = response.get('data', {})
                    if isinstance(data, dict):
                        order_id = data.get('orderid', 'N/A')
                    elif isinstance(data, str):
                        order_id = data
                    else:
                        order_id = str(data) if data else 'N/A'
                    print(f"\n✅ [SUCCESS] Stop Loss order placed successfully!")
                    print(f"   Order ID: {order_id}")
                    return True
                else:
                    error_msg = response.get('message', str(response))
                    print(f"\n❌ [ERROR] Stop Loss order failed: {error_msg}")
                    return False
            
            print(f"\n❌ [ERROR] Unexpected response format: {response}")
            return False
                
        except Exception as e:
            print(f"\n❌ [ERROR] Failed to place stop loss order: {e}")
            return False
    
    def place_stoploss_order_with_id(self, symbol, token, quantity, stoploss_price, trigger_price):
        """Place stop loss order and return order ID (for trailing SL)"""
        try:
            order_params = {
                "variety": "STOPLOSS",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity),
                "price": str(stoploss_price),
                "triggerprice": str(trigger_price)
            }
            
            print(f"\n📋 [STOP LOSS ORDER DETAILS]")
            print(f"   Symbol: {symbol}")
            print(f"   Type: SELL (Stop Loss)")
            print(f"   Quantity: {quantity}")
            print(f"   Stop Loss Price: ₹{stoploss_price:.2f}")
            print(f"   Trigger Price: ₹{trigger_price:.2f}")
            
            # Place order
            response = self.client.placeOrder(order_params)
            
            print(f"\n🔍 [DEBUG] SL Response type: {type(response)}, Value: {response}")
            
            # Return order ID if successful
            if isinstance(response, str) and response and len(response) > 5:
                print(f"\n✅ [SUCCESS] Stop Loss order placed successfully!")
                print(f"   Order ID: {response}")
                return response  # Return order ID
            
            if response and isinstance(response, dict) and response.get('status'):
                data = response.get('data', {})
                if isinstance(data, dict):
                    order_id = data.get('orderid')
                elif isinstance(data, str):
                    order_id = data
                else:
                    order_id = str(data) if data else None
                
                if order_id:
                    print(f"\n✅ [SUCCESS] Stop Loss order placed successfully!")
                    print(f"   Order ID: {order_id}")
                    return order_id  # Return order ID
            
            print(f"\n❌ [ERROR] Stop Loss order failed: {response}")
            return None
                
        except Exception as e:
            print(f"\n❌ [ERROR] Failed to place stop loss order: {e}")
            return None
    
    def place_target_order(self, symbol, token, quantity, target_price):
        """Place target order (SELL) at specified price"""
        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity),
                "price": str(target_price)
            }
            
            print(f"\n📋 [TARGET ORDER DETAILS]")
            print(f"   Symbol: {symbol}")
            print(f"   Type: SELL (Target)")
            print(f"   Quantity: {quantity}")
            print(f"   Target Price: ₹{target_price:.2f}")
            
            # Place order
            response = self.client.placeOrder(order_params)
            
            print(f"\n🔍 [DEBUG] Target Response type: {type(response)}, Value: {response}")
            
            if isinstance(response, str):
                if response and len(response) > 5:
                    print(f"\n✅ [SUCCESS] Target order placed successfully!")
                    print(f"   Order ID: {response}")
                    return True
                else:
                    print(f"\n❌ [ERROR] Target order failed - API returned: {response}")
                    return False
            
            if response and isinstance(response, dict):
                if response.get('status'):
                    data = response.get('data', {})
                    if isinstance(data, dict):
                        order_id = data.get('orderid', 'N/A')
                    elif isinstance(data, str):
                        order_id = data
                    else:
                        order_id = str(data) if data else 'N/A'
                    print(f"\n✅ [SUCCESS] Target order placed successfully!")
                    print(f"   Order ID: {order_id}")
                    return True
                else:
                    error_msg = response.get('message', str(response))
                    print(f"\n❌ [ERROR] Target order failed: {error_msg}")
                    return False
            
            print(f"\n❌ [ERROR] Unexpected response format: {response}")
            return False
                
        except Exception as e:
            print(f"\n❌ [ERROR] Failed to place target order: {e}")
            return False
    
    # =========================================================================
    # TRAILING STOP LOSS SYSTEM
    # =========================================================================
    
    def get_order_status(self, order_id):
        """Get status of an order"""
        try:
            order_book = self.client.orderBook()
            
            if order_book and order_book.get('data'):
                for order in order_book['data']:
                    if order.get('orderid') == order_id:
                        return {
                            'status': order.get('orderstatus', 'unknown'),
                            'filled_qty': order.get('filledshares', 0),
                            'price': order.get('price', 0),
                            'trigger_price': order.get('triggerprice', 0)
                        }
            return None
        except Exception as e:
            print(f"❌ [ERROR] Failed to get order status: {e}")
            return None
    
    def modify_stoploss_order(self, order_id, symbol, token, quantity, new_price, new_trigger_price):
        """Modify existing stop loss order with new price"""
        try:
            modify_params = {
                "variety": "STOPLOSS",
                "orderid": order_id,
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity),
                "price": str(new_price),
                "triggerprice": str(new_trigger_price)
            }
            
            response = self.client.modifyOrder(modify_params)
            
            if isinstance(response, str) and response and len(response) > 5:
                print(f"✅ SL Modified! New SL: ₹{new_price:.2f} (Trigger: ₹{new_trigger_price:.2f})")
                return True
            
            if response and isinstance(response, dict) and response.get('status'):
                print(f"✅ SL Modified! New SL: ₹{new_price:.2f} (Trigger: ₹{new_trigger_price:.2f})")
                return True
            
            print(f"⚠️  SL modification failed: {response}")
            return False
            
        except Exception as e:
            print(f"❌ [ERROR] Failed to modify SL order: {e}")
            return False
    
    def calculate_trailing_sl(self, entry_price, current_price, current_sl):
        """
        Calculate new trailing SL based on profit level
        
        Rules:
        - Initial SL: 10% below entry
        - At 7% profit: Lock 3% profit
        - Every 5% after 7%: Move SL up 5%
        """
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        # If not yet at 7% profit, keep initial SL (10% below entry)
        if profit_percent < 7:
            initial_sl = round(entry_price * 0.90, 2)
            return initial_sl, False  # (sl_price, should_modify)
        
        # At 7% or more profit - calculate trailing SL
        if profit_percent >= 7:
            # Calculate how many 5% steps above the 7% threshold
            steps_above_7 = int((profit_percent - 7) / 5)
            
            # Lock profit: 3% at 7%, then +5% for each step
            locked_profit_percent = 3 + (steps_above_7 * 5)
            
            # Calculate new SL price
            new_sl = round(entry_price * (1 + locked_profit_percent / 100), 2)
            
            # Only modify if new SL is higher than current SL
            if new_sl > current_sl:
                return new_sl, True
        
        return current_sl, False
    
    def trailing_stoploss_monitor(self, symbol, token, quantity, entry_price, sl_order_id):
        """
        Main trailing stop loss monitoring loop
        
        Continuously monitors price and adjusts SL based on profit levels
        """
        import time
        
        print("\n" + "="*60)
        print("  🔄 TRAILING STOP LOSS MONITOR STARTED")
        print("="*60)
        print(f"\n📊 Entry Price: ₹{entry_price:.2f}")
        print(f"📋 SL Order ID: {sl_order_id}")
        
        # Initial SL (10% below entry)
        current_sl = round(entry_price * 0.90, 2)
        print(f"📉 Initial SL: ₹{current_sl:.2f} (10% below entry)")
        
        # Trailing milestones
        print("\n📈 Trailing Milestones:")
        print(f"   At 7% profit (₹{entry_price * 1.07:.2f}) → Lock 3% (SL = ₹{entry_price * 1.03:.2f})")
        print(f"   At 12% profit (₹{entry_price * 1.12:.2f}) → Lock 8% (SL = ₹{entry_price * 1.08:.2f})")
        print(f"   At 17% profit (₹{entry_price * 1.17:.2f}) → Lock 13% (SL = ₹{entry_price * 1.13:.2f})")
        
        print("\n" + "-"*60)
        print("⏳ Monitoring price... (Press Ctrl+C to stop)")
        print("-"*60)
        
        last_profit_milestone = -10  # Track last reported milestone
        check_interval = 3  # Check every 3 seconds
        
        try:
            while True:
                # Get current price
                current_price = self.get_option_ltp(symbol, token)
                
                if not current_price:
                    print("⚠️  Could not fetch price, retrying...")
                    time.sleep(check_interval)
                    continue
                
                # Calculate profit
                profit_percent = ((current_price - entry_price) / entry_price) * 100
                
                # Check if SL order is filled (exit condition)
                order_status = self.get_order_status(sl_order_id)
                if order_status and order_status['status'] in ['complete', 'filled']:
                    print(f"\n🛑 STOP LOSS HIT!")
                    print(f"   Exit Price: ₹{order_status.get('price', current_sl):.2f}")
                    print(f"   P&L: {((current_sl - entry_price) / entry_price) * 100:.1f}%")
                    break
                
                # Calculate new trailing SL
                new_sl, should_modify = self.calculate_trailing_sl(entry_price, current_price, current_sl)
                
                # Print status update at profit milestones (every 2%)
                current_milestone = int(profit_percent / 2) * 2
                if current_milestone != last_profit_milestone:
                    status_icon = "📈" if profit_percent > 0 else "📉"
                    print(f"{status_icon} LTP: ₹{current_price:.2f} | Profit: {profit_percent:+.1f}% | Current SL: ₹{current_sl:.2f}")
                    last_profit_milestone = current_milestone
                
                # Modify SL if needed
                if should_modify:
                    print(f"\n🔄 TRAILING SL ADJUSTMENT!")
                    print(f"   Profit: {profit_percent:.1f}%")
                    print(f"   Moving SL: ₹{current_sl:.2f} → ₹{new_sl:.2f}")
                    
                    trigger_price = round(new_sl + 0.05, 2)
                    
                    success = self.modify_stoploss_order(
                        sl_order_id, symbol, token, quantity,
                        new_sl, trigger_price
                    )
                    
                    if success:
                        current_sl = new_sl
                        print(f"   New SL locked at ₹{current_sl:.2f}")
                    
                    print("-"*60)
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Trailing SL monitoring stopped by user")
            print(f"📊 Final Status:")
            print(f"   Entry: ₹{entry_price:.2f}")
            print(f"   Current SL: ₹{current_sl:.2f}")
            print("="*60)
        except Exception as e:
            print(f"\n❌ [ERROR] Trailing monitor error: {e}")
            print(f"📊 Last known SL: ₹{current_sl:.2f}")
    
    def option_chain_buy(self):
        """Option chain buy logic with user interaction"""
        print("\n" + "="*60)
        print("  📈 OPTION CHAIN BUY")
        print("="*60)
        
        # Get NIFTY LTP
        nifty_ltp = self.get_nifty_ltp()
        if not nifty_ltp:
            print("❌ [ERROR] Could not fetch NIFTY LTP")
            return
        
        print(f"\n💹 Current NIFTY 50 LTP: {nifty_ltp:.2f}")
        
        # Ask for CALL or PUT
        print("\n📊 Select Option Type:")
        print("  1. CALL (CE)")
        print("  2. PUT (PE)")
        
        choice = input("\nEnter your choice (1/2): ").strip()
        
        if choice == "1":
            option_type = "CE"
            print("\n✅ Selected: CALL (CE)")
        elif choice == "2":
            option_type = "PE"
            print("\n✅ Selected: PUT (PE)")
        else:
            print("❌ [ERROR] Invalid choice")
            return
        
        # Suggest ATM strike
        atm_strike = round(nifty_ltp / 50) * 50
        print(f"\n💡 Suggested ATM Strike: {atm_strike}")
        
        # Ask for strike price
        strike_input = input(f"Enter strike price (or press Enter for ATM {atm_strike}): ").strip()
        
        if strike_input:
            try:
                strike = int(strike_input)
            except:
                print("❌ [ERROR] Invalid strike price")
                return
        else:
            strike = atm_strike
        
        print(f"\n✅ Selected Strike: {strike}")
        
        # Find option contract
        print(f"\n🔍 Searching for NIFTY {strike} {option_type}...")
        option_contract = self.find_option_contract(strike, option_type)
        
        if not option_contract:
            print("❌ [ERROR] Option contract not found")
            return
        
        print(f"✅ Found: {option_contract['symbol']}")
        print(f"   Expiry: {option_contract['expiry']}")
        
        # Get option LTP
        option_ltp = self.get_option_ltp(option_contract['symbol'], option_contract['token'])
        
        if option_ltp:
            print(f"   Current Price: ₹{option_ltp:.2f}")
        
        # Ask for quantity
        print("\n📦 Enter Quantity:")
        print("  Type 'market' for minimum lot size (15)")
        print("  Or enter custom quantity (multiples of 15)")
        
        qty_input = input("\nEnter quantity: ").strip().lower()
        
        if qty_input == "market":
            quantity = 15
            print(f"\n✅ Selected Quantity: {quantity} (Market lot)")
        else:
            try:
                quantity = int(qty_input)
                if quantity % 15 != 0:
                    print(f"⚠️  [WARNING] Quantity should be multiple of 15")
                    quantity = (quantity // 15) * 15
                    print(f"   Adjusted to: {quantity}")
                
                if quantity <= 0:
                    print("❌ [ERROR] Invalid quantity")
                    return
                    
            except:
                print("❌ [ERROR] Invalid quantity input")
                return
        
        # Calculate estimated cost
        if option_ltp:
            estimated_cost = option_ltp * quantity
            print(f"\n💰 Estimated Cost: ₹{estimated_cost:.2f}")
        
        # Confirm order
        print("\n" + "-"*60)
        print("📋 ORDER SUMMARY:")
        print(f"   Symbol: {option_contract['symbol']}")
        print(f"   Type: BUY {option_type}")
        print(f"   Strike: {strike}")
        print(f"   Quantity: {quantity}")
        if option_ltp:
            print(f"   Price: ₹{option_ltp:.2f}")
            print(f"   Total: ₹{estimated_cost:.2f}")
        print("-"*60)
        
        # Automatic Stop Loss (10%) and Target (20%) setup
        print("\n" + "-"*60)
        print("🎯 AUTOMATIC STOP LOSS & TARGET SETUP")
        print("-"*60)
        
        # Fixed percentages
        sl_percent = 10  # 10% Stop Loss
        target_percent = 30  # 30% Target
        
        stoploss_price = None
        target_price = None
        trigger_price = None
        
        if option_ltp:
            print(f"\n📊 Current Option Price (Buy Price): ₹{option_ltp:.2f}")
            
            # Calculate Stop Loss (BELOW buy price)
            stoploss_price = round(option_ltp * (1 - sl_percent / 100), 2)
            # Trigger price should be slightly ABOVE the SL price for SELL order to trigger
            trigger_price = round(stoploss_price + 0.05, 2)
            
            # Calculate Target (ABOVE buy price)
            target_price = round(option_ltp * (1 + target_percent / 100), 2)
            
            print(f"\n   📉 Stop Loss ({sl_percent}%): ₹{stoploss_price:.2f}")
            print(f"      (Trigger at: ₹{trigger_price:.2f})")
            print(f"\n   � Target ({target_percent}%): ₹{target_price:.2f}")
            
            # Show potential profit/loss
            potential_loss = (option_ltp - stoploss_price) * quantity
            potential_profit = (target_price - option_ltp) * quantity
            print(f"\n   � Potential Profit: ₹{potential_profit:.2f}")
            print(f"   💸 Max Loss: ₹{potential_loss:.2f}")
        
        # Updated order summary
        print("\n" + "-"*60)
        print("📋 COMPLETE ORDER SUMMARY:")
        print(f"   Symbol: {option_contract['symbol']}")
        print(f"   Type: BUY {option_type}")
        print(f"   Strike: {strike}")
        print(f"   Quantity: {quantity}")
        if option_ltp:
            print(f"   Buy Price: ₹{option_ltp:.2f}")
            print(f"   Total Cost: ₹{estimated_cost:.2f}")
        if stoploss_price:
            print(f"   Stop Loss: ₹{stoploss_price:.2f} ({sl_percent}% below)")
        if target_price:
            print(f"   Target: ₹{target_price:.2f} ({target_percent}% above)")
        print("-"*60)
        
        confirm = input("\n🔔 Confirm BUY order? (yes/no): ").strip().lower()
        
        if confirm in ['yes', 'y']:
            print("\n🚀 Placing BUY order...")
            success = self.place_option_order(
                option_contract['symbol'],
                option_contract['token'],
                quantity,
                "BUY"
            )
            
            if success:
                print("\n🎉 BUY Order completed successfully!")
                
                # Fetch FRESH LTP after buy order for accurate SL/Target calculation
                import time
                time.sleep(1)  # Small delay to let the order execute
                
                print("\n🔄 Fetching latest market price for SL/Target...")
                fresh_ltp = self.get_option_ltp(option_contract['symbol'], option_contract['token'])
                
                sl_order_id = None
                entry_price = fresh_ltp if fresh_ltp else option_ltp
                
                if fresh_ltp:
                    print(f"📊 Current Market Price: ₹{fresh_ltp:.2f}")
                    
                    # Recalculate SL and Target based on FRESH LTP
                    fresh_stoploss_price = round(fresh_ltp * (1 - sl_percent / 100), 2)
                    fresh_trigger_price = round(fresh_stoploss_price + 0.05, 2)
                    fresh_target_price = round(fresh_ltp * (1 + target_percent / 100), 2)
                    
                    print(f"\n   📉 Stop Loss ({sl_percent}%): ₹{fresh_stoploss_price:.2f}")
                    print(f"      (Trigger at: ₹{fresh_trigger_price:.2f})")
                    print(f"   📈 Target ({target_percent}%): ₹{fresh_target_price:.2f}")
                    
                    # Place Stop Loss order and capture order ID
                    print("\n📉 Placing Stop Loss order...")
                    sl_response = self.place_stoploss_order_with_id(
                        option_contract['symbol'],
                        option_contract['token'],
                        quantity,
                        fresh_stoploss_price,
                        fresh_trigger_price
                    )
                    
                    if sl_response:
                        sl_order_id = sl_response
                        print("✅ Stop Loss order placed!")
                    else:
                        print("⚠️  Stop Loss order failed. Please place manually.")
                    
                    # Place Target order
                    print("\n📈 Placing Target order...")
                    target_success = self.place_target_order(
                        option_contract['symbol'],
                        option_contract['token'],
                        quantity,
                        fresh_target_price
                    )
                    
                    if target_success:
                        print("✅ Target order placed!")
                    else:
                        print("⚠️  Target order failed. Please place manually.")
                else:
                    print("⚠️  Could not fetch latest price. Using original calculations...")
                    entry_price = option_ltp
                    
                    # Fallback to original calculations
                    if stoploss_price and trigger_price:
                        print("\n📉 Placing Stop Loss order...")
                        sl_response = self.place_stoploss_order_with_id(
                            option_contract['symbol'],
                            option_contract['token'],
                            quantity,
                            stoploss_price,
                            trigger_price
                        )
                        if sl_response:
                            sl_order_id = sl_response
                            print("✅ Stop Loss order placed!")
                        else:
                            print("⚠️  Stop Loss order failed. Please place manually.")
                    
                    if target_price:
                        print("\n📈 Placing Target order...")
                        target_success = self.place_target_order(
                            option_contract['symbol'],
                            option_contract['token'],
                            quantity,
                            target_price
                        )
                        if target_success:
                            print("✅ Target order placed!")
                        else:
                            print("⚠️  Target order failed. Please place manually.")
                
                print("\n" + "="*60)
                print("📋 ORDER PLACEMENT COMPLETE!")
                print("="*60)
                
                # Auto-enable Trailing SL
                if sl_order_id:
                    print("\n" + "-"*60)
                    print("🔄 AUTO-STARTING TRAILING STOP LOSS")
                    print("-"*60)
                    print("Trailing SL will automatically adjust stop loss as price rises.")
                    print("  - At 7% profit: Lock 3% profit")
                    print("  - Every 5% rise after: Move SL up 5%")
                    print("  - Press Ctrl+C to stop monitoring")
                    
                    self.trailing_stoploss_monitor(
                        option_contract['symbol'],
                        option_contract['token'],
                        quantity,
                        entry_price,
                        sl_order_id
                    )
            else:
                print("\n❌ BUY Order failed. Please check your account or try again.")
        else:
            print("\n❌ Order cancelled by user")
    
    def find_affordable_options(self, max_budget=100):
        """Find options within budget and allow purchase"""
        print("\n" + "="*60)
        print(f"  💰 BUDGET OPTION FINDER (Max: ₹{max_budget} per lot)")
        print("="*60)
        
        # Get NIFTY LTP
        nifty_ltp = self.get_nifty_ltp()
        if not nifty_ltp:
            print("❌ [ERROR] Could not fetch NIFTY LTP")
            return
        
        print(f"\n💹 Current NIFTY 50 LTP: {nifty_ltp:.2f}")
        
        # Download instrument master
        if not hasattr(self, 'instrument_df') or self.instrument_df is None:
            print("\n🔄 Downloading instrument master...")
            if not self.download_instrument_master():
                print("❌ [ERROR] Failed to download instrument master")
                return
        
        print("\n🔍 Scanning for affordable options (this may take a moment)...")
        
        tradingsymbol_col = 'tradingsymbol' if 'tradingsymbol' in self.instrument_df.columns else 'symbol'
        token_col = 'token' if 'token' in self.instrument_df.columns else 'symboltoken'
        exch_col = 'exch_seg' if 'exch_seg' in self.instrument_df.columns else 'exchange'
        
        # Get NIFTY options (both CE and PE)
        nifty_options = self.instrument_df[
            (self.instrument_df['instrumenttype'] == 'OPTIDX') &
            (self.instrument_df[exch_col] == 'NFO') &
            (self.instrument_df[tradingsymbol_col].str.startswith('NIFTY', na=False)) &
            (~self.instrument_df[tradingsymbol_col].str.contains('BANK|MID|FIN|SENSEX', case=False, na=False))
        ]
        
        # Filter for future expiries
        from datetime import datetime
        def parse_expiry_date(expiry_str):
            try:
                return datetime.strptime(expiry_str, '%d%b%Y')
            except:
                return datetime.strptime(expiry_str, '%d%B%Y')
        
        nifty_options = nifty_options.copy()
        nifty_options['expiry_date'] = nifty_options['expiry'].apply(parse_expiry_date)
        today = datetime.now().date()
        nifty_options = nifty_options[nifty_options['expiry_date'].dt.date > today]
        
        # Get nearest expiry options only (to reduce API calls)
        nifty_options = nifty_options.sort_values('expiry_date')
        nearest_expiry_date = nifty_options['expiry_date'].iloc[0]
        nifty_options = nifty_options[nifty_options['expiry_date'] == nearest_expiry_date]
        
        print(f"📅 Checking nearest expiry: {nifty_options['expiry'].iloc[0]}")
        
        # Sample some strikes around ATM to check prices
        atm_strike = round(nifty_ltp / 50) * 50
        
        # Get OTM options (more likely to be affordable)
        otm_ce_strikes = [atm_strike + (i * 50) for i in range(1, 8)]  # OTM calls
        otm_pe_strikes = [atm_strike - (i * 50) for i in range(1, 8)]  # OTM puts
        
        affordable_options = []
        
        print("\n🔎 Checking option prices...")
        
        for strike in otm_ce_strikes + otm_pe_strikes:
            for option_type in ['CE', 'PE']:
                try:
                    # Find this specific option
                    option = nifty_options[
                        ((nifty_options['strike'] == strike) | (nifty_options['strike'] == strike * 100)) &
                        (nifty_options[tradingsymbol_col].str.contains(option_type, na=False))
                    ]
                    
                    if option.empty:
                        continue
                    
                    option_row = option.iloc[0]
                    symbol = option_row[tradingsymbol_col]
                    token = str(option_row[token_col])
                    
                    # Get LTP
                    ltp = self.get_option_ltp(symbol, token)
                    
                    if ltp and ltp <= max_budget:
                        cost_for_lot = ltp * 15  # 15 is lot size
                        affordable_options.append({
                            'symbol': symbol,
                            'token': token,
                            'strike': strike,
                            'type': option_type,
                            'ltp': ltp,
                            'cost_per_lot': cost_for_lot,
                            'expiry': option_row['expiry']
                        })
                        print(f"  ✓ Found: {symbol} @ ₹{ltp:.2f} (Total: ₹{cost_for_lot:.2f} for 15 qty)")
                    
                except Exception as e:
                    continue
        
        if not affordable_options:
            print(f"\n❌ No options found below ₹{max_budget}")
            return
        
        # Sort by price (cheapest first)
        affordable_options.sort(key=lambda x: x['ltp'])
        
        # Display options
        print("\n" + "="*60)
        print(f"💎 AFFORDABLE OPTIONS (Below ₹{max_budget})")
        print("="*60)
        
        for idx, opt in enumerate(affordable_options, 1):
            opt_type_name = "CALL" if opt['type'] == "CE" else "PUT"
            print(f"\n{idx}. {opt['symbol']}")
            print(f"   Type: {opt_type_name} | Strike: {opt['strike']}")
            print(f"   Price: ₹{opt['ltp']:.2f} per unit")
            print(f"   Total for 15 qty: ₹{opt['cost_per_lot']:.2f}")
        
        print("\n" + "="*60)
        
        # Ask user to select
        try:
            choice = input(f"\nSelect option to buy (1-{len(affordable_options)}) or 0 to cancel: ").strip()
            choice_num = int(choice)
            
            if choice_num == 0:
                print("\n❌ Cancelled by user")
                return
            
            if choice_num < 1 or choice_num > len(affordable_options):
                print("\n❌ Invalid selection")
                return
            
            selected = affordable_options[choice_num - 1]
            
            # Show order summary
            print("\n" + "-"*60)
            print("📋 ORDER SUMMARY:")
            print(f"   Symbol: {selected['symbol']}")
            print(f"   Type: BUY {selected['type']}")
            print(f"   Strike: {selected['strike']}")
            print(f"   Quantity: 15 (1 lot)")
            print(f"   Price: ₹{selected['ltp']:.2f} per unit")
            print(f"   Total Cost: ₹{selected['cost_per_lot']:.2f}")
            print("-"*60)
            
            confirm = input("\n🔔 Confirm order? (yes/no): ").strip().lower()
            
            if confirm in ['yes', 'y']:
                print("\n🚀 Placing order...")
                success = self.place_option_order(
                    selected['symbol'],
                    selected['token'],
                    15,  # Fixed lot size
                    "BUY"
                )
                
                if success:
                    print("\n🎉 Order completed successfully!")
                else:
                    print("\n❌ Order failed. Please check your account or try again.")
            else:
                print("\n❌ Order cancelled by user")
                
        except ValueError:
            print("\n❌ Invalid input")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    def find_affordable_options_with_balance(self):
        """Find options within available account balance"""
        # Get account balance first
        print("\n🔄 Fetching your account balance...")
        funds = self.get_funds()
        
        if not funds:
            print("\n❌ Could not fetch account balance")
            return
        
        # Get available cash
        available_cash = funds.get('availablecash', 0)
        
        try:
            available_cash = float(available_cash)
        except:
            print("\n❌ Invalid balance data")
            return
        
        if available_cash <= 0:
            print(f"\n❌ Insufficient funds. Available: ₹{available_cash:.2f}")
            return
        
        print(f"\n💰 Available Cash: ₹{available_cash:.2f}")
        
        # Calculate max budget per option (considering lot size of 15)
        # We'll search for options where price * 15 <= available_cash
        max_per_unit = available_cash / 15
        
        print(f"💡 Looking for options priced up to ₹{max_per_unit:.2f} per unit")
        print(f"   (Total cost for 15 qty: ₹{available_cash:.2f})")
        
        # Call the find method with calculated budget
        self.find_affordable_options(max_budget=max_per_unit)


def main():
    """Main function to fetch account balance"""
    print("\n" + "="*60)
    print("  🏦 ANGEL ONE ACCOUNT BALANCE FETCHER")
    print("="*60)
    
    # Initialize fetcher
    fetcher = AngelAccountFetcher()
    
    if fetcher.session_generated:
        while True:
            print("\n" + "-"*60)
            print("📋 MENU:")
            print("  1. View Account Summary")
            print("  2. Option Chain Buy")
            print("  3. Find Affordable Options (Based on Balance)")
            print("  4. Exit")
            print("-"*60)
            
            choice = input("\nEnter your choice (1/2/3/4): ").strip()
            
            if choice == "1":
                fetcher.get_complete_account_summary()
            elif choice == "2":
                fetcher.option_chain_buy()
            elif choice == "3":
                fetcher.find_affordable_options_with_balance()
            elif choice == "4":
                print("\n👋 Goodbye!")
                break
            else:
                print("\n❌ Invalid choice. Please try again.")
    else:
        print("\n❌ [ERROR] Could not connect to Angel One. Please check credentials.")


if __name__ == "__main__":
    main()
