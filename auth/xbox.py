import requests


class XboxAuth:
    XBL_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
    XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"

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

        return (
            data["Token"],
            data["DisplayClaims"]["xui"][0]["uhs"],
        )

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

        return (
            data["Token"],
            data["DisplayClaims"]["xui"][0]["uhs"],
        )
