from pyd2bot.logic.managers.AccountManager import AccountManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


Logger.logToConsole = True
AccountManager.clear()
AccountManager.import_launcher_accounts(fetch_characters=True, save_to_local_json=True)
