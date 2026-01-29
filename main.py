import asyncio

from requests import HTTPError

from auth.microsoft import MicrosoftAuth
from auth.xbox import XboxAuth
from auth.minecraft import MinecraftAuth

from tg import update_status
from db import set_setting


LAST_BACKUP_URL = "last_backup_url"


def _is_auth_error(error: HTTPError) -> bool:
    response = getattr(error, "response", None)
    if response is None:
        return False
    return response.status_code in {401, 403}


async def main():
    ms = MicrosoftAuth()
    xbox = XboxAuth()
    mc = MinecraftAuth()

    # Microsoft
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

    uuid = profile["id"]
    name = profile["name"]

    print(f"Logged in as: {name}")

    for world in mc.get_worlds(mc_token, uuid, name)["servers"]:
        if world["id"] != 12829680:
            continue

        print("=== world info ===")
        world_info = mc.get_world_info(mc_token, uuid, name, world["id"])
        online_players = sorted([player["name"] for player in world_info["players"] if player["online"]])
        print(online_players)

        await update_status(online_players)

        print("\n=== backup ===")
        last_backup = mc.get_world_last_backup(mc_token, uuid, name, world["id"], 1)
        set_setting(LAST_BACKUP_URL, last_backup["downloadLink"])


if __name__ == "__main__":
    asyncio.run(main())
