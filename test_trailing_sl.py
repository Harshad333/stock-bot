"""
TRAILING SL LOGIC TESTER
=========================
Ye script trailing SL logic ko test karta hai bina actual trade ke.

Usage: python test_trailing_sl.py
"""

def round_to_tick(price, tick_size=0.05):
    """Round price to nearest tick size"""
    return round(price / tick_size) * tick_size

def calculate_trailing_sl(entry_price, current_price, current_sl):
    """
    Calculate new trailing SL based on profit level
    
    THREE-PHASE TRAILING SL LOGIC (ENHANCED):
    ==========================================
    Phase 1 (7% to 19%): 5% lock, then +5% every 5% step
    Phase 2 (20% to 29%): 18% lock, then +3% every 3% step  
    Phase 3 (30%+): 28% lock, then +2% every 2% step (SUPER TIGHT)
    """
    profit_percent = ((current_price - entry_price) / entry_price) * 100
    
    # If not yet at 7% profit, keep initial SL
    if profit_percent < 7:
        return current_sl, False, 0
    
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
    
    # Calculate new SL price
    new_sl = round(entry_price * (1 + locked_profit_percent / 100), 2)
    new_sl = round_to_tick(new_sl)
    
    # Only modify if new SL is higher than current SL
    if new_sl > current_sl:
        return new_sl, True, locked_profit_percent
    
    return current_sl, False, locked_profit_percent


def test_trailing_sl():
    """Test the trailing SL logic with various scenarios"""
    
    print("=" * 70)
    print("   TRAILING STOP LOSS LOGIC TESTER")
    print("=" * 70)
    
    # Get entry price from user
    entry_price = float(input("\n📥 Entry Price daalo (e.g., 100): ") or "100")
    
    # Calculate initial SL (10% below entry)
    initial_sl = round_to_tick(entry_price * 0.90)
    target_price = round_to_tick(entry_price * 1.30)  # 30% target
    
    print(f"\n📊 Trade Details:")
    print(f"   Entry Price:  ₹{entry_price:.2f}")
    print(f"   Initial SL:   ₹{initial_sl:.2f} (10% below)")
    print(f"   Target:       ₹{target_price:.2f} (30% above)")
    
    print("\n" + "=" * 70)
    print("   TRAILING SL TABLE")
    print("=" * 70)
    print(f"{'LTP':>10} | {'Profit %':>10} | {'SL Price':>10} | {'Locked %':>10} | {'Trail?':>8}")
    print("-" * 70)
    
    current_sl = initial_sl
    
    # Test various price levels
    test_prices = []
    
    # Generate test prices from 0% to 40% profit in 1% steps
    for pct in range(0, 41, 1):
        price = entry_price * (1 + pct/100)
        test_prices.append(round_to_tick(price))
    
    for ltp in test_prices:
        profit_pct = ((ltp - entry_price) / entry_price) * 100
        new_sl, should_modify, locked_pct = calculate_trailing_sl(entry_price, ltp, current_sl)
        
        # Mark important milestones
        marker = ""
        if profit_pct >= 10 and profit_pct < 11:
            marker = " ⬅️ TRAIL STARTS"
        elif profit_pct >= 23 and profit_pct < 24:
            marker = " ⬅️ PHASE 2 STARTS"
        
        if should_modify:
            current_sl = new_sl
            print(f"₹{ltp:>8.2f} | {profit_pct:>9.1f}% | ₹{new_sl:>8.2f} | {locked_pct:>9.1f}% | {'✅ YES':>8}{marker}")
        else:
            print(f"₹{ltp:>8.2f} | {profit_pct:>9.1f}% | ₹{current_sl:>8.2f} | {locked_pct:>9.1f}% | {'❌ NO':>8}{marker}")
    
    print("-" * 70)
    
    # Interactive test
    print("\n" + "=" * 70)
    print("   INTERACTIVE TEST MODE")
    print("=" * 70)
    print("Ab aap apna LTP enter karke test kar sakte ho.")
    print("'q' type karke quit karo.\n")
    
    current_sl = initial_sl
    highest_price = entry_price
    
    while True:
        user_input = input("📈 Current LTP daalo: ").strip()
        
        if user_input.lower() == 'q':
            print("\n👋 Goodbye!")
            break
        
        try:
            ltp = float(user_input)
        except:
            print("❌ Invalid input. Number daalo ya 'q' for quit.\n")
            continue
        
        profit_pct = ((ltp - entry_price) / entry_price) * 100
        pnl_rs = (ltp - entry_price) * 75  # Assuming 75 qty
        
        # Track highest
        if ltp > highest_price:
            highest_price = ltp
        
        # Calculate new SL
        new_sl, should_modify, locked_pct = calculate_trailing_sl(entry_price, ltp, current_sl)
        
        print(f"\n   LTP: ₹{ltp:.2f}")
        print(f"   Profit: {profit_pct:+.1f}% (₹{pnl_rs:+.0f})")
        print(f"   Highest: ₹{highest_price:.2f}")
        print(f"   Current SL: ₹{current_sl:.2f}")
        
        if should_modify:
            old_sl = current_sl
            current_sl = new_sl
            print(f"\n   ✅ SL TRAILED!")
            print(f"   Old SL: ₹{old_sl:.2f} → New SL: ₹{new_sl:.2f}")
            print(f"   Locked Profit: {locked_pct:.1f}%")
        else:
            if profit_pct < 10:
                print(f"\n   ⏳ Trail inactive (need 10%+ profit, current: {profit_pct:.1f}%)")
            else:
                print(f"\n   ➖ SL unchanged at ₹{current_sl:.2f}")
        
        # Check SL hit
        if ltp <= current_sl:
            print(f"\n   🛑 SL HIT! Trade would close at ₹{current_sl:.2f}")
            final_pnl = (current_sl - entry_price) * 75
            print(f"   Final P&L: ₹{final_pnl:+.0f}")
        
        # Check target hit
        if ltp >= target_price:
            print(f"\n   🎯 TARGET HIT! Trade would close at ₹{target_price:.2f}")
            final_pnl = (target_price - entry_price) * 75
            print(f"   Final P&L: ₹{final_pnl:+.0f}")
        
        print()


if __name__ == "__main__":
    test_trailing_sl()
