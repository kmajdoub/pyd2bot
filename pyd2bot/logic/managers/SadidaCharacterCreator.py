import random
from Grinder.models import Account
from pyd2bot.data.models import Character
from pydofus2.com.ankamagames.berilia.managers.EventsHandler import Event
from pydofus2.com.ankamagames.berilia.managers.KernelEvent import KernelEvent
from pydofus2.com.ankamagames.berilia.managers.KernelEventsManager import KernelEventsManager
from pydofus2.com.ankamagames.dofus.datacenter.breeds.Breed import Breed
from pydofus2.com.ankamagames.dofus.kernel.Kernel import Kernel
from pydofus2.com.ankamagames.dofus.kernel.net.DisconnectionReasonEnum import DisconnectionReasonEnum
from pydofus2.com.ankamagames.dofus.logic.common.managers.PlayerManager import PlayerManager
from pydofus2.com.ankamagames.dofus.network.enums.BreedEnum import BreedEnum
from pydofus2.com.ankamagames.jerakine.logger.Logger import Logger
from pydofus2.com.DofusClient import DofusClient


class SadidaCharacterCreator(DofusClient):

    def __init__(self, account: Account, serverId=291, callback=None) -> None:
        self.account = account
        if account.apikey is None:
            raise ValueError("Account apikey is required!")
        if callback is not None and not callable(callback):
            raise ValueError("Callback must be a callable function")
        if account.id is None or account.nickname is None:
            raise ValueError("Account id or nickname cant be None")
        super().__init__(account.nickname)
        self.callback = callback
        self.requestTimer = None
        self._characterName = None
        self._breedId = BreedEnum.Sadida
        self._breed = Breed.getBreedById(self._breedId)
        if not self._breed:
            raise ValueError("Invalid breedId")
        self.sex = False
        self.character = None
        self.name_suggestion_fails = 0
        self.create_character_fails = 0
        self.callback = callback
        self.setCredentials(account.apikey, account.certId, account.certHash)
        self.addShutdownListener(self.afterShutDown)
        self.setAutoServerSelection(serverId)
        self.addEventListener(KernelEvent.CharactersList, self.onCharactersList)

    def afterShutDown(self, reason, message):
        Logger().info(f"Character create for account {self.account.login} ended with message : {message} and reason : {reason}")
        if self.callback:
            if not callable(self.callback):
                Logger().error("Callback is not callable", exc_info=True)
                return
            self.callback(self.character, message, reason)
    
    def onCharactersList(self, event, charactersList):
        Logger().debug("received characters list")
        if self._characterName is None:
            self.askNameSuggestion()
        else:
            self.requestNewCharacter()

    def onCharacterNameSuggestion(self, event: Event, suggestion):
        Logger().debug("received character name suggestion")
        self._characterName = suggestion
        self.terminated.wait(5)
        self.requestNewCharacter()

    def askNameSuggestion(self):
        self.once(KernelEvent.CharacterNameSuggestion, self.onCharacterNameSuggestion)
        self.once(KernelEvent.CharacterNameSuggestionFailed, self.onCharacterNameSuggestionFail)
        Kernel().gameServerApproachFrame.requestNameSuggestion()

    def onCharacterNameSuggestionFail(self, event: Event):
        self.name_suggestion_fails += 1
        if self.name_suggestion_fails > 3:
            return self.shutdown("failed to get character name suggestion", DisconnectionReasonEnum.EXCEPTION_THROWN)
        self.terminated.wait(5)
        self.once(KernelEvent.CharacterNameSuggestionFailed, self.onCharacterNameSuggestionFail)
        Kernel().gameServerApproachFrame.requestNameSuggestion()

    def onNewCharacterResult(self, event, result, reason, error_text):
        if result > 0:
            self.create_character_fails += 1
            if self.create_character_fails > 10:
                return self.shutdown(f"Create character error : {error_text}", DisconnectionReasonEnum.EXCEPTION_THROWN)
            Logger().error(f"Create character error : {error_text}")
            self.terminated.wait(5)
            self.askNameSuggestion()
        self.once(KernelEvent.CharactersList, self.onCharacterList)

    def onCharacterList(self, event, charactersList):
        for character in PlayerManager().charactersList:
            if character.name == self._characterName:
                self.character = {
                    "name": character.name,
                    "id": character.id,
                    "level": character.level,
                    "breedId": character.breedId,
                    "breedName": character.breed.name,
                    "serverId": PlayerManager().server.id,
                    "serverName": PlayerManager().server.name,
                    "accountId": self.account.id,
                }
                return self.shutdown("Success!", None)
        self.shutdown("The created character is not found in characters list!", DisconnectionReasonEnum.EXCEPTION_THROWN)

    def requestNewCharacter(self):
        ssi = Kernel().serverSelectionFrame.getSelectedServerInformations()
        if ssi is None:
            return self.shutdown("No server selected", DisconnectionReasonEnum.EXCEPTION_THROWN)
        if ssi.charactersCount >= ssi.charactersSlots:
            return self.shutdown("No more character slots", DisconnectionReasonEnum.EXCEPTION_THROWN)
        self.once(
            KernelEvent.CharacterCreationResult,
            self.onNewCharacterResult,
            timeout=10,
            ontimeout=lambda: self.shutdown("Request character create timed out", DisconnectionReasonEnum.EXCEPTION_THROWN),
        )
        Kernel().gameServerApproachFrame.requestCharacterCreation(
            str(self._characterName), int(self._breedId), bool(self.sex), [12488553, 9163102, 4542781, 6921543, 12114595], 145
        )

    def once(self, event_id, callback, timeout=None, ontimeout=None):
        return KernelEventsManager().once(
            event_id, callback=callback, originator=self, timeout=timeout, ontimeout=ontimeout
        )
