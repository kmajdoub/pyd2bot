import json
import os

from pyd2bot.logic.managers.AccountCharactersFetcher import AccountCharactersFetcher
from pyd2bot.models.session.models import Account, Certificate, Character
from pydofus2.com.ankamagames.dofus.misc.utils.GameID import GameID
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.Zaap.ZaapDecoy import ZaapDecoy
from pyd2bot.BotConstants import BotConstants

__dir__ = os.path.dirname(os.path.abspath(__file__))
accounts_jsonfile = os.path.join(BotConstants.PERSISTENCE_DIR, "accounts.json")


class AccountManager:

    if not os.path.exists(accounts_jsonfile):
        accounts = {}
    else:
        with open(accounts_jsonfile, "r") as fp:
            try:
                accounts_dto: dict = json.load(fp)
            except json.JSONDecodeError:
                accounts_dto = {}
            accounts: dict[int, Account] = {int(k): Account.from_dict(v) for k, v in accounts_dto.items()}
    
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
    def fetch_account(cls, game, apikey, certid="", certhash="", with_characters_fetch=True) -> Account:
        Logger().debug(f"Fetching account for game {game}, apikey {apikey}, certid {certid}, certhash {certhash}")
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
    def import_launcher_accounts(cls, with_characters_fetch=True) -> dict[int, Account]:
        apikeys = ZaapDecoy.get_all_stored_apikeys()
        certs = ZaapDecoy.get_all_stored_certificates()
        print(f"Found {len(apikeys)} apikeys and {len(certs)} certificates")
        for apikey_details in apikeys:
            keydata = apikey_details['apikey']
            apikey = keydata['key']
            certid = ""
            certhash = ""
            if 'certificate' in keydata:
                certid = keydata['certificate']['id']
                for cert in certs:
                    certdata = cert['cert']
                    if certdata['id'] == certid:
                        certhash = cert['hash']
                        break
            try:
                AccountManager.fetch_account(GameID.DOFUS, apikey, certid, certhash, with_characters_fetch)
            except Exception as exc:
                Logger().error(f"Failed to fetch characters from game server:\n{exc}", exc_info=True)
        return cls.accounts