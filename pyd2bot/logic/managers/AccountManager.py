import json
import os

from ankalauncher.pythonversion.CryptoHelper import CryptoHelper

from pyd2bot.thriftServer.pyd2botServer import Pyd2botServer
from pyd2bot.thriftServer.pyd2botService.ttypes import (Certificate, Character,
                                                        D2BotError)
from pydofus2.com.ankamagames.atouin.Haapi import Haapi

__dir__ = os.path.dirname(os.path.abspath(__file__))
persistence_dir = "D://botdev//pyd2bot//pyd2bot//persistence"
accounts_jsonfile = os.path.join(persistence_dir, "accounts.json")


class AccountManager:
    if not os.path.exists(persistence_dir):
        os.makedirs(persistence_dir)

    if not os.path.exists(accounts_jsonfile):
        accounts = {}
    else:
        with open(accounts_jsonfile, "r") as fp:
            accounts: dict = json.load(fp)
    
    _haapi_client = None
    _session_id = None
            
    @classmethod
    def get_cert(cls, accountId):
        account = cls.get_account(accountId)
        return Certificate(id=account.get("certid", ""), hash=account.get("certhash", ""))

    @classmethod
    def get_account(cls, accountId) -> dict:
        if accountId not in cls.accounts:
            raise Exception(f"Account {accountId} not found")
        return cls.accounts[accountId]

    @classmethod
    def get_accounts(cls):
        return cls.accounts.values()

    @classmethod
    def get_accountkey(cls, accountId):
        for key, value in cls.accounts.items():
            if value["id"] == int(accountId):
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
    def get_character(cls, accountId, charId=None):
        account = cls.get_account(accountId)
        if "characters" not in account:
            return None
        characterJson = None
        if charId is None:
            characterJson = account["characters"][0]
        else:
            characters = account.get("characters", [])
            for ch in characters:
                if ch["id"] == int(charId):
                    characterJson = ch
        if characterJson is None:
            raise Exception(f"Character {charId} not found")
        return Character(
            name=characterJson["name"],
            id=characterJson["id"],
            level=characterJson["level"],
            breedId=characterJson["breedId"],
            breedName=characterJson["breedName"],
            serverId=characterJson["serverId"],
            serverName=characterJson["serverName"],
            login=characterJson["login"],
            accountId=characterJson["accountId"],
        )

    @classmethod
    def get_apikey(cls, accountId):
        acc = cls.get_account(accountId)
        return acc["apikey"]

    @classmethod
    def fetch_account(cls, game, apikey, certid="", certhash="", with_characters_fetch=True):
        print(f"Fetching account for game {game}, apikey {apikey}, certid {certid}, certhash {certhash}")
        if not cls._haapi_client:
            cls._haapi_client = Haapi()
            cls._haapi_client.api_key = apikey
        r = cls._haapi_client.signOnWithApikey(game)
        print(f"Got account {r}")
        accountId = r["id"]
        cls.accounts[accountId] = r["account"]
        cls.accounts[accountId]["apikey"] = apikey
        cls.accounts[accountId]["certid"] = certid
        cls.accounts[accountId]["certhash"] = certhash
        if with_characters_fetch:
            cls.fetch_characters(accountId, certid, certhash)
        cls.save()
        return cls.accounts[accountId]
        

    @classmethod
    def fetch_characters(cls, accountId, certid, certhash):
        acc = cls.get_account(accountId)
        apikey = acc["apikey"]
        if not cls._haapi_client:
            cls._haapi_client = Haapi()
            cls._haapi_client.api_key = apikey
        if not cls._session_id:
            cls._session_id = cls._haapi_client.startSessionWithApiKey(accountId)
            print(f"Got session id {cls._session_id}")
        token = cls._haapi_client.getLoginToken(1, certid, certhash)
        srv = Pyd2botServer("test")
        print(f"Fetching characters for token {token}")
        chars = srv.fetchCharacters(token, cls._session_id)
        chars_json = [
            {
                "name": ch.name,
                "id": ch.id,
                "level": ch.level,
                "breedId": ch.breedId,
                "breedName": ch.breedName,
                "serverId": ch.serverId,
                "serverName": ch.serverName,
                "login": acc["login"],
                "accountId": accountId,
            }
            for ch in chars
        ]
        print(f"Got characters {chars_json}")
        cls.accounts[accountId]["characters"] = chars_json
        return chars_json

    @classmethod
    def save(cls):
        with open(accounts_jsonfile, "w") as fp:
            json.dump(cls.accounts, fp, indent=4)
            
    @classmethod
    def clear(cls):
        cls.accounts = {}
        cls.save()

    @classmethod
    def import_launcher_accounts(cls, with_characters_fetch=True):
        apikeys = CryptoHelper.get_all_stored_apikeys()
        certs = CryptoHelper.get_all_stored_certificates()
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
                AccountManager.fetch_account(1, apikey, certid, certhash, with_characters_fetch)
            except D2BotError as e:
                raise Exception(f"Failed to fetch characters from game server:\n{e.message}")
        return cls.accounts