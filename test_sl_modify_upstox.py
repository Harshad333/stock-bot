"""
SL MODIFICATION TESTER - UPSTOX
================================
Test: Place order -> Place SL -> Wait 30s -> Modify SL

IMPORTANT: This will place REAL orders!
"""

import upstox_client
from upstox_client.rest import ApiException
import time
import datetime
import requests
import gzip

# ========== CONFIG ==========
API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0TkNUUFEiLCJqdGkiOiI2OTUyM2Y2NmEyNWJmMTZmNjE1YTg1ODAiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk5Nzg2MiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.Vw7j3I1LtPlX9Zu-_XhHKKe8k06rc8uxj-O_B612CrU"

ORDER_QTY = 25  # Minimum lot (smaller for testing)
# ============================

def round_to_tick(price, tick_size=0.05):
    return round(price / tick_size) * tick_size


def get_nifty_ltp(api_client):
    """Get NIFTY spot LTP"""
    try:
        api_instance = upstox_client.MarketQuoteApi(api_client)
        
        # Try different formats
        tokens_to_try = [
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX:Nifty 50',
            'NSE_INDEX|NIFTY 50',
            'NSE_INDEX:NIFTY_50'
        ]
        
        for token in tokens_to_try:
            try:
                api_response = api_instance.ltp(token, api_version='2.0')
                if api_response and api_response.status == 'success':
                    data = api_response.data
                    if data:
                        for key in data:
                            ltp = float(getattr(data[key], 'last_price', 0))
                            if ltp > 0:
                                return ltp
            except:
                continue
                
        # Fallback - Ask user
        print("[INFO] Could not fetch NIFTY LTP from API")
        user_input = input("Enter current NIFTY price (e.g. 23850): ")
        return float(user_input)
        
    except Exception as e:
        print(f"[ERROR] NIFTY LTP: {e}")
        user_input = input("Enter current NIFTY price (e.g. 23850): ")
        return float(user_input)



def get_atm_option(api_client, nifty_price, option_type='CE'):
    """Find ATM option contract"""
    try:
        atm_strike = round(nifty_price / 50) * 50
        print(f"[INFO] ATM Strike: {atm_strike}")
        
        # Download instrument master
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NFO.json.gz"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = gzip.decompress(response.content)
            instruments = eval(data.decode('utf-8'))
            
            # Find NIFTY options with this strike
            today = datetime.datetime.now().date()
            
            for inst in instruments:
                if inst.get('instrument_type') == 'OPTIDX' and 'NIFTY' in inst.get('name', ''):
                    # Check if not BANKNIFTY/FINNIFTY
                    trading_symbol = inst.get('tradingsymbol', '')
                    if 'BANK' in trading_symbol or 'FIN' in trading_symbol or 'MID' in trading_symbol:
                        continue
                    
                    # Check strike
                    if int(inst.get('strike', 0)) == atm_strike:
                        # Check option type
                        if option_type in trading_symbol:
                            # Check expiry (future)
                            expiry_str = inst.get('expiry', '')
                            try:
                                expiry_dt = datetime.datetime.strptime(expiry_str, '%Y-%m-%d').date()
                                if expiry_dt >= today:
                                    print(f"[FOUND] {trading_symbol} | Token: {inst.get('instrument_key', '')} | Expiry: {expiry_str}")
                                    return {
                                        'symbol': trading_symbol,
                                        'token': inst.get('instrument_key', ''),
                                        'strike': atm_strike,
                                        'expiry': expiry_str
                                    }
                            except:
                                continue
        
        print("[ERROR] Could not find ATM option")
        return None
        
    except Exception as e:
        print(f"[ERROR] Finding option: {e}")
        return None


def get_option_ltp(api_client, token):
    """Get option LTP"""
    try:
        api_instance = upstox_client.MarketQuoteApi(api_client)
        api_response = api_instance.ltp(token, api_version='2.0')
        
        if api_response and api_response.status == 'success':
            data = api_response.data
            if data and token in data:
                return float(getattr(data[token], 'last_price', 0))
    except Exception as e:
        print(f"[ERROR] Option LTP: {e}")
    return None


def run_sl_modify_test():
    """Main test function"""
    
    print("=" * 60)
    print("   SL MODIFICATION TEST - UPSTOX")
    print("=" * 60)
    print(f"\n⚠️  WARNING: This will place REAL orders!")
    print(f"   Quantity: {ORDER_QTY}")
    print()
    
    confirm = input("Type 'YES' to proceed: ")
    if confirm != 'YES':
        print("Aborted.")
        return
    
    # Connect
    print("\n[STEP 1] Connecting to Upstox...")
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    
    # Verify connection
    try:
        user_api = upstox_client.UserApi(api_client)
        profile = user_api.get_profile(api_version='2.0')
        if profile.status != 'success':
            print("[ERROR] Connection failed!")
            return
        print(f"[OK] Connected as: {profile.data.user_id}")
    except Exception as e:
        print(f"[ERROR] Connection: {e}")
        return
    
    # Get NIFTY LTP
    print("\n[STEP 2] Getting NIFTY LTP...")
    nifty_ltp = get_nifty_ltp(api_client)
    if not nifty_ltp:
        print("[ERROR] Could not get NIFTY LTP")
        return
    print(f"[OK] NIFTY: {nifty_ltp}")
    
    # Find ATM option
    print("\n[STEP 3] Finding ATM CE option...")
    contract = get_atm_option(api_client, nifty_ltp, 'CE')
    if not contract:
        print("[ERROR] Could not find option contract")
        return
    
    # Get option LTP
    opt_ltp = get_option_ltp(api_client, contract['token'])
    print(f"[OK] Option LTP: ₹{opt_ltp}")
    
    # Place BUY order
    print("\n[STEP 4] Placing BUY order...")
    order_api = upstox_client.OrderApi(api_client)
    
    buy_body = upstox_client.PlaceOrderRequest(
        quantity=ORDER_QTY,
        product='I',
        validity='DAY',
        price=0.0,
        instrument_token=contract['token'],
        order_type='MARKET',
        transaction_type='BUY',
        disclosed_quantity=0,
        trigger_price=0.0,
        is_amo=False
    )
    
    try:
        buy_response = order_api.place_order(buy_body, api_version='2.0')
        if buy_response.status != 'success':
            print(f"[ERROR] Buy order failed: {buy_response}")
            return
        buy_order_id = buy_response.data.order_id
        print(f"[OK] Buy Order ID: {buy_order_id}")
    except Exception as e:
        print(f"[ERROR] Buy order: {e}")
        return
    
    # Wait for order to fill
    print("[INFO] Waiting 3s for order fill...")
    time.sleep(3)
    
    # Get fill price
    entry_price = opt_ltp  # Fallback
    try:
        order_history = order_api.get_order_history(buy_order_id, api_version='2.0')
        if order_history.status == 'success':
            for order in order_history.data:
                if getattr(order, 'status', '').lower() == 'complete':
                    entry_price = float(getattr(order, 'average_price', opt_ltp))
                    break
        print(f"[OK] Entry Price: ₹{entry_price}")
    except:
        pass
    
    # Calculate SL
    initial_sl = round_to_tick(entry_price * 0.90)  # 10% below
    initial_trigger = round_to_tick(initial_sl + 0.05)
    
    print(f"\n[STEP 5] Placing SL order at ₹{initial_sl} (Trigger: ₹{initial_trigger})...")
    
    sl_body = upstox_client.PlaceOrderRequest(
        quantity=ORDER_QTY,
        product='I',
        validity='DAY',
        price=float(initial_sl),
        trigger_price=float(initial_trigger),
        instrument_token=contract['token'],
        order_type='SL',
        transaction_type='SELL',
        disclosed_quantity=0,
        is_amo=False
    )
    
    try:
        sl_response = order_api.place_order(sl_body, api_version='2.0')
        if sl_response.status != 'success':
            print(f"[ERROR] SL order failed: {sl_response}")
            # Exit position
            print("[INFO] Exiting position...")
            exit_body = upstox_client.PlaceOrderRequest(
                quantity=ORDER_QTY, product='I', validity='DAY', price=0.0,
                instrument_token=contract['token'], order_type='MARKET',
                transaction_type='SELL', disclosed_quantity=0, trigger_price=0.0, is_amo=False
            )
            order_api.place_order(exit_body, api_version='2.0')
            return
        sl_order_id = sl_response.data.order_id
        print(f"[OK] SL Order ID: {sl_order_id}")
    except Exception as e:
        print(f"[ERROR] SL order: {e}")
        return
    
    # Wait 30 seconds
    print("\n" + "=" * 60)
    print("   WAITING 30 SECONDS BEFORE SL MODIFICATION...")
    print("=" * 60)
    for i in range(30, 0, -1):
        print(f"\r   Countdown: {i}s ", end='', flush=True)
        time.sleep(1)
    print("\n")
    
    # Now MODIFY SL
    new_sl = round_to_tick(entry_price * 0.95)  # Move SL up to 5% below (from 10%)
    new_trigger = round_to_tick(new_sl + 0.05)
    
    print(f"[STEP 6] Modifying SL: ₹{initial_sl} -> ₹{new_sl} (Trigger: ₹{new_trigger})...")
    
    modify_body = upstox_client.ModifyOrderRequest(
        quantity=ORDER_QTY,
        order_id=sl_order_id,
        order_type='SL',
        price=float(new_sl),
        trigger_price=float(new_trigger),
        validity='DAY',
        disclosed_quantity=0
    )
    
    try:
        modify_response = order_api.modify_order(modify_body, api_version='2.0')
        print(f"\n[MODIFY RESPONSE] Status: {modify_response.status}")
        print(f"[MODIFY RESPONSE] Full: {modify_response}")
        
        if modify_response.status == 'success':
            print("\n✅ SL MODIFICATION SUCCESS!")
        else:
            print(f"\n❌ SL MODIFICATION FAILED!")
            print(f"   Response: {modify_response}")
            
    except ApiException as e:
        print(f"\n❌ SL MODIFICATION API ERROR!")
        print(f"   Status: {e.status}")
        print(f"   Reason: {e.reason}")
        print(f"   Body: {e.body}")
        
    except Exception as e:
        print(f"\n❌ SL MODIFICATION ERROR: {e}")
    
    # Cleanup - Exit position
    print("\n[STEP 7] Cleaning up - Exiting position...")
    
    # Cancel SL order first
    try:
        order_api.cancel_order(sl_order_id, api_version='2.0')
        print(f"[OK] SL order cancelled")
    except:
        pass
    
    # Exit position
    try:
        exit_body = upstox_client.PlaceOrderRequest(
            quantity=ORDER_QTY,
            product='I',
            validity='DAY',
            price=0.0,
            instrument_token=contract['token'],
            order_type='MARKET',
            transaction_type='SELL',
            disclosed_quantity=0,
            trigger_price=0.0,
            is_amo=False
        )
        exit_response = order_api.place_order(exit_body, api_version='2.0')
        if exit_response.status == 'success':
            print(f"[OK] Position closed. Exit Order ID: {exit_response.data.order_id}")
        else:
            print(f"[WARN] Exit order: {exit_response}")
    except Exception as e:
        print(f"[ERROR] Exit: {e}")
    
    print("\n" + "=" * 60)
    print("   TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_sl_modify_test()
