from auth.microsoft import MicrosoftAuth
from auth.xbox import XboxAuth
from auth.minecraft import MinecraftAuth

from requests import HTTPError


def _is_auth_error(error: HTTPError) -> bool:
    response = getattr(error, "response", None)
    if response is None:
        return False
    return response.status_code in {401, 403}

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
    xbl_token, uhs = xbox.get_xbl_token(token)
    try:
        xsts_token, uhs = xbox.get_xsts_token(xbl_token)
    except HTTPError as error:
        if not _is_auth_error(error):
            raise
        xbl_token, uhs = xbox.authenticate(token)
        xsts_token, uhs = xbox.authorize_xsts(xbl_token)

    # Minecraft
    try:
        mc_token = mc.get_token(xsts_token, uhs)
    except HTTPError as error:
        if not _is_auth_error(error):
            raise
        xbl_token, uhs = xbox.authenticate(token)
        xsts_token, uhs = xbox.authorize_xsts(xbl_token)
        mc_token = mc.authenticate(xsts_token, uhs)

    try:
        profile = mc.get_profile(mc_token)
    except HTTPError as error:
        if not _is_auth_error(error):
            raise
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
