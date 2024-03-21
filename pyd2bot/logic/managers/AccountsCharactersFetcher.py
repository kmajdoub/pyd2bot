from re import S
import threading
from pydofus2.com.DofusClient import DofusClient
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.actions.ChangeServerAction import ChangeServerAction
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.logic.connection.actions.ServerSelectionAction import ServerSelectionAction
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class AccountsCharactersFetcher:
    
    def __init__(self):
        self.characters = []
        self.changeSevrer = False
        self.currServer = None
        self.serversList = None

    def start(self, accountId, login, apikey, certid, certhash):
        self.accountId = accountId
        self.login = login
        self.client = DofusClient(login)
        self.client.setApiKey(apikey)
        self.client.setCertificate(certid, certhash)
        self.client.addShutDownListener(self.onClientShutdown)
        self.client.start()
        self.evtsManager = KernelEventsManager.waitThreadRegister(self.login, 30)
        self.evtsManager.once(KernelEvent.ServersList, self.onServersList)
        self.playerManager = PlayerManager.waitThreadRegister(self.login, 60)
        self.client.join()
        return self.characters
    
    def onClientShutdown(self, event, message, reason):
        Logger().info(f"Client {self.login} shutdown : {message} - {reason}")
    
    def onServersList(self, event, erversList, serversUsedList, serversTypeAvailableSlots):
        self.kernel = Kernel.waitThreadRegister(self.login, 30)
        selectableServers = [server for server in self.kernel.serverSelectionFrame.usedServers if server.isSelectable]
        self.serversListIter = iter(selectableServers)
        self.processServer()

    def onServerSelectRefused(self, event, serverId, error, serverStatus, error_text, selectableServers):
        Logger().error(f"Server {serverId} selection refused for reason : {error_text}")
        self.processServer()
    
    def processServer(self):
        try:
            self.currServer = next(self.serversListIter)
        except StopIteration:
            self.client.shutdown("Shutdowned by the characters fetcher")
            return
        if self.changeSevrer:
            self.playerManager.charactersList.clear()
            self.kernel.worker.process(ChangeServerAction.create(self.currServer.id))
        else:
            self.changeSevrer = False
            self.kernel.worker.process(ServerSelectionAction.create(self.currServer.id))
        self.evtsManager.once(KernelEvent.CharactersList, self.onCharactersList)
        self.evtsManager.once(KernelEvent.SelectedServerRefused, self.onServerSelectRefused)
        
    def onCharactersList(self, event, charactersList):
        Logger().info(f"Server : {self.currServer.id}, List characters received")
        self.characters += [
            {
                "name": character.name,
                "id": character.id,
                "level": character.level,
                "breedId": character.breedId,
                "breedName": character.breed.name,
                "serverId": self.playerManager.server.id,
                "serverName": self.playerManager.server.name,
                "login": self.login,
                "accountId": self.accountId,
            }
            for character in self.playerManager.charactersList
        ]
        self.processServer()