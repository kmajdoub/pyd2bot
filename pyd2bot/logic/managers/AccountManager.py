from calendar import c
import json
import os

from pyd2bot.logic.managers.AccountCharactersFetcher import AccountCharactersFetcher
from pyd2bot.data.models import Account, Character, Credentials
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.Zaap.ZaapDecoy import ZaapDecoy

__dir__ = os.path.dirname(os.path.abspath(__file__))
default_accounts_jsonfile = os.path.join(__dir__, "accounts.json")


class AccountManager:
    _zaap: ZaapDecoy = None
    _accounts = dict[int, Account]()
    _db_file = default_accounts_jsonfile

    @classmethod
    def get_account(cls, accountId) -> Account:
        if accountId not in cls._accounts:
            raise Exception(f"Account {accountId} not found")
        return cls._accounts[accountId]

    @classmethod
    def get_accounts(cls) -> list[Account]:
        return cls._accounts.values()

    @classmethod
    def get_credentials(cls, accountId) -> Credentials:
        return cls.get_account(accountId).credentials

    @classmethod
    def get_character(cls, accountId, charId=None) -> Character:
        return cls.get_account(accountId).get_character(charId)

    @classmethod
    def get_apikey(cls, accountId):
        return cls.get_account(accountId).apikey

    @classmethod
    def fetch_account(cls, apikey, certid=0, certhash="") -> Account:
        Logger().debug(f"Fetching account data")
        if not cls._zaap:
            cls._zaap = ZaapDecoy(apikey)
            accountData = cls._zaap.mainAccount
        else:
            accountData = ZaapDecoy().fetch_account_data(apikey)
        account = Account(**accountData["account"])
        account.apikey = apikey
        account.certId = certid
        account.certHash = certhash
        return account

    @classmethod
    def fetch_characters_async(cls, accountId, callback) -> AccountCharactersFetcher:
        account = cls.get_account(accountId)
        fetcher = AccountCharactersFetcher(account, callback)
        fetcher.start()
        return fetcher

    @classmethod
    def fetch_characters_sync(cls, accountId) -> list[Character]:
        account = cls.get_account(accountId)
        fetcher = AccountCharactersFetcher(account)
        fetcher.start()
        fetcher.join()
        return account.characters

    @classmethod
    def load(cls, local_jsonfile=None):
        if local_jsonfile is not None:
            cls._db_file = local_jsonfile
        if not cls._db_file:
            cls._db_file = default_accounts_jsonfile
        if not os.path.exists(cls._db_file):
            return
        with open(cls._db_file, "r") as fp:
            accounts_json = json.load(fp)
            cls._accounts = {
                int(accountId): Account(**account) for accountId, account in accounts_json.items()
            }

    @classmethod
    def save(cls, local_jsonfile=None):
        if local_jsonfile is None:
            cls._db_file = default_accounts_jsonfile
        if not cls._db_file:
            cls._db_file = local_jsonfile
        with open(cls._db_file, "w") as fp:
            accounts_json = {accountId: account.model_dump() for accountId, account in cls._accounts.items()}
            json.dump(accounts_json, fp, indent=4)

    @classmethod
    def clear(cls, persist=False):
        cls._accounts = {}
        if persist:
            cls.save()

    @classmethod
    def import_launcher_accounts(cls, fetch_characters=False, save_to_loal_json=False):
        cls._zaap = ZaapDecoy()
        cls._accounts.clear()
        for apikey in cls._zaap._apikeys:
            try:
                cert = cls._zaap.get_api_cert(apikey)
                account = AccountManager.fetch_account(apikey.key, cert.id, cert.hash)
                cls._accounts[account.id] = account
            except Exception as exc:
                Logger().error(f"Failed to fetch characters from game server:\n{exc}", exc_info=True)
        if fetch_characters:
            tasks = [AccountCharactersFetcher(account) for account in cls._accounts.values()]
            for task in tasks:
                task.start()
            for task in tasks:
                task.join()
        if save_to_loal_json:
            cls.save(save_to_loal_json)
        return cls._accounts


if __name__ == "__main__":
    Logger.logToConsole = True
    AccountManager.clear()
    AccountManager.import_launcher_accounts(fetch_characters=True, save_to_loal_json=True)
