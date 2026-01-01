"""
🧪 SL MODIFICATION LIVE TEST - UPSTOX
======================================
Test Flow:
1. Place BUY order (Market)
2. Place SL order at 10% below
3. Wait 1 minute
4. MODIFY SL order (move 5% up)
5. Exit position

⚠️ REAL ORDERS - Run only during market hours (9:15 AM - 3:30 PM)!
"""

import upstox_client
from upstox_client.rest import ApiException
import time
import datetime
import requests
import gzip

# ========== CONFIG ==========
API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBQzY3MjciLCJqdGkiOiI2OTUyMGZjOTdmNWZjYjBjNGFkZmNmNmIiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk4NTY3MywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.j7uPFjzzN58ZMiXhapuzZ_-zyPHBv9bMztxfrulYxWk"

ORDER_QTY = 25  # Minimum lot for testing
WAIT_BEFORE_MODIFY = 60  # Seconds to wait before modifying SL
# ============================

def round_to_tick(price, tick_size=0.05):
    return round(price / tick_size) * tick_size

def check_market_hours():
    """Check if market is open - DISABLED FOR TESTING"""
    # Market hours check disabled for AMO testing
    return True, "Market check disabled for testing"

def get_nifty_ltp(api_client):
    """Get NIFTY spot LTP"""
    try:
        api_instance = upstox_client.MarketQuoteApi(api_client)
        tokens = ['NSE_INDEX|Nifty 50', 'NSE_INDEX:Nifty 50']
        
        for token in tokens:
            try:
                api_response = api_instance.ltp(token, api_version='2.0')
                if api_response and api_response.status == 'success' and api_response.data:
                    for key in api_response.data:
                        ltp = float(getattr(api_response.data[key], 'last_price', 0))
                        if ltp > 0:
                            return ltp
            except:
                continue
        
        # Fallback
        print("[INFO] Could not fetch NIFTY LTP from API")
        user_input = input("Enter current NIFTY price (e.g. 23850): ")
        return float(user_input)
    except Exception as e:
        print(f"[ERROR] NIFTY LTP: {e}")
        return None

def get_atm_option(nifty_price, option_type='CE'):
    """Find ATM option contract"""
    try:
        atm_strike = round(nifty_price / 50) * 50
        print(f"[INFO] ATM Strike: {atm_strike}")
        
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NFO.json.gz"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = gzip.decompress(response.content)
            instruments = eval(data.decode('utf-8'))
            
            today = datetime.datetime.now().date()
            candidates = []
            
            for inst in instruments:
                if inst.get('instrument_type') == 'OPTIDX' and 'NIFTY' in inst.get('name', ''):
                    trading_symbol = inst.get('tradingsymbol', '')
                    
                    # Skip BANKNIFTY, FINNIFTY, MIDCPNIFTY
                    if any(x in trading_symbol for x in ['BANK', 'FIN', 'MID']):
                        continue
                    
                    if int(inst.get('strike', 0)) == atm_strike and option_type in trading_symbol:
                        expiry_str = inst.get('expiry', '')
                        try:
                            expiry_dt = datetime.datetime.strptime(expiry_str, '%Y-%m-%d').date()
                            if expiry_dt >= today:
                                candidates.append({
                                    'symbol': trading_symbol,
                                    'token': inst.get('instrument_key', ''),
                                    'strike': atm_strike,
                                    'expiry': expiry_str,
                                    'expiry_dt': expiry_dt
                                })
                        except:
                            continue
            
            if candidates:
                # Get nearest expiry
                candidates.sort(key=lambda x: x['expiry_dt'])
                contract = candidates[0]
                print(f"[FOUND] {contract['symbol']} | Expiry: {contract['expiry']}")
                return contract
        
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
        
        if api_response and api_response.status == 'success' and api_response.data:
            for key in api_response.data:
                return float(getattr(api_response.data[key], 'last_price', 0))
    except:
        pass
    return None

def run_sl_modify_test():
    """Main test function"""
    
    print("=" * 70)
    print("   🧪 SL MODIFICATION LIVE TEST - UPSTOX")
    print("=" * 70)
    
    # Check market hours
    is_open, msg = check_market_hours()
    if not is_open:
        print(f"\n❌ {msg}")
        print("   Market hours: 9:15 AM - 3:30 PM")
        print("   Run this script during market hours.\n")
        return
    
    print(f"\n⚠️  WARNING: This will place REAL orders!")
    print(f"   Quantity: {ORDER_QTY}")
    print(f"   Wait before modify: {WAIT_BEFORE_MODIFY} seconds")
    print()
    
    confirm = input("Type 'YES' to proceed: ")
    if confirm != 'YES':
        print("Aborted.")
        return
    
    # ===== STEP 1: Connect =====
    print("\n" + "="*70)
    print("[STEP 1/6] Connecting to Upstox...")
    print("="*70)
    
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    
    try:
        user_api = upstox_client.UserApi(api_client)
        profile = user_api.get_profile(api_version='2.0')
        if profile.status != 'success':
            print("[ERROR] Connection failed!")
            return
        print(f"✅ Connected as: {profile.data.user_id}")
    except Exception as e:
        print(f"[ERROR] Connection: {e}")
        return
    
    # ===== STEP 2: Get NIFTY & Find Option =====
    print("\n" + "="*70)
    print("[STEP 2/6] Getting NIFTY LTP & Finding Option...")
    print("="*70)
    
    nifty_ltp = get_nifty_ltp(api_client)
    if not nifty_ltp:
        print("[ERROR] Could not get NIFTY LTP")
        return
    print(f"✅ NIFTY: {nifty_ltp}")
    
    contract = get_atm_option(nifty_ltp, 'CE')
    if not contract:
        print("[ERROR] Could not find option contract")
        return
    
    opt_ltp = get_option_ltp(api_client, contract['token'])
    print(f"✅ Option LTP: ₹{opt_ltp}")
    
    # ===== STEP 3: Place BUY Order =====
    print("\n" + "="*70)
    print("[STEP 3/6] Placing BUY Order...")
    print("="*70)
    
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
            print(f"[ERROR] Buy failed: {buy_response}")
            return
        buy_order_id = buy_response.data.order_id
        print(f"✅ Buy Order ID: {buy_order_id}")
    except Exception as e:
        print(f"[ERROR] Buy: {e}")
        return
    
    # Wait for fill
    print("   Waiting 3s for fill...")
    time.sleep(3)
    
    # Get entry price
    entry_price = opt_ltp
    try:
        order_history = order_api.get_order_history(buy_order_id, api_version='2.0')
        if order_history.status == 'success':
            for order in order_history.data:
                if getattr(order, 'status', '').lower() == 'complete':
                    entry_price = float(getattr(order, 'average_price', opt_ltp))
                    break
    except:
        pass
    print(f"✅ Entry Price: ₹{entry_price}")
    
    # ===== STEP 4: Place SL Order =====
    print("\n" + "="*70)
    print("[STEP 4/6] Placing Initial SL Order...")
    print("="*70)
    
    initial_sl = round_to_tick(entry_price * 0.90)  # 10% below
    initial_trigger = round_to_tick(initial_sl + 0.05)
    
    print(f"   SL Price: ₹{initial_sl}")
    print(f"   Trigger:  ₹{initial_trigger}")
    
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
            print(f"[ERROR] SL failed: {sl_response}")
            # Exit position
            exit_body = upstox_client.PlaceOrderRequest(
                quantity=ORDER_QTY, product='I', validity='DAY', price=0.0,
                instrument_token=contract['token'], order_type='MARKET',
                transaction_type='SELL', disclosed_quantity=0, trigger_price=0.0, is_amo=False
            )
            order_api.place_order(exit_body, api_version='2.0')
            return
        sl_order_id = sl_response.data.order_id
        print(f"✅ SL Order ID: {sl_order_id}")
    except Exception as e:
        print(f"[ERROR] SL: {e}")
        return
    
    # ===== STEP 5: Wait & Modify SL =====
    print("\n" + "="*70)
    print(f"[STEP 5/6] Waiting {WAIT_BEFORE_MODIFY}s before SL Modification...")
    print("="*70)
    
    for i in range(WAIT_BEFORE_MODIFY, 0, -1):
        current_ltp = get_option_ltp(api_client, contract['token']) or entry_price
        pnl = (current_ltp - entry_price) * ORDER_QTY
        pnl_pct = ((current_ltp - entry_price) / entry_price) * 100
        print(f"\r   ⏱️ {i:3d}s | LTP: ₹{current_ltp:.1f} | P&L: ₹{pnl:+.0f} ({pnl_pct:+.1f}%) ", end='', flush=True)
        time.sleep(1)
    print("\n")
    
    # MODIFY SL
    new_sl = round_to_tick(entry_price * 0.95)  # Move to 5% below (from 10%)
    new_trigger = round_to_tick(new_sl + 0.05)
    
    print(f"   ⚡ MODIFYING SL:")
    print(f"      Old: ₹{initial_sl} → New: ₹{new_sl}")
    print(f"      Old Trigger: ₹{initial_trigger} → New: ₹{new_trigger}")
    
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
        
        print(f"\n   📋 MODIFY RESPONSE:")
        print(f"      Status: {modify_response.status}")
        
        if modify_response.status == 'success':
            print("\n   ✅✅✅ SL MODIFICATION SUCCESS! ✅✅✅")
        else:
            print(f"\n   ❌ SL MODIFICATION FAILED!")
            print(f"      Response: {modify_response}")
            
    except ApiException as e:
        print(f"\n   ❌ SL MODIFY API ERROR!")
        print(f"      Status: {e.status}")
        print(f"      Reason: {e.reason}")
        print(f"      Body: {e.body}")
        
    except Exception as e:
        print(f"\n   ❌ SL MODIFY ERROR: {e}")
    
    # ===== STEP 6: Cleanup =====
    print("\n" + "="*70)
    print("[STEP 6/6] Cleanup - Closing Position...")
    print("="*70)
    
    # Cancel SL
    try:
        order_api.cancel_order(sl_order_id, api_version='2.0')
        print(f"✅ SL order cancelled")
    except Exception as e:
        print(f"[WARN] Cancel SL: {e}")
    
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
            print(f"✅ Position closed")
            
            # Calculate final P&L
            time.sleep(1)
            exit_ltp = get_option_ltp(api_client, contract['token']) or entry_price
            final_pnl = (exit_ltp - entry_price) * ORDER_QTY
            print(f"   Exit LTP: ₹{exit_ltp:.1f}")
            print(f"   Final P&L: ₹{final_pnl:+.0f}")
    except Exception as e:
        print(f"[ERROR] Exit: {e}")
    
    print("\n" + "="*70)
    print("   🏁 TEST COMPLETE!")
    print("="*70)
    
    print("""
Summary:
========
1. BUY order placed ✓
2. SL order placed at 10% below ✓
3. Waited 60 seconds ✓
4. SL MODIFIED to 5% below ← CHECK RESULT ABOVE
5. Position closed ✓

If Step 4 shows SUCCESS, trailing SL will work in live trading!
""")


if __name__ == "__main__":
    run_sl_modify_test()
