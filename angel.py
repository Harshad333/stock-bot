import random
import time
from datetime import datetime, timedelta
import pandas as pd
import threading
import numpy as np
import math
import sys
import zipfile  
import io   
    

import os # For securely loading credentials
# --- ⚠️ REAL API IMPORTS (INSTALLATION IS MANDATORY) ---
# 🟢 FINAL FIX: SmartConnect को आयात करने का यह सही तरीका है।
from SmartApi import SmartConnect, SmartWebSocket  # <-- MODIFIED: Added SmartWebSocket
import requests # Used for downloading instrument master file
# --------------------------------------------------------

# --- Matplotlib Imports for Charting (Commented out due to tkinter dependency) ---
# import matplotlib
# matplotlib.use('TkAgg')
# from matplotlib.figure import Figure
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# =================================================================
# 1. GLOBAL CONSTANTS AND MOCK DATA SETUP
# =================================================================

ATR_TSL_TRIGGER = 1.0 
ATR_TSL_STEP = 1.0    
MOCK_ATR = 30.0       
TIMEFRAME = '5minute' 
QUANTITY = 50
MAX_TRADES_PER_DAY = 5

GLOBAL_INDEX_PARAMS = {} 

CURRENT_TRADE_STATE = {
    "NIFTY": {'is_open': False, 'symbol': None, 'token': 0, 'entry_price': 0.0, 'quantity': 0, 'ltp': 0.0, 
              'sl_price': 0.0, 'target_price': 0.0, 'Entry_Time': None, 'trades_done': 0, 'index_ltp': 20000.0,
              'high_seen': 0.0, 'low_seen': float('inf'),
              'latest_rsi': 50.0, 'latest_sma': 20000.0},
    "BANKNIFTY": {'is_open': False, 'symbol': None, 'token': 0, 'entry_price': 0.0, 'quantity': 0, 'ltp': 0.0, 
                  'sl_price': 0.0, 'target_price': 0.0, 'Entry_Time': None, 'trades_done': 0, 'index_ltp': 45000.0,
                  'high_seen': 0.0, 'low_seen': float('inf'),
                  'latest_rsi': 50.0, 'latest_sma': 45000.0}
}

TRADE_LOG_DATA = []
MAX_HISTORY_POINTS = 150 
GLOBAL_HISTORY = {
    "NIFTY": {'ltp': [], 'ema9': [], 'ema15': [], 'rsi': [], 'sma': []},
    "BANKNIFTY": {'ltp': [], 'ema9': [], 'ema15': [], 'rsi': [], 'sma': []}
}

# =================================================================
# 2. ANGEL ONE CLIENT AND HELPER FUNCTIONS (API INTEGRATION)
# =================================================================

class AngelOneAPIClient:
    def __init__(self, client_id, password, api_key, secret_key):
        self.client_id = client_id
        self.password = password
        self.api_key = api_key
        self.secret_key = secret_key 
        self.client = None
        self.session_generated = False
        self.instrument_df = None
        
        # --- 🟢 NEW: Tokens for WebSocket ---
        self.auth_token = None
        self.feed_token = None
        self.websocket = None
        # -------------------------------------
        
        self.connect()

    def connect(self):
        """Generates the Angel One session, gets tokens, and downloads instrument master."""
        try:
            self.obj = SmartConnect(api_key=self.api_key, access_token=self.secret_key) 
            
            print(f"Attempting login for Client ID: {self.client_id}...")
            data = self.obj.generateSession(self.client_id, self.password) 
            
            # MODIFIED: Check for 'jwtToken' specifically
            if data and data.get('status') and data['data'].get('jwtToken'):
                self.client = self.obj
                self.session_generated = True
                
                # --- 🟢 IMPORTANT: STORE TOKENS ---
                self.auth_token = data['data']['jwtToken']
                self.feed_token = self.obj.getfeedToken()
                # ------------------------------------
                
                print("✅ Angel One Session generated successfully.")
                print(f"✅ Feed Token obtained: {self.feed_token[:10]}...") # Show partial token
                
                # --- 🟢 INSTRUMENT MASTER DOWNLOAD AND LOAD ---
                print("Downloading Instrument Master...")
                response = requests.get("https://marginmns.angelbroking.com/history/symbolfile.txt", stream=True)
                
                if response.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        file_name = z.namelist()[0] 
                        with z.open(file_name) as f:
                            self.instrument_df = pd.read_csv(f)
                            print("✅ Instrument Master loaded.")
                            self.instrument_df = self.instrument_df[self.instrument_df['exch_seg'] == 'NFO'] 
                else:
                    print(f"❌ Failed to download Instrument Master. Status Code: {response.status_code}")
                    
            else:
                print(f"❌ Angel One Login Failed: {data.get('message', 'Unknown error')}")
                self.session_generated = False
                
        except Exception as e:
            print(f"Angel One Connection Error during Connect/Master Download: {e}")
            self.session_generated = False

    def get_ltp(self, exchange, tradingsymbol, symboltoken):
        """Fetches Live LTP from Angel One API."""
        if not self.session_generated:
            return 0.0
            
        try:
            response = self.client.ltpData(exchange, tradingsymbol, symboltoken)
            if response and response.get('data') and response['data'].get('ltp'):
                return float(response['data']['ltp']) 
            else:
                return 0.0
            
        except Exception as e:
            print(f"Error fetching LTP for {tradingsymbol}: {e}")
            return 0.0
            
    def fetch_instrument_token_and_ltp(self, exchange, tradingsymbol):
        """Fetches the active SymbolToken and the current LTP using the Instrument Master."""
        if not self.session_generated or self.instrument_df is None:
            return None, None
            
        try:
            result = self.instrument_df[self.instrument_df['tradingsymbol'] == tradingsymbol]
            
            if not result.empty:
                found_token = str(result.iloc[0]['token']) 
                ltp = self.get_ltp(exchange, tradingsymbol, found_token)
                
                if ltp > 0.0:
                    return found_token, ltp
                else:
                    return None, None
            else:
                return None, None
            
        except Exception as e:
            print(f"Error fetching token/LTP for {tradingsymbol}: {e}")
            return None, None
            
    def place_order(self, *args, **kwargs):
        # ⚠️ Real Order Placement Logic - Replace with self.client.order.placeOrder
        print(f"MOCK ORDER PLACED: {kwargs.get('transactiontype')} {kwargs.get('tradingsymbol')}")
        return {'status': True, 'orderid': random.randint(100000, 999999)} 
        
    def modify_order(self, *args, **kwargs):
        # ⚠️ Real Order Modification Logic
        print(f"MOCK ORDER MODIFIED: ID {kwargs.get('orderid')} Trigger {kwargs.get('triggerprice')}")
        return {'status': True}
        
    def cancel_order(self, *args, **kwargs):
        # ⚠️ Real Order Cancellation Logic
        print(f"MOCK ORDER CANCELLED: ID {kwargs.get('orderid')}")
        return {'status': True}
        
    # --- 🟢 NEW: WEBSOCKET METHODS ---
    
    def start_websocket(self, on_data_callback, on_open_callback):
        """Initializes and connects to the SmartWebSocketV2."""
        if not self.auth_token or not self.feed_token:
            print("❌ Cannot start WebSocket: Auth Token or Feed Token is missing.")
            return

        print("Starting WebSocket connection...")
        self.websocket = SmartWebSocket(self.auth_token, self.api_key, self.client_id, self.feed_token)

        # Assign callback functions
        self.websocket.on_data = on_data_callback
        self.websocket.on_open = on_open_callback
        self.websocket.on_error = self.on_error_callback
        self.websocket.on_close = self.on_close_callback

        # Run the WebSocket connection in a separate thread
        # This is CRITICAL so it doesn't block your main GUI/logic thread
        ws_thread = threading.Thread(target=self.websocket.connect)
        ws_thread.daemon = True  # Ensures thread exits when main program exits
        ws_thread.start()
        print("✅ WebSocket connection thread started.")

    def subscribe_to_instruments(self, tokens_to_subscribe):
        """
        Subscribes to a list of instrument tokens.
        Call this *after* the on_open_callback is triggered.
        """
        if self.websocket and self.websocket.is_open():
            correlation_id = "my_subscription_1"
            mode = 1  # 1 for LTP
            
            # Format: [{"exchangeType": 1, "tokens": ["12345", "67890"]}]
            # 2 = NFO
            token_list = [
                {
                    "exchangeType": 2, # 2 for NFO (Futures & Options)
                    "tokens": tokens_to_subscribe
                }
            ]
            
            print(f"Attempting to subscribe to tokens: {tokens_to_subscribe}")
            self.websocket.subscribe(correlation_id, mode, token_list)
        else:
            print("❌ Cannot subscribe: WebSocket is not connected or open.")

    # --- 🟢 NEW: WEBSOCKET CALLBACKS ---
    
    def on_error_callback(self, wsapp, error):
        print(f"WebSocket Error: {error}")

    def on_close_callback(self, wsapp, code, reason):
        print("WebSocket Connection Closed.")

# --- DYNAMIC ROLLOVER LOGIC ---

def get_futures_symbols_for_rollover(angelone_client):
    """Generates Trading Symbols, fetches the active SymbolToken, and Current LTP (Entry Level)."""
    global GLOBAL_INDEX_PARAMS 
    now = datetime.now()
    next_month_date = now + timedelta(days=30) 
    
    if now.day > 20 and now.weekday() >= 3: 
        active_contract_month = next_month_date.strftime('%y%b').upper() 
    else:
        active_contract_month = now.strftime('%y%b').upper() 
        
    NIFTY_SYMBOL = f"NIFTY{active_contract_month}FUT" 
    BNF_SYMBOL = f"BANKNIFTY{active_contract_month}FUT" 
    
    nifty_token, nifty_ltp = angelone_client.fetch_instrument_token_and_ltp(exchange='NFO', tradingsymbol=NIFTY_SYMBOL)
    bnf_token, bnf_ltp = angelone_client.fetch_instrument_token_and_ltp(exchange='NFO', tradingsymbol=BNF_SYMBOL)
    
    INDEX_PARAMS_DYN = {
        "NIFTY": {
            'FUTURES_TOKEN': nifty_token,       
            'EXCHANGE': 'NFO', 
            'FUTURES_SYMBOL': NIFTY_SYMBOL, 
            'ENTRY_LEVEL': nifty_ltp,           
            'MOCK_LAST_ATR': MOCK_ATR
        },
        "BANKNIFTY": {
            'FUTURES_TOKEN': bnf_token,         
            'EXCHANGE': 'NFO', 
            'FUTURES_SYMBOL': BNF_SYMBOL,
            'ENTRY_LEVEL': bnf_ltp,             
            'MOCK_LAST_ATR': MOCK_ATR
        }
    }
    
    if nifty_ltp is None or bnf_ltp is None:
        raise ConnectionError("❌ Initial Token/LTP fetch failed. Could not proceed.")
        
    print(f"✅ Initial Parameters Set: NIFTY LTP {nifty_ltp:,.2f}, BNF LTP {bnf_ltp:,.2f}")
    print(f"📈 Initial Data Retrieved - NIFTY: ₹{nifty_ltp:,.2f}, BANKNIFTY: ₹{bnf_ltp:,.2f}")
    GLOBAL_INDEX_PARAMS = INDEX_PARAMS_DYN
    return INDEX_PARAMS_DYN

# --- INDICATOR AND TRADING LOGIC (Placeholder for completeness) ---
# ... (All indicator, monitoring thread, and GUI code assumed to be here) ...


# --- 🟢 NEW: WebSocket Callback Definitions ---
# These functions run in the background thread and get the live data

def my_on_data_callback(wsapp, message):
    """
    This is where you get the LIVE data.
    'message' is the data packet from the server.
    """
    # --- YOUR LOGIC HERE ---
    # This is where you'll parse the 'message' dictionary,
    # find the token, find the 'ltp',
    # and update your CURRENT_TRADE_STATE or trigger chart updates.
    
    # Example:
    # print(f"LIVE TICK: {message}") # (Optional: very noisy, prints every tick)
    
    try:
        # Check if it's an LTP packet (token 'tk' and last price 'lp' fields)
        if 'tk' in message and 'lp' in message:
            ltp = float(message['lp'])
            token = message['tk']
            
            # Update NIFTY state if token matches
            if token == GLOBAL_INDEX_PARAMS["NIFTY"]["FUTURES_TOKEN"]:
                CURRENT_TRADE_STATE["NIFTY"]["index_ltp"] = ltp
                print(f"🔴 NIFTY Live: ₹{ltp:,.2f}")
            
            # Update BANKNIFTY state if token matches
            elif token == GLOBAL_INDEX_PARAMS["BANKNIFTY"]["FUTURES_TOKEN"]:
                CURRENT_TRADE_STATE["BANKNIFTY"]["index_ltp"] = ltp
                print(f"🔵 BANKNIFTY Live: ₹{ltp:,.2f}")

    except Exception as e:
        print(f"Error parsing tick data: {e} - Data: {message}")


def my_on_open_callback(wsapp):
    """
    This function is called once the connection is successfully established.
    This is the correct place to subscribe to instruments.
    """
    print("✅ WebSocket Connection Opened. Subscribing to instruments...")
    
    try:
        # Get the tokens we found during startup
        nifty_token = GLOBAL_INDEX_PARAMS["NIFTY"]["FUTURES_TOKEN"]
        bnf_token = GLOBAL_INDEX_PARAMS["BANKNIFTY"]["FUTURES_TOKEN"]
        
        # Put them in a list of strings
        tokens_to_watch = [nifty_token, bnf_token]
        
        # Call the subscribe method (it's part of the angelone object)
        angelone.subscribe_to_instruments(tokens_to_watch)
    except Exception as e:
        print(f"Error during subscription: {e}")

# =================================================================
# 6. MAIN EXECUTION - 🔑 आपकी अद्यतन क्रेडेंशियल्स की जगह
# =================================================================

if __name__ == '__main__':
    # ⚠️ 1. SECURITY IMPROVEMENT: Load credentials securely from environment variables
    try:
        API_KEY = os.environ['ANGEL_API_KEY']
        SECRET_KEY = os.environ['ANGEL_SECRET_KEY']
        CLIENT_ID = os.environ['ANGEL_CLIENT_ID']
        PASSWORD = os.environ['ANGEL_PASSWORD']
    except KeyError as e:
        print(f"❌ Fatal Error: Environment variable not set: {e}")
        print("Please set ANGEL_API_KEY, ANGEL_SECRET_KEY, ANGEL_CLIENT_ID, and ANGEL_PASSWORD.")
        sys.exit(1)
    
    # 2. Initialize the Angel One Client
    # This will now also log in AND get the feed_token
    angelone = AngelOneAPIClient(CLIENT_ID, PASSWORD, API_KEY, SECRET_KEY) 
    
    if not angelone.session_generated:
        print("Could not start the application due to login failure. Please check credentials and try again.")
        sys.exit(1)

    # 3. AUTO-UPDATE INDEX PARAMS: Use the client to fetch live data
    try:
        GLOBAL_INDEX_PARAMS = get_futures_symbols_for_rollover(angelone)
    except ConnectionError as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
    
    # 4. --- 🟢 NEW: Start the WebSocket ---
    if angelone.session_generated:
        angelone.start_websocket(
            on_data_callback=my_on_data_callback,
            on_open_callback=my_on_open_callback
        )
    
    # 5. Start GUI / Main Logic
    # ... (Your Tkinter GUI .mainloop() would go here) ...
    
    if angelone.session_generated:
        print("\n🎉 ALL SETUP COMPLETE! WebSocket is attempting to connect.")
        print("The system is now ready to receive live data.")
        print("Press CTRL+C to stop the script.")

    # 6. --- 🟢 NEW: Keep main thread alive ---
    # This is essential. If your script ends, the background thread dies.
    # If you are running a Tkinter GUI, its .mainloop() function
    # does this for you, and you can remove this part.
    try:
        while True:
            # Print current prices every 5 seconds
            if int(time.time()) % 5 == 0:
                nifty_price = CURRENT_TRADE_STATE['NIFTY']['index_ltp']
                bnf_price = CURRENT_TRADE_STATE['BANKNIFTY']['index_ltp']
                print(f"💹 Current Prices - NIFTY: ₹{nifty_price:,.2f} | BANKNIFTY: ₹{bnf_price:,.2f}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if angelone.websocket:
            angelone.websocket.close() # Attempt to close WebSocket gracefully
        sys.exit(0)