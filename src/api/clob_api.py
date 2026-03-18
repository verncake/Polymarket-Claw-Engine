import time
import hmac
import hashlib
import requests
import json

class CLOBAPI:
    def __init__(self, api_key, api_secret, passphrase):
        self.base_url = "https://clob.polymarket.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

    def _generate_signature(self, timestamp, method, path):
        # message = timestamp + method + path + nonce(0)
        message = f"{timestamp}{method}{path}0"
        return hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def get_balances(self):
        timestamp = str(int(time.time() * 1000))
        path = "/balances"
        sig = self._generate_signature(timestamp, "GET", path)
        
        headers = {
            "Api-Key": self.api_key,
            "Passphrase": self.passphrase,
            "Timestamp": timestamp,
            "Nonce": "0",
            "Signature": sig
        }
        resp = requests.get(f"{self.base_url}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()
