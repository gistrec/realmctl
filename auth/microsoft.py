import time
import os
import base64
import hashlib
import requests
from urllib.parse import urlencode

from db import get_setting, set_setting


class MicrosoftAuth:
    CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
    REDIRECT_URI = "http://localhost:3000"
    SCOPES = "XboxLive.signin offline_access"

    ACCESS_TOKEN_KEY = "ms_access_token"
    REFRESH_TOKEN_KEY = "ms_refresh_token"
    EXPIRES_KEY = "ms_access_token_expires"
    PKCE_VERIFIER_KEY = "ms_pkce_verifier"

    TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    AUTH_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"

    # ---------- PKCE ----------

    @staticmethod
    def _gen_pkce():
        verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        return verifier, challenge

    # ---------- PUBLIC API ----------

    def get_access_token(self) -> str:
        token = get_setting(self.ACCESS_TOKEN_KEY)
        expires = get_setting(self.EXPIRES_KEY)

        if token and expires and time.time() < float(expires):
            return token

        return self._refresh_token()

    def login(self):
        verifier, challenge = self._gen_pkce()
        set_setting(self.PKCE_VERIFIER_KEY, verifier)

        url = (
            f"{self.AUTH_URL}?"
            + urlencode({
                "client_id": self.CLIENT_ID,
                "response_type": "code",
                "redirect_uri": self.REDIRECT_URI,
                "scope": self.SCOPES,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            })
        )

        print("Open this URL in browser:")
        print(url)

        code = input("Paste authorization code: ").strip()
        if not code:
            raise RuntimeError("Authorization code not provided")

        return self._exchange_code(code)

    # ---------- INTERNAL ----------

    def _exchange_code(self, code: str) -> str:
        verifier = get_setting(self.PKCE_VERIFIER_KEY)
        if not verifier:
            raise RuntimeError("PKCE verifier not found")

        r = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.REDIRECT_URI,
                "code_verifier": verifier,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        return self._store_tokens(data)

    def _refresh_token(self) -> str:
        refresh_token = get_setting(self.REFRESH_TOKEN_KEY)
        if not refresh_token:
            raise RuntimeError("No refresh token — login required")

        r = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": self.SCOPES,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        return self._store_tokens(data)

    def _store_tokens(self, data: dict) -> str:
        set_setting(self.ACCESS_TOKEN_KEY, data["access_token"])

        if "refresh_token" in data:
            set_setting(self.REFRESH_TOKEN_KEY, data["refresh_token"])

        set_setting(
            self.EXPIRES_KEY,
            str(int(time.time()) + int(data["expires_in"]) - 60)
        )

        return data["access_token"]
