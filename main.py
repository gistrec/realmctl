import os
import time
import base64
import hashlib
import requests

from urllib.parse import urlencode

from auth.microsoft import MicrosoftAuth
from auth.xbox import XboxAuth
from auth.minecraft import MinecraftAuth

from db import get_setting, set_setting



MS_ACCESS_TOKEN_EXPIRES_KEY = "ms_access_token_expires"
MS_ACCESS_TOKEN_KEY = "access_token"
MS_REFRESH_TOKEN_KEY = "refresh_token"



# =========================
# MAIN
# =========================
def main():
    ms = MicrosoftAuth()
    xbox = XboxAuth()
    mc = MinecraftAuth()

    try:
        token = ms.get_access_token()
    except:
        token = ms.login()

    # Xbox
    xbl_token, uhs = xbox.authenticate(token)
    xsts_token, _ = xbox.authorize_xsts(xbl_token)

    # Minecraft
    mc_token = mc.authenticate(xsts_token, uhs)
    profile = mc.get_profile(mc_token)

    print(profile)

    uuid = profile["id"]
    name = profile["name"]

    print(f"Logged in as: {name}")

    for world in mc.get_worlds(mc_token, uuid, name)["servers"]:
        print(mc.get_world_info(mc_token, uuid, name, world["id"]))



if __name__ == "__main__":
    main()
