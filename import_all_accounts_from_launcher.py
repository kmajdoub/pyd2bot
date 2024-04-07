import os
from pyd2bot.logic.managers.AccountManager import AccountManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
currdir = os.path.dirname(os.path.abspath(__file__))

Logger.logToConsole = True
dest_accounts_db = os.path.join(currdir, "accounts.json")

AccountManager.clear()
AccountManager.import_launcher_accounts(fetch_characters=True, save_to_loal_json=dest_accounts_db)
