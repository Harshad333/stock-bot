import math

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def calculate_rho(S, K, T, r, sigma, option_type='CE'):
    """Black-Scholes Rho calculation"""
    d1 = (math.log(S / K) + (r + (sigma ** 2) / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == 'CE':
        rho = (K * T * math.exp(-r * T) * norm_cdf(d2)) / 100
    else:
        rho = -(K * T * math.exp(-r * T) * norm_cdf(-d2)) / 100
    
    return rho, d1, d2, norm_cdf(d2)

print("="*70)
print("VERIFICATION: Upstox Data vs Console Data")
print("="*70)

# Common parameters
r = 0.065  # RBI repo rate 6.5%
T = 4 / 365  # 4 days to expiry (Dec 26 to Dec 30)

print(f"\nTime to Expiry (T): {T:.6f} years ({4} days)")
print(f"Risk-free rate (r): {r*100}%")

# ============ UPSTOX SCREENSHOT DATA ============
print("\n" + "="*70)
print("1. UPSTOX APP SCREENSHOT DATA:")
print("="*70)
S_upstox = 26037.00
K = 26050
IV_upstox = 5.81 / 100  # 5.81% as decimal

print(f"   NIFTY Spot (S): {S_upstox}")
print(f"   Strike (K): {K}")
print(f"   IV (σ): {IV_upstox*100}%")
print(f"   Upstox shows Rho: 1.4978")

rho_calc, d1, d2, nd2 = calculate_rho(S_upstox, K, T, r, IV_upstox, 'CE')
print(f"\n   My Formula Calculation:")
print(f"   d1 = {d1:.6f}")
print(f"   d2 = {d2:.6f}")
print(f"   N(d2) = {nd2:.6f}")
print(f"   Calculated Rho = {rho_calc:.4f}")
print(f"   Upstox Rho = 1.4978")
print(f"   Difference = {abs(rho_calc - 1.4978):.4f} ({abs(rho_calc - 1.4978)/1.4978*100:.2f}%)")

# ============ CONSOLE SCREENSHOT DATA ============
print("\n" + "="*70)
print("2. CONSOLE SCREENSHOT DATA:")
print("="*70)
S_console = 26040.85
IV_console = 5.81 / 100  # 5.81% as decimal

print(f"   NIFTY Spot (S): {S_console}")
print(f"   Strike (K): {K}")
print(f"   IV (σ): {IV_console*100}%")
print(f"   Console showed Rho: 1.0974 (OLD WRONG VALUE)")

rho_calc2, d1_2, d2_2, nd2_2 = calculate_rho(S_console, K, T, r, IV_console, 'CE')
print(f"\n   My Formula Calculation:")
print(f"   d1 = {d1_2:.6f}")
print(f"   d2 = {d2_2:.6f}")
print(f"   N(d2) = {nd2_2:.6f}")
print(f"   Calculated Rho = {rho_calc2:.4f}")

print("\n" + "="*70)
print("3. CONCLUSION:")
print("="*70)
print(f"   Upstox data → My Rho: {rho_calc:.4f} (Upstox shows: 1.4978)")
print(f"   Console data → My Rho: {rho_calc2:.4f}")
print(f"\n   Both calculations give ~1.46-1.47")
print(f"   If console was showing 1.0974, that was WRONG formula!")
print(f"   After fix, console should show ~1.48-1.50")
