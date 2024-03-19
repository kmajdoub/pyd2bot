import os
import sys

from PyQt5 import QtGui, QtWidgets
from system_tray import SystemTrayIcon

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.thriftServer.pyd2botService.ttypes import (Certificate, JobFilter,
                                                        Path, PathType,
                                                        Session, SessionType,
                                                        UnloadType, Vertex)

# ankarnam 154010883
# village astrub 191106048
# ankama coin bouftou 88082704
# Lac cania - pleines rocheuses : 156240386
# astrub forest 189531147

__dir__ = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    account_key = "244588168227218920"
    creds = AccountManager.get_credentials(account_key)
    print(creds)
    session = Session(
        id="test",
        character=creds['character'],
        unloadType=UnloadType.BANK,
        type=SessionType.FARM,
        path=Path(
            id="test",
            type=PathType.RandomAreaFarmPath,
            startVertex=Vertex(mapId=154010883.0, zoneId=1), # Ankama coin bouftou 
            subAreaBlacklist=[6, 482, 276, 277],  # exclude astrub cimetery, Milicluster, Bwork village
        ),
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
    bot.addShutDownListener(lambda name, message, reason: QtWidgets.QApplication.quit())

    # Setting up the system tray icon
    icon = QtGui.QIcon(os.path.join(__dir__, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bot)
    trayIcon.show()
    sys.exit(app.exec_())
