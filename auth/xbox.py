import time
from datetime import datetime, timezone

import requests

from db import get_setting, set_setting


class XboxAuth:
    XBL_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
    XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"

    XBL_TOKEN_KEY = "xbl_token"
    XBL_EXPIRES_KEY = "xbl_token_expires"
    XBL_UHS_KEY = "xbl_user_hash"

    XSTS_TOKEN_KEY = "xsts_token"
    XSTS_EXPIRES_KEY = "xsts_token_expires"
    XSTS_UHS_KEY = "xsts_user_hash"

    @staticmethod
    def _parse_not_after(data: dict, fallback_seconds: int = 23 * 3600) -> int:
        not_after = data.get("NotAfter")
        if not_after:
            try:
                parsed = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
                return int(parsed.timestamp()) - 60
            except ValueError:
                pass
        return int(time.time()) + fallback_seconds

    def _store_xbl(self, data: dict) -> tuple[str, str]:
        token = data["Token"]
        uhs = data["DisplayClaims"]["xui"][0]["uhs"]
        set_setting(self.XBL_TOKEN_KEY, token)
        set_setting(self.XBL_UHS_KEY, uhs)
        set_setting(self.XBL_EXPIRES_KEY, str(self._parse_not_after(data)))
        return token, uhs

    def _store_xsts(self, data: dict) -> tuple[str, str]:
        token = data["Token"]
        uhs = data["DisplayClaims"]["xui"][0]["uhs"]
        set_setting(self.XSTS_TOKEN_KEY, token)
        set_setting(self.XSTS_UHS_KEY, uhs)
        set_setting(self.XSTS_EXPIRES_KEY, str(self._parse_not_after(data)))
        return token, uhs

    def get_xbl_token(self, ms_access_token: str) -> tuple[str, str]:
        token = get_setting(self.XBL_TOKEN_KEY)
        uhs = get_setting(self.XBL_UHS_KEY)
        expires = get_setting(self.XBL_EXPIRES_KEY)

        if token and uhs and expires and time.time() < float(expires):
            return token, uhs

        return self.authenticate(ms_access_token)

    def authenticate(self, ms_access_token: str) -> tuple[str, str]:
        """
        Step 1:
        Microsoft access token → Xbox Live token (XBL)
        Returns:
            (xbl_token, user_hash)
        """
        r = requests.post(
            self.XBL_AUTH_URL,
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={ms_access_token}",
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
            },
            timeout=15,
        )

        r.raise_for_status()
        data = r.json()

        return self._store_xbl(data)

    def get_xsts_token(self, xbl_token: str) -> tuple[str, str]:
        token = get_setting(self.XSTS_TOKEN_KEY)
        uhs = get_setting(self.XSTS_UHS_KEY)
        expires = get_setting(self.XSTS_EXPIRES_KEY)

        if token and uhs and expires and time.time() < float(expires):
            return token, uhs

        return self.authorize_xsts(xbl_token)

    def authorize_xsts(self, xbl_token: str) -> tuple[str, str]:
        """
        Step 2:
        Xbox Live token → XSTS token
        Returns:
            (xsts_token, user_hash)
        """
        r = requests.post(
            self.XSTS_AUTH_URL,
            json={
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbl_token],
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT",
            },
            timeout=15,
        )

        r.raise_for_status()
        data = r.json()

        return self._store_xsts(data)
