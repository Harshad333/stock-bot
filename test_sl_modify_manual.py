"""
🧪 SL MODIFICATION LIVE TEST - UPSTOX (MANUAL TOKEN)
=====================================================
Test Flow:
1. Place BUY order (Market)
2. Place SL order at 10% below
3. Wait 1 minute
4. MODIFY SL order (move 5% up)
5. Exit position

⚠️ REAL ORDERS!
"""

import upstox_client
from upstox_client.rest import ApiException
import time
import datetime

# ========== CONFIG ==========
API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0TkNUUFEiLCJqdGkiOiI2OTUyM2Y2NmEyNWJmMTZmNjE1YTg1ODAiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk5Nzg2MiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY3MDQ1NjAwfQ.Vw7j3I1LtPlX9Zu-_XhHKKe8k06rc8uxj-O_B612CrU"

ORDER_QTY = 25  # Minimum lot for testing
WAIT_BEFORE_MODIFY = 60  # Seconds to wait before modifying SL
# ============================

def round_to_tick(price, tick_size=0.05):
    return round(price / tick_size) * tick_size

def get_option_ltp(api_client, token):
    """Get option LTP"""
    try:
        api_instance = upstox_client.MarketQuoteApi(api_client)
        api_response = api_instance.ltp(token, api_version='2.0')
        
        if api_response and api_response.status == 'success' and api_response.data:
            for key in api_response.data:
                return float(getattr(api_response.data[key], 'last_price', 0))
    except Exception as e:
        print(f"[WARN] LTP fetch: {e}")
    return None

def run_sl_modify_test():
    """Main test function"""
    
    print("=" * 70)
    print("   🧪 SL MODIFICATION LIVE TEST - UPSTOX")
    print("=" * 70)
    
    print(f"\n⚠️  WARNING: This will place REAL orders!")
    print(f"   Quantity: {ORDER_QTY}")
    print(f"   Wait before modify: {WAIT_BEFORE_MODIFY} seconds")
    
    # Manual contract input
    print("\n📝 Enter Option Contract Details:")
    print("   (Check Upstox app for current contract)")
    print()
    
    symbol = input("   Trading Symbol (e.g., NIFTY30DEC2525950PE): ").strip()
    if not symbol:
        symbol = "NIFTY30DEC2525950PE"
        print(f"   Using default: {symbol}")
    
    # Auto-construct token from symbol
    token = f"NSE_FO|{symbol}"
    print(f"   Auto Token: {token}")
    
    entry_price_input = input("   Entry Price estimate (e.g., 150): ").strip()
    entry_price = float(entry_price_input) if entry_price_input else 150.0
    
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
    
    # ===== STEP 2: Check LTP =====
    print("\n" + "="*70)
    print("[STEP 2/6] Checking Option LTP...")
    print("="*70)
    
    opt_ltp = get_option_ltp(api_client, token)
    if opt_ltp:
        print(f"✅ Current LTP: ₹{opt_ltp}")
        entry_price = opt_ltp
    else:
        print(f"⚠️ Could not fetch LTP, using estimate: ₹{entry_price}")
    
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
        instrument_token=token,
        order_type='MARKET',
        transaction_type='BUY',
        disclosed_quantity=0,
        trigger_price=0.0,
        is_amo=False
    )
    
    print(f"   Symbol: {symbol}")
    print(f"   Token: {token}")
    print(f"   Qty: {ORDER_QTY}")
    
    try:
        buy_response = order_api.place_order(buy_body, api_version='2.0')
        print(f"\n   Response Status: {buy_response.status}")
        
        if buy_response.status != 'success':
            print(f"[ERROR] Buy failed: {buy_response}")
            return
        buy_order_id = buy_response.data.order_id
        print(f"✅ Buy Order ID: {buy_order_id}")
    except ApiException as e:
        print(f"[ERROR] Buy API Error:")
        print(f"   Status: {e.status}")
        print(f"   Body: {e.body}")
        return
    except Exception as e:
        print(f"[ERROR] Buy: {e}")
        return
    
    # Wait for fill
    print("   Waiting 3s for fill...")
    time.sleep(3)
    
    # Get entry price from order history
    try:
        order_history = order_api.get_order_history(buy_order_id, api_version='2.0')
        if order_history.status == 'success':
            for order in order_history.data:
                status = getattr(order, 'status', '').lower()
                avg_price = float(getattr(order, 'average_price', 0))
                print(f"   Order Status: {status}, Avg Price: {avg_price}")
                if status == 'complete' and avg_price > 0:
                    entry_price = avg_price
                    break
    except Exception as e:
        print(f"   [WARN] Could not get order history: {e}")
    
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
        instrument_token=token,
        order_type='SL',
        transaction_type='SELL',
        disclosed_quantity=0,
        is_amo=False
    )
    
    try:
        sl_response = order_api.place_order(sl_body, api_version='2.0')
        print(f"\n   Response Status: {sl_response.status}")
        
        if sl_response.status != 'success':
            print(f"[ERROR] SL failed: {sl_response}")
            # Exit position
            print("[INFO] Exiting position...")
            exit_body = upstox_client.PlaceOrderRequest(
                quantity=ORDER_QTY, product='I', validity='DAY', price=0.0,
                instrument_token=token, order_type='MARKET',
                transaction_type='SELL', disclosed_quantity=0, trigger_price=0.0, is_amo=False
            )
            order_api.place_order(exit_body, api_version='2.0')
            return
        sl_order_id = sl_response.data.order_id
        print(f"✅ SL Order ID: {sl_order_id}")
    except ApiException as e:
        print(f"[ERROR] SL API Error:")
        print(f"   Status: {e.status}")
        print(f"   Body: {e.body}")
        return
    except Exception as e:
        print(f"[ERROR] SL: {e}")
        return
    
    # ===== STEP 5: Wait & Modify SL =====
    print("\n" + "="*70)
    print(f"[STEP 5/6] Waiting {WAIT_BEFORE_MODIFY}s before SL Modification...")
    print("="*70)
    
    for i in range(WAIT_BEFORE_MODIFY, 0, -1):
        current_ltp = get_option_ltp(api_client, token) or entry_price
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
        print(f"      Data: {modify_response.data}")
        
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
        cancel_response = order_api.cancel_order(sl_order_id, api_version='2.0')
        print(f"✅ SL order cancelled: {cancel_response.status}")
    except Exception as e:
        print(f"[WARN] Cancel SL: {e}")
    
    # Exit position
    try:
        exit_body = upstox_client.PlaceOrderRequest(
            quantity=ORDER_QTY,
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
        exit_response = order_api.place_order(exit_body, api_version='2.0')
        print(f"✅ Exit order: {exit_response.status}")
        
        if exit_response.status == 'success':
            exit_ltp = get_option_ltp(api_client, token) or entry_price
            final_pnl = (exit_ltp - entry_price) * ORDER_QTY
            print(f"   Final P&L: ₹{final_pnl:+.0f}")
    except Exception as e:
        print(f"[ERROR] Exit: {e}")
    
    print("\n" + "="*70)
    print("   🏁 TEST COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    run_sl_modify_test()
