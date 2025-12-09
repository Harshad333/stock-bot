"""
Angel One Account Balance Fetcher
Fetches account funds/balance from Angel One trading account
"""

from datetime import datetime
import pyotp
from SmartApi import SmartConnect
import json


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


def main():
    """Main function to fetch account balance"""
    print("\n" + "="*60)
    print("  🏦 ANGEL ONE ACCOUNT BALANCE FETCHER")
    print("="*60)
    
    # Initialize fetcher
    fetcher = AngelAccountFetcher()
    
    if fetcher.session_generated:
        # Fetch complete account summary
        fetcher.get_complete_account_summary()
    else:
        print("\n❌ [ERROR] Could not connect to Angel One. Please check credentials.")


if __name__ == "__main__":
    main()
