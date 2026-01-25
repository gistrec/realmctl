import time

import requests

from db import get_setting, set_setting


class MinecraftAuth:
    MC_AUTH_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
    PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"

    REALMS_BASE = "https://pc.realms.minecraft.net"

    MC_TOKEN_KEY = "mc_token"
    MC_EXPIRES_KEY = "mc_token_expires"

    def _realm_cookies(self, mc_token: str, uuid: str, name: str) -> dict:
        return {
            "sid": f"token:{mc_token}:{uuid}",
            "user": name,
            "version": "1.20.4",
        }

    def get_token(self, xsts_token: str, user_hash: str) -> str:
        token = get_setting(self.MC_TOKEN_KEY)
        expires = get_setting(self.MC_EXPIRES_KEY)

        if token and expires and time.time() < float(expires):
            return token

        return self.authenticate(xsts_token, user_hash)

    def authenticate(self, xsts_token: str, user_hash: str) -> str:
        """
        Step 3:
        XSTS token → Minecraft access token
        """
        r = requests.post(
            self.MC_AUTH_URL,
            json={
                "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
            },
            timeout=15,
        )

        r.raise_for_status()
        data = r.json()

        token = data["access_token"]
        set_setting(self.MC_TOKEN_KEY, token)
        expires_in = int(data.get("expires_in", 23 * 3600))
        set_setting(self.MC_EXPIRES_KEY, str(int(time.time()) + expires_in - 60))

        return token

    def check_realms_available(self, mc_token, uuid, name):
        """
        Check if Realms service is available for user
        """
        r = requests.get(
            f"{self.REALMS_BASE}/mco/available",
            cookies=self._realm_cookies(mc_token, uuid, name),
            timeout=15,
        )
        return r.json()

    def get_profile(self, mc_token: str) -> dict:
        """
        Get Minecraft profile info
        """
        r = requests.get(
            self.PROFILE_URL,
            headers={
                "Authorization": f"Bearer {mc_token}"
            },
            timeout=15,
        )

        r.raise_for_status()
        return r.json()


    def get_worlds(self, mc_token, uuid, name):
        """
        Get list of all Realms worlds
        """
        r = requests.get(
            f"{self.REALMS_BASE}/worlds",
            cookies=self._realm_cookies(mc_token, uuid, name),
            timeout=15,
        )
        return r.json()


    def get_world_info(self, mc_token: str, uuid: str, name: str, world_id: int) -> dict:
        """
        Get info about a specific Realm world
        """
        r = requests.get(
            f"{self.REALMS_BASE}/worlds/{world_id}",
            cookies=self._realm_cookies(mc_token, uuid, name),
            timeout=15,
        )

        r.raise_for_status()
        return r.json()
