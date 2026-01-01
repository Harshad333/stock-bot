"""
🧪 SL MODIFICATION LIVE TEST - UPSTOX (Option Chain API)
=========================================================
Uses Option Chain API to get correct instrument_key
"""

import upstox_client
from upstox_client.rest import ApiException
import time
import datetime
import requests

# ========== CONFIG ==========
API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBQzY3MjciLCJqdGkiOiI2OTUyMGZjOTdmNWZjYjBjNGFkZmNmNmIiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk4NTY3MywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.j7uPFjzzN58ZMiXhapuzZ_-zyPHBv9bMztxfrulYxWk"

ORDER_QTY = 75  # NIFTY lot size
WAIT_BEFORE_MODIFY = 60
# ============================

def round_to_tick(price, tick_size=0.05):
    return round(price / tick_size) * tick_size

def get_option_chain_contract(access_token, strike, option_type='PE'):
    """Get contract from Upstox Option Chain API"""
    try:
        url = "https://api.upstox.com/v2/option/contract"
        params = {"instrument_key": "NSE_INDEX|Nifty 50"}
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print(f"[INFO] Fetching option chain from API...")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and 'data' in data:
                contracts = data['data']
                print(f"[INFO] Got {len(contracts)} contracts")
                
                today = datetime.datetime.now().date()
                candidates = []
                
                for contract in contracts:
                    # Check strike and type
                    if contract.get('strike_price') == float(strike) and \
                       contract.get('instrument_type') == option_type:
                        expiry_str = contract.get('expiry')
                        if expiry_str:
                            try:
                                exp_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
                                if exp_date >= today:
                                    candidates.append({
                                        'contract': contract,
                                        'expiry': exp_date
                                    })
                            except:
                                continue
                
                if candidates:
                    candidates.sort(key=lambda x: x['expiry'])
                    best = candidates[0]['contract']
                    
                    return {
                        'symbol': best['trading_symbol'],
                        'token': best['instrument_key'],
                        'strike': strike,
                        'expiry': best['expiry']
                    }
        
        print(f"[ERROR] Option chain API failed: {response.status_code}")
        print(f"        Response: {response.text[:200]}")
        return None
        
    except Exception as e:
        print(f"[ERROR] Option chain: {e}")
        return None

def get_option_ltp(api_client, token):
    """Get option LTP"""
    try:
        api_instance = upstox_client.MarketQuoteApi(api_client)
        api_response = api_instance.ltp(token, api_version='2.0')
        
        if api_response and api_response.status == 'success' and api_response.data:
            for key in api_response.data:
                return float(getattr(api_response.data[key], 'last_price', 0))
    except Exception as e:
        print(f"[WARN] LTP: {e}")
    return None

def run_test():
    print("=" * 70)
    print("   🧪 SL MODIFICATION TEST - UPSTOX")
    print("=" * 70)
    
    print(f"\n⚠️  WARNING: REAL orders!")
    print(f"   Qty: {ORDER_QTY}, Wait: {WAIT_BEFORE_MODIFY}s")
    
    # Get strike input
    strike_input = input("\n   Enter Strike (e.g., 25950): ").strip()
    strike = int(strike_input) if strike_input else 25950
    
    option_input = input("   CE or PE [PE]: ").strip().upper()
    option_type = option_input if option_input in ['CE', 'PE'] else 'PE'
    
    confirm = input("\nType 'YES' to proceed: ")
    if confirm != 'YES':
        print("Aborted.")
        return
    
    # Connect
    print("\n[STEP 1] Connecting...")
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    
    try:
        user_api = upstox_client.UserApi(api_client)
        profile = user_api.get_profile(api_version='2.0')
        print(f"✅ Connected: {profile.data.user_id}")
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    
    # Get contract from Option Chain API
    print("\n[STEP 2] Getting Contract from Option Chain API...")
    contract = get_option_chain_contract(ACCESS_TOKEN, strike, option_type)
    
    if not contract:
        print("[ERROR] Could not get contract. Try during market hours.")
        return
    
    print(f"✅ Contract: {contract['symbol']}")
    print(f"   Token: {contract['token']}")
    print(f"   Expiry: {contract['expiry']}")
    
    # Get LTP
    opt_ltp = get_option_ltp(api_client, contract['token'])
    entry_price = opt_ltp if opt_ltp else 50.0
    print(f"✅ LTP: ₹{entry_price}")
    
    # Place BUY
    print("\n[STEP 3] Placing BUY Order...")
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
        buy_resp = order_api.place_order(buy_body, api_version='2.0')
        if buy_resp.status != 'success':
            print(f"[ERROR] Buy: {buy_resp}")
            return
        buy_order_id = buy_resp.data.order_id
        print(f"✅ Buy Order: {buy_order_id}")
    except ApiException as e:
        print(f"[ERROR] {e.status}: {e.body}")
        return
    
    time.sleep(3)
    
    # Get fill price
    try:
        history = order_api.get_order_history(buy_order_id, api_version='2.0')
        if history.status == 'success':
            for o in history.data:
                if getattr(o, 'status', '').lower() == 'complete':
                    entry_price = float(getattr(o, 'average_price', entry_price))
                    break
    except:
        pass
    print(f"✅ Entry: ₹{entry_price}")
    
    # Place SL
    print("\n[STEP 4] Placing SL Order...")
    initial_sl = round_to_tick(entry_price * 0.90)
    initial_trigger = round_to_tick(initial_sl + 0.05)
    
    print(f"   SL: ₹{initial_sl}, Trigger: ₹{initial_trigger}")
    
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
        sl_resp = order_api.place_order(sl_body, api_version='2.0')
        if sl_resp.status != 'success':
            print(f"[ERROR] SL: {sl_resp}")
            # Exit
            order_api.place_order(upstox_client.PlaceOrderRequest(
                quantity=ORDER_QTY, product='I', validity='DAY', price=0.0,
                instrument_token=contract['token'], order_type='MARKET',
                transaction_type='SELL', disclosed_quantity=0, trigger_price=0.0, is_amo=False
            ), api_version='2.0')
            return
        sl_order_id = sl_resp.data.order_id
        print(f"✅ SL Order: {sl_order_id}")
    except ApiException as e:
        print(f"[ERROR] {e.status}: {e.body}")
        return
    
    # Wait
    print(f"\n[STEP 5] Waiting {WAIT_BEFORE_MODIFY}s...")
    for i in range(WAIT_BEFORE_MODIFY, 0, -1):
        ltp = get_option_ltp(api_client, contract['token']) or entry_price
        pnl = (ltp - entry_price) * ORDER_QTY
        print(f"\r   {i:3d}s | LTP: ₹{ltp:.1f} | P&L: ₹{pnl:+.0f} ", end='', flush=True)
        time.sleep(1)
    print()
    
    # Modify SL
    new_sl = round_to_tick(entry_price * 0.95)
    new_trigger = round_to_tick(new_sl + 0.05)
    
    print(f"\n[STEP 6] Modifying SL: ₹{initial_sl} → ₹{new_sl}")
    
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
        mod_resp = order_api.modify_order(modify_body, api_version='2.0')
        print(f"   Status: {mod_resp.status}")
        if mod_resp.status == 'success':
            print("\n   ✅✅✅ SL MODIFICATION SUCCESS! ✅✅✅")
        else:
            print(f"   ❌ Failed: {mod_resp}")
    except ApiException as e:
        print(f"   ❌ Error: {e.status} - {e.body}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Cleanup
    print("\n[STEP 7] Cleanup...")
    try:
        order_api.cancel_order(sl_order_id, api_version='2.0')
        print("✅ SL cancelled")
    except:
        pass
    
    try:
        exit_body = upstox_client.PlaceOrderRequest(
            quantity=ORDER_QTY, product='I', validity='DAY', price=0.0,
            instrument_token=contract['token'], order_type='MARKET',
            transaction_type='SELL', disclosed_quantity=0, trigger_price=0.0, is_amo=False
        )
        order_api.place_order(exit_body, api_version='2.0')
        print("✅ Position closed")
    except:
        pass
    
    print("\n" + "=" * 70)
    print("   🏁 TEST COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    run_test()
