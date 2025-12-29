import requests

# We need the access token from the main script or user.
# For now, I will ask the user to provide it or hardcode the one from the file if I can read it.
# Actually, I'll rely on the main script's logic to get token if I integrate it there.
# But for a test script, I need a token.
# I will use a placeholder token and expect 401, but the structure might be revealed using a valid token if user has one.
# Wait, the user already authenticated in the main script. I can't easily grab that token without parsing the output or file.
# The user *edited* the file with a token: "eyJ0eX..."
# I will read the token from `fetch_account_balance_upstox.py`.

import re

def get_token():
    try:
        with open('fetch_account_balance_upstox.py', 'r') as f:
            content = f.read()
            match = re.search(r'self.ACCESS_TOKEN = "(.*?)"', content)
            if match:
                return match.group(1)
    except:
        pass
    return None

token = get_token()
print(f"Using Token: {token[:10]}..." if token else "No Token Found")

if token:
    url = "https://api.upstox.com/v2/option/contract"
    params = {
        "instrument_key": "NSE_INDEX|Nifty 50",
        # "expiry_date": "2025-12-31" # Optional? Let's try without first
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Try getting contracts
    response = requests.get(url, headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Success! Sample data:")
        if 'data' in data and len(data['data']) > 0:
            print(data['data'][0])
            print(f"Total contracts: {len(data['data'])}")
        else:
            print("No data found")
    else:
        print(response.text)
