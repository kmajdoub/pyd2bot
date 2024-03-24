import os
import sys

from PyQt5 import QtGui, QtWidgets
from pyd2bot.models.session.models import Path, PathType, Session, SessionType, TransitionType, UnloadType, Vertex
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
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    account_key = "244588168231330085"
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
    icon = QtGui.QIcon(os.path.join(currdir, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bot)
    def onShutdown(name, message, reason):
        print(f"Shutting down {name} because {reason}, details:\n{message}")
        QtWidgets.QApplication.quit()
    bot.addShutDownListener(onShutdown)
    trayIcon.show()
    sys.exit(app.exec_())
