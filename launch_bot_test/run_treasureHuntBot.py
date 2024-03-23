import os
import sys

from launch_bot_test.system_tray import SystemTrayIcon
from PyQt5 import QtGui, QtWidgets

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot
from pyd2bot.models.session.models import Session, SessionType, UnloadType


__dir__ = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    account_key = "244588168235074572"
    creds = AccountManager.get_credentials(account_key)
    session = Session(
        id="account_key",
        character=creds['character'],
        unloadType=UnloadType.BANK,
        type=SessionType.TREASURE_HUNT,
        apikey=creds['apikey'],
        cert=creds['cert'],
    )
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bot = Pyd2Bot(session)
    bot.start()
    bot.addShutDownListener(lambda login, reason, message: QtWidgets.QApplication.quit())
    icon = QtGui.QIcon(os.path.join(__dir__, "icon.png"))
    trayIcon = SystemTrayIcon(icon, bot)
    trayIcon.show()
    sys.exit(app.exec_())