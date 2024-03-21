import os
import sys

from PyQt5 import QtGui, QtWidgets
from system_tray import SystemTrayIcon

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (JobFilter, Path, PathType,
                                                        Session, SessionType,
                                                        TransitionType,
                                                        UnloadType, Vertex)

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
        type=SessionType.MULTIPLE_PATHS_FARM,
        pathsList=[
            Path(
                id="mine_astrub",
                type=PathType.CustomRandomFarmPath,
                mapIds=[ 193331715, 193200131, 188484108 ]
            ),
            Path(
                id="mine_astrub2",
                type=PathType.CustomRandomFarmPath,
                mapIds=[ 193331713, 193200129 ]
            ),
        ],
        jobFilters=[
            JobFilter(36, []),  # Pêcheur goujon
            JobFilter(2, []),  # Bucheron,
            JobFilter(26, []),  # Alchimiste
            JobFilter(28, []),  # Paysan
            JobFilter(1, [311]),  # Base : eau
            JobFilter(24, []),  # Miner
        ],
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
