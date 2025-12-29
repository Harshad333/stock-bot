"""
Upstox Token Generator
Generate a new access token for Upstox API
Run this script whenever your token expires (typically daily around 3:30 AM IST)
"""

import requests
import webbrowser

# ============================================
# YOUR UPSTOX CREDENTIALS
# ============================================
API_KEY = "43fdf842-a9e1-4f20-9977-b6d1e4c8a9dc"
API_SECRET = "2on3ns8j9a"
REDIRECT_URI = "https://account.upstox.com/developer/apps/createapp"

def get_new_token():
    """Generate a new access token through OAuth flow"""
    
    # Step 1: Generate authorization URL
    auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}"
    
    print("\n" + "="*60)
    print("  🔑 UPSTOX TOKEN GENERATOR")
    print("="*60)
    print("\n📋 Step 1: Opening authorization URL in your browser...")
    print(f"\n🔗 If browser doesn't open, visit this URL manually:")
    print(f"   {auth_url}")
    
    # Try to open browser automatically
    try:
        webbrowser.open(auth_url)
        print("\n✅ Browser opened!")
    except:
        print("\n⚠️  Could not open browser automatically.")
    
    print("\n" + "-"*60)
    print("📋 Step 2: After login, you'll be redirected to a URL like:")
    print("   https://account.upstox.com/...?code=XXXXXX")
    print("\n   Copy the 'code' value from that URL")
    print("-"*60)
    
    # Step 2: Get the authorization code from user
    code = input("\n🔐 Paste the 'code' from the redirect URL: ").strip()
    
    if not code:
        print("❌ No code provided. Exiting.")
        return None
    
    # Step 3: Exchange code for access token
    print("\n🔄 Exchanging code for access token...")
    
    token_url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "code": code,
        "client_id": API_KEY,
        "client_secret": API_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        result = response.json()
        
        if "access_token" in result:
            access_token = result["access_token"]
            
            print("\n" + "="*60)
            print("  ✅ SUCCESS! NEW ACCESS TOKEN GENERATED")
            print("="*60)
            print(f"\n🔑 Access Token:\n{access_token}")
            print("\n" + "-"*60)
            print("📝 NEXT STEPS:")
            print("   1. Copy the access token above")
            print("   2. Update 'ACCESS_TOKEN' in fetch_account_balance_upstox.py (line 26)")
            print("   3. Run your main script again")
            print("-"*60)
            
            # Also save to a file for convenience
            with open("upstox_token.txt", "w") as f:
                f.write(f"# Generated at: {__import__('datetime').datetime.now()}\n")
                f.write(f"ACCESS_TOKEN={access_token}\n")
            print(f"\n💾 Token also saved to: upstox_token.txt")
            
            # Ask if user wants to auto-update the main script
            update = input("\n🔄 Auto-update fetch_account_balance_upstox.py? (y/n): ").strip().lower()
            if update == 'y':
                update_main_script(access_token)
            
            return access_token
        else:
            print(f"\n❌ Error: {result}")
            if "errors" in result:
                for err in result["errors"]:
                    print(f"   - {err.get('message', err)}")
            return None
            
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return None


def update_main_script(new_token):
    """Update the ACCESS_TOKEN in fetch_account_balance_upstox.py"""
    try:
        file_path = "fetch_account_balance_upstox.py"
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find and replace the ACCESS_TOKEN line
        import re
        pattern = r'self\.ACCESS_TOKEN\s*=\s*"[^"]*"'
        replacement = f'self.ACCESS_TOKEN = "{new_token}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        print(f"\n✅ Updated {file_path} with new token!")
        
    except Exception as e:
        print(f"\n❌ Could not update file: {e}")
        print("   Please manually update the ACCESS_TOKEN in fetch_account_balance_upstox.py")


if __name__ == "__main__":
    get_new_token()
