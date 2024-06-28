import os
import sys

from PyQt5 import QtGui, QtWidgets
from pyd2bot.data.models import Session, SessionTypeEnum, UnloadTypeEnum
from pyd2bot.farmPaths.PathManager import PathManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from system_tray import SystemTrayIcon

from pyd2bot.logic.managers.AccountManager import AccountManager
from pyd2bot.Pyd2Bot import Pyd2Bot


currdir = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    AccountManager.load()
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    accountId = 178805104
    characterId = 711154991395.0
    account = AccountManager.get_account(accountId)
    character = account.get_character(characterId)
    if not character:
        raise Exception("character not found")
    session = Session(
        **{
            "id": "fight_solo",
            "unloadType": UnloadTypeEnum.BANK.value,
            "type": SessionTypeEnum.SOLO_FIGHT.value,
            "path": PathManager.get_path("Astrub_City"),
            "monsterLvlCoefDiff": 1.5,
            "credentials": account.credentials,
            "character": character,
        }
    )
    bot = Pyd2Bot(session)
    bot.start()
    icon = QtGui.QIcon(os.path.join(currdir, "icon.png"))
    trayIcon = SystemTrayIcon(icon, [bot], title=character.name)

    def onShutdown(message, reason):
        print(f"Shutting down {character.name} because {reason}, details:\n{message}")
        QtWidgets.QApplication.quit()

    bot.addShutdownListener(onShutdown)
    trayIcon.show()
    sys.exit(app.exec_())
