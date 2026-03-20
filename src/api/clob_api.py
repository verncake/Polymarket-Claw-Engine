import time
import hmac
import hashlib
import requests
import uuid

class CLOBAPI:
    def __init__(self, api_key, api_secret, passphrase):
        self.base_url = "https://clob.polymarket.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

    def _generate_signature(self, timestamp, method, path, nonce):
        message = f"{timestamp}{method}{path}{nonce}"
        return hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def get_balances(self):
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        path = "/trade-api/v0/balances"
        sig = self._generate_signature(timestamp, "GET", path, nonce)
        
        headers = {
            "Api-Key": self.api_key,
            "Passphrase": self.passphrase,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Signature": sig
        }
        resp = requests.get(f"{self.base_url}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_open_orders(self, market=None):
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        path = "/trade-api/v0/open-orders"
        sig = self._generate_signature(timestamp, "GET", path, nonce)
        
        headers = {
            "Api-Key": self.api_key,
            "Passphrase": self.passphrase,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Signature": sig
        }
        params = {"market": market} if market else {}
        resp = requests.get(f"{self.base_url}{path}", headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
