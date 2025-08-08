import requests
import base64
import json
import argparse
import sys

def decode_jwt(token):
    """Decode JWT payload without validation (for inspection only)."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)  # pad base64 string
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        return json.loads(decoded)
    except Exception as e:
        print(f"[!] Failed to decode token: {e}")
        return {}

def get_access_token(refresh_token, scope, client_id, client_secret, tenant="common"):
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": scope
    }

    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"[!] Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    token_data = response.json()
    access_token = token_data.get("access_token")

    print(f"\n[+] Access token acquired for scope: {scope}")
    print(f"    Token (truncated): {access_token[:80]}...")

    decoded = decode_jwt(access_token)
    print(f"    aud: {decoded.get('aud')}")
    print(f"    scp: {decoded.get('scp', 'N/A')}")
    print(f"    exp: {decoded.get('exp')}")
    print()

    return access_token

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Azure OAuth Token Multiplexer")
    parser.add_argument("--refresh-token", required=True, help="Refresh token to exchange")
    parser.add_argument("--client-id", required=True, help="App's client_id")
    parser.add_argument("--client-secret", required=True, help="App's client_secret")
    parser.add_argument("--scope", required=True, help="Target scope, e.g. https://vault.azure.net/.default")
    parser.add_argument("--tenant", default="common", help="Tenant ID or 'common'")

    args = parser.parse_args()

    get_access_token(
        refresh_token=args.refresh_token,
        scope=args.scope,
        client_id=args.client_id,
        client_secret=args.client_secret,
        tenant=args.tenant
    )
