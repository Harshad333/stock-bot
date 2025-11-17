from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import os
import time
import threading
import requests
import pandas as pd
from datetime import datetime, timedelta

# Initialize SmartConnect
api_key = os.environ.get('ANGEL_API_KEY')
username = os.environ.get('ANGEL_CLIENT_ID') 
pwd = os.environ.get('ANGEL_MPIN')
totp_secret = os.environ.get('ANGEL_TOTP_SECRET')

smartApi = SmartConnect(api_key)

try:
    totp = pyotp.TOTP(totp_secret).now()
    print(f"Generated TOTP: {totp}")
except Exception as e:
    print(f"Invalid Token: {e}")
    exit(1)

# Login
data = smartApi.generateSession(username, pwd, totp)
print(f"Login response: {data}")

if data['status'] == False:
    print(f"Login failed: {data}")
    exit(1)
else:
    # Get tokens
    authToken = data['data']['jwtToken']
    refreshToken = data['data']['refreshToken']
    feedToken = smartApi.getfeedToken()
    
    print(f"✅ Login successful!")
    # print(f"Auth Token: {authToken}...")
    # print(f"Feed Token: {feedToken}...")
    
    # WebSocket setup
    correlation_id = "abc123"
    action = 1
    mode = 1
    
    # Get instrument master for options
    print("📥 Downloading instrument master...")
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(url)
        instruments = response.json()
        
        # Filter for NIFTY and BANKNIFTY options
        nifty_options = []
        banknifty_options = []
        
        current_date = datetime.now()
        
        for instrument in instruments:
            if instrument.get('exch_seg') == 'NFO':
                symbol = instrument.get('symbol', '')
                if 'NIFTY' in symbol and 'CE' in symbol or 'PE' in symbol:
                    if 'BANKNIFTY' not in symbol:
                        nifty_options.append(instrument)
                elif 'BANKNIFTY' in symbol and ('CE' in symbol or 'PE' in symbol):
                    banknifty_options.append(instrument)
        
        # Get current week expiry options
        def get_current_expiry_options(options_list, name):
            # Sort by expiry date
            valid_options = []
            for opt in options_list:
                try:
                    expiry_str = opt.get('expiry', '')
                    if expiry_str:
                        expiry_date = datetime.strptime(expiry_str, '%d%b%Y')
                        if expiry_date >= current_date:
                            valid_options.append((opt, expiry_date))
                except:
                    continue
            
            # Sort by expiry date and get nearest
            valid_options.sort(key=lambda x: x[1])
            
            if valid_options:
                nearest_expiry = valid_options[0][1]
                current_expiry_options = [opt[0] for opt in valid_options if opt[1] == nearest_expiry]
                print(f"📅 {name} current expiry: {nearest_expiry.strftime('%d%b%Y')}")
                return current_expiry_options[:10]  # Limit to 10 options
            else:
                print(f"⚠️ No valid {name} options found, using previous expiry")
                # Get last expired options
                expired_options = []
                for opt in options_list:
                    try:
                        expiry_str = opt.get('expiry', '')
                        if expiry_str:
                            expiry_date = datetime.strptime(expiry_str, '%d%b%Y')
                            expired_options.append((opt, expiry_date))
                    except:
                        continue
                
                if expired_options:
                    expired_options.sort(key=lambda x: x[1], reverse=True)
                    last_expiry = expired_options[0][1]
                    return [opt[0] for opt in expired_options if opt[1] == last_expiry][:10]
                return []
        
        current_nifty_options = get_current_expiry_options(nifty_options, "NIFTY")
        current_banknifty_options = get_current_expiry_options(banknifty_options, "BANKNIFTY")
        
        # Prepare tokens for WebSocket
        option_tokens = []
        
        for opt in current_nifty_options[:5]:  # Top 5 NIFTY options
            option_tokens.append(opt['token'])
            print(f"🔵 NIFTY: {opt['symbol']} - Token: {opt['token']}")
        
        for opt in current_banknifty_options[:5]:  # Top 5 BANKNIFTY options
            option_tokens.append(opt['token'])
            print(f"🔴 BANKNIFTY: {opt['symbol']} - Token: {opt['token']}")
        
        token_list = [
            {
                "exchangeType": 2,  # NFO
                "tokens": option_tokens
            }
        ]
        
    except Exception as e:
        print(f"❌ Error loading instruments: {e}")
        # Fallback to sample tokens
        token_list = [
            {
                "exchangeType": 2,
                "tokens": ["26009", "26037"]
            }
        ]
    
    sws = SmartWebSocketV2(authToken, api_key, username, feedToken)
    
    # Store live data
    nifty_data = {}
    banknifty_data = {}
    
    def on_data(wsapp, message):
        try:
            if isinstance(message, dict) and 'tk' in message:
                token = message['tk']
                ltp = message.get('lp', 0)
                symbol = message.get('ts', 'Unknown')
                print(f"📊 Live Update for Token: {symbol}")
                if 'NIFTY' in str(symbol) and 'BANKNIFTY' not in str(symbol):
                    nifty_data[token] = {'symbol': symbol, 'ltp': ltp}
                    print(f"\n🔵 === NIFTY OPTIONS ===")
                    for tk, data in nifty_data.items():
                        print(f"   {data['symbol']} | LTP: ₹{data['ltp']}")
                    
                elif 'BANKNIFTY' in str(symbol):
                    banknifty_data[token] = {'symbol': symbol, 'ltp': ltp}
                    print(f"\n🔴 === BANKNIFTY OPTIONS ===")
                    for tk, data in banknifty_data.items():
                        print(f"   {data['symbol']} | LTP: ₹{data['ltp']}")
                    
                print("\n" + "="*50)
                
            else:
                print(f"📊 Live Data: {message}")
        except Exception as e:
            print(f"📊 Data: {message}")
    
    def on_open(wsapp):
        print("✅ WebSocket Connected!")
        sws.subscribe(correlation_id, mode, token_list)
        print(f"📡 Subscribed to tokens")
    
    def on_error(wsapp, error):
        print(f"❌ WebSocket Error: {error}")
    
    def on_close(wsapp):
        print("🔌 WebSocket Closed")
    
    # Assign callbacks
    sws.on_open = on_open
    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = on_close
    
    # Start WebSocket in background thread
    ws_thread = threading.Thread(target=sws.connect, daemon=True)
    ws_thread.start()
    
    print("🚀 System started! Press Ctrl+C to exit...")
    
    try:
        while True:
            time.sleep(5)
            # Print summary every 5 seconds
            if nifty_data or banknifty_data:
                print("\n" + "="*60)
                print("📈 LIVE OPTIONS SUMMARY")
                print("="*60)
                
                if nifty_data:
                    print("🔵 NIFTY OPTIONS:")
                    for token, data in nifty_data.items():
                        print(f"  • {data['symbol']}: ₹{data['ltp']}")
                
                if banknifty_data:
                    print("\n🔴 BANKNIFTY OPTIONS:")
                    for token, data in banknifty_data.items():
                        print(f"  • {data['symbol']}: ₹{data['ltp']}")
                
                print("="*60)
                
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sws.close_connection()