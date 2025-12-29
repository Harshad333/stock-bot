import requests

token = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI0TkNUUFEiLCJqdGkiOiI2OTRlMzJhY2Q0OWM4NDA1NDQyMWY4NjIiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2NjczMjQ2MCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY2Nzg2NDAwfQ.m_XOebq-loQjQktEYmiPXQSftW9Z84BWeRGwkTM16g0"

url = "https://api.upstox.com/v2/option/chain"
params = {
    "instrument_key": "NSE_INDEX|Nifty 50",
    "expiry_date": "2025-12-30"  # Known good expiry
}
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers, params=params)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"Success: {data.get('status')}")
    chain = data.get('data', [])
    print(f"Chain items: {len(chain)}")
    if chain:
        # Find ATM 26050
        for item in chain:
            if item.get('strike_price') == 26050:
                print(f"\nATM 26050 Data:")
                print(f"  Call: {item.get('call_options')}")
                print(f"  Put: {item.get('put_options')}")
                break
else:
    print(response.text[:500])
