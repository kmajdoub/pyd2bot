from pyd2bot.data.models import Account, Character
from pydofus2.com.DofusClient import DofusClient
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger


class AccountCharactersFetcher(DofusClient):

    def __init__(self, account: Account, callback=None):
        self.account = account
        if account.apikey is None:
            raise ValueError("Account apikey is required!")
        if callback is not None and not callable(callback):
            raise ValueError("Callback must be a callable function")
        super().__init__(account.id)
        self.callback = callback
        self.changeServer = False
        self.currServer = None
        self.serversList = None
        self.setCredentials(account.apikey, account.certId, account.certHash)
        self.addShutdownListener(self.afterShutDown)

    def afterShutDown(self, reason, message):
        Logger().info(f"Characters fetched for account {self.account.login} ended with message : {message} and reason : {reason}")
        if self.callback:
            if not callable(self.callback):
                Logger().error("Callback is not callable", exc_info=True)
                return
            self.callback(self.account.characters, message, reason)

    def initListeners(self):
        super().initListeners()
        KernelEventsManager().once(
            KernelEvent.ServersList,
            self.onServersList,
            originator=self,
        )

    def onServersList(self, event, serversList, serversUsedList, serversTypeAvailableSlots):
        selectableServers = [server for server in Kernel().serverSelectionFrame.usedServers if server.isSelectable]
        self.serversListIter = iter(selectableServers)
        self.processServer()

    def onServerSelectionRefused(self, event, serverId, error, serverStatus, error_text, selectableServers):
        Logger().error(f"Server {serverId} selection refused for reason : {error_text}")
        self.processServer()

    def processServer(self):
        try:
            self.currServer = next(self.serversListIter)
        except StopIteration:
            self.shutdown("Wanted shutdown after all servers processed.")
            return
        if self.changeServer:
            PlayerManager().charactersList.clear()
            Kernel().characterFrame.changeToServer(self.currServer.id)
        else:
            self.changeServer = True
            Kernel().serverSelectionFrame.selectServer(self.currServer.id)
        KernelEventsManager().once(KernelEvent.CharactersList, self.onCharactersList)

    def onCharactersList(self, event, charactersList):
        Logger().info(f"Server : {self.currServer.id}, List of characters received")
        self.account.characters += [
            Character(**
                {
                    "name": character.name,
                    "id": character.id,
                    "level": character.level,
                    "breedId": character.breedId,
                    "breedName": character.breed.name,
                    "serverId": PlayerManager().server.id,
                    "serverName": PlayerManager().server.name,
                    "accountId": self.account.id,
                }
            )
            for character in PlayerManager().charactersList
        ]
        self.processServer()
