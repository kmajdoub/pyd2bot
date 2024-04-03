import os
import sys

from PyQt5 import QtGui, QtWidgets
from pyd2bot.data.models import Path, PathTypeEnum, Session, SessionTypeEnum, UnloadTypeEnum, Vertex
from pydofus2.com.ankamagames.dofus.modules.utils.pathFinding.world.TransitionTypeEnum import TransitionTypeEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from system_tray import SystemTrayIcon

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot


ankarnam_lvl1 = 154010883
ankarnal_lvl5 = 154010884
village_astrub = 191106048
ankama_coin_bouftou = 88082704
cania_pleines_rocheuses = 156240386
currdir = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    Logger.logToConsole = True
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    account_key = 244588168244175251
    creds = AccountManager.get_credentials(account_key)
    session = Session.from_dict(
        {
            "id": "test_fight_solo",
            "character": creds["character"],
            "unloadType": UnloadTypeEnum.BANK.value,
            "type": SessionTypeEnum.FIGHT.value,
            "path": {
                "id": "test_path",
                "type": PathTypeEnum.RandomSubAreaFarmPath.value,
                "startVertex": {"mapId": village_astrub, "zoneId": 1},
                "allowedTransitions": [TransitionTypeEnum.SCROLL.value, TransitionTypeEnum.SCROLL_ACTION.value],
            },
            "monsterLvlCoefDiff": 1.5,
            "apikey": creds["apikey"],
            "cert": creds["cert"],
        }
    )
    bot = Pyd2Bot(session)
    bot.start()
    icon = QtGui.QIcon(os.path.join(currdir, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bot)

    def onShutdown(name, message, reason):
        print(f"Shutting down {name} because {reason}, details:\n{message}")
        QtWidgets.QApplication.quit()

    bot.addShutDownListener(onShutdown)
    trayIcon.show()
    sys.exit(app.exec_())
