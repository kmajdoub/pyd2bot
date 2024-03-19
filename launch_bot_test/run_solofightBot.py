import sys
import os
from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (Path, PathType,
                                                        Session, SessionType,
                                                        TransitionType,
                                                        UnloadType, Vertex)
from PyQt5 import QtGui, QtWidgets
from system_tray import SystemTrayIcon

ankarnam = 154010883
village_astrub = 191106048
# ankama coin bouftou 88082704
# Lac cania - pleines rocheuses : 156240386
currdir = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    account_key = "244588168227834474"
    creds = AccountManager.get_credentials(account_key)
    session = Session(
        id="test_fight_solo",
        character=creds['character'],
        unloadType=UnloadType.BANK,
        type=SessionType.FIGHT,
        path=Path(
            id="test_path",
            type=PathType.RandomSubAreaFarmPath,
            startVertex=Vertex(mapId=village_astrub, zoneId=1),
            transitionTypeWhitelist=[TransitionType.SCROLL, TransitionType.SCROLL_ACTION],
        ),
        monsterLvlCoefDiff=1.5,
        apikey=creds['apikey'],
        cert=creds['cert'],
    )
    bot = Pyd2Bot(session)
    bot.start()
    bot.addShutDownListener(lambda name, message, reason: print(f"Shutting down {name} because {reason}, details:\n{message}"))

    # Setting up the system tray icon
    icon = QtGui.QIcon(os.path.join(currdir, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bot)
    trayIcon.show()
    sys.exit(app.exec_())
