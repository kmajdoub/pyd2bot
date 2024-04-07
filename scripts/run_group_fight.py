import json
import os
import sys

from PyQt5 import QtGui, QtWidgets
from pyd2bot.data.models import Path, PathTypeEnum, Session, SessionTypeEnum, UnloadTypeEnum
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from system_tray import SystemTrayIcon

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot


ankarnam_lvl1 = 154010883
ankarnal_lvl5 = 154010884
village_astrub = 191106048
ankama_coin_bouftou = 88082704
cania_pleines_rocheuses = 156240386
currdir = os.path.dirname(os.path.abspath(__file__))

paths_file = os.path.join(os.path.dirname(__file__), "..", "app", "db", "paths.json")
with open(paths_file, "r") as f:
    paths_json = json.load(f)
    paths: dict[str, Path] = {json_path["id"]: Path(**json_path) for json_path in paths_json}
    
if __name__ == "__main__":
    # Logger.logToConsole = True
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bots = []
    followers_chars = []
    farmer = {"account_key": 244588168247577056, "character_id": 829955506469}
    farmer_creds = AccountManager.get_credentials(farmer["account_key"], farmer["character_id"])
    session_dict = {
        "id": farmer_creds["character"].accountId,
        "character": farmer_creds["character"],
        "unloadType": UnloadTypeEnum.BANK.value,
        "type": SessionTypeEnum.MULTIPLE_PATHS_FARM.value,
        "pathsList": [paths["Cania_Plains_Mine"], paths["Astrub_Mine"], paths["Dyna_Mine"], paths["Korussant_Mine"]],
        "apikey": farmer_creds["apikey"],
        "cert": farmer_creds["cert"]
    }
    bot = Pyd2Bot(Session(**session_dict))
    bots.append(bot)
    leader = {
        "account_key": 244588168247577395, "character_id": 710703972643
    }
    leader_creds = AccountManager.get_credentials(leader["account_key"], leader["character_id"])
    
    followers = [
        {
            "account_key": 244588168247578055, "character_id": 710798475555
        },
        {
            "account_key": 244588168247577841, "character_id": 710798344483
        },
        {
            "account_key": 244588168247577629, "character_id": 710798278947
        }
    ]
    for player in followers:
        creds = AccountManager.get_credentials(player["account_key"], player["character_id"])
        session_dict = {
            "id": creds["character"].accountId,
            "character": creds["character"],
            "unloadType": UnloadTypeEnum.BANK.value,
            "type": SessionTypeEnum.MULE_FIGHT.value,
            "leader": leader_creds["character"],
            "apikey": creds["apikey"],
            "cert": creds["cert"]
        }
        followers_chars.append(creds["character"])
        bot = Pyd2Bot(Session(**session_dict))
        bots.append(bot)
        
    session_dict = {
        "id": leader_creds["character"].accountId,
        "character": leader_creds["character"],
        "unloadType": UnloadTypeEnum.BANK.value,
        "type": SessionTypeEnum.FIGHT.value,
        "followers": followers_chars,
        "path": paths["astrub_village"],
        "apikey": leader_creds["apikey"],
        "cert": leader_creds["cert"]
    }
    bot = Pyd2Bot(Session(**session_dict))
    bots.append(bot)
    icon = QtGui.QIcon(os.path.join(currdir, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bots)
    for bot in bots:
        bot.start()
    trayIcon.show()
    sys.exit(app.exec_())
