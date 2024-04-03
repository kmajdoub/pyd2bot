import json
import os

from pyd2bot.logic.managers.AccountCharactersFetcher import AccountCharactersFetcher
from pyd2bot.data.models import Account, Certificate
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.Zaap.ZaapDecoy import ZaapDecoy

__dir__ = os.path.dirname(os.path.abspath(__file__))

class AccountManager:
    
    _zaap = None
            
    @classmethod
    def get_cert(cls, accountId) -> Certificate:
        account = cls.get_account(accountId)
        return Certificate(id=account.certid, hash=account.certhash)

    @classmethod
    def get_account(cls, accountId) -> Account:
        if accountId not in cls.accounts:
            raise Exception(f"Account {accountId} not found")
        return cls.accounts[accountId]

    @classmethod
    def get_accounts(cls) -> list[Account]:
        return cls.accounts.values()

    @classmethod
    def get_accountkey(cls, accountId) -> int:
        for key, value in cls.accounts.items():
            if value.id == int(accountId):
                return key
        raise Exception(f"Account {accountId} not found")

    @classmethod
    def get_credentials(cls, accountId, characterId=None):
        character = cls.get_character(accountId, characterId)
        apikey = cls.get_apikey(accountId)
        cert = cls.get_cert(accountId)
        return {
            "apikey": apikey,
            "cert": cert,
            "character": character,
        }
    
    @classmethod
    def get_character(cls, accountId, charId=None) -> Character:
        return cls.get_account(accountId).get_character(charId)

    @classmethod
    def get_apikey(cls, accountId):
        return cls.get_account(accountId).apikey

    @classmethod
    def fetch_account(cls, apikey, certid="", certhash="", with_characters_fetch=True) -> Account:
        Logger().debug(f"Fetching account data")
        if not cls._zaap:
            cls._zaap = ZaapDecoy(apikey)
            r = cls._zaap.mainAccount
        else:
            r = ZaapDecoy().fetchAccountData(apikey)
        accountId = r["id"]
        cls.accounts[accountId] = Account.from_dict(r["account"])
        cls.accounts[accountId].apikey = apikey
        cls.accounts[accountId].certid = certid
        cls.accounts[accountId].certhash = certhash
        if with_characters_fetch:
            cls.fetch_characters(accountId)
        cls.save()
        return cls.accounts[accountId]
        

    @classmethod
    def fetch_characters(cls, accountId) -> list[Character]:
        account = cls.get_account(accountId)
        characters = AccountCharactersFetcher().run(account)
        Logger().info(f"Characters fetched for account {accountId}: {characters}")
        cls.accounts[accountId].characters = characters
        return characters

    @classmethod
    def save(cls):
        with open(accounts_jsonfile, "w") as fp:
            accounts_json = {str(k): v.to_dict() for k, v in cls.accounts.items()}
            json.dump(accounts_json, fp, indent=4)
            
    @classmethod
    def clear(cls):
        cls.accounts = {}
        cls.save()

    @classmethod
    def import_launcher_accounts(cls, with_characters_fetch=True):
        apikeys = ZaapDecoy.get_all_stored_apikeys()
        certs = ZaapDecoy.get_all_stored_certificates()
        print(f"Found {len(apikeys)} apikeys and {len(certs)} certificates")
        for apikey_details in apikeys:
            keydata = apikey_details['apikey']
            apikey = keydata['key']
            certid = 0
            certhash = ""
            if 'certificate' in keydata:
                certid = keydata['certificate']['id']
                for cert in certs:
                    certdata = cert['cert']
                    if certdata['id'] == certid:
                        certhash = cert['hash']
                        break
            try:
                AccountManager.fetch_account(apikey, certid, certhash, with_characters_fetch)
            except Exception as exc:
                Logger().error(f"Failed to fetch characters from game server:\n{exc}", exc_info=True)
