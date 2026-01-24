import os
import base64
import hashlib

import requests
from urllib.parse import urlencode

from db import get_setting, set_setting


# =========================
# CONFIG
# =========================
#
CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
REDIRECT_URI = "http://localhost:3000"
SCOPES = "XboxLive.signin offline_access"
MS_TOKEN_KEY = "microsoft_access_token"


# =========================
# PKCE
# =========================
def gen_pkce():
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# =========================
# MICROSOFT LOGIN
# =========================
def microsoft_login():
    cached_token = get_setting(MS_TOKEN_KEY)
    if cached_token:
        print("✅ Using cached Microsoft token from settings table.")
        return cached_token

    _, challenge = gen_pkce()

    url = (
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?"
        + urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
    )

    print("🔐 Microsoft login required.")
    print("Open this URL on a machine with a browser and complete the login:")
    print(url)

    ms_token = input("Paste the Microsoft access token here: ").strip()
    if not ms_token:
        raise RuntimeError("Microsoft access token was not provided")

    set_setting(MS_TOKEN_KEY, ms_token)
    print("💾 Microsoft token saved to settings table.")
    return ms_token


# =========================
# XBOX AUTH
# =========================
def xbox_auth(ms_token):
    r = requests.post(
        "https://user.auth.xboxlive.com/user/authenticate",
        json={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
    ).json()

    return r["Token"], r["DisplayClaims"]["xui"][0]["uhs"]


def xsts_auth(xbl_token):
    r = requests.post(
        "https://xsts.auth.xboxlive.com/xsts/authorize",
        json={
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbl_token]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT"
        }
    ).json()

    return r["Token"], r["DisplayClaims"]["xui"][0]["uhs"]


# =========================
# MINECRAFT AUTH
# =========================
def minecraft_auth(xsts_token, uhs):
    r = requests.post(
        "https://api.minecraftservices.com/authentication/login_with_xbox",
        json={
            "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
        }
    ).json()

    return r["access_token"]


def get_profile(mc_token):
    return requests.get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers={"Authorization": f"Bearer {mc_token}"}
    ).json()


# =========================
# REALMS
# =========================
def get_realms_avaliable(mc_token, uuid, name):
    cookies = {
        "sid": f"token:{mc_token}:{uuid}",
        "user": name,
        "version": "1.20.4"
    }

    r = requests.get(
        "https://pc.realms.minecraft.net/mco/available",
        cookies=cookies
    )

    return r.json()


def get_realms(mc_token, uuid, name):
    cookies = {
        "sid": f"token:{mc_token}:{uuid}",
        "user": name,
        "version": "1.20.4"
    }

    r = requests.get(
        "https://pc.realms.minecraft.net/worlds",
        cookies=cookies
    )

    return r.json()


def get_realm(mc_token, uuid, name, world_id):
    cookies = {
        "sid": f"token:{mc_token}:{uuid}",
        "user": name,
        "version": "1.20.4"
    }

    r = requests.get(
        f"https://pc.realms.minecraft.net/activities/liveplayerlist",
        cookies=cookies
    )

    return r.json()


def get_online_players(mc_token, uuid, name, world_id):
    cookies = {
        "sid": f"token:{mc_token}:{uuid}",
        "user": name,
        "version": "1.20.4"
    }

    r = requests.get(
        f"https://pc.realms.minecraft.net/invites/{world_id}",
        cookies=cookies
    )

    return r.json()


# =========================
# MAIN
# =========================
def main():
    print("== Microsoft login ==")
    ms_token = microsoft_login()

    print("== Xbox auth ==")
    xbl_token, uhs = xbox_auth(ms_token)

    print("== XSTS ==")
    xsts_token, _ = xsts_auth(xbl_token)

    print("== Minecraft auth ==")
    mc_token = minecraft_auth(xsts_token, uhs)

    profile = get_profile(mc_token)
    print(f"Logged in as: {profile['name']}")

    avaliable = get_realms_avaliable(mc_token, profile["id"], profile["name"])
    print("\n=== REALMS ===")
    print(f"Avaliable: {avaliable}")

    realms = get_realms(mc_token, profile["id"], profile["name"])

    for realm in realms["servers"]:
        realm = get_realm(mc_token, profile["id"], profile["name"], realm["id"])
        print(realm)


if __name__ == "__main__":
    main()
